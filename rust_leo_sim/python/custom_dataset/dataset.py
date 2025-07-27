import os
from random import shuffle
from torch.utils.data import Dataset, DataLoader
from multiprocessing import Pool

class LazyDataset(Dataset):
    def __init__(self, folder: str, batch_size: int = 8, randomized_order = True):
        self.folder = folder
        self.batch_size = batch_size
        self.randomized_order = randomized_order

        data = os.listdir(folder)
        self.batches = batch_list(data, self.batch_size)
        self.loaded_in = [] #used to store the currently loaded batch data
        self.num_batches = len(self.batches)

        if self.randomized_order:
            shuffle(self.batches)

        if self.num_batches > 0:
            self.loaded_in = self.get_batch(0)

    def __getitem__(self, idx):
        return self.batches[idx]

    def get_batch(self, idx): 
        with Pool(5) as pool:
            line_args = [(f"{self.folder}/{filepath}",) for filepath in self.batches[idx]]
            loaded_lines = pool.starmap(read_zst, line_args)

            batch_args = [(lines,) for lines in loaded_lines]
            loaded_batch = pool.starmap(read_blocks, batch_args)

def read_folder(folder_path):
    results = []
    files = os.listdir(folder_path)
    for file in files:
        lines = read_zst(f"{folder_path}/{file}")
        (tle_arr, state_arr) = read_blocks(lines)
        step = TrainingStep(tle_arr, state_arr)
        results.append(step)
    return results