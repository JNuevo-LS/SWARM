import os
from lazy_dataset.dataset import LazyDataset

def create_datasets(
    train_path: str | None = None, 
    test_path: str | None = None, 
    val_path: str | None = None,
    world_size: int = 1,
    rank: int | None = None,
    batch_size: int = 12, 
    mp: bool = False, 
    states_per_tle: int = 64, 
    ):

    TRAIN_PATH = os.getenv("TRAIN_PATH", train_path)
    TEST_PATH = os.getenv("TEST_PATH", test_path)
    VAL_PATH = os.getenv("VAL_PATH", val_path)

    if TRAIN_PATH is None or TEST_PATH is None or VAL_PATH is None:
        raise ValueError("One or more dataset paths are not set in the environment variables.")
    
    if world_size > 1 and rank is None:
        raise ValueError("Rank must be specified when world_size > 1")
    
    train_satellites = LazyDataset(TRAIN_PATH, world_size=world_size, rank=rank, batch_size=batch_size, multiprocess=mp, num_states_per_tle=states_per_tle)
    test_satellites = LazyDataset(TEST_PATH, world_size=world_size, rank=rank,  batch_size=batch_size, multiprocess=mp, num_states_per_tle=states_per_tle)
    val_satellites = LazyDataset(VAL_PATH, world_size=world_size, rank=rank,  batch_size=batch_size, multiprocess=mp, num_states_per_tle=states_per_tle)

    return train_satellites, test_satellites, val_satellites