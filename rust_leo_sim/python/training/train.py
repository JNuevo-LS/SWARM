import logging
import time

import torch
import torch.nn as nn
from dsgp4 import mldsgp4
from lazy_dataset.async_data import AsyncDataLoader
from lazy_dataset.dataset import LazyDataset
from torch import optim
from torch.amp import GradScaler, autocast  # type: ignore
from torch.nn.parallel import DistributedDataParallel


def descent(
        model,
        training:bool,
        dataset: LazyDataset,
        optimizer: optim.Optimizer,
        device: torch.device,
        criterion: nn.Module = nn.SmoothL1Loss(),
        scaler: GradScaler = GradScaler(),
        chunk_size=512,
        ):
    
    if training:
        model.train()
    else:
        model.eval()

    total_loss = 0.0
    total_steps = 0
    start_time = time.time()

    prefetcher = AsyncDataLoader(dataset, device)
    try:
        for batch_data in prefetcher:
            i, tles, steps, target_states_normalized = batch_data
            logging.info(f"Processing batch {i+1}/{len(dataset)} with {len(steps)} steps")

            total_steps += len(steps)

            if training:
                optimizer.zero_grad()

            # Process in smaller chunks to save GPU memory
            accumulated_loss = 0.0
            propagation_start = time.time()
            logging.info(f"Propagating {len(steps)} steps in chunks of size {chunk_size}")

            # Wrap the forward pass with appropriate gradient context
            gradient_context = torch.enable_grad() if training else torch.no_grad()
            
            with gradient_context, torch.device(device), torch.cuda.device(device):
                for j in range(0, len(steps), chunk_size):
                    with autocast("cuda"):
                        steps_on_device = steps[j:j+chunk_size].to(device)
                        chunk_states = model(tles[j:j+chunk_size], steps_on_device).to(device)
                        # Compute the loss for the chunk
                        loss = criterion(chunk_states, target_states_normalized[j:j+chunk_size].to(device))

                    # Backpropagate the loss for this chunk
                    if training:
                        scaler.scale(loss).backward()
                    # Before adding to total_loss
                    if not torch.isnan(loss).any() and not torch.isinf(loss).any():
                        accumulated_loss += loss.item()
                    else:
                        logging.warning(f"Encountered NaN or Inf in loss computation for chunk starting at index {j}. Skipping this chunk's loss.")

            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            # Only step optimizer and scaler during training
            if training:
                scaler.step(optimizer)
                scaler.update()

            total_loss += accumulated_loss
            logging.info(f"Accumulated loss for batch {i+1}: {accumulated_loss} | Average loss so far: {total_loss / total_steps:.4f}")
            logging.info(f"Finished propagating and backpropagating (if training) in {time.time() - propagation_start:.2f} seconds")
            logging.info(f"Finished batch {i+1}/{len(dataset)} in {(time.time() - start_time) / 60:.2f} minutes")
        logging.info(f"Finished epoch in {(time.time() - start_time) / 60:.2f} minutes")
    finally:
        prefetcher.stop()

    avg_loss = total_loss / total_steps
    return avg_loss
        

def epoch_sequence(
        model: mldsgp4 | DistributedDataParallel,
        optimizer: optim.Optimizer,
        criterion: nn.Module,
        scheduler: optim.lr_scheduler.ReduceLROnPlateau,
        scaler: GradScaler,
        train_satellites: LazyDataset,
        val_satellites: LazyDataset,
        device: torch.device,
        chunk_size=2**19,
):
    train_loss = descent(
        model=model,
        training=True,
        dataset=train_satellites,
        optimizer=optimizer,
        device=device,
        criterion=criterion,
        scaler=scaler,
        chunk_size=chunk_size
    )

    val_loss = descent(
        model=model,
        training=False,
        dataset=val_satellites,
        optimizer=optimizer,
        device=device,
        criterion=criterion,
        scaler=scaler,
        chunk_size=chunk_size
    )

    scheduler.step(val_loss)

    return train_loss, val_loss