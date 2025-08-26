from torch.cuda.amp import autocast, GradScaler
from torch import optim
from lazy_dataset.dataset import LazyDataset, TrainingStep, State
from dsgp4.tle import TLE
from util.transform import gcrf_to_teme
import satkit as sk
import time
from collections import defaultdict
import logging
import torch
import torch.nn as nn
import numpy as np

def extract_batch_data(batch: list[TrainingStep], device: torch.device) -> tuple[list[TLE], list[State], torch.Tensor]:
    """
    Extracts TLEs and states from a batch of data.
    """
    tles = [step.tle for step in batch]
    all_state_lists = [step.states for step in batch]
    all_tsince_lists = [step.tsinces for step in batch]
    states = [state for state_list in all_state_lists for state in state_list]

    flattened_tles = [] # All TLEs repeated for each time step
    batched_steps = []
    for tle, tsince_list in zip(tles, all_tsince_lists):
        flattened_tles.extend([tle] * len(tsince_list))
        if len(tsince_list) > 0:
            batched_steps.extend(tsince_list) # Represent steps as actual time since epoch values

    batched_steps = torch.tensor(batched_steps, device=device)

    return flattened_tles, states, batched_steps

def normalize_ground_truth(states, normalization_R=6958.137, normalization_V=7.947155867983262):
    """
    Normalize ground truth states to match model's output space.
    
    Args:
        states: Tensor [N, 6] with positions (km) and velocities (km/s)
        
    Returns:
        normalized_states: Tensor [N, 6] in normalized units
    """
    normalized = torch.zeros_like(states)
    normalized[:, :3] = states[:, :3] / normalization_R  # Normalize positions
    normalized[:, 3:] = states[:, 3:] / normalization_V   # Normalize velocities
    
    return normalized

def descent(
        model,
        train:bool,
        dataset: LazyDataset,
        optimizer: optim.Optimizer,
        criterion: nn.Module = nn.SmoothL1Loss(),
        scaler: GradScaler = GradScaler(),
        chunk_size=512,
        ):
    
    if train:
        model.train()
    else:
        model.eval()

    device = next(model.parameters()).device

    total_loss = 0.0
    total_steps = 0
    start_time = time.time()
    for i, batch in enumerate(dataset):
        logging.info(f"Processing batch {i+1}/{len(dataset)} with {len(batch)} steps")
        tles, states, steps = extract_batch_data(batch, device=device)

        total_steps += len(steps)


        if train:
            optimizer.zero_grad()

        # Convert ground truth states to a normalized tensor in TEME frame
        logging.info(f"Converting {len(states)} ground truth states to TEME frame")
        rotation_start = time.time()
        # Group states by epoch to minimize redundant transformations
        logging.info(f"[1/2] Mapping epochs to indices")
        epoch_table = defaultdict(list)
        for index, state in enumerate(states):
            epoch_table[state.dt_time].append(index)
        logging.info(f"Found {len(epoch_table)} unique epochs for {len(states)} states in {time.time() - rotation_start:.2f} seconds")

        # Preallocate state tensor list
        state_tensors_teme = torch.zeros((len(states), 6), dtype=torch.float32, device=device)

        logging.info(f"[2/2] Converting states epoch by epoch")

        rotation_fn_time = time.time()
        for epoch, indices in epoch_table.items():
            states_for_epoch = [states[index] for index in indices]
            state_vectors = np.stack([np.concatenate([state.get_position_vector(), state.get_velocity_vector()]) for state in states_for_epoch])
            state_tensor_teme = gcrf_to_teme(
                torch.tensor(
                    state_vectors,
                    dtype=torch.float32,
                    device=device
                ), sk.time.from_datetime(epoch)
            )
            # Fancy indexing to place converted states in the correct positions
            state_tensors_teme[indices] = state_tensor_teme.squeeze(0)
        
        logging.info(f"[Done] Converted all states to TEME frame in {time.time() - rotation_fn_time:.2f} seconds")
        logging.info(f"Finished converting ground truth states to TEME frame in {time.time() - rotation_start:.2f} total seconds")
        normalization_start = time.time()
        target_states_normalized = normalize_ground_truth(state_tensors_teme)
        logging.info(f"Finished normalizing ground truth states in {time.time() - normalization_start:.2f} seconds")


        # Process in smaller chunks to save GPU memory
        accumulated_loss = 0.0
        propagation_start = time.time()
        logging.info(f"Propagating {len(steps)} steps in chunks of size {chunk_size}")

        # Wrap the forward pass with appropriate gradient context
        gradient_context = torch.enable_grad() if train else torch.no_grad()
        
        with gradient_context:
            for j in range(0, len(steps), chunk_size):
                with autocast():
                    with torch.cuda.device(device):
                        chunk_states = model(tles[j:j+chunk_size], steps[j:j+chunk_size]).to(device)
                    # Compute the loss for the chunk
                    loss = criterion(chunk_states, target_states_normalized[j:j+chunk_size].to(device))
                    # Backpropagate the loss for this chunk
                    if train:
                        scaler.scale(loss).backward()
                accumulated_loss += loss.item()

        # Only step optimizer and scaler during training
        if train:
            scaler.step(optimizer)
            scaler.update()

        total_loss += accumulated_loss
        logging.info(f"Accumulated loss for batch {i+1}: {accumulated_loss} | Average loss so far: {total_loss / total_steps:.4f}")
        logging.info(f"Finished propagating and backpropagating (if training) in {time.time() - propagation_start:.2f} seconds")
        logging.info(f"Finished batch {i+1}/{len(dataset)} in {(time.time() - start_time) / 60:.2f} minutes")


    logging.info(f"Finished epoch in {(time.time() - start_time) / 60:.2f} minutes")

    avg_loss = total_loss / total_steps
    return avg_loss