import pandas as pd
import numpy as np
from ..config.json_parser import load_default

import logging
log = logging.getLogger(name=__name__)

def make_df(index, spec):
    '''

    '''
    dtypes = np.dtype([(name, type(val))
                       for name, val in spec.items()])
    N = len(index)
    arr = np.empty(N, dtype=dtypes)
    df = pd.DataFrame.from_records(arr, index=index)
    for name, val in spec.items():
        df[name] = val
    return df


"""

Hexagonal grids
---------------

"""

def hexa_grid2d(nx, ny, distx, disty, noise=None):
    """Creates an hexagonal grid of points
    """
    cy, cx = np.mgrid[0:ny, 0:nx]
    cx = cx.astype(np.float)
    cy = cy.astype(np.float)
    cx[::2, :] += 0.5

    centers = np.vstack([cx.flatten(),
                         cy.flatten()]).astype(np.float).T
    centers[:, 0] *= distx
    centers[:, 1] *= disty
    if noise is not None:
        pos_noise = np.random.normal(scale=noise, size=centers.shape)
        centers += pos_noise
    return centers


def hexa_grid3d(nx, ny, nz, distx=1., disty=1., distz=1., noise=None):
    """Creates an hexagonal grid of points
    """
    cz, cy, cx = np.mgrid[0:nz, 0:ny, 0:nx]
    cx = cx.astype(np.float)
    cy = cy.astype(np.float)
    cz = cz.astype(np.float)
    cx[:, ::2] += 0.5
    cy[::2, :] += 0.5
    cy *= np.sqrt(3) / 2
    cz *= np.sqrt(3) / 2

    centers = np.vstack([cx.flatten(),
                         cy.flatten(),
                         cz.flatten()]).T
    centers[:, 0] *= distx
    centers[:, 1] *= disty
    centers[:, 2] *= distz
    if noise is not None:
        pos_noise = np.random.normal(scale=noise, size=centers.shape)
        centers += pos_noise
    return centers


"""
From Voronoi tessalations
-------------------------
"""

def from_3d_voronoi(voro):
    """
    """
    specs3d = load_default('geometry', 'bulk')

    el_idx = []

    for f_idx, (rv, rp) in enumerate(
        zip(voro.ridge_vertices,
            voro.ridge_points)):

        if -1 in rv:
            continue
        face_verts = voro.vertices[rv]
        f_center = face_verts.mean(axis=0)
        c0 = voro.points[rp[0]]
        ctof = f_center - c0

        for rv0, rv1 in zip(rv, np.roll(rv, 1, axis=0)):
            fv0 = voro.vertices[rv0]
            fv1 = voro.vertices[rv1]
            edge_v = fv1 - fv0
            fto0 = fv0 - f_center
            normal = np.cross(fto0, edge_v)
            dotp = np.dot(ctof, normal)
            if np.sign(dotp) > 0:
                el_idx.append([rv0, rv1, f_idx, rp[0]])
                el_idx.append([rv1, rv0, f_idx, rp[1]])
            else:
                el_idx.append([rv1, rv0, f_idx, rp[0]])
                el_idx.append([rv0, rv1, f_idx, rp[1]])

    el_idx = np.array(el_idx)

    coords = ['x', 'y', 'z']
    edge_idx = pd.Index(range(el_idx.shape[0]), name='edge')
    edge_df = make_df(edge_idx,
                    specs3d['edge'])

    for i, elem in enumerate(['srce', 'trgt', 'face', 'cell']):
        edge_df[elem] = el_idx[:, i]

    vert_idx = pd.Index(range(voro.vertices.shape[0]), name='vert')
    vert_df = make_df(vert_idx,
                    specs3d['vert'])
    vert_df[coords] = voro.vertices

    cell_idx = pd.Index(range(voro.points.shape[0]), name='cell')
    cell_df = make_df(cell_idx,
                      specs3d['cell'])
    cell_df[coords] = voro.points

    nfaces = len(voro.ridge_vertices)
    face_idx = pd.Index(np.arange(nfaces), name='face')
    face_df = make_df(face_idx, specs3d['face'])
    edge_df.sort_values(by='cell', inplace=True)

    datasets= {
        'vert': vert_df,
        'edge': edge_df,
        'face': face_df,
        'cell': cell_df,
        }
    return datasets


def from_2d_voronoi(voro, specs=None):
    """
    """
    if specs is None:
        specs = load_default('geometry', 'planar')

    el_idx = []

    for rv, rp in zip(voro.ridge_vertices,
                      voro.ridge_points):

        if -1 in rv:
            continue
        f_center = voro.points[rp[0]]
        for rv0, rv1 in zip(rv, np.roll(rv, 1, axis=0)):
            fv0 = voro.vertices[rv0]
            fv1 = voro.vertices[rv1]
            edge_v = fv1 - fv0
            fto0 = fv0 - f_center
            normal = np.cross(fto0, edge_v)
            if np.sign(normal) > 0:
                el_idx.append([rv0, rv1, rp[0]])
            else:
                el_idx.append([rv0, rv1, rp[1]])

    el_idx = np.array(el_idx)
    coords = ['x', 'y']
    edge_idx = pd.Index(range(el_idx.shape[0]), name='edge')
    edge_df = make_df(edge_idx, specs['edge'])

    for i, elem in enumerate(['srce', 'trgt', 'face']):
        edge_df[elem] = el_idx[:, i]

    vert_idx = pd.Index(range(voro.vertices.shape[0]), name='vert')
    vert_df = make_df(vert_idx, specs['vert'])

    vert_df[coords] = voro.vertices

    face_idx = pd.Index(range(voro.points.shape[0]), name='face')
    face_df = make_df(face_idx, specs['face'])
    face_df[coords] = voro.points

    datasets= {
        'vert': vert_df,
        'edge': edge_df,
        'face': face_df,
        }
    return datasets

"""

Three cells sheet generations
-----------------------------

"""

def three_faces_sheet_array():
    '''
    Creates the apical junctions mesh of three packed hexagonal faces.
    If `zaxis` is `True` (defaults to False), adds a `z` coordinates,
    with `z = 0`.

    Faces have a side length of 1.0 +/- 1e-3.

    Returns
    -------

    points: (13, ndim) np.array of floats
      the positions, where ndim is 2 or 3 depending on `zaxis`
    edges: (15, 2)  np.array of ints
      indices of the edges
    (Nc, Nv, Ne): triple of ints
      number of faces, vertices and edges (3, 13, 15)

    '''


    Nc = 3 # Number of faces

    points = np.array([[0., 0.],
                       [1.0, 0.0],
                       [1.5, 0.866],
                       [1.0, 1.732],
                       [0.0, 1.732],
                       [-0.5, 0.866],
                       [-1.5, 0.866],
                       [-2, 0.],
                       [-1.5, -0.866],
                       [-0.5, -0.866],
                       [0, -1.732],
                       [1, -1.732],
                       [1.5, -0.866]])

    edges = np.array([[0, 1],
                      [1, 2],
                      [2, 3],
                      [3, 4],
                      [4, 5],
                      [5, 0],
                      [5, 6],
                      [6, 7],
                      [7, 8],
                      [8, 9],
                      [9, 0],
                      [9, 10],
                      [10, 11],
                      [11, 12],
                      [12, 1]])

    Nv, Ne = len(points), len(edges)
    return points, edges, (Nc, Nv, Ne)


def three_faces_sheet(zaxis=False):
    '''
    Creates the apical junctions mesh of three packed hexagonal faces.
    If `zaxis` is `True` (defaults to False), adds a `z` coordinates,
    with `z = 0`.

    Faces have a side length of 1.0 +/- 1e-3.

    Returns
    -------

    face_df: the faces `DataFrame` indexed from 0 to 2
    vert_df: the junction vertices `DataFrame`
    edge_df: the junction edges `DataFrame`

    '''
    points, _, (Nc, Nv, Ne) = three_faces_sheet_array()

    if zaxis:
        coords = ['x', 'y', 'z']
    else:
        coords = ['x', 'y']

    face_idx = pd.Index(range(Nc), name='face')
    vert_idx = pd.Index(range(Nv), name='vert')

    _edge_e_idx = np.array([[0, 1, 0],
                          [1, 2, 0],
                          [2, 3, 0],
                          [3, 4, 0],
                          [4, 5, 0],
                          [5, 0, 0],
                          [0, 5, 1],
                          [5, 6, 1],
                          [6, 7, 1],
                          [7, 8, 1],
                          [8, 9, 1],
                          [9, 0, 1],
                          [0, 9, 2],
                          [9, 10, 2],
                          [10, 11, 2],
                          [11, 12, 2],
                          [12, 1, 2],
                          [1, 0, 2]])

    edge_idx = pd.Index(range(_edge_e_idx.shape[0]), name='edge')

    specifications = load_default('geometry', 'sheet')
    ### Face - face graph
    cc_idx = [(0, 1), (1, 2), (0, 2)]
    cc_idx = pd.MultiIndex.from_tuples(cc_idx, names=['facea', 'faceb'])
    ### Faces DataFrame

    face_df = make_df(index=face_idx,
                      spec=specifications['face'])

    ### Junction vertices and edges DataFrames
    vert_df = make_df(index=vert_idx,
                    spec=specifications['vert'])
    edge_df = make_df(index=edge_idx,
                    spec=specifications['edge'])
    edge_df['srce'] = _edge_e_idx[:, 0]
    edge_df['trgt'] = _edge_e_idx[:, 1]
    edge_df['face'] = _edge_e_idx[:, 2]

    vert_df.loc[:, coords[:2]] = points
    if zaxis:
        vert_df.loc[:, coords[2:]] = 0.

    datasets = {'face': face_df, 'vert': vert_df, 'edge': edge_df}
    return datasets, specifications
