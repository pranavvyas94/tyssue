"""Viscosity based ODE solver


"""
import logging
import numpy as np
import pandas as pd
import warnings

from itertools import count

from scipy.integrate import solve_ivp

from ..collisions import auto_collisions
from ..topology import all_rearangements, auto_t1, auto_t3

from ..core.history import History
from ..core.sheet import Sheet

# from .base import set_pos, TopologyChangeError


log = logging.getLogger(__name__)
MAX_ITER = 1000


def set_pos(eptm, geom, pos):
    """Updates the vertex position of the :class:`Epithelium` object.

    Assumes that pos is passed as a 1D array to be reshaped as (eptm.Nv, eptm.dim)

    """
    log.debug("set pos")
    eptm.vert_df.loc[eptm.active_verts, eptm.coords] = pos.reshape((-1, eptm.dim))
    geom.update_all(eptm)


class EulerSolver:
    """
    """

    def __init__(
        self,
        eptm,
        geom,
        model,
        history=None,
        with_t1=False,
        with_t3=False,
        manager=None,
        bounds=None,
    ):
        self._set_pos = set_pos
        if with_t1:
            warnings.warn("with_t1 is deprecated and has no effect")
            # self._set_pos = auto_t1(self._set_pos)
        if with_t3:
            warnings.warn("with_t3 is deprecated and has no effect")
            # self._set_pos = auto_t3(self._set_pos)

        # self.rearange = with_t1 or with_t3
        # self.with_t3 = with_t3
        self.eptm = eptm
        self.geom = geom
        self.model = model
        if history is None:
            self.history = History(eptm)
        else:
            self.history = history
        self.prev_t = 0
        self.manager = manager
        self.bounds = bounds

    @property
    def current_pos(self):
        return self.eptm.vert_df[self.eptm.coords].values.ravel()

    def set_pos(self, pos):
        """Updates the eptm vertices position
        """
        return self._set_pos(self.eptm, self.geom, pos)

    def record(self, t):
        self.history.record(["vert"], t)

    def solve(self, tf, dt, on_topo_change=None, topo_change_args=()):
        """Solves the system of differential equations from the current time
        to tf with steps of dt with a forward Euler method.

        Parameters
        ----------
        tf : float, final time when we stop solving
        dt : float, time step
        on_topo_change : function, optional, default None
             function of `self.eptm`
        topo_change_args : tuple, arguments passed to `on_topo_change`

        """
        for t in np.arange(self.prev_t, tf + dt, dt):
            pos = self.current_pos
            dot_r = self.ode_func(t, pos)
            if self.bounds is not None:
                dot_r = np.clip(dot_r, *self.bounds)
            pos = pos + dot_r * dt
            self.set_pos(pos)
            self.prev_t = t
            if self.manager is not None:
                self.manager.execute(self.eptm)
                self.geom.update_all(self.eptm)
                self.manager.update()

            if self.eptm.topo_changed:
                log.info("Topology changed")
                if on_topo_change is not None:
                    on_topo_change(*topo_change_args)

                self.history.record(["face", "edge"], t)
                if "cell" in self.eptm.datasets:
                    self.history.record(["cell"], t)
                self.eptm.topo_changed = False

            self.record(t)

    def ode_func(self, t, pos):
        """Computes the models' gradient.


        Returns
        -------
        dot_r : 1D np.ndarray of shape (self.eptm.Nv * self.eptm.dim, )

        .. math::
        \frac{dr_i}{dt} = \frac{\nabla U_i}{\eta_i}

        """

        grad_U = -self.model.compute_gradient(self.eptm)
        return (grad_U.values / self.eptm.vert_df["viscosity"].values[:, None]).ravel()


class IVPSolver(EulerSolver):
    """
    """

    def solve(self, tf, on_topo_change=None, topo_change_args=(), **solver_kwargs):
        """

        on_topo_change : function, optional, default None
             function of `self.eptm`
        topo_change_args : tuple, arguments passed to `on_topo_change`

        """
        res = {"message": "Not started", "success": False}
        for i in count():
            if i == MAX_ITER:
                res["message"] = res["message"] + "\nMax number of iterations reached!"
                return res
            pos0 = self.current_pos
            if self.prev_t > tf:
                return
            if "t_eval" in solver_kwargs:
                solver_kwargs["t_eval"] = solver_kwargs["t_eval"][
                    np.where(solver_kwargs["t_eval"] >= self.prev_t)[0]
                ]

            res = solve_ivp(self.ode_func, (self.prev_t, tf), pos0, **solver_kwargs)
            self.record(res)
            return res

    def record(self, res):
        """Records the solution
        """
        positions = res.y.T.reshape((-1, 3))

        vert_id = np.tile(self.eptm.vert_df.index, res.t.shape[0])

        times = np.repeat(res.t, self.eptm.Nv)
        hist = pd.DataFrame(
            index=np.arange(times.shape[0]), columns=["vert", *self.eptm.coords, "time"]
        )
        hist["vert"] = vert_id
        hist["time"] = times
        hist[self.eptm.coords] = positions

        self.history.datasets["vert"] = pd.concat(
            (self.history.datasets["vert"], hist), ignore_index=True, sort=False
        )
        self.history.record(["face", "edge"], res.t[-1])
        if "cell" in self.eptm.datasets:
            self.history.record(["cell"], res.t[-1])
