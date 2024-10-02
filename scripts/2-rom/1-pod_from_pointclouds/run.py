# Import required modules
from mpi4py import MPI #equivalent to the use of MPI_init() in C
import matplotlib.pyplot as plt
import numpy as np
import h5py
import json
import os

# Get mpi info
comm = MPI.COMM_WORLD

# Import the pynektools routines
from pynektools.rom.phy_pod_wrappers import pod_from_files, physical_space
from pynektools.rom.phy_pod_wrappers import write_3dfield_to_file
from pynektools.rom.phy_pod_wrappers import save_pod_state

if comm.Get_size() > 1:
    raise ValueError("This script is not designed to run in parallel (You can stream) For this case, this can be fixed by using hdf5 with parallel IO support")

def main():

    # Read inputs
    with open("inputs.json", "r") as f:
        inputs = json.load(f)

    # Fix the file sequence
    path = os.path.dirname(inputs["file_sequence"]["fname"])
    if path == "": path = "."
    prefix = os.path.basename(inputs["file_sequence"]["fname"]).split(".")[0]
    extension = os.path.basename(inputs["file_sequence"]["fname"]).split(".")[1]
    min_index = inputs["file_sequence"]["first_index"]
    max_index = inputs["file_sequence"]["first_index"] + inputs["file_sequence"]["number_of_files"]
    file_sequence = []
    for i in range(min_index, max_index):
        suffix = str(i).zfill(inputs["file_sequence"]["fill_name_with_zeros"])
        file_sequence.append(f"{path}/{prefix}{suffix}.{extension}")

    pod_fields = inputs["pod_fields"]
    mass_matrix_fname = inputs["mass_matrix"]["fname"]
    mass_matrix_key = inputs["mass_matrix"]["key"]
    k = inputs["pod_modes_to_update"]
    p = inputs["batch_size"]

    # Perform the POD with your input data
    pod, ioh, _3d_bm_shape = pod_from_files(comm, file_sequence, pod_fields, mass_matrix_fname, mass_matrix_key, k, p)

    # Save outputs
    mesh_fname = inputs["mass_matrix"]["fname"]
    # Load the mesh
    with h5py.File(mesh_fname, 'r') as f:
        x = f["x"][:]
        y = f["y"][:]
        z = f["z"][:]

    if inputs["outputs"]["write_modes"]["write"]:
    
        if inputs["outputs"]["write_modes"]["modes"] == "all":
            modes = [i for i in range(0, k)]
        else:
            modes = inputs["outputs"]["write_modes"]["modes"]
    
        write_3dfield_to_file(inputs["outputs"]["prefix"], x, y, z, pod, ioh, modes=modes, field_shape=_3d_bm_shape, field_names=pod_fields)
    
    if inputs["outputs"]["write_reconstruction"]["write"]:
    
        if inputs["outputs"]["write_reconstruction"]["modes"] == "all":
            modes = [i for i in range(0, k)]
        else:
            modes = inputs["outputs"]["write_reconstruction"]["modes"]

        if inputs["outputs"]["write_reconstruction"]["snapshots"] == "all":
            snapshots = [i for i in range(0, len(file_sequence))]
        else:
            snapshots = inputs["outputs"]["write_reconstruction"]["snapshots"]
        
        write_3dfield_to_file(inputs["outputs"]["prefix"], x, y, z, pod, ioh, modes=modes, field_shape=_3d_bm_shape, field_names=pod_fields, snapshots=snapshots)

    if inputs["outputs"]["write_state"]["write"]: 

        save_pod_state(inputs["outputs"]["write_state"]["name"], pod)

if __name__ == "__main__":
    main()