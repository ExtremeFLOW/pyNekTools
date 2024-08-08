import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

# Initialize MPI
from mpi4py import MPI
comm = MPI.COMM_WORLD

# Import general modules
import numpy as np
# Import relevant modules
from pynektools.io.ppymech.neksuite import preadnek, pwritenek, pynekread, pynekwrite
from pymech.neksuite import readnek, writenek
from pynektools.datatypes.msh import Mesh as msh_c
from pynektools.datatypes.msh import get_coordinates_from_hexadata
from pynektools.datatypes.field import Field as field_c


NoneType = type(None)

#==============================================================================

def test_read_data_single():

    # Read the original mesh data
    fname = 'examples/data/rbc0.f00001'
    
    ddtype = np.single
    create_connectivity = True

    data1 = preadnek(fname, comm, data_dtype=ddtype)
    msh1 = msh_c(comm, data = data1, create_connectivity=create_connectivity)
    fld1 = field_c(comm, data=data1)
    
    data2 = preadnek(fname, comm)
    x, y, z = get_coordinates_from_hexadata(data2)
    msh2 = msh_c(comm, x = x, y = y, z = z, create_connectivity=create_connectivity)
    fld2 = field_c(comm, data=data2)

    msh3 = msh_c(comm, create_connectivity=create_connectivity)
    fld3 = field_c(comm)
    pynekread(fname, comm, msh = msh3, fld=fld3)

    #compare the objects
    t1 = np.allclose(msh1.x, msh2.x)
    t2 = np.allclose(msh1.y, msh2.y)
    t3 = np.allclose(msh1.z, msh2.z)
    t4 = np.allclose(msh1.x, msh3.x)
    t5 = np.allclose(msh1.y, msh3.y)
    t6 = np.allclose(msh1.z, msh3.z)
    t7 = np.allclose(msh2.x, msh3.x)
    t8 = np.allclose(msh2.y, msh3.y)
    t9 = np.allclose(msh2.z, msh3.z)
    passed1 = np.all([t1, t2, t3, t4, t5, t6, t7, t8, t9])
    
    if create_connectivity:
        t1 = msh1.coord_hash_to_shared_map == msh2.coord_hash_to_shared_map
        t2 = msh1.coord_hash_to_shared_map == msh3.coord_hash_to_shared_map
        t3 = msh2.coord_hash_to_shared_map == msh3.coord_hash_to_shared_map
        passed2 = np.all([t1, t2, t3])

    passed3 = True
    for key in fld1.fields.keys():
        if not passed3:
            break
        for j in range(len(fld1.fields[key])):
            if not passed3:
                break
            t1 = np.allclose(fld1.fields[key][j], fld2.fields[key][j])
            t2 = np.allclose(fld1.fields[key][j], fld3.fields[key][j])
            t3 = np.allclose(fld2.fields[key][j], fld3.fields[key][j])
            passed3 = np.all([t1, t2, t3])

      
    assert np.all([passed1, passed2, passed3])

#==============================================================================

def test_read_data_double():

    # Read the original mesh data
    fname = 'examples/data/rbc0.f00001'
    
    ddtype = np.double
    create_connectivity = True

    data1 = preadnek(fname, comm, data_dtype=ddtype)
    msh1 = msh_c(comm, data = data1, create_connectivity=create_connectivity)
    fld1 = field_c(comm, data=data1)
    
    data2 = preadnek(fname, comm)
    x, y, z = get_coordinates_from_hexadata(data2)
    msh2 = msh_c(comm, x = x, y = y, z = z, create_connectivity=create_connectivity)
    fld2 = field_c(comm, data=data2)

    msh3 = msh_c(comm, create_connectivity=create_connectivity)
    fld3 = field_c(comm)
    pynekread(fname, comm, msh = msh3, fld=fld3)

    #compare the objects
    t1 = np.allclose(msh1.x, msh2.x)
    t2 = np.allclose(msh1.y, msh2.y)
    t3 = np.allclose(msh1.z, msh2.z)
    t4 = np.allclose(msh1.x, msh3.x)
    t5 = np.allclose(msh1.y, msh3.y)
    t6 = np.allclose(msh1.z, msh3.z)
    t7 = np.allclose(msh2.x, msh3.x)
    t8 = np.allclose(msh2.y, msh3.y)
    t9 = np.allclose(msh2.z, msh3.z)
    passed1 = np.all([t1, t2, t3, t4, t5, t6, t7, t8, t9])
    
    if create_connectivity:
        t1 = msh1.coord_hash_to_shared_map == msh2.coord_hash_to_shared_map
        t2 = msh1.coord_hash_to_shared_map == msh3.coord_hash_to_shared_map
        t3 = msh2.coord_hash_to_shared_map == msh3.coord_hash_to_shared_map
        passed2 = np.all([t1, t2, t3])

    passed3 = True
    for key in fld1.fields.keys():
        if not passed3:
            break
        for j in range(len(fld1.fields[key])):
            if not passed3:
                break
            t1 = np.allclose(fld1.fields[key][j], fld2.fields[key][j])
            t2 = np.allclose(fld1.fields[key][j], fld3.fields[key][j])
            t3 = np.allclose(fld2.fields[key][j], fld3.fields[key][j])
            passed3 = np.all([t1, t2, t3])

      
    assert np.all([passed1, passed2, passed3])

#==============================================================================

def test_write_data_single():

    # Read the original mesh data
    fname = 'examples/data/rbc0.f00001'
    fname2 = 'examples/data/rbc0.f00004'
    
    ddtype = np.single
    create_connectivity = True

    msh1 = msh_c(comm, create_connectivity=create_connectivity)
    fld1 = field_c(comm)
    pynekread(fname, comm, msh = msh1, fld=fld1)
    pynekwrite(fname2, comm, msh=msh1, fld=fld1)

    data2 = preadnek(fname2, comm, data_dtype=ddtype)
    msh2 = msh_c(comm, data = data2, create_connectivity=create_connectivity)
    fld2 = field_c(comm, data=data2)
    
    #compare the objects
    t1 = np.allclose(msh1.x, msh2.x)
    t2 = np.allclose(msh1.y, msh2.y)
    t3 = np.allclose(msh1.z, msh2.z)
    passed1 = np.all([t1, t2, t3])
    
    if create_connectivity:
        t1 = msh1.coord_hash_to_shared_map == msh2.coord_hash_to_shared_map
        passed2 = np.all([t1])

    passed3 = True
    for key in fld1.fields.keys():
        if not passed3:
            break
        for j in range(len(fld1.fields[key])):
            if not passed3:
                break
            t1 = np.allclose(fld1.fields[key][j], fld2.fields[key][j])
            passed3 = np.all([t1])
      
    assert np.all([passed1, passed2, passed3])

#==============================================================================

def test_write_data_double():

    # Read the original mesh data
    fname = 'examples/data/rbc0.f00001'
    fname2 = 'examples/data/rbc0.f00004'
    
    ddtype = np.double
    create_connectivity = True

    msh1 = msh_c(comm, create_connectivity=create_connectivity)
    fld1 = field_c(comm)
    pynekread(fname, comm, msh = msh1, fld=fld1)
    pynekwrite(fname2, comm, msh=msh1, fld=fld1)

    data2 = preadnek(fname2, comm, data_dtype=ddtype)
    msh2 = msh_c(comm, data = data2, create_connectivity=create_connectivity)
    fld2 = field_c(comm, data=data2)
    
    #compare the objects
    t1 = np.allclose(msh1.x, msh2.x)
    t2 = np.allclose(msh1.y, msh2.y)
    t3 = np.allclose(msh1.z, msh2.z)
    passed1 = np.all([t1, t2, t3])
    
    if create_connectivity:
        t1 = msh1.coord_hash_to_shared_map == msh2.coord_hash_to_shared_map
        passed2 = np.all([t1])

    passed3 = True
    for key in fld1.fields.keys():
        if not passed3:
            break
        for j in range(len(fld1.fields[key])):
            if not passed3:
                break
            t1 = np.allclose(fld1.fields[key][j], fld2.fields[key][j])
            passed3 = np.all([t1])
      
    assert np.all([passed1, passed2, passed3])
