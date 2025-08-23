import io
import logging
import random

import zstandard as zstd
from dsgp4.tle import TLE

class ResultReader():
    def __init__(self, num_lines_per_block: int, num_states_per_tle: int) -> None:
        self.num_lines_per_block = num_lines_per_block
        self.num_states_per_tle = num_states_per_tle
        self.decompressor = zstd.ZstdDecompressor()

        logging.info(f"Initialized ResultReader with {num_lines_per_block} lines per block, gathering {num_states_per_tle} states each.")

        if num_states_per_tle + 2 > num_lines_per_block:
            logging.error("num_states_per_tle + 2 cannot be greater than num_lines_per_block")
            raise ValueError("num_states_per_tle + 2 cannot be greater than num_lines_per_block")
        elif num_states_per_tle + 2 < num_lines_per_block:
            logging.info("num_states_per_tle + 2 is less than num_lines_per_block, some lines will be ignored")

    def read_blocks(self, file_lines: list[str]):
        """
        Parses a list of lines from a file containing TLEs and satellite state data into blocks.
        Each block consists of two TLE lines followed by a specified number of satellite state lines.
        For each block, the function creates a TLE object, a tuple of State objects, computes the time
        since the TLE epoch for each state, and returns a list of TrainingStep objects containing these.
        Args:
            file_lines (list[str]): List of lines read from the input file.
            num_lines_per_block (int, optional): Number of lines per block (2 for TLE + N for states).
                Defaults to 1002 (2 TLE lines + 1000 state lines).
            num_states_per_tle (int, optional): Number of state lines per TLE. Defaults to 1000.
        Returns:
            list[TrainingStep]: List of TrainingStep objects, each containing a TLE, states, and time since epoch.
        """
        from lazy_dataset.dataset import State, TrainingStep

        def _compute_tsinces(epoch: float, states: tuple[State, ...]) -> tuple[int, ...]:
            """
            Epoch: Unix timestamp of TLE
            States: List of State objects representing satellite states in time
            """
            return tuple((state.dt_time - epoch).total_seconds() for state in states)

        def _process_block(start_idx: int, end_idx: int):
            tle = TLE([file_lines[start_idx].rstrip(), file_lines[start_idx + 1].rstrip()])
            states = tuple(State(file_lines[j]) for j in random.sample(range(start_idx + 2, end_idx), self.num_states_per_tle))
            return (tle, states)

        num_tles = int(
            len(file_lines) / self.num_lines_per_block
        )

        start = 0
        steps: list[TrainingStep] = []

        for i in range(num_tles):  # for each TLE
            upper_end = start + self.num_lines_per_block
            tle, states = _process_block(start, upper_end)
            tsinces = _compute_tsinces(tle["_epoch"], states)
            steps.append(TrainingStep(tle, states, tsinces))

        return steps
    
    def read_zst(self, filepath: str) -> list[str]:
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
        logging.info(f"Reading and decompressing file: {filepath}")
        lines = []
        with open(filepath, "rb") as file:
            reader = self.decompressor.stream_reader(file)
            text_stream = io.TextIOWrapper(reader, encoding="utf-8")

            for line in text_stream:
                lines.append(line.rstrip("\n"))
        return lines
