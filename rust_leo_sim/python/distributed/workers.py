import os
import logging
from multiprocessing import Queue

import torch
import torch.distributed as dist
import torch.nn as nn
import torch.optim as optim
from dsgp4 import mldsgp4
from lazy_dataset.setup import create_datasets
from torch.amp import GradScaler # type: ignore
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.optim.lr_scheduler import ReduceLROnPlateau
from training.test import test_model
from training.train import descent
from lazy_dataset.dataset import LazyDataset


def _setup(rank, world_size):
    os.environ['MASTER_ADDR'] = 'localhost'
    os.environ['MASTER_PORT'] = '12355'

    dist.init_process_group("gloo", rank=rank, world_size=world_size)
    
# Define a wrapper function to handle the spawn correctly
def run_worker(
        rank: int, 
        world_size: int, 
        model: mldsgp4,
        optimizer_name: str, 
        lr: int, 
        results_queue: Queue, 
        chunk_size: int =2**19
        ):
    """
    Runs a distributed training worker using PyTorch DDP.
    Args:
        rank (int): The rank of the current worker process in the distributed setup.
        world_size (int): Total number of worker processes participating in training.
        model (mldsgp4): The model instance to be trained.
        optimizer_name (str): Name of the optimizer to use ('AdamW', 'SGD', or 'RMSprop').
        lr (int): Learning rate for the optimizer.
        results_queue (Queue): Multiprocessing queue to send training/validation/test results to the main process.
        chunk_size (int, optional): Size of data chunks for training and evaluation. Defaults to 2**19.
    Notes:
        - Only the master process (rank 0) computes validation and test metrics and puts results in the queue.
        - Non-master processes only participate in training.
        - The function sets up logging, device assignment, optimizer, scheduler, loss function, and mixed precision scaler.
        - Destroys the distributed process group at the end of execution.
    """
    
    # Configure logging in the worker process
    logging.basicConfig(
        level=logging.INFO,
        filename='training.log',
        filemode='a',
        format=f'%(asctime)s [Rank {rank}] %(levelname)s:%(message)s'
    )
    logging.info(f"Worker process {rank}/{world_size-1} started")

    _setup(rank, world_size)
    
    torch.cuda.set_device(rank)
    device = torch.device(f"cuda:{rank}")
    
    model_on_gpu = model.to(rank)
    ddp_model = DDP(model_on_gpu, device_ids=[rank])
    match optimizer_name:
        case 'AdamW':
            local_optimizer = optim.AdamW(ddp_model.parameters(), lr=lr, weight_decay=0.05)
        case 'SGD':
            local_optimizer = optim.SGD(ddp_model.parameters(), lr=lr, momentum=0.9, weight_decay=0.05)
        case 'RMSprop':
            local_optimizer = optim.RMSprop(ddp_model.parameters(), lr=lr, weight_decay=0.05)
        case _:
            raise ValueError(f"Unsupported optimizer: {optimizer_name}")
    
    local_scheduler = ReduceLROnPlateau(local_optimizer, mode='min', factor=0.5, patience=2)
    local_criterion = nn.SmoothL1Loss()
    local_scaler = GradScaler()

    train_satellites, test_satellites, val_satellites = create_datasets(world_size=world_size, rank=rank, mp=True)
    
    # Only process 0 computes validation and test metrics
    if rank == 0:
        train_loss = descent(
            model=ddp_model,
            training=True,
            dataset=train_satellites,
            optimizer=local_optimizer,
            device=device,
            criterion=local_criterion,
            scaler=local_scaler,
            chunk_size=chunk_size
        )
        
        val_loss = descent(
            model=ddp_model,
            training=False,
            dataset=val_satellites,
            optimizer=local_optimizer,
            device=device,
            criterion=local_criterion,
            scaler=local_scaler,
            chunk_size=chunk_size
        )
        
        local_scheduler.step(val_loss) #FIXME
        test_metrics = test_model(ddp_model, test_satellites, device=device, chunk_size=chunk_size)
        
        # Put results in the queue for the main process
        results_queue.put((train_loss, val_loss, test_metrics))
    else:
        # Non-master processes only participate in training
        _ = descent(
            model=ddp_model,
            training=True,
            dataset=train_satellites,
            optimizer=local_optimizer,
            device=device,
            criterion=local_criterion,
            scaler=local_scaler,
            chunk_size=chunk_size
        )
        val_loss = descent(
            model=ddp_model,
            training=False,
            dataset=val_satellites,
            optimizer=local_optimizer,
            device=device,
            criterion=local_criterion,
            scaler=local_scaler,
            chunk_size=chunk_size
        )
    
    dist.destroy_process_group()    