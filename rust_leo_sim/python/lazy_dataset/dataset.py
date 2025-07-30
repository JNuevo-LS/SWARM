import datetime
import math
import os
from dataclasses import dataclass
from itertools import chain
from multiprocessing import Pool
from random import shuffle

import numpy as np
from satkit import satstate
from torch.utils.data import Dataset

from custom_satkit.CustomTLE import CustomTLE as TLE
from util.read import read_blocks, read_zst


class State:
    def __init__(self, line:str):
        orbital_data = line.split(",")

        self.dt_time = datetime.datetime.fromtimestamp(float(orbital_data[0].rstrip())) #to be optimized
        # self.time = time.from_datetime(self.dt_time)
        self.pos_x = float(orbital_data[1])
        self.pos_y = float(orbital_data[2])
        self.pos_z = float(orbital_data[3])
        self.vel_x = float(orbital_data[4])
        self.vel_y = float(orbital_data[5])
        self.vel_z = float(orbital_data[6])
    
    def get_position_vector(self):
        """
        Returns the position vector as a numpy array
        """
        return np.array([self.pos_x, self.pos_y, self.pos_z])
    
    def get_velocity_vector(self):
        """
        Returns the velocity vector as a numpy array
        """
        return np.array([self.vel_x, self.vel_y, self.vel_z])
    
    def get_velocity_magnitude(self):
        """
        Returns magnitude of the velocity vector, in km/s
        """
        return math.sqrt(self.vel_x**2 + self.vel_y**2 + self.vel_z**2)/1000

    def create_SatState(self):
        """
        Returns a SatState object from satkit with the current object's data
        """
        return satstate(self.time, self.get_position_vector(), self.get_velocity_vector())
    
@dataclass
class TrainingStep:
    tle: TLE
    states: tuple[State]
    tsinces: tuple[int]

@dataclass
class CurrentBatch:
    idx: int
    training_step: list[TrainingStep]

class LazyDataset(Dataset):
    def __init__(
            self, 
            folder: str, 
            batch_size: int = 8, 
            randomized_order: bool = True, 
            multiprocess: bool = False,
            ):
        self.folder = folder
        self.batch_size = batch_size
        self.randomized_order = randomized_order

        files = self._read_folder()
        self.batches = self._batch_list(files, self.batch_size)


        self.loaded_in: CurrentBatch = None #used to store the currently loaded batch data
        self.batcher = self._get_batch if not multiprocess else self._get_batch_pooled

        if self.randomized_order:
            shuffle(self.batches)

        self.current_batch_idx = 0

    def __getitem__(self, idx: int):
        if abs(idx) >= len(self.batches):
            raise IndexError(f"Index {idx} out of range for dataset with {len(self.batches)} batches.")

        return self.batches[idx]
    
    def __len__(self):
        """
        Returns the number of batches in the dataset.
        """
        return len(self.batches)
    
    def __iter__(self):
        """
        Sets up the iterator for the dataset.
        """
        for batch in self.batches:
            yield self._get_next_batch()

    def _get_batch(self, idx: int):
        if abs(idx) >= len(self.batches):
            raise IndexError(f"Index {idx} out of range for dataset with {len(self.batches)} batches.")

        line_args = [f"{self.folder}/{filepath}" for filepath in self.batches[idx]]
        loaded_lines: list[list[str]] = [read_zst(filepath) for filepath in line_args]

        loaded_batch: list[TrainingStep] = []
        for file_lines in loaded_lines:
            loaded_batch.extend(read_blocks(file_lines))
        return loaded_batch

    def _get_batch_pooled(self, idx: int, use_imap: bool = False):
        """
        Gets a batch of data using multiprocessing. Uses a pool of workers to read files and process
        Parameters:
            idx (int): Index of the batch to get.
            use_imap (bool): If True, uses imap for lazy loading of results. (Better for very large datasets only)
        """
        if abs(idx) >= len(self.batches):
            raise IndexError(f"Index {idx} out of range for dataset with {len(self.batches)} batches.")

        def process_file(filepath):
            lines = read_zst(filepath)
            return read_blocks(lines)

        with Pool() as pool:
            line_args = [f"{self.folder}/{filepath}" for filepath in self.batches[idx]]

            batch_results: list[list[TrainingStep]] = pool.imap(process_file, line_args) if use_imap else pool.map(process_file, line_args)
            loaded_batch: list[TrainingStep] = list(chain.from_iterable(batch_results))  # Flatten the list of lists
        return loaded_batch
        
    def _batch_list(self, input_list: list, batch_size: int):
        """
        Divides a given list into sublists of size = batch_size
        """
        
        if not input_list:
            raise ValueError("Input list is empty, cannot create batches.")

        return [input_list[i:i+batch_size] for i in range(0, len(input_list), batch_size)]

    def _get_next_batch(self):
        """
        Returns the next batch of data, loading it if necessary. Increments the current index.
        """
        if not self.loaded_in or self.loaded_in.idx != self.current_batch_idx:
            self.loaded_in = CurrentBatch(self.current_batch_idx, self.batcher(self.current_batch_idx))

        batch = self.loaded_in.training_step
        self.current_batch_idx = (self.current_batch_idx + 1) % len(self.batches)
        return batch
    
    def _read_folder(self):
        """
        Reads the folder and returns a list of files.
        """
        if not os.path.exists(self.folder):
            raise FileNotFoundError(f"Dataset folder '{self.folder}' does not exist.")
        
        files = os.listdir(self.folder)
        if not files:
            raise ValueError(f"No files found in dataset folder '{self.folder}'.")
        
        return files
    