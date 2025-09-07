import logging
import time
from collections import defaultdict

import numpy as np
import satkit as sk
import torch
from util.transform import normalize_ground_truth, denormalize_predictions, extract_batch_data
from util.transform import gcrf_to_teme
from lazy_dataset.dataset import LazyDataset
from dsgp4.tle import TLE
from dsgp4 import mldsgp4
from torch.nn.parallel import DistributedDataParallel


def calculate_metrics(predictions: torch.Tensor, targets: torch.Tensor) -> dict:
    """
    Calculate various accuracy and precision metrics for satellite state predictions.
    
    Args:
        predictions: Tensor [N, 6] - predicted states (position + velocity)
        targets: Tensor [N, 6] - ground truth states (position + velocity)
    
    Returns:
        dict: Dictionary containing various metrics
    """
    with torch.no_grad():
        # Position and velocity errors
        pos_pred = predictions[:, :3]  # km
        pos_true = targets[:, :3]      # km
        vel_pred = predictions[:, 3:]  # km/s
        vel_true = targets[:, 3:]      # km/s
        
        # Position metrics
        pos_error = pos_pred - pos_true
        pos_error_magnitude = torch.norm(pos_error, dim=1)  # Euclidean distance error
        pos_rmse = torch.sqrt(torch.mean(pos_error_magnitude ** 2))
        pos_mae = torch.mean(pos_error_magnitude)
        pos_max_error = torch.max(pos_error_magnitude)
        pos_std = torch.std(pos_error_magnitude)
        
        # Velocity metrics
        vel_error = vel_pred - vel_true
        vel_error_magnitude = torch.norm(vel_error, dim=1)
        vel_rmse = torch.sqrt(torch.mean(vel_error_magnitude ** 2))
        vel_mae = torch.mean(vel_error_magnitude)
        vel_max_error = torch.max(vel_error_magnitude)
        vel_std = torch.std(vel_error_magnitude)
        
        # Overall state vector error
        state_error = predictions - targets
        state_error_magnitude = torch.norm(state_error, dim=1)
        state_rmse = torch.sqrt(torch.mean(state_error_magnitude ** 2))
        state_mae = torch.mean(state_error_magnitude)
        
        # Accuracy thresholds (you can adjust these based on requirements)
        pos_accuracy_1km = (pos_error_magnitude < 1.0).float().mean() * 100  # % within 1 km
        pos_accuracy_5km = (pos_error_magnitude < 5.0).float().mean() * 100  # % within 5 km
        pos_accuracy_10km = (pos_error_magnitude < 10.0).float().mean() * 100  # % within 10 km
        
        vel_accuracy_01ms = (vel_error_magnitude < 0.01).float().mean() * 100  # % within 0.01 km/s
        vel_accuracy_05ms = (vel_error_magnitude < 0.05).float().mean() * 100  # % within 0.05 km/s
        vel_accuracy_10ms = (vel_error_magnitude < 0.10).float().mean() * 100  # % within 0.10 km/s
        
        return {
            'position_rmse_km': pos_rmse.item(),
            'position_mae_km': pos_mae.item(),
            'position_max_error_km': pos_max_error.item(),
            'position_std_km': pos_std.item(),
            'position_accuracy_1km_percent': pos_accuracy_1km.item(),
            'position_accuracy_5km_percent': pos_accuracy_5km.item(),
            'position_accuracy_10km_percent': pos_accuracy_10km.item(),
            
            'velocity_rmse_kmps': vel_rmse.item(),
            'velocity_mae_kmps': vel_mae.item(),
            'velocity_max_error_kmps': vel_max_error.item(),
            'velocity_std_kmps': vel_std.item(),
            'velocity_accuracy_001kmps_percent': vel_accuracy_01ms.item(),
            'velocity_accuracy_005kmps_percent': vel_accuracy_05ms.item(),
            'velocity_accuracy_010kmps_percent': vel_accuracy_10ms.item(),
            
            'overall_state_rmse': state_rmse.item(),
            'overall_state_mae': state_mae.item(),
            
            'num_samples': len(predictions)
        }

def test_model(model: mldsgp4 | DistributedDataParallel, dataset: LazyDataset, device: torch.device, chunk_size: int =2**19):
    """Test the model and calculate accuracy/precision metrics."""
    model.eval()
    
    all_predictions = []
    all_targets = []
    
    total_samples = 0
    start_time = time.time()
    
    with torch.no_grad():
        for i, batch in enumerate(dataset):
            logging.info(f"Processing batch {i+1}/{len(dataset)} with {len(batch)} steps")
            tles, states, steps = extract_batch_data(batch, device=device)
            
            # Convert ground truth states to TEME frame
            logging.info(f"Converting {len(states)} ground truth states to TEME frame")
            epoch_table = defaultdict(list)
            for index, state in enumerate(states):
                epoch_table[state.dt_time].append(index)
            
            state_tensors_teme = torch.zeros((len(states), 6), dtype=torch.float32, device=device)
            
            for epoch, indices in epoch_table.items():
                states_for_epoch = [states[index] for index in indices]
                state_vectors = np.stack([
                    np.concatenate([state.get_position_vector(), state.get_velocity_vector()]) 
                    for state in states_for_epoch
                ])
                state_tensor_teme = gcrf_to_teme(
                    torch.tensor(state_vectors, dtype=torch.float32, device=device), 
                    sk.time.from_datetime(epoch)
                )
                state_tensors_teme[indices] = state_tensor_teme.squeeze(0)
            
            # Normalize ground truth
            target_states_normalized = normalize_ground_truth(state_tensors_teme)
            
            # Get model predictions in chunks
            predictions_normalized = []
            for j in range(0, len(steps), chunk_size):
                with torch.cuda.amp.autocast():
                    chunk_predictions = model(tles[j:j+chunk_size], steps[j:j+chunk_size]).to(device)
                    predictions_normalized.append(chunk_predictions)
            
            predictions_normalized = torch.cat(predictions_normalized, dim=0)
            
            # Denormalize predictions and targets for metric calculation
            predictions_physical = denormalize_predictions(predictions_normalized)
            targets_physical = denormalize_predictions(target_states_normalized)
            
            all_predictions.append(predictions_physical)
            all_targets.append(targets_physical)
            total_samples += len(predictions_physical)
            
            logging.info(f"Processed batch {i+1}, total samples: {total_samples}")
    
    # Concatenate all predictions and targets
    all_predictions = torch.cat(all_predictions, dim=0)
    all_targets = torch.cat(all_targets, dim=0)
    
    # Calculate metrics
    logging.info("Calculating accuracy and precision metrics...")
    metrics = calculate_metrics(all_predictions, all_targets)
    
    # Log results
    logging.info("\n" + "="*60)
    logging.info("SATELLITE ORBIT PREDICTION TEST RESULTS")
    logging.info("="*60)
    logging.info(f"Total samples tested: {metrics['num_samples']}")
    logging.info(f"Test duration: {(time.time() - start_time) / 60:.2f} minutes")
    logging.info("")
    
    logging.info("POSITION ACCURACY:")
    logging.info(f"  RMSE: {metrics['position_rmse_km']:.3f} km")
    logging.info(f"  MAE:  {metrics['position_mae_km']:.3f} km")
    logging.info(f"  Max Error: {metrics['position_max_error_km']:.3f} km")
    logging.info(f"  Std Dev: {metrics['position_std_km']:.3f} km")
    logging.info(f"  Accuracy (≤1 km):  {metrics['position_accuracy_1km_percent']:.1f}%")
    logging.info(f"  Accuracy (≤5 km):  {metrics['position_accuracy_5km_percent']:.1f}%")
    logging.info(f"  Accuracy (≤10 km): {metrics['position_accuracy_10km_percent']:.1f}%")
    logging.info("")
    
    logging.info("VELOCITY ACCURACY:")
    logging.info(f"  RMSE: {metrics['velocity_rmse_kmps']:.6f} km/s")
    logging.info(f"  MAE:  {metrics['velocity_mae_kmps']:.6f} km/s")
    logging.info(f"  Max Error: {metrics['velocity_max_error_kmps']:.6f} km/s")
    logging.info(f"  Std Dev: {metrics['velocity_std_kmps']:.6f} km/s")
    logging.info(f"  Accuracy (≤0.01 km/s): {metrics['velocity_accuracy_001kmps_percent']:.1f}%")
    logging.info(f"  Accuracy (≤0.05 km/s): {metrics['velocity_accuracy_005kmps_percent']:.1f}%")
    logging.info(f"  Accuracy (≤0.10 km/s): {metrics['velocity_accuracy_010kmps_percent']:.1f}%")
    logging.info("")
    
    logging.info("OVERALL METRICS:")
    logging.info(f"  State Vector RMSE: {metrics['overall_state_rmse']:.3f}")
    logging.info(f"  State Vector MAE:  {metrics['overall_state_mae']:.3f}")
    logging.info("="*60)
    
    return metrics