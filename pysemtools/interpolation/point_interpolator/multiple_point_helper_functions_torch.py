""" helper functions for multiple point interpolation using pytorch"""

import numpy as np
import torch

# from .multiple_point_helper_functions_numpy import GLC_pwts, GLL_pwts

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def apply_operators_3d(dr, ds, dt, x):
    """

    This function applies operators the same way as they are applied in NEK5000

    The only difference is that it is reversed, as this is
    python and we decided to leave that arrays as is

    this function is more readable in sem.py, where tensor optimization is not used.

    """

    dshape = dr.shape
    xshape = x.shape
    xsize = xshape[2] * xshape[3]

    # Reshape the operator in the r direction
    drt = dr.permute(
        0, 1, 3, 2
    )  # This is just the transpose of the operator, leaving the first dimensions unaltered
    drt_s0 = drt.shape[2]
    # drt_s1 = drt.shape[3]
    # Reshape the field to be consistent
    xreshape = x.reshape((xshape[0], xshape[1], int(xsize / drt_s0), drt_s0))
    # Apply the operator with einsum
    temp = torch.einsum("ijkl,ijlm->ijkm", xreshape, drt)

    # Reshape the arrays as needed
    tempsize = temp.shape[2] * temp.shape[3]
    ds_s0 = ds.shape[2]
    ds_s1 = ds.shape[3]

    # Apply in s direction
    temp = temp.reshape(
        (xshape[0], xshape[1], ds_s1, ds_s1, int(tempsize / (ds_s1**2)))
    )
    temp = torch.einsum(
        "ijklm,ijkmn->ijkln", ds.reshape((dshape[0], dshape[1], 1, ds_s0, ds_s1)), temp
    )

    # Reshape the arrays as needed
    tempsize = temp.shape[2] * temp.shape[3] * temp.shape[4]
    # dt_s0 = dt.shape[2]
    dt_s1 = dt.shape[3]

    # Apply in t direction

    temp = temp.reshape((xshape[0], xshape[1], dt_s1, int(tempsize / dt_s1)))
    temp = torch.einsum("ijkl,ijlm->ijkm", dt, temp)

    # Reshape to proper size
    tempshape = temp.shape
    tempsize = temp.shape[2] * temp.shape[3]

    return temp.reshape((tempshape[0], tempshape[1], tempsize, 1))


def legendre_basis_at_xtest(n, xtest):
    """
    The legendre basis depends on the element order and the points

    """
    m = xtest.shape[0]
    m2 = xtest.shape[1]

    # Allocate space
    leg = torch.zeros((m, m2, n, 1), dtype=torch.float64, device=device)

    # First row is filled with 1 according to recursive formula
    leg[:, :, 0, 0] = 1.0

    # Second row is filled with x according to recursive formula
    leg[:, :, 1, 0] = xtest[:, :, 0, 0]

    # Apply the recursive formula for all x_i
    # look for recursive formula here if you want to verify
    # https://en.wikipedia.org/wiki/Legendre_polynomials

    ## Here we perform the extra step of cloning the tensor to not have trouble
    ## with inplace modifications in case we want to use autograd for xtest.
    for j in range(1, n - 1):
        leg_j_p1 = (
            (2 * j + 1) * xtest[:, :, 0, 0] * leg[:, :, j, 0] - j * leg[:, :, j - 1, 0]
        ) / (j + 1)
        leg = leg.clone()
        leg[:, :, j + 1, 0] = leg_j_p1

    return leg


def legendre_basis_derivative_at_xtest(legtest, xtest):
    """

    This is a slow implementaiton with a slow recursion. It does not need
    special treatmet at the boundary

    """

    ## Now find the derivative matrix D_N,ij=(dpi_j/dxi)_at_xi=xi_i
    ##https://en.wikipedia.org/wiki/Legendre_polynomials

    m = legtest.shape[0]
    m2 = xtest.shape[1]
    n = legtest.shape[2]

    # Allocate space
    d_n = torch.zeros((m, m2, n, 1), dtype=torch.float64, device=device)

    # For first polynomial: derivatice is 0
    d_n[:, :, 0, 0] = torch.zeros((m, m2, 1, 1), dtype=torch.float64, device=device)[
        :, :, 0, 0
    ]
    # For second polynomial: derivatice is 1
    d_n[:, :, 1, 0] = torch.ones((m, m2, 1, 1), dtype=torch.float64, device=device)[
        :, :, 0, 0
    ]

    for j in range(1, n - 1):
        for p in range(j, 0 - 1, -2):
            d_n[:, :, j + 1, 0] += (
                2 * legtest[:, :, p, 0] / (np.sqrt(2 / (2 * p + 1)) ** 2)
            )

    return d_n


def lag_interp_matrix_at_xtest(x, xtest):
    """

    Lagrange interpolation in 1D space

    """

    n = x.shape[0]
    m = xtest.shape[0]
    m2 = xtest.shape[1]
    # k=np.arange(n)

    # Allocate space
    lk = torch.zeros((m, m2, n, 1), dtype=torch.float64, device=device)

    for k_ in range(0, n):
        prod_ = torch.ones((m, m2, 1, 1), dtype=torch.float64, device=device)
        for j in range(n):
            if j != k_:
                prod_ = (
                    prod_
                    * (xtest[:, :, :, :] - x[j, :, :, :])
                    / (x[k_, :, :, :] - x[j, :, :, :])
                )
        lk[:, :, k_, :] = prod_[:, :, 0, :]

    return lk
