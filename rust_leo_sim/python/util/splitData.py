import os
import random
import time

source = input("Source: ")

all_files = os.listdir(source)
num_files = len(all_files)

random.shuffle(all_files)

train_count = int(0.7 * num_files)
test_count = int(0.15 * num_files)
val_count = num_files - train_count - test_count

train_set = all_files[:train_count]
test_set = all_files[train_count : train_count + test_count]
val_set = all_files[train_count + test_count : train_count + test_count + val_count]


def split_to_folder(filepath_array, root_path: str, destination_filepath: str):
    if os.path.exists(destination_filepath) != True:
        os.makedirs(destination_filepath)

    for file in filepath_array:
        path = f"{root_path}/{file}"
        try:
            os.rename(path, f"{destination_filepath}/{file}")
        except FileNotFoundError as e:
            print(f"File {file} was not found")


print("Moving train folder...")
t = time.time()
split_to_folder(train_set, source, f"{source}/train")
print(f"Done moving train folder in {time.time() - t} seconds")
print("Moving test folder...")
t = time.time()
split_to_folder(test_set, source, f"{source}/test")
print(f"Done moving test folder in {time.time() - t}")
print("Moving validation folder...")
t = time.time()
split_to_folder(val_set, source, f"{source}/val")
print(f"Done moving validation folder in {time.time() - t}")
