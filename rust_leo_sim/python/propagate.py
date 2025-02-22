from customMLDSGP4 import mldsgp4


# def propagate(record:list, time:int, density:int):
#     """
#     Record: Expects a list of dictionaries \n
#     Time: Hours to propagate \n
#     Density: Number of timesteps in between \n
#     """
#     import torch
#     import customMLDSGP4

#     tle_list = process_records(record)

#     name = tle_list[0]["international_designator"]

#     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#     print(f"Current Device: {device}")
#     time_in_minutes = 60*time

#     ml_dsgp4 = customMLDSGP4.mldsgp4(hidden_size=35)

#     time_steps = torch.cat([torch.linspace(0,time_in_minutes,density)]*len(tle_list))

#     tle_expanded = []
#     for tle in tle_list: #we need a tle for each timestep
#         tle_expanded += [tle]*density

#     print("Generating states")

#     with torch.no_grad():    
#         states_normalized_out = ml_dsgp4(tle_expanded, time_steps)

#     states_normalized_out = states_normalized_out.detach().clone().numpy()

#     print(f"Propagating {len(tle_expanded)} steps for {time_in_minutes} minutes")

#     _, batched_tle = customMLDSGP4.initialize_tle(tle_expanded)
#     states_teme = customMLDSGP4.propagate_batch(batched_tle, time_steps)
#     print("Finished propagation")
#     plot(states_normalized_out, name, ml_dsgp4)

#     return states_teme

def propagate_between_gaps(tle_records, density_per_segment):
    """
    tle_list: A sorted list of TLE dictionaries or CustomTLE objects.
    density: Number of timesteps to simulate in each gap.
    """
    import torch
    import customMLDSGP4
    import numpy as np
    from customTLE import CustomTLE

    ml_dsgp4 = customMLDSGP4.mldsgp4(hidden_size=35)
    all_states = []

    tle_list, gaps = process_records(tle_records)
    id = tle_list[0]["international_designator"]


    for i in range(len(tle_list) - 1):
        tle_start = tle_list[i]

        dt = gaps[i]
        time_steps = torch.linspace(0, dt, density_per_segment)
        tle_expanded = [tle_start] * density_per_segment

        with torch.no_grad():
            segment_states = ml_dsgp4(tle_expanded, time_steps)
        segment_states = segment_states.detach().clone().numpy()
        all_states.append(segment_states)
    
    # states_combined = np.concatenate(all_states, axis=0)
    # filepath = f"./data/plots/{id.strip()}_2006.png"
    # plot(states_combined, filepath, ml_dsgp4)

    return all_states

def process_records(records: list):
    from customTLE import CustomTLE
    from datetime import datetime

    tle_list = []
    gaps = []

    if not records:
        return tle_list, gaps

    first_tle = CustomTLE(records[0])
    tle_list.append(first_tle)
    t1 = first_tle["epoch"]  #datetime obj

    for rec in records[1:]:
        tle = CustomTLE(rec)
        tle_list.append(tle)
        t2 = tle["epoch"]
        t_diff = (t2 - t1).total_seconds()
        gaps.append(t_diff)
        t1 = t2

    return tle_list, gaps


def plot(states, filepath:str, model:mldsgp4):
    from matplotlib import pyplot as plt

    #unnormalize:
    position=states[:,:3]*model.normalization_R
    velocity=states[:,3:]*model.normalization_V

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(position[:,0], position[:,1], position[:,2])
    ax.axis('equal')
    plt.savefig(filepath)

def plot_segments(all_states, filepath: str, model: mldsgp4):
    from matplotlib import pyplot as plt
    import numpy as np
    import itertools

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Create an iterator of colors (or choose a colormap)
    colors = itertools.cycle(plt.cm.viridis(np.linspace(0, 1, len(all_states))))

    for segment, color in zip(all_states, colors):
        # Unnormalize segment positions
        position = segment[:, :3] * model.normalization_R
        ax.scatter(position[:, 0], position[:, 1], position[:, 2], c=[color], s=1)

    ax.axis('equal')
    plt.savefig(filepath)
    plt.show()
