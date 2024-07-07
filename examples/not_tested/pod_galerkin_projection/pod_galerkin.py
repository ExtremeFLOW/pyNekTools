# Import general modules
import sys
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import json
import numpy as np
import matplotlib.pyplot as plt

# Import MPI
from mpi4py import MPI #equivalent to the use of MPI_init() in C


def get_gradU(u, v, w, msh, coef):

    grad = np.zeros((msh.nelv, msh.lz, msh.ly, msh.lx, 3, 3)) # For each point, I get a tensor

    # Fill the Gradient 
    grad[:,:,:,:,0,0] = coef.dudxyz(u, coef.drdx, coef.dsdx, coef.dtdx) #dudx
    grad[:,:,:,:,0,1] = coef.dudxyz(u, coef.drdy, coef.dsdy, coef.dtdy) #dudy
    grad[:,:,:,:,0,2] = coef.dudxyz(u, coef.drdz, coef.dsdz, coef.dtdz) #dudz
    
    grad[:,:,:,:,1,0] = coef.dudxyz(v, coef.drdx, coef.dsdx, coef.dtdx) #dudx
    grad[:,:,:,:,1,1] = coef.dudxyz(v, coef.drdy, coef.dsdy, coef.dtdy) #dudy
    grad[:,:,:,:,1,2] = coef.dudxyz(v, coef.drdz, coef.dsdz, coef.dtdz) #dudz
    
    grad[:,:,:,:,2,0] = coef.dudxyz(w, coef.drdx, coef.dsdx, coef.dtdx) #dudx
    grad[:,:,:,:,2,1] = coef.dudxyz(w, coef.drdy, coef.dsdy, coef.dtdy) #dudy
    grad[:,:,:,:,2,2] = coef.dudxyz(w, coef.drdz, coef.dsdz, coef.dtdz) #dudz

    return grad

def get_gradU_p_gradUT(grad_U, msh):

    grad_U_UT   = np.zeros((msh.nelv, msh.lz, msh.ly, msh.lx, 3, 3)) 
    
    for e in range(0, msh.nelv):
        for k in range(0, msh.lz):
            for j in range(0, msh.ly):
                for i in range(0, msh.lx):
                    grad_U_UT[e, k, j, i, :, :] = grad_U[e, k, j, i, :, :] + grad_U[e, k, j, i, :, :].T 

    return grad_U_UT

def get_UgradU(U, grad_U, msh):

    U_grad_U   = np.zeros((msh.nelv, msh.lz, msh.ly, msh.lx, 3)) # For each point, 3 arrays, one for each velocity
    
    for e in range(0, msh.nelv):
        for k in range(0, msh.lz):
            for j in range(0, msh.ly):
                for i in range(0, msh.lx):
                    U_grad_U[e, k, j, i, :] = (grad_U[e, k, j, i, :, :] @ np.array([U[e, k, j, i, 0], U[e, k, j, i, 1], U[e, k, j, i, 2]]).reshape(-1,1))[:,0] 

    return U_grad_U



# Split communicator for MPI - MPMD
worldcomm = MPI.COMM_WORLD
worldrank = worldcomm.Get_rank()
worldsize = worldcomm.Get_size()
col = 1
comm = worldcomm.Split(col,worldrank)
rank = comm.Get_rank()
size = comm.Get_size()


# Open input file to see path
f = open ("inputs.json", "r")
params_file = json.loads(f.read())
f.close()

# Read the POD inputs
pod_number_of_snapshots = params_file["number_of_snapshots"]
pod_fields = params_file["fields"]
number_of_pod_fields = len(pod_fields)
pod_batch_size = pod_number_of_snapshots
pod_keep_modes = params_file["keep_modes"]
pod_write_modes = params_file["write_modes"]
projection_project_on = params_file["project_on_modes"]
M = projection_project_on

# Import IO helper functions
from pynektools.io.utils import get_fld_from_ndarray, io_path_data

# Import modules for reading and writing
from pynektools.ppymech.neksuite import preadnek, pwritenek
# Import the data types
from pynektools.datatypes.msh import msh_c
from pynektools.datatypes.coef import coef_c
from pynektools.datatypes.field import field_c
from pynektools.datatypes.utils import create_hexadata_from_msh_fld
# Import types asociated with POD
from pynektools.rom.pod import POD_c
from pynektools.rom.io_help import io_help_c

# Read the data paths from the input file
mesh_data = io_path_data(params_file["IO"]["mesh_data"])
field_data = io_path_data(params_file["IO"]["field_data"])


# Instance the POD object
pod = POD_c(comm, number_of_modes_to_update = pod_keep_modes, global_updates = True, auto_expand = False, threads = 1)

# Initialize the mesh file
path     = mesh_data.dataPath
casename = mesh_data.casename
index    = mesh_data.index
fname    = path+casename+'0.f'+str(index).zfill(5)
data     = preadnek(fname, comm)
msh      = msh_c(comm, data = data)
del data

# Initialize coef to get the mass matrix
coef = coef_c(msh, comm)
bm = coef.B

# Instance io helper that will serve as buffer for the snapshots
ioh = io_help_c(comm, number_of_fields = number_of_pod_fields, batch_size = pod_batch_size, field_size = bm.size)
ioh_unscaled = io_help_c(comm, number_of_fields = number_of_pod_fields, batch_size = pod_batch_size, field_size = bm.size, module_name = "io_helper_2")

# Put the mass matrix in the appropiate format (long 1d array)
mass_list = []
for i in range(0, number_of_pod_fields):
    mass_list.append(np.copy(np.sqrt(bm)))
ioh.copy_fieldlist_to_xi(mass_list)
ioh.bm1sqrt[:,:] = np.copy(ioh.xi[:,:])

# Put the mass matrix in the appropiate format (long 1d array)
mass_list = []
for i in range(0, number_of_pod_fields):
    mass_list.append(np.copy((bm)))
ioh_unscaled.copy_fieldlist_to_xi(mass_list)
ioh_unscaled.bm1[:,:] = np.copy(ioh_unscaled.xi[:,:])


j = 0
while j < pod_number_of_snapshots:

    # Recieve the data from fortran
    path     = field_data.dataPath
    casename = field_data.casename
    index    = field_data.index
    fname=path+casename+'0.f'+str(index + j).zfill(5)
    fld_data = preadnek(fname, comm)

    # Get the data in field format
    fld = field_c(comm, data = fld_data)

    # Get the required fields
    u = fld.fields["vel"][0]
    v = fld.fields["vel"][1]
    w = fld.fields["vel"][2]

    u_ = np.copy(u)
    v_ = np.copy(v)
    w_ = np.copy(w)

    # Put the snapshot data into a column array
    ioh.copy_fieldlist_to_xi([u, v, w])
    ioh_unscaled.copy_fieldlist_to_xi([u_, v_, w_])

    # Load the column array into the buffer
    ioh.load_buffer(scale_snapshot = True)
    ioh_unscaled.load_buffer(scale_snapshot = False)

    # Update POD modes
    if ioh.update_from_buffer:

        # Find the mean of the snapshots
        ## For the scaled snapshots
        scaled_mean = np.mean(ioh.buff[:,:(ioh.buffer_index)], axis = 1)
        scaled_mean = scaled_mean.reshape(-1,1)
        ## For the unscaled snapshots to be used in the ROM
        s_mean = np.mean(ioh_unscaled.buff[:,:(ioh_unscaled.buffer_index)], axis = 1)
        s_mean = s_mean.reshape(-1,1)

        # Write the means
        field_list1d = ioh.split_narray_to_1dfields(s_mean[:,0])
        u_mean = get_fld_from_ndarray(field_list1d[0], msh.lx, msh.ly, msh.lz, msh.nelv)
        v_mean = get_fld_from_ndarray(field_list1d[1], msh.lx, msh.ly, msh.lz, msh.nelv)
        w_mean = get_fld_from_ndarray(field_list1d[2], msh.lx, msh.ly, msh.lz, msh.nelv)

        ## Create an empty field and update its metadata
        out_fld = field_c(comm)
        out_fld.fields["scal"].append(u_mean)
        out_fld.fields["scal"].append(v_mean)
        out_fld.fields["scal"].append(w_mean)
        out_fld.update_vars()

        ## Create the hexadata to write out
        out_data = create_hexadata_from_msh_fld(msh = msh, fld = out_fld)

        ## Write out a file
        fname = "mean_field0.f"+str(0).zfill(5)
        pwritenek("./"+fname,out_data, comm)
        print("Wrote file: " + fname)

        # Subtract the scaled mean from the scaled snapshot before the POD
        ioh.buff[:,:(ioh.buffer_index)] = ioh.buff[:,:(ioh.buffer_index)] - scaled_mean

        # Perform the POD
        pod.update(comm, buff = ioh.buff[:,:(ioh.buffer_index)])


    j += 1


# Check if there is information in the buffer that should be taken in case the loop exit without flushing
if ioh.buffer_index > ioh.buffer_max_index:
    ioh.log.write("info","All snapshots where properly included in the updates")
else: 
    ioh.log.write("warning","Last loaded snapshot to buffer was: "+repr(ioh.buffer_index-1))
    ioh.log.write("warning","The buffer updates when it is full to position: "+repr(ioh.buffer_max_index))
    ioh.log.write("warning","Data must be updated now to not lose anything,  Performing an update with data in buffer ")
    pod.update(comm, buff = ioh.buff[:,:(ioh.buffer_index)])

# Scale back the modes
pod.scale_modes(comm, bm1sqrt = ioh.bm1sqrt, op = "div")

# Rotate local modes back to global, This only enters in effect if global_update = false
pod.rotate_local_modes_to_global(comm)

# Go over the modes
for j in range(0, pod_write_modes):

    ## Split the snapshots into the proper fields
    field_list1d = ioh.split_narray_to_1dfields(pod.U_1t[:,j])
    u_mode = get_fld_from_ndarray(field_list1d[0], msh.lx, msh.ly, msh.lz, msh.nelv)
    v_mode = get_fld_from_ndarray(field_list1d[1], msh.lx, msh.ly, msh.lz, msh.nelv)
    w_mode = get_fld_from_ndarray(field_list1d[2], msh.lx, msh.ly, msh.lz, msh.nelv)

    ## Create an empty field and update its metadata
    out_fld = field_c(comm)
    out_fld.fields["scal"].append(u_mode)
    out_fld.fields["scal"].append(v_mode)
    out_fld.fields["scal"].append(w_mode)
    out_fld.update_vars()

    ## Create the hexadata to write out
    out_data = create_hexadata_from_msh_fld(msh = msh, fld = out_fld)

    ## Write out a file
    fname = "modes0.f"+str(j).zfill(5)
    pwritenek("./"+fname,out_data, comm)
    if comm.Get_rank() == 0: print("Wrote file: " + fname)


if comm.Get_rank() == 0:
    np.save("singular_values", pod.D_1t)
    print("Wrote signular values")
    np.save("right_singular_vectors", pod.Vt_1t)
    print("Wrote right signular values")



####################### Galerkin projection part

# Time coefficients projecting the snapshots into a number of modes
snaps = pod_number_of_snapshots
aa = np.zeros((M, snaps))
time = np.arange(len(aa[0,:]))*0.5

for i in range(0,snaps):
    centered_snapshot = (ioh_unscaled.buff[:,i]-s_mean[:,0]).reshape(-1,1)
    projection_i = pod.U_1t[:, :M].T@(ioh_unscaled.bm1*centered_snapshot)
    
    # Use MPI_SUM to get the global one by aggregating local
    projection = np.zeros_like(projection_i,dtype=projection_i.dtype)
    comm.Allreduce(projection_i, projection, op=MPI.SUM)

    aa[:,i] = np.copy(projection[:,0]) # Here, the inner product is with respect to the weights

# Save projected coefficients:
if comm.Get_rank() == 0: np.save("projected_coefficients", aa)



b = np.zeros((M))
A = np.zeros((M, M))
B = np.zeros((M, M, M))

re = 160

# Allocate arrays
phi_k      = np.zeros((msh.nelv, msh.lz, msh.ly, msh.lx, 3)) # For each point, 3 arrays, one for each velocity
phi_m      = np.zeros((msh.nelv, msh.lz, msh.ly, msh.lx, 3)) # For each point, 3 arrays, one for each velocity
phi_n      = np.zeros((msh.nelv, msh.lz, msh.ly, msh.lx, 3)) # For each point, 3 arrays, one for each velocity
U          = np.zeros((msh.nelv, msh.lz, msh.ly, msh.lx, 3)) # For each point, 3 arrays, one for each velocity

# Put data in appropiate format
field_list1d = ioh.split_narray_to_1dfields(s_mean[:,0])
U[:,:,:,:,0] = get_fld_from_ndarray(field_list1d[0], msh.lx, msh.ly, msh.lz, msh.nelv) 
U[:,:,:,:,1] = get_fld_from_ndarray(field_list1d[1], msh.lx, msh.ly, msh.lz, msh.nelv) 
U[:,:,:,:,2] = get_fld_from_ndarray(field_list1d[2], msh.lx, msh.ly, msh.lz, msh.nelv)

bm_for_array = bm.reshape(msh.nelv, msh.lz, msh.ly, msh.lx, 1) # Just reshape in a way that we can broadcast a multiplication operation
bm_for_grad = bm.reshape(msh.nelv, msh.lz, msh.ly, msh.lx, 1, 1) # Just reshape in a way that we can broadcast a multiplication operation

# Get the gradient
grad_U = get_gradU(U[:,:,:,:,0], U[:,:,:,:,1], U[:,:,:,:,2], msh, coef)

# Get the strain matrix
grad_U_UT = get_gradU_p_gradUT(grad_U, msh)

# Get U_grad_U, i.e., non linear term
U_grad_U = get_UgradU(U, grad_U, msh)

from tqdm import tqdm

pbar= tqdm(total=M*M*M)

for k in range(0, M):

    #print("k = {}".format(k))
    
    # Get phi_k
    field_list1d = ioh.split_narray_to_1dfields(pod.U_1t[:,k])
    phi_k[:,:,:,:,0] = get_fld_from_ndarray(field_list1d[0], msh.lx, msh.ly, msh.lz, msh.nelv) 
    phi_k[:,:,:,:,1] = get_fld_from_ndarray(field_list1d[1], msh.lx, msh.ly, msh.lz, msh.nelv) 
    phi_k[:,:,:,:,2] = get_fld_from_ndarray(field_list1d[2], msh.lx, msh.ly, msh.lz, msh.nelv)

    # Grad of phi_k
    grad_phi_k = get_gradU(phi_k[:,:,:,:,0], phi_k[:,:,:,:,1], phi_k[:,:,:,:,2], msh, coef)

    # first inner product in b
    inner_phi_k_U_grad_U = coef.glsum(U_grad_U * phi_k * bm_for_array, comm)
    
    # second inner product in b
    inner_grad_phi_k_grad_UUT_2 = coef.glsum(grad_phi_k * grad_U_UT/2 * bm_for_grad, comm)

    # b
    b[k] = - inner_phi_k_U_grad_U - 2/re * inner_grad_phi_k_grad_UUT_2

    for m in range(0, M):

        #print("m = {}".format(m))

        # Get phi_m
        field_list1d = ioh.split_narray_to_1dfields(pod.U_1t[:,m])
        phi_m[:,:,:,:,0] = get_fld_from_ndarray(field_list1d[0], msh.lx, msh.ly, msh.lz, msh.nelv) 
        phi_m[:,:,:,:,1] = get_fld_from_ndarray(field_list1d[1], msh.lx, msh.ly, msh.lz, msh.nelv) 
        phi_m[:,:,:,:,2] = get_fld_from_ndarray(field_list1d[2], msh.lx, msh.ly, msh.lz, msh.nelv)

        # Grad of phi_m
        grad_phi_m = get_gradU(phi_m[:,:,:,:,0], phi_m[:,:,:,:,1], phi_m[:,:,:,:,2], msh, coef)

        # Get the strain matrix
        grad_phi_m_phi_mT = get_gradU_p_gradUT(grad_phi_m, msh)

        # Get non linear terms
        U_grad_phi_m = get_UgradU(U, grad_phi_m, msh)
        phi_m_grad_U = get_UgradU(phi_m, grad_U, msh)

        
        # first inner product in A
        inner_phi_k_u_grad_phi_m = coef.glsum(phi_k * U_grad_phi_m  * bm_for_array, comm)

        # Second inner product in A
        inner_phi_k_phi_m_grad_u = coef.glsum(phi_k * phi_m_grad_U  * bm_for_array, comm)

        # Third inner product in A
        inner_grad_phi_k_grad_phi_m_phi_mT_2 =  coef.glsum(grad_phi_k * grad_phi_m_phi_mT/2 * bm_for_grad, comm)

        A[k, m] = - inner_phi_k_u_grad_phi_m - inner_phi_k_phi_m_grad_u - 2/re*inner_grad_phi_k_grad_phi_m_phi_mT_2


        for n in range(0, M):

            #print("n = {}".format(n))

            # Get phi_n
            field_list1d = ioh.split_narray_to_1dfields(pod.U_1t[:,n])
            phi_n[:,:,:,:,0] = get_fld_from_ndarray(field_list1d[0], msh.lx, msh.ly, msh.lz, msh.nelv) 
            phi_n[:,:,:,:,1] = get_fld_from_ndarray(field_list1d[1], msh.lx, msh.ly, msh.lz, msh.nelv) 
            phi_n[:,:,:,:,2] = get_fld_from_ndarray(field_list1d[2], msh.lx, msh.ly, msh.lz, msh.nelv)

            # Grad of phi_n
            grad_phi_n = get_gradU(phi_n[:,:,:,:,0], phi_n[:,:,:,:,1], phi_n[:,:,:,:,2], msh, coef)
        
            # Get non linear terms
            phi_m_grad_phi_n = get_UgradU(phi_m, grad_phi_n, msh)

            #first inner product in B
            inner_phi_k_phi_m_grad_phi_n = coef.glsum(phi_k * phi_m_grad_phi_n * bm_for_array, comm)

            B[k,m,n] = - inner_phi_k_phi_m_grad_phi_n

            pbar.update(1)

pbar.close()


if comm.Get_rank() == 0 :
    np.save("b", b)
    np.save("A", A)
    np.save("B", B)
