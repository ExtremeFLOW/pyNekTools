---
title: 'PyNekTools: A library for post-processing hexahedral spectral element data.'
tags:
  - Python
  - Computational fluid dynamics
  - Message passing interdace (MPI)
  - High performance computing
authors:
  - name: Adalberto Perez
    orcid: 0000-0001-5204-8549
    affiliation: 1 # (Multiple affiliations must be quoted)
    corresponding: true # (This is how to denote the corresponding author)
  - name: Siavash Toosi
    orcid: 0000-0001-6733-9744
    affiliation: 2
  - name: Stefano Markidis
    orcid: 0000-0003-0639-0639
    affiliation: 3
  - name: Philipp Schlatter
    orcid: 0000-0001-9627-5903
    affiliation: "1, 2"

affiliations:
 - name: FLOW Dept.  Engineering Mechanics, KTH Royal Institute of Technology
   index: 1
 - name: Institute of Fluid Mechanics (LSTM), Friedrich--Alexander--Universität (FAU)
   index: 2
 - name: CST, KTH Royal Institute of Technology
   index: 3
date: 03 January 2018
bibliography: paper.bib

---

# Summary

`PyNekTools` is a Python-based library for post-processing data produced with hexahedral elements in the context of the spectral element method in computational fluid dynamics. It aims to minimize intermediate steps typically needed when analyzing large files. Specifically, the need to use separate codebases (like the solvers themselves) at post-processing. For this effect, we leverage the use of message passing interface (MPI) for distributed computing to perform typical data processing tasks such as differentiation, integration, interpolation, and reduced order modeling, among others from a spectral element mesh. We believe that with `PyNekTools` we provide tools to researchers to accelerate scientific discovery and reduce the entry requirements for the use of advanced methods in computational fluid dynamics.

# Statement of need

The motion of fluids around objects is fundamental for many industrial and natural systems, from aerodynamics and cooling to the behavior of weather systems. The most interesting applications generally exist in the turbulent flow regime, where the fluid is subject to chaotic motions that are characterized by the interactions of eddies of multiple sizes and where increased levels of fluctuations and mixing exist.

A popular method to study these phenomena is to use computers to simulate the physics that governs them. The multi-scale characteristic of turbulence and the high Reynolds numbers (ratio between inertial and viscous forces) that are typical of interest require that the numerical grids are fine enough to capture the motion of the smallest eddies. While this has implied that the computational cost of simulations is high, the advent of graphics processing units (GPUs) has opened the doors to perform simulations that would not have been possible in the past. This increase in capability has made managing the data produced on a typical simulation campaign more challenging. Our work in `PyNekTools` aims to streamline the data management and post-processing of the results obtained from a particular numerical method often used to study turbulent flows.

`PyNekTools` aims to help post-processing data from solvers that use the spectral element method (SEM) by @PATERA1984, which is a high-order variant of the finite element method (FEM). In SEM, the computational domain is divided into a finite set of elements in which a Gauss-Lobatto-Legendre (GLL) grid of a given degree $N$ is embedded. The method is then of order $P = N - 1$ and produces low dissipation and dispersive errors. 

Nek5000 [@nek5000-web-page], written in Fortran 77, is a successful implementation of SEM that has been used for several studies on the field, such as ( cite some ....). In general, the post-processing pipeline has been somewhat complicated, as when the data is needed in the SEM format, for example, to calculate derivatives of velocity fields, the solver itself has been used in a "post-processing" mode. This mode uses the solver and additional Fortran code that needs to be compiled to produce smaller files that can be used in Matlab or Python (via PyMech by @pymech) to perform signal processing, create plots, etc. NekRS by @fischer2021nekrs,  a GPU version of Nek5000, and Neko [@jansson2024; @jansson2023], a modern Fortran implementation of SEM have followed the same approach. 

The motivation behind using the solvers themselves with the data in its raw format is understandable, as these large files need to be processed in parallel due to their sheer size. Still, we believe that the process has become very cumbersome as multiple code bases need to be maintained for post-processing the data. With `PyNekTools` we have brought a solution to this, as we have included all the functionalities that are typically needed from the solvers while ensuring that the codes perform efficiently in parallel while also taking advantage of the rich library ecosystem present in Python.

# Features 

`PyNekTools` relies heavily on MPI for Python by @mpi4py, given that it has been designed from the beginning to work on distributed settings. For computations, we rely on NumPy [@numpy]. It has been extensively tested on data produced by Nek5000 and Neko but, as mentioned before, all the methods work on any SEM-like data structure with hexahedral elements. Among its most relevant features are the following:

* **Parallel IO**: A set of routines to perform distributed IO on Nek5000/Neko files and directly keep the data in memory on NumPy arrays or PyMech data objects.
* **Data compression/streaming**: Through the use of ADIOS2 [@adios2], a set of interfaces is available to perform data compression or to connect Python scripts to running simulations to perform in-situ data processing. 
* **Parallel data interfaces**: A set of objects that aim to facilitate the transfer of messages among processors. Done to ease the use of MPI functions for more inexperienced users.
* **Interpolation**: Routines to perform high-order interpolation from an SEM mesh into any arbitrary query point. A crucial functionality when performing post-processing.
* **Mesh connectivity and partitioning**: Objects to determine the connectivity based on the geometry and mesh repartitioning tools.
* **Calculus**:  Objects to calculate the derivation and integration matrices based on the geometry, which allows to perform calculus operations on the spectral element mesh.
* **Reduced-order modeling**: Objects to perform parallel and streaming proper orthogonal decomposition (POD).

We note that all of these functionalities are supported by examples in the software repository.


# Acknowledgements

This work is partially funded by the “Adaptive multi-tier intelligent data manager for Exascale (ADMIRE)” project, which is funded by the European Union's Horizon 2020 JTI-EuroHPC research and innovation program under grant Agreement number: 956748. Computations for testing were enabled by resources provided by the Swedish National Infrastructure for Computing (SNIC), partially funded by the Swedish Research Council through grant agreement no. 2018-05973.

# References
