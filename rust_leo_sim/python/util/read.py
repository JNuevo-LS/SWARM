import zstandard as zstd
import io
import os
from custom_satkit.CustomTLE import CustomTLE as TLE

def read_zst(filepath: str) -> list[str]:
    """
    Reads and decompresses a Zstandard-compressed file, returning its contents as a list of strings.

    Args:
        filepath (str): The path to the Zstandard-compressed file.

    Returns:
        list[str]: A list of strings, where each string represents a line from the decompressed file.

    Notes:
        - The function uses the Zstandard library to decompress the file.
        - Lines are stripped of trailing newline characters before being added to the list.
    """
    lines = []
    with open(filepath, "rb") as file:
        decompressor = zstd.ZstdDecompressor()
        reader = decompressor.stream_reader(file)
        text_stream = io.TextIOWrapper(reader, encoding="utf-8")

        for line in text_stream:
            lines.append(line.rstrip("\n"))
    return lines

def read_blocks(file_lines: list[str], num_lines_per_block: int = 5003):
    """   
     Parses a list of lines from a file containing TLEs and satellite state data into blocks.
    Each block consists of two TLE lines followed by a specified number of satellite state lines.
    For each block, the function creates a TLE object, a tuple of State objects, computes the time
    since the TLE epoch for each state, and returns a list of TrainingStep objects containing these.
    Args:
        file_lines (list[str]): List of lines read from the input file.
        num_lines_per_block (int, optional): Number of lines per block (2 for TLE + N for states).
            Defaults to 5003 (2 TLE lines + 5001 state lines).
    Returns:
        list[TrainingStep]: List of TrainingStep objects, each containing a TLE, states, and time since epoch."""
    from lazy_dataset.dataset import State, TrainingStep
    def compute_tsinces(epoch:float, states: list[State]):
        """
        Epoch: Unix timestamp of TLE
        States: List of State objects representing satellite states in time
        """
        return tuple((state.dt_time - epoch).total_seconds() for state in states)

    def process_block(start_idx: int, end_idx: int):
        tle = TLE([file_lines[start_idx].rstrip(), file_lines[start_idx+1].rstrip()])
        states = tuple(State(file_lines[j]) for j in range(start_idx+2, end_idx))
        return (tle, states)

    num_tles = int(len(file_lines)/num_lines_per_block) # 2 lines for TLE, 5001 lines for satstates
    start = 0
    steps: list[TrainingStep] = []

    for _ in range(num_tles): #for each TLE
        upper_end = start + num_lines_per_block
        tle, states = process_block(start, upper_end)
        tsinces = compute_tsinces(tle["_epoch"], states)
        steps.append(TrainingStep(tle, states, tsinces))

    return steps

