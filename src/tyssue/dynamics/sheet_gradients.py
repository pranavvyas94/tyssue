"""
Base gradients for sheet like geometries
"""

import numpy as np
import pandas as pd

from ..utils.utils import _to_3d


def height_grad(sheet):

    r_to_rho = sheet.jv_df[sheet.coords] / _to_3d(sheet.jv_df['rho'])

    ### Cyl. geom
    r_to_rho['z'] = 0.

    r_to_rho = sheet.upcast_srce(df=r_to_rho)
    r_to_rho.columns = sheet.coords
    return r_to_rho


def area_grad(sheet):

    coords = sheet.coords
    ncoords = sheet.ncoords
    inv_area = sheet.je_df.eval('1 / (4 * sub_area)')

    cell_pos = sheet.upcast_cell(sheet.cell_df[coords])
    srce_pos = sheet.upcast_srce(sheet.jv_df[coords])
    trgt_pos = sheet.upcast_trgt(sheet.jv_df[coords])

    r_ak = srce_pos - cell_pos
    r_aj = trgt_pos - cell_pos

    grad_a_srce = _to_3d(inv_area) * np.cross(r_aj, sheet.je_df[ncoords])
    grad_a_trgt = _to_3d(inv_area) * np.cross(sheet.je_df[ncoords], r_ak)
    return (pd.DataFrame(grad_a_srce,
                         index=sheet.je_df.index,
                         columns=sheet.coords),
            pd.DataFrame(grad_a_trgt, index=sheet.je_df.index,
                         columns=sheet.coords))
