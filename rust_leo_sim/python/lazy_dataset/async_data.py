import queue
import threading
import time
from collections import defaultdict
import logging

import numpy as np
import satkit as sk
import torch
from torch.cuda import Stream
from util.transform import (extract_batch_data, gcrf_to_teme,
                            normalize_ground_truth)


class AsyncDataLoader:
    def __init__(self, dataset, device, max_prefetch=2):
        """Initialize the async data loader without starting threads yet."""
        self.dataset = dataset
        self.device = device
        self.max_prefetch = max_prefetch
        self.queue = queue.Queue(maxsize=max_prefetch)
        self.stop_event = threading.Event()
        self.worker_thread = None  # Will be started when iteration begins
        self.dataset_iterator = None  # Store the iterator

    def _prefetch_worker(self):
        """Worker thread that fetches and preprocesses data."""
        try:
            for i, batch in enumerate(self.dataset):
                if self.stop_event.is_set():
                    break

                # Process batch on CPU
                tles, states, steps = extract_batch_data(batch, self.device)
                
                # Check again before expensive operations
                if self.stop_event.is_set():
                    break

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
                state_tensors_teme = torch.zeros((len(states), 6), dtype=torch.float32, device=self.device)

                logging.info(f"[2/2] Converting states epoch by epoch")

                rotation_fn_time = time.time()
                for epoch, indices in epoch_table.items():
                    states_for_epoch = [states[index] for index in indices]
                    state_vectors = np.stack([np.concatenate([state.get_position_vector(), state.get_velocity_vector()]) for state in states_for_epoch])
                    state_tensor_teme = gcrf_to_teme(
                        torch.tensor(
                            state_vectors,
                            dtype=torch.float32,
                            device=self.device
                        ), sk.time.from_datetime(epoch)
                    )
                    # Fancy indexing to place converted states in the correct positions
                    state_tensors_teme[indices] = state_tensor_teme.squeeze(0)
                
                logging.info(f"[Done] Converted all states to TEME frame in {time.time() - rotation_fn_time:.2f} seconds")
                logging.info(f"Finished converting ground truth states to TEME frame in {time.time() - rotation_start:.2f} total seconds")
                normalization_start = time.time()
                target_states_normalized = normalize_ground_truth(state_tensors_teme)
                logging.info(f"Finished normalizing ground truth states in {time.time() - normalization_start:.2f} seconds")
                
                # Put processed batch in queue
                # Use put with timeout so we can check stop_event periodically
                try:
                    # Non-blocking put with timeout
                    self.queue.put((i, tles, steps, target_states_normalized, len(states)), 
                                timeout=1)
                except queue.Full:
                    if self.stop_event.is_set():
                        break
                    # If queue is full but we're not stopping, try again
                    continue
        except queue.Empty:
            logging.error("Timed out waiting for batch from worker thread")
            self.stop()  # Clean up
            raise StopIteration
        except Exception as e:
            logging.error(f"Error in prefetch worker: {e}")
            try:
                self.queue.put(None, timeout=1)  # Non-blocking error signal
            except queue.Full:
                pass  # We tried to signal error but queue was full
    
    def __iter__(self):
        """Start worker thread when iteration begins."""
        # Clear any previous state
        self.stop()
        self.queue = queue.Queue(maxsize=self.max_prefetch)
        self.stop_event.clear()
        self.dataset_iterator = None
        
        # Start a new worker thread
        self.worker_thread = threading.Thread(
            target=self._prefetch_worker, 
            daemon=True
        )
        self.worker_thread.start()
        logging.info("Started background prefetch worker thread")
        
        return self
        
    def __next__(self):
        """Get the next batch, with timeout protection."""
        if self.worker_thread is None:
            raise RuntimeError("Iterator not initialized properly - call iter() first")
            
        try:
            # Get data with timeout
            logging.info("Waiting for next batch from queue...")
            batch_data = self.queue.get(timeout=300)
            
            # Check for error signal
            if batch_data is None:
                raise RuntimeError("Background worker failed - check logs")
                
            # Unpack and move to correct device
            batch_idx, tles, steps, target_states_normalized, num_states = batch_data
            
            # Move tensors to target device right before use
            steps_device = steps.to(self.device)
            target_device = target_states_normalized.to(self.device)
            
            logging.info(f"Retrieved batch with {num_states} states from queue")
            return batch_idx, tles, steps_device, target_device
            
        except queue.Empty:
            logging.error("Timed out waiting for batch from worker thread")
            self.stop()  # Clean up
            raise StopIteration
    
    def stop(self):
        """Stop the worker thread and clean up."""
        if hasattr(self, 'stop_event'):
            self.stop_event.set()
            
        if hasattr(self, 'worker_thread') and self.worker_thread and self.worker_thread.is_alive():
            logging.info("Waiting for worker thread to terminate...")
            self.worker_thread.join(timeout=5)
            if self.worker_thread.is_alive():
                logging.warning("Worker thread did not terminate cleanly")
                
        # Clear queue
        if hasattr(self, 'queue'):
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break