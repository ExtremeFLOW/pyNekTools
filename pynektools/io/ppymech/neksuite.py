""" Module that wraps the parallel IO calls and put data in the pymech format"""

import sys
from mpi4py import MPI
import numpy as np
from pymech.neksuite.field import read_header
from pymech.core import HexaData
from pymech.neksuite.field import Header
from .parallel_io import (
    fld_file_read_vector_field,
    fld_file_read_field,
    fld_file_write_vector_field,
    fld_file_write_field,
    fld_file_write_vector_metadata,
    fld_file_write_metadata,
)


class IoHelper:
    """
    Class to contain general information of the file and some buffers
    
    This is used primarly to pass data around in writing routines/reading routines.

    :meta private:
    """

    def __init__(self, h):

        self.fld_data_size = h.wdsz
        self.lx = h.orders[0]
        self.ly = h.orders[1]
        self.lz = h.orders[2]
        self.lxyz = self.lx * self.ly * self.lz
        self.glb_nelv = h.nb_elems
        self.time = h.time
        self.istep = h.istep
        self.variables = h.variables
        self.realtype = h.realtype
        self.gdim = h.nb_dims
        self.pos_variables = h.nb_vars[0]
        self.vel_variables = h.nb_vars[1]
        self.pres_variables = h.nb_vars[2]
        self.temp_variables = h.nb_vars[3]
        self.scalar_variables = h.nb_vars[4]

        # Allocate optional variables
        self.nelv = None
        self.n = None
        self.offset_el = None

        self.m = None
        self.pe_rank = None
        self.pe_size = None
        self.l = None
        self.r = None
        self.ip = None

        self.tmp_sp_vector = None
        self.tmp_dp_vector = None
        self.tmp_sp_field = None
        self.tmp_dp_field = None

    def element_mapping(self, comm):
        """
        Maps the number of elements each processor has equally.

        Not used anymore.

        Parameters
        ----------
        comm : Comm
            MPI communicator
            
        Returns
        -------

        """
        rank = comm.Get_rank()
        size = comm.Get_size()

        # Divide the global number of elements equally
        self.nelv = int(self.glb_nelv / size)
        self.n = self.lxyz * self.nelv
        self.offset_el = rank * self.nelv

    def element_mapping_load_balanced_linear(self, comm):
        """Maps the number of elements each processor has
        in a linearly load balanced manner

        Parameters
        ----------
        comm :
            

        Returns
        -------

        """
        self.m = self.glb_nelv
        self.pe_rank = comm.Get_rank()
        self.pe_size = comm.Get_size()
        self.l = np.floor(np.double(self.m) / np.double(self.pe_size))
        self.r = np.mod(self.m, self.pe_size)
        self.ip = np.floor(
            (
                np.double(self.m)
                + np.double(self.pe_size)
                - np.double(self.pe_rank)
                - np.double(1)
            )
            / np.double(self.pe_size)
        )

        self.nelv = int(self.ip)
        self.offset_el = int(self.pe_rank * self.l + min(self.pe_rank, self.r))
        self.n = self.lxyz * self.nelv

    def element_mapping_from_parallel_hexadata(self, comm):
        """Find the element mapping when the input data was already parallel and divided equally

        Parameters
        ----------
        comm :
            

        Returns
        -------

        """
        rank = comm.Get_rank()
        size = comm.Get_size()

        # io helper assume that the nel in header is the global one
        # So we have to correct if the header is initialized from a parallel hexadata object
        self.nelv = self.glb_nelv
        self.n = self.lxyz * self.nelv

        # Later do a running sum
        self.offset_el = rank * self.nelv

        # Later on, update this to an mpi reduction,
        # now we assume that all elements are divided equally
        self.glb_nelv = self.nelv * size

    def element_mapping_from_parallel_hexadata_mpi(self, comm):
        """Find the element mapping when the input data was already parallel and divided
        in a linearly load balanced manner

        Parameters
        ----------
        comm :
            

        Returns
        -------

        """

        # io helper assume that the nel in header is the global one
        # So we have to correct if the header is initialized from a parallel hexadata object
        self.nelv = self.glb_nelv
        self.n = self.lxyz * self.nelv

        # do a running sum
        sendbuf = np.ones((1), np.intc) * self.nelv
        recvbuf = np.zeros((1), np.intc)
        comm.Scan(sendbuf, recvbuf)
        self.offset_el = recvbuf[0] - self.nelv

        # Later on, update this to an mpi reduction,
        sendbuf = np.ones((1), np.intc) * self.nelv
        recvbuf = np.zeros((1), np.intc)
        comm.Allreduce(sendbuf, recvbuf)
        self.glb_nelv = recvbuf[0]

    def allocate_temporal_arrays(self):
        """'Allocate temporal arrays for reading and writing fields"""
        self.tmp_sp_vector = np.zeros(self.gdim * self.n, dtype=np.single)
        self.tmp_dp_vector = np.zeros(self.gdim * self.n, dtype=np.double)
        self.tmp_sp_field = np.zeros(self.n, dtype=np.single)
        self.tmp_dp_field = np.zeros(self.n, dtype=np.double)


def preadnek(filename, comm, data_dtype="float64"):
    """
    Read and fld file and return a pymech hexadata object (Parallel).

    Main function for readinf nek type fld filed.

    Parameters
    ----------
    filename : str
        The filename of the fld file.
        
    comm : Comm
        MPI communicator.
        
    data_dtype : str
        The data type of the data in the file. (Default value = "float64").

    Returns
    -------
    HexaData
        The data read from the file in a pymech hexadata object.
    
    Examples
    --------
    >>> from mpi4py import MPI
    >>> from pynektools.io.ppymech.neksuite import preadnek
    >>> comm = MPI.COMM_WORLD
    >>> data = preadnek('field00001.fld', comm)
    """

    mpi_int_size = MPI.INT.Get_size()
    mpi_real_size = MPI.REAL.Get_size()
    # mpi_double_size = MPI.DOUBLE.Get_size()
    mpi_character_size = MPI.CHARACTER.Get_size()

    # Read the header
    header = read_header(filename)

    # Initialize the io helper
    ioh = IoHelper(header)

    # Find the appropiate partitioning of the file
    # ioh.element_mapping(comm)
    ioh.element_mapping_load_balanced_linear(comm)

    # allocate temporal arrays
    ioh.allocate_temporal_arrays()

    # Create the pymech hexadata object
    data = HexaData(
        header.nb_dims, ioh.nelv, header.orders, header.nb_vars, 0, dtype=data_dtype
    )
    data.time = header.time
    data.istep = header.istep
    data.wdsz = header.wdsz
    data.endian = sys.byteorder

    # Open the file
    fh = MPI.File.Open(comm, filename, MPI.MODE_RDONLY)

    # Read the test pattern
    mpi_offset = 132 * mpi_character_size
    test_pattern = np.zeros(1, dtype=np.single)
    fh.Read_at_all(mpi_offset, test_pattern, status=None)

    # Read the indices?
    mpi_offset += mpi_real_size
    idx = np.zeros(ioh.nelv, dtype=np.intc)
    byte_offset = mpi_offset + ioh.offset_el * mpi_int_size
    fh.Read_at_all(byte_offset, idx, status=None)
    data.elmap = idx
    mpi_offset += ioh.glb_nelv * mpi_int_size

    # Read the coordinates
    if ioh.pos_variables > 0:
        byte_offset = (
            mpi_offset + ioh.offset_el * ioh.gdim * ioh.lxyz * ioh.fld_data_size
        )
        x, y, z = fld_file_read_vector_field(fh, byte_offset, ioh)
        for e in range(0, ioh.nelv):
            data.elem[e].pos[0, :, :, :] = x[e, :, :, :]
            data.elem[e].pos[1, :, :, :] = y[e, :, :, :]
            data.elem[e].pos[2, :, :, :] = z[e, :, :, :]
        mpi_offset += ioh.glb_nelv * ioh.gdim * ioh.lxyz * ioh.fld_data_size

    # Read the velocity
    if ioh.vel_variables > 0:
        byte_offset = (
            mpi_offset + ioh.offset_el * ioh.gdim * ioh.lxyz * ioh.fld_data_size
        )
        u, v, w = fld_file_read_vector_field(fh, byte_offset, ioh)
        for e in range(0, ioh.nelv):
            data.elem[e].vel[0, :, :, :] = u[e, :, :, :]
            data.elem[e].vel[1, :, :, :] = v[e, :, :, :]
            data.elem[e].vel[2, :, :, :] = w[e, :, :, :]
        mpi_offset += ioh.glb_nelv * ioh.gdim * ioh.lxyz * ioh.fld_data_size

    # Read pressure
    if ioh.pres_variables > 0:
        byte_offset = mpi_offset + ioh.offset_el * 1 * ioh.lxyz * ioh.fld_data_size
        p = fld_file_read_field(fh, byte_offset, ioh)
        for e in range(0, ioh.nelv):
            data.elem[e].pres[0, :, :, :] = p[e, :, :, :]
        mpi_offset += ioh.glb_nelv * 1 * ioh.lxyz * ioh.fld_data_size

    # Read temperature
    if ioh.temp_variables > 0:
        byte_offset = mpi_offset + ioh.offset_el * 1 * ioh.lxyz * ioh.fld_data_size
        t = fld_file_read_field(fh, byte_offset, ioh)
        for e in range(0, ioh.nelv):
            data.elem[e].temp[0, :, :, :] = t[e, :, :, :]
        mpi_offset += ioh.glb_nelv * 1 * ioh.lxyz * ioh.fld_data_size

    # Read scalars
    for var in range(0, ioh.scalar_variables):
        byte_offset = mpi_offset + ioh.offset_el * 1 * ioh.lxyz * ioh.fld_data_size
        s = fld_file_read_field(fh, byte_offset, ioh)
        for e in range(0, ioh.nelv):
            data.elem[e].scal[var, :, :, :] = s[e, :, :, :]
        mpi_offset += ioh.glb_nelv * 1 * ioh.lxyz * ioh.fld_data_size

    fh.Close()

    return data


def pwritenek(filename, data, comm):
    """
    Write and fld file and from a pymech hexadata object (Parallel).

    Main function to write fld files.

    Parameters
    ----------
    filename : str
        The filename of the fld file.
        
    data : HexaData
        The data to write to the file.
        
    comm : Comm
        MPI communicator.
        
    Examples
    --------
    Assuming you have a hexadata object already:

    >>> from pynektools.io.ppymech.neksuite import pwritenek
    >>> pwritenek('field00001.fld', data, comm)
    """

    mpi_int_size = MPI.INT.Get_size()
    mpi_real_size = MPI.REAL.Get_size()
    # mpi_double_size = MPI.DOUBLE.Get_size()
    mpi_character_size = MPI.CHARACTER.Get_size()

    # instance a dummy header
    dh = Header(
        data.wdsz,
        data.lr1,
        data.nel,
        data.nel,
        data.time,
        data.istep,
        fid=0,
        nb_files=1,
        nb_vars=data.var,
    )

    # instance the parallel io helper with the dummy header
    ioh = IoHelper(dh)

    # Get actual element mapping from the parallel hexadata
    # We need this since what we have in data.nel is the
    # local number of elements, not the global one
    # ioh.element_mapping_from_parallel_hexadata(comm)
    ioh.element_mapping_from_parallel_hexadata_mpi(comm)

    # allocate temporal arrays
    ioh.allocate_temporal_arrays()

    # instance actual header
    h = Header(
        data.wdsz,
        data.lr1,
        ioh.glb_nelv,
        ioh.glb_nelv,
        data.time,
        data.istep,
        fid=0,
        nb_files=1,
        nb_vars=data.var,
    )

    # Open the file
    amode = MPI.MODE_WRONLY | MPI.MODE_CREATE
    fh = MPI.File.Open(comm, filename, amode)

    # Write the header
    mpi_offset = 0
    fh.Write_all(h.as_bytestring())
    mpi_offset += 132 * mpi_character_size

    # write test pattern
    test_pattern = np.zeros(1, dtype=np.single)
    test_pattern[0] = 6.54321
    fh.Write_all(test_pattern)
    mpi_offset += mpi_real_size

    # write element mapping
    idx = np.zeros(ioh.nelv, dtype=np.intc)
    for i in range(0, data.nel):
        idx[i] = data.elmap[i]
    byte_offset = mpi_offset + ioh.offset_el * mpi_int_size
    fh.Write_at_all(byte_offset, idx, status=None)
    mpi_offset += ioh.glb_nelv * mpi_int_size

    # Write the coordinates
    if ioh.pos_variables > 0:
        x = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
        y = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
        z = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
        for e in range(0, ioh.nelv):
            x[e, :, :, :] = data.elem[e].pos[0, :, :, :]
            y[e, :, :, :] = data.elem[e].pos[1, :, :, :]
            z[e, :, :, :] = data.elem[e].pos[2, :, :, :]
        byte_offset = (
            mpi_offset + ioh.offset_el * ioh.gdim * ioh.lxyz * ioh.fld_data_size
        )
        fld_file_write_vector_field(fh, byte_offset, x, y, z, ioh)
        mpi_offset += ioh.glb_nelv * ioh.gdim * ioh.lxyz * ioh.fld_data_size

    # Write the velocity
    if ioh.vel_variables > 0:
        u = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
        v = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
        w = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
        for e in range(0, ioh.nelv):
            u[e, :, :, :] = data.elem[e].vel[0, :, :, :]
            v[e, :, :, :] = data.elem[e].vel[1, :, :, :]
            w[e, :, :, :] = data.elem[e].vel[2, :, :, :]
        byte_offset = (
            mpi_offset + ioh.offset_el * ioh.gdim * ioh.lxyz * ioh.fld_data_size
        )
        fld_file_write_vector_field(fh, byte_offset, u, v, w, ioh)
        mpi_offset += ioh.glb_nelv * ioh.gdim * ioh.lxyz * ioh.fld_data_size

    # Write pressure
    if ioh.pres_variables > 0:
        p = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
        for e in range(0, ioh.nelv):
            p[e, :, :, :] = data.elem[e].pres[0, :, :, :]
        byte_offset = mpi_offset + ioh.offset_el * 1 * ioh.lxyz * ioh.fld_data_size
        fld_file_write_field(fh, byte_offset, p, ioh)
        mpi_offset += ioh.glb_nelv * 1 * ioh.lxyz * ioh.fld_data_size

    # Write Temperature
    if ioh.temp_variables > 0:
        t = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
        for e in range(0, ioh.nelv):
            t[e, :, :, :] = data.elem[e].temp[0, :, :, :]
        byte_offset = mpi_offset + ioh.offset_el * 1 * ioh.lxyz * ioh.fld_data_size
        fld_file_write_field(fh, byte_offset, t, ioh)
        mpi_offset += ioh.glb_nelv * 1 * ioh.lxyz * ioh.fld_data_size

    # Write scalars
    for var in range(0, ioh.scalar_variables):
        s = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
        for e in range(0, ioh.nelv):
            s[e, :, :, :] = data.elem[e].scal[var, :, :, :]
        byte_offset = mpi_offset + ioh.offset_el * 1 * ioh.lxyz * ioh.fld_data_size
        fld_file_write_field(fh, byte_offset, s, ioh)
        mpi_offset += ioh.glb_nelv * 1 * ioh.lxyz * ioh.fld_data_size

    # ================== Metadata
    if ioh.gdim > 2:

        # Write the coordinates
        if ioh.pos_variables > 0:
            x = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
            y = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
            z = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
            for e in range(0, ioh.nelv):
                x[e, :, :, :] = data.elem[e].pos[0, :, :, :]
                y[e, :, :, :] = data.elem[e].pos[1, :, :, :]
                z[e, :, :, :] = data.elem[e].pos[2, :, :, :]
            byte_offset = mpi_offset + ioh.offset_el * ioh.gdim * 2 * ioh.fld_data_size
            fld_file_write_vector_metadata(fh, byte_offset, x, y, z, ioh)
            mpi_offset += ioh.glb_nelv * ioh.gdim * 2 * ioh.fld_data_size

        # Write the velocity
        if ioh.vel_variables > 0:
            u = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
            v = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
            w = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
            for e in range(0, ioh.nelv):
                u[e, :, :, :] = data.elem[e].vel[0, :, :, :]
                v[e, :, :, :] = data.elem[e].vel[1, :, :, :]
                w[e, :, :, :] = data.elem[e].vel[2, :, :, :]
            byte_offset = mpi_offset + ioh.offset_el * ioh.gdim * 2 * ioh.fld_data_size
            fld_file_write_vector_metadata(fh, byte_offset, u, v, w, ioh)
            mpi_offset += ioh.glb_nelv * ioh.gdim * 2 * ioh.fld_data_size

        # Write pressure
        if ioh.pres_variables > 0:
            p = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
            for e in range(0, ioh.nelv):
                p[e, :, :, :] = data.elem[e].pres[0, :, :, :]
            byte_offset = mpi_offset + ioh.offset_el * 1 * 2 * ioh.fld_data_size
            fld_file_write_metadata(fh, byte_offset, p, ioh)
            mpi_offset += ioh.glb_nelv * 1 * 2 * ioh.fld_data_size

        # Write Temperature
        if ioh.temp_variables > 0:
            t = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
            for e in range(0, ioh.nelv):
                t[e, :, :, :] = data.elem[e].temp[0, :, :, :]
            byte_offset = mpi_offset + ioh.offset_el * 1 * 2 * ioh.fld_data_size
            fld_file_write_metadata(fh, byte_offset, t, ioh)
            mpi_offset += ioh.glb_nelv * 1 * 2 * ioh.fld_data_size

        # Write scalars
        for var in range(0, ioh.scalar_variables):
            s = np.zeros((ioh.nelv, ioh.lz, ioh.ly, ioh.lx), dtype=np.double)
            for e in range(0, ioh.nelv):
                s[e, :, :, :] = data.elem[e].scal[var, :, :, :]
            byte_offset = mpi_offset + ioh.offset_el * 1 * 2 * ioh.fld_data_size
            fld_file_write_metadata(fh, byte_offset, s, ioh)
            mpi_offset += ioh.glb_nelv * 1 * 2 * ioh.fld_data_size

    fh.Close()

    return