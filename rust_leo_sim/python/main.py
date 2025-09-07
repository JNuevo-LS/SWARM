import json
import logging
import os
from multiprocessing import Queue

from dotenv import load_dotenv

load_dotenv()

import torch
import torch.nn as nn
import torch.optim as optim
from distributed.workers import run_worker
from dsgp4 import mldsgp4
from lazy_dataset.setup import create_datasets
from torch.amp import GradScaler  # type: ignore
from torch.multiprocessing.spawn import spawn
from torch.optim.lr_scheduler import ReduceLROnPlateau
from training.test import test_model
from training.train import epoch_sequence

scaler = GradScaler('cuda')

def main():
    EPOCHS = int(os.getenv("EPOCHS", 10))

    results_queue = Queue()

    world_size = torch.cuda.device_count()
    logging.info(f"Using {world_size} GPUs for training")

    train_loss_over_time = []
    val_loss_over_time = []
    test_acc_over_time = []
    
    for lr in [0.01, 0.001, 0.0005, 0.0001, 0.00005, 0.00001, 0.000005, 0.000001]:
        for optimizer_name in ['AdamW', 'SGD', 'RMSprop']:

            model = mldsgp4()
            chunk_size = int(os.getenv("CHUNK_SIZE", 2**19))
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            if world_size > 1:
                for epoch in range(EPOCHS):
                    logging.info(f"Starting epoch {epoch+1}/{EPOCHS} with {optimizer_name} optimizer and learning rate {lr} using {world_size} GPUs")
                    
                    if epoch != 0:
                        try:
                            train_loss, val_loss, test_metrics = results_queue.get(timeout=10)
                            train_loss_over_time.append(train_loss)
                            val_loss_over_time.append(val_loss)
                            test_acc_over_time.append(test_metrics)
                        except:
                            logging.error("Failed to get results from worker processes")

                    #Spawn automatically handles rank parameters
                    spawn(
                        run_worker,
                        args=(world_size, model, optimizer_name, lr, results_queue, chunk_size),
                        nprocs=world_size,
                        join=True
                    )
                    model_filename = f"model_states/mldsgp4_model_{optimizer_name}_lr{lr}_epoch{epoch}.pth"
                    torch.save(model.state_dict(), model_filename)
                    logging.info(f"Saved trained model to {model_filename}")
            else:
                logging.info(f"Initializing model with {optimizer_name} optimizer and learning rate {lr} on single GPU")
                model = model.to(device)
                match optimizer_name:
                    case 'AdamW':
                        optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=0.05)
                    case 'SGD':
                        optimizer = optim.SGD(model.parameters(), lr=lr, momentum=0.9, weight_decay=0.05)
                    case 'RMSprop':
                        optimizer = optim.RMSprop(model.parameters(), lr=lr, weight_decay=0.05)
                    case _:
                        raise ValueError(f"Unsupported optimizer: {optimizer_name}")
                    
                scheduler = ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=2)
                criterion = nn.SmoothL1Loss()
                scaler = GradScaler('cuda')
                logging.info(f"Initialized model with {optimizer_name} optimizer and learning rate {lr}")
                train_satellites, val_satellites, test_satellites = create_datasets()
                for epoch in range(EPOCHS):
                    logging.info(f"Starting epoch {epoch+1}/{EPOCHS} with {optimizer_name} optimizer and learning rate {lr}")
                    train_loss, val_loss = epoch_sequence(
                        model=model,
                        optimizer=optimizer,
                        criterion=criterion,
                        scheduler=scheduler,
                        scaler=scaler,
                        train_satellites=train_satellites,
                        val_satellites=val_satellites,
                        device=device,
                        chunk_size=chunk_size
                    )
                    test_metrics = test_model(model, test_satellites, device=device, chunk_size=chunk_size)

                    train_loss_over_time.append(train_loss)
                    val_loss_over_time.append(val_loss)
                    test_acc_over_time.append(test_metrics)

            # Save the trained model
            model_filename = f"model_states/mldsgp4_model_{optimizer_name}_lr{lr}.pth"
            torch.save(model.state_dict(), model_filename)
            logging.info(f"Saved trained model to {model_filename}")

            if test_metrics is not None: # type: ignore
                results_filename = f"final_test_metrics_{optimizer_name}_lr{lr}.json"
                with open(results_filename, 'w') as f:
                    json.dump(test_metrics, f, indent=4) # type: ignore
                logging.info(f"Saved final test metrics to {results_filename}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, filename='training.log', filemode='a', format='%(asctime)s %(levelname)s:%(message)s')
    logging.info("Starting training script")
    load_dotenv()
    main()