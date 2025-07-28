from zstandard import zstd
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
        Processes a list of file lines to extract TLE (Two-Line Element) objects and satellite state data.

        Args:
            file_lines (list[str]): A list of strings representing the lines of a file. 
                                    Each block of 5003 lines contains 2 lines for TLE data 
                                    and 5001 lines for satellite state data.
            num_lines_per_block (int, optional): The number of lines per block. Defaults to 5003.

        Returns:
            tuple[list[TLE], list[TLE]]: A tuple containing two lists:
                - The first list contains TLE objects extracted from the file lines.
                - The second list contains State objects representing satellite state data.

        Raises:
            IndexError: If the input file lines do not conform to the expected block structure.
            ValueError: If the TLE or State objects cannot be created due to malformed input.

        Notes:
            - The State class is imported dynamically from `custom_dataset.dataset`.
        """
    from custom_dataset.dataset import State, TrainingStep
    def compute_tsinces(epoch:float, states: list[State]):
        """
        Epoch: Unix timestamp of TLE
        States: List of State objects representing satellite states in time
        """
        tsinces = []

        tuple()

        for state in states:
            tsince = (state.time - epoch) / 60
            tsinces.append(tsince)

        return tsinces
    
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

