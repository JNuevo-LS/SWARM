import torch
import torch.nn as nn
import numpy as np

def main():
    if torch.cuda.is_available():
        torch.set_default_device('cuda')
        device_str = 'cuda'
    else:
        device_str = 'cpu'

    device = torch.device(device_str)
    