"""
Shared KMeans-based IQ readout calibration, used by TestService (fitting) and
CircuitService (shot labeling).
"""

from typing import Any

import numpy as np
import xarray as xr

from cqedtoolbox.readout.qubit_readout import (
    apply_kmeans_calibration,
    kmeans_calibration,
    lbl2prob,
)


class ReadoutCalibrator:
    """Owns a fitted KMeans calibration and provides shot-labeling for circuit execution.

    Lifecycle:
        1. fit()          — called once after ROCal; stores the fitted KMeans.
        2. label()        — assign 0/1 to each IQ shot (0=ground, 1=excited).
        3. probabilities() — optional: average labels into P(0)/P(1).
    """

    _VAR = "signal"  # xarray variable prefix expected by cqedtoolbox functions

    def __init__(self) -> None:
        self.km: Any = None

    @property
    def is_calibrated(self) -> bool:
        return self.km is not None

    def fit(
        self,
        I_ground: np.ndarray,
        Q_ground: np.ndarray,
        I_excited: np.ndarray,
        Q_excited: np.ndarray,
    ) -> None:
        """Fit a KMeans classifier from known ground and excited IQ shots.

        Args:
            I_ground, Q_ground: numpy arrays of I/Q values for the ground state.
            I_excited, Q_excited: numpy arrays of I/Q values for the excited state.
        """
        all_I = np.concatenate([I_ground.flatten(), I_excited.flatten()])
        all_Q = np.concatenate([Q_ground.flatten(), Q_excited.flatten()])
        cal_dset = xr.Dataset({
            f"{self._VAR}_Re": (["repetition"], all_I),
            f"{self._VAR}_Im": (["repetition"], all_Q),
        })
        g_center = [float(I_ground.mean()), float(Q_ground.mean())]
        e_center = [float(I_excited.mean()), float(Q_excited.mean())]
        self.km = kmeans_calibration(cal_dset, self._VAR, g_center, e_center)

    def label(self, I: np.ndarray, Q: np.ndarray) -> np.ndarray:
        """Assign 0/1 label to each shot using the fitted KMeans.

        Args:
            I, Q: numpy arrays of I/Q readout values (arbitrary shape).

        Returns:
            Integer numpy array of the same shape as I with 0=ground, 1=excited.

        Raises:
            RuntimeError: If fit() has not been called yet.
        """
        if not self.is_calibrated:
            raise RuntimeError(
                "ReadoutCalibrator has not been fitted — run ROCal before executing circuits."
            )
        I_arr = np.asarray(I)
        shp = I_arr.shape
        data = xr.Dataset({
            f"{self._VAR}_Re": (["repetition"], I_arr.flatten()),
            f"{self._VAR}_Im": (["repetition"], np.asarray(Q).flatten()),
        })
        labeled = apply_kmeans_calibration(data, self._VAR, self.km)
        return labeled["label"].values.reshape(shp)

    def probabilities(self, I: np.ndarray, Q: np.ndarray) -> dict[str, float]:
        """Label shots and return state probabilities averaged over all shots.

        Returns:
            {"Pr_0": float, "Pr_1": float}
        """
        if not self.is_calibrated:
            raise RuntimeError(
                "ReadoutCalibrator has not been fitted — run ROCal before calling probabilities()."
            )
        data = xr.Dataset({
            f"{self._VAR}_Re": (["repetition"], np.asarray(I).flatten()),
            f"{self._VAR}_Im": (["repetition"], np.asarray(Q).flatten()),
        })
        labeled = apply_kmeans_calibration(data, self._VAR, self.km)
        result = lbl2prob(labeled)
        return {
            "Pr_0": float(result["Pr_0"].values),
            "Pr_1": float(result["Pr_1"].values),
        }
