from customMLDSGP4 import mldsgp4
from multiprocessing import Pool
import torch
import customMLDSGP4
from CustomTLE import CustomTLE
import matplotlib
import time
from functools import partial
matplotlib.use('Agg')

def propagate_between_gaps(tle_records, density_per_segment):
    """
    tle_list: A sorted list of TLE dictionaries
    density: Number of timesteps to simulate in between each gap
    """
    ml_dsgp4 = customMLDSGP4.mldsgp4(hidden_size=35)
    start = time.time()
    (tle, gap) = process_records(tle_records) #tuple of record and time to be as arguments
    print(f"Processed in {time.time() - start} seconds")
    all_states = []
    id = tle[0].international_designator.strip()

    tle_n = len(tle)
    for i in range(tle_n-1):
        # print(f"[{id}] Step ({i+1}/{tle_n})")
        tle_i = tle[i]
        gap_i = gap[i]
        all_states.append(propagate(tle_i, gap_i, density_per_segment, ml_dsgp4))
    all_states.append(propagate(tle[tle_n-1], 60*24, density_per_segment, ml_dsgp4))

    #Optional plotting of each orbit
    # filepath = f"{id.strip()}_{year}.png"
    # print("Plotting to PNGs")
    # plot_segments(all_states, filepath, ml_dsgp4)

    return all_states

def propagate_between_gaps_mp(tle_records, density_per_segment):
    ml_dsgp4 = customMLDSGP4.mldsgp4(hidden_size=35)
    
    start = time.time()
    tle_gaps = process_records(tle_records)
    print(f"Processed in {time.time() - start} seconds")

    propagate_partial = partial(propagate, density=density_per_segment)
    
    with Pool(5) as pool:
        all_states = pool.starmap(propagate_partial, tle_gaps, chunksize=10)
    return all_states
    

def propagate(record:CustomTLE, time:int, density:int, model:customMLDSGP4):
    """
    Record: Expects a CustomTLE object \n
    Time: Seconds to propagate as an integer \n
    Density: Number of timesteps in between \n
    """
    time_steps = torch.linspace(0, time, density)
    tle_expanded = [record] * density

    with torch.no_grad():
        segment_states = model(tle_expanded, time_steps)
    segment_states = segment_states.detach().clone().numpy()
    
    return segment_states

def process_records(records: list): 
    tle_list = []
    gaps = []

    if not records:
        return (tle_list, gaps)

    first_tle = CustomTLE(records[0])
    tle_list.append(first_tle)
    t1 = first_tle["_epoch"]  #datetime obj

    for rec in records[1:]:
        tle = CustomTLE(rec)
        tle_list.append(tle)
        t2 = tle["_epoch"]
        t_diff = (t2 - t1).total_seconds() / 60
        gaps.append(t_diff)
        t1 = t2
    
    return (tle_list, gaps)

def plot_segments(all_states, base_filename, model: mldsgp4):
    """
    all_states: list of numpy arrays, each representing one propagated path
    base_filename: base name to use for the saved plots
    model: mldsgp4 model (needed for unnormalizing)
    """
    import matplotlib.pyplot as plt
    import numpy as np
    import os

    out_dir = "../data/plots"
    os.makedirs(out_dir, exist_ok=True)

    for i, segment in enumerate(all_states):
        #unnormalize the segment
        position = segment[:,:3]*model.normalization_R

        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        ax.scatter(position[:, 0], position[:, 1], position[:, 2])

        segment_filename = f"{base_filename}_segment_{i}.png"
        full_path = os.path.join(out_dir, segment_filename)

        plt.savefig(full_path)
        plt.close(fig)

    print(f"Saved {len(all_states)} plots to '{out_dir}'")

def plot(states, filepath:str, model: mldsgp4):
    from matplotlib import pyplot as plt

    #unnormalize:
    position=states[:,:3]*model.normalization_R
    velocity=states[:,3:]*model.normalization_V

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(position[:,0], position[:,1], position[:,2])
    ax.axis('equal')
    plt.savefig(f"../data/plots/{filepath}")