"This module contains the class router"

import numpy as np

NoneType = type(None)


class Router:
    """
    This class can be used to handle communication between ranks in a MPI communicator.

    With this one can send and recieve data to any rank that is specified in the destination list.

    Parameters
    ----------
    comm : MPI communicator
        The MPI communicator that is used for the communication.

    Attributes
    ----------
    comm : MPI communicator
        The MPI communicator that is used for the communication.

    destination_count : ndarray
        Specifies a buffer to see how many points I send to each rank

    source_count : ndarray
        Specifies a buffer to see how many points I recieve from each rank

    Notes
    -----
    The data is always flattened before sending and recieved data is always flattened.
    The user must reshape the data after recieving it.

    Examples
    --------
    To initialize simply use the communicator

    >>> from mpi4py import MPI
    >>> from pynektools.comm.router import Router
    >>> comm = MPI.COMM_WORLD
    >>> rt = Router(comm)
    """

    def __init__(self, comm):

        self.comm = comm
        # Specifies a buffer to see how many points I send to each rank
        self.destination_count = np.zeros((comm.Get_size()), dtype=np.ulong)
        # Specifies a buffer to see how many points I recieve from each rank
        self.source_count = np.zeros((comm.Get_size()), dtype=np.ulong)

    def route_data(self, keyword, **kwargs):
        """
        Moves data between ranks in the specified patthern.

        This method wraps others in this class.

        Parameters
        ----------
        keyword : str
            The keyword that specifies the pattern of the data movement.
            current options are:
                - distribute: sends data to specified destinations. 
                  and recieves data from whoever sent.
                - gather: gathers data from all processes to the root process.
                - scatter: scatters data from the root process to all other processes.
        kwargs : dict
            The arguments that are passed to the specified pattern.
            One needs to check the pattern documentation for the required arguments.
            For each scenario

        Returns
        -------
        tuple
            The output of the specified pattern.
        """

        router_factory = {
            "distribute": self.send_recv,
            "gather": self.gather_in_root,
            "scatter": self.scatter_from_root,
        }

        if keyword not in router_factory:
            raise ValueError(f"Method '{method_keyword}' not recognized.")

        return router_factory[keyword](**kwargs)

    def send_recv(self, destination=None, data=None, dtype=None, tag=None):
        """
        Sends data to specified destinations and recieves data from whoever sent.

        Typically, when a rank needs to send some data, it also needs to recieve some.
        In this method this is done by using non blocking communication.
        We note, however, that when the method returns, the data is already recieved.

        Parameters
        ----------
        destination : list
            A list with the rank ids that the data should be sent to.
        data : list or ndarray
            The data that will be sent. If it is a list, 
            the data will be sent to the corresponding destination.
            if the data is an ndarray, the same data will be sent to all destinations.
        dtype : dtype
            The data type of the data that is sent.
        tag : int
            Tag used to identify the messages.

        Returns
        -------
        sources : list
            A list with the rank ids that the data was recieved from.
        recvbuff : list
            A list with the recieved data. The data is stored in the same order as the sources.

        Examples
        --------
        To send and recieve data between ranks, do the following:

        local_data = np.zeros(((rank+1)*10, 3), dtype=np.double)

        >>> rt = Router(comm)
        >>> destination = [rank + 1, rank + 2]
        >>> for i, dest in enumerate(destination):
        >>>     if dest >= size:
        >>>         destination[i] = dest - size
        >>> sources, recvbf = rt.send_recv(destination = destination, 
        >>>                   data = local_data, dtype=np.double, tag = 0)
        >>> for i in range(0, len(recvbf)):
        >>>     recvbf[i] = recvbf[i].reshape((-1, 3))
        """

        # ===========================
        # Fill the destination count
        # ===========================

        self.destination_count[:] = 0
        # Check if the data to send is a list
        if isinstance(data, list):
            # If it is a list, match each destination with its data
            for dest_ind, dest in enumerate(destination):
                self.destination_count[dest] = data[dest_ind].size
        else:
            # If it is not a list, send the same data to all destinations
            self.destination_count[destination] = data.size

        # ======================
        # Fill the source count
        # ======================
        self.source_count[:] = 0
        self.comm.Alltoall(sendbuf=self.destination_count, recvbuf=self.source_count)
        sources = np.where(self.source_count != 0)[0]

        # =========================
        # Allocate recieve buffers
        # =========================
        recvbuff = [
            np.zeros((self.source_count[source]), dtype=dtype) for source in sources
        ]

        # =========================
        # Send and recieve the data
        # =========================

        ## set up recieve request
        recvreq = [
            self.comm.Irecv(recvbuff[source_ind], source=source, tag=tag)
            for source_ind, source in enumerate(sources)
        ]

        ## Set up and complete the send request
        if isinstance(data, list):
            # If it is a list, send matching position to destination
            for dest_ind, dest in enumerate(destination):
                sendreq = self.comm.Isend(data[dest_ind].flatten(), dest=dest, tag=tag)
                sendreq.wait()
        else:
            # If it is not a list, send the same data to all destinations
            for dest_ind, dest in enumerate(destination):
                sendreq = self.comm.Isend(data.flatten(), dest=dest, tag=tag)
                sendreq.wait()

        ## complete the recieve request
        for req in recvreq:
            req.wait()

        return sources, recvbuff

    def gather_in_root(self, data=None, root=0, dtype=None):
        """
        Gathers data from all processes to the root process.

        This is a wrapper to the MPI Gatherv function.

        Parameters
        ----------
        data : ndarray
            Data that is gathered in the root process.
        root : int
            The rank that will gather the data.
        dtype : dtype
            The data type of the data that is gathered.

        Returns
        -------
        recvbuf : ndarray
            The gathered data in the root process.
            The data is always recieved flattened. User must reshape it.
        sendcounts : ndarray
            The number of data that was sent from each rank.

        Examples
        --------
        To gather data from all ranks to the root rank, do the following:

        >>> rt = Router(comm)
        >>> local_data = np.ones(((rank+1)*10, 3), dtype=np.double)*rank
        >>> recvbf, sendcounts = rt.gather_in_root(data = local_data, 
        >>>                      root = 0, dtype = np.double)
        """

        rank = self.comm.Get_rank()

        # Collect local array sizes using the high-level mpi4py gather
        sendcounts = np.array(self.comm.allgather(data.size), dtype=np.ulong)

        if rank == root:
            # print("sendcounts: {}, total: {}".format(sendcounts, sum(sendcounts)))
            recvbuf = np.empty(sum(sendcounts), dtype=dtype)
        else:
            recvbuf = None

        self.comm.Gatherv(sendbuf=data, recvbuf=(recvbuf, sendcounts), root=root)

        return recvbuf, sendcounts

    def scatter_from_root(self, data=None, sendcounts=None, root=0, dtype=None):
        """
        Scatters data from the root process to all other processes.

        This is a wrapper to the MPI Scatterv function.

        Parameters
        ----------
        data : ndarray
            The data that is scattered to all processes.
        sendcounts : ndarray, optional
            The number of data that is sent to each process. 
            If not specified, the data is divided equally among all processes.
        root : int
            The rank that will scatter
        dtype : dtype
            The data type of the data that is scattered.

        Returns
        -------
        recvbuf : ndarray
            The scattered data in the current process. 
            The data is always recieved flattened. User must reshape it.

        Examples
        --------
        To scatter data from the root rank, do the following:

        >>> rt = Router(comm)
        >>> recvbf = rt.scatter_from_root(data = recvbf, 
                        sendcounts=sendcounts, root = 0, dtype = np.double)
        >>> recvbf = recvbf.reshape((-1, 3))

        Note tha the sendcounts are just a ndarray of size comm.Get_size() 
        with the number of data that is sent to each rank.
        """

        if self.comm.Get_rank() == root:
            if isinstance(sendcounts, NoneType):
                # Divide the data equally among all processes
                sendcounts = np.zeros((self.comm.Get_size()), dtype=np.ulong)
                sendcounts[:] = data.size // self.comm.Get_size()

            sendbuf = data.flatten()
        else:
            sendbuf = None

        rank = self.comm.Get_rank()

        recvbuf = np.ones(sendcounts[rank], dtype=dtype) * -100

        self.comm.Scatterv(sendbuf=(sendbuf, sendcounts), recvbuf=recvbuf, root=root)

        return recvbuf