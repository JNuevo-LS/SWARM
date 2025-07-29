import pytest
from unittest.mock import MagicMock
import numpy as np
import math
import datetime
import os
from lazy_dataset.dataset import State, LazyDataset, TrainingStep, CurrentBatch

# State class tests
def test_state_initialization_and_vectors():
    timestamp = 1710000000.0
    line = f"{timestamp},1000,2000,3000,4000,5000,6000"
    state = State(line)
    assert isinstance(state.dt_time, datetime.datetime)
    assert state.pos_x == 1000.0
    assert state.pos_y == 2000.0
    assert state.pos_z == 3000.0
    assert state.vel_x == 4000.0
    assert state.vel_y == 5000.0
    assert state.vel_z == 6000.0

    pos_vec = state.get_position_vector()
    vel_vec = state.get_velocity_vector()
    assert np.allclose(pos_vec, [1000, 2000, 3000])
    assert np.allclose(vel_vec, [4000, 5000, 6000])

def test_state_velocity_magnitude():
    line = "0,0,0,0,3000,4000,0"
    state = State(line)
    expected_mag = math.sqrt(3000**2 + 4000**2 + 0**2) / 1000
    assert np.isclose(state.get_velocity_magnitude(), expected_mag)

def test_state_invalid_line():
    with pytest.raises(IndexError):
        State("1,2,3")  # Not enough values

# LazyDataset
@pytest.fixture
def mock_dataset_folder(mocker):
    # Mock the file reading functions
    mock_files = ["file1.zst", "file2.zst", "file3.zst", "file4.zst", "file5.zst", 
                  "file6.zst", "file7.zst", "file8.zst", "file9.zst", "file10.zst"]
    mocker.patch("lazy_dataset.dataset.os.path.exists", return_value=True)
    mocker.patch("lazy_dataset.dataset.os.listdir", return_value=mock_files)  

def test_lazy_dataset_batching(mocker):
    mock_files = [["mock_file"]] * 10  # Simulate 10 files
    mocker.patch("lazy_dataset.dataset.os.path.exists", return_value=True)
    mocker.patch("lazy_dataset.dataset.os.listdir", return_value=mock_files)    

    ds = LazyDataset("mock_folder", batch_size=3, randomized_order=False)

    assert len(ds) == 4  # 10 files, batch_size = 3 -> 4 batches
    # Each batch should have <= 3 files
    for batch in ds.batches:
        assert 1 <= len(batch) <= 3

def test_lazy_dataset_randomized_order(mocker):

    # Mock a lot of files to ensure randomness
    mock_files = []
    for i in range(100):
        mock_files.append(f"file{i}.zst")

    mocker.patch("lazy_dataset.dataset.os.path.exists", return_value=True)
    mocker.patch("lazy_dataset.dataset.os.listdir", return_value=mock_files)    

    ds1 = LazyDataset("mock_folder", batch_size=2, randomized_order=True)
    ds2 = LazyDataset("mock_folder", batch_size=2, randomized_order=True)

    # Order is randomized, so batches should differ
    assert ds1.batches != ds2.batches

def test_lazy_dataset_getitem(mock_dataset_folder):
    ds = LazyDataset(mock_dataset_folder, batch_size=4)
    batch = ds[0]

    assert isinstance(batch, list)
    assert all(isinstance(f, str) for f in batch)

    with pytest.raises(IndexError):
        _ = ds[100]

def test_lazy_dataset_len(mock_dataset_folder):
    ds = LazyDataset(mock_dataset_folder, batch_size=5)
    assert len(ds) == 2

def test_lazy_dataset_iter(mock_dataset_folder, monkeypatch):
    # Patch read_zst and read_blocks to return dummy data
    monkeypatch.setattr("lazy_dataset.dataset.read_zst", lambda f: ["line1", "line2"])
    monkeypatch.setattr("lazy_dataset.dataset.read_blocks", lambda lines: [lines])
    
    ds = LazyDataset(mock_dataset_folder, batch_size=2)
    batches = []
    for batch in ds:
        assert isinstance(batch, list)
        batches.append(batch)
    assert len(batches) == len(ds)

def test_lazy_dataset_no_batches(tmp_path):
    # Empty folder
    with pytest.raises(ValueError):
        LazyDataset(str(tmp_path), batch_size=2)

def test_lazy_dataset_batch_list():
    ds = LazyDataset.__new__(LazyDataset)
    input_list = list(range(7))
    batches = ds._batch_list(input_list, batch_size=3)
    assert batches == [[0,1,2],[3,4,5],[6]]

# Training Step and CurrentBatch
def test_training_step_and_current_batch():
    # Dummy TLE and State
    class DummyTLE: pass
    dummy_tle = DummyTLE()
    dummy_state = State("0,1,2,3,4,5,6")
    ts = TrainingStep(tle=dummy_tle, states=(dummy_state,), tsinces=(0,))
    assert ts.tle is dummy_tle
    assert isinstance(ts.states[0], State)
    cb = CurrentBatch(idx=0, training_step=[ts])
    assert cb.idx == 0
    assert cb.training_step[0] == ts