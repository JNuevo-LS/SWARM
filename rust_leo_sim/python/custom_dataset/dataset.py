from dataclasses import dataclass
import datetime
import math
import os
from multiprocessing import Pool
from random import shuffle
from custom_satkit.CustomTLE import CustomTLE as TLE
import numpy as np
from satkit import satstate, time
from torch.utils.data import Dataset
from functools import lru_cache

from util.read import read_blocks, read_zst


class State:
    def __init__(self, line:str):
        orbital_data = line.split(",")

        dt_time = datetime.datetime.fromtimestamp(float(orbital_data[0].rstrip())) #to be optimized
        self.time = time.from_datetime(dt_time)
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
    step: list[TrainingStep]

class LazyDataset(Dataset):
    def __init__(self, folder: str, batch_size: int = 8, randomized_order: bool = True, multiprocess: bool = False):
        self.folder = folder
        self.batch_size = batch_size
        self.randomized_order = randomized_order

        data = os.listdir(folder)
        self.batches = self._batch_list(data, self.batch_size)
        self.loaded_in: CurrentBatch = None #used to store the currently loaded batch data
        self.num_batches = len(self.batches)

        self.batcher = self._get_batch if not multiprocess else self._get_batch_pooled

        if self.randomized_order:
            shuffle(self.batches)

        self.current_batch_idx = 0
        if not self.num_batches > 0:
            raise ValueError("No batches found in the dataset.")

    def __getitem__(self, idx):
        if abs(idx) >= self.num_batches:
            raise IndexError(f"Index {idx} out of range for dataset with {self.num_batches} batches.")
        
        return self.batches[idx]
    
    def __len__(self):
        """
        Returns the number of batches in the dataset.
        """
        return self.num_batches 
    
    def __iter__(self):
        """
        Initializes the iterator by resetting the batch index.
        """
        self.current_batch_idx = 0
        return self

    def __next__(self):
        """
        Returns the next batch of data. Raises StopIteration when all batches are exhausted.
        """
        if self.current_batch_idx >= self.num_batches:
            raise StopIteration
        batch = self._get_next_batch()
        return batch

    def _get_batch(self, idx):
        if abs(idx) >= self.num_batches:
            raise IndexError(f"Index {idx} out of range for dataset with {self.num_batches} batches.")

        line_args = [(f"{self.folder}/{filepath}",) for filepath in self.batches[idx]]
        loaded_lines = read_zst(line_args)

        batch_args = [(lines,) for lines in loaded_lines]
        loaded_batch = read_blocks(batch_args)
        return CurrentBatch(self.current_batch_idx, loaded_batch)

    def _get_batch_pooled(self, idx):
        if abs(idx) >= self.num_batches:
            raise IndexError(f"Index {idx} out of range for dataset with {self.num_batches} batches.")
        
        with Pool(5) as pool:
            line_args = [(f"{self.folder}/{filepath}",) for filepath in self.batches[idx]]
            loaded_lines = pool.starmap(read_zst, line_args)

            batch_args = [(lines,) for lines in loaded_lines]
            loaded_batch = pool.starmap(read_blocks, batch_args)
        return CurrentBatch(self.current_batch_idx, loaded_batch)
        
    def _batch_list(input_list: list, batch_size: int = 8):
        """
        Divides a given list into sublists of size = batch_size
        """
        return [input_list[i:i+batch_size] for i in range(0, len(input_list), batch_size)]

    def _get_next_batch(self):
        """
        Returns the next batch of data, loading it if necessary. Increments the current index.
        """
        if self.current_batch_idx >= self.num_batches:
            self.current_batch_idx = 0
        if not self.loaded_in or self.loaded_in.idx != self.current_batch_idx:
            self.loaded_in = self.batcher(self.current_batch_idx)

        batch = self.loaded_in
        self.current_batch_idx += 1
        return batch