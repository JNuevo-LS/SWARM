from unittest.mock import MagicMock
import numpy as np
import pytest
import torch
import datetime as dt
import satkit as sk
import util.transform as transform

def test_teme_to_gcrf():
    states_teme = torch.tensor([[7000, 0, 0, 0, 7.5, 1]], dtype=torch.float32)
    epoch = dt.datetime(2023, 1, 1, 0, 0, 0)
    epoch_sk = sk.time.from_datetime(epoch)

    states_gcrf = transform.teme_to_gcrf(states_teme, epoch_sk)

    assert states_gcrf.shape == states_teme.shape
    assert not torch.allclose(states_gcrf, states_teme)  # Should be different after transformation

def test_gcrf_to_teme():
    states_gcrf = torch.tensor([[7000, 0, 0, 0, 7.5, 1]], dtype=torch.float32)
    epoch = dt.datetime(2023, 1, 1, 0, 0, 0)
    epoch_sk = sk.time.from_datetime(epoch)

    states_teme = transform.gcrf_to_teme(states_gcrf, epoch_sk)

    assert states_teme.shape == states_gcrf.shape
    assert not torch.allclose(states_teme, states_gcrf)  # Should be different after transformation

def test_teme_to_gcrf_and_back():
    states_teme = torch.tensor([[7000, 0, 0, 0, 7.5, 1]], dtype=torch.float32)
    epoch = dt.datetime(2023, 1, 1, 0, 0, 0)
    epoch_sk = sk.time.from_datetime(epoch)

    states_gcrf = transform.teme_to_gcrf(states_teme, epoch_sk)
    states_teme_converted = transform.gcrf_to_teme(states_gcrf, epoch_sk)

    assert torch.allclose(states_teme, states_teme_converted, atol=1e-3)  # Should be close to original