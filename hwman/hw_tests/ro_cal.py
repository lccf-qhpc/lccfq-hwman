
import logging
import shutil
import time
from pathlib import Path

import numpy as np

from labcore.data.datadict_storage import datadict_from_hdf5
from labcore.measurement.storage import run_and_save_sweep
from qcui_measurement.qick.single_transmon_v2 import SingleShotGroundProgram, SingleShotExcitedProgram

from hwman.hw_tests.utils import get_params
from hwman.utils.plotting import PlotItem, PlotSpec, create_plot_in_subprocess

logger = logging.getLogger(__name__)

FAKEDATAG = Path("test_data/2025-09-15T220662_06b1dca4-ground_single_shot~a74a8056")
FAKEDATAE = Path("test_data/2025-09-15T220663_06eec3f8-excited_single_shot~79e6a6b3")


def measure_ground(job_id: str):
    logger.info("Starting RO calib ground measurement for {}".format(job_id))

    sweep = SingleShotGroundProgram()
    logger.debug("sweep created, running measurement")
    loc, da = run_and_save_sweep(sweep, "data", f"RO_ground~{job_id}", return_data=True)
    logger.info("Measurement done, data in %s", loc)
    return loc, da


def measure_excited(job_id: str):
    logger.info("Starting RO calib excited measurement for {}".format(job_id))

    sweep = SingleShotExcitedProgram()
    logger.debug("sweep created, running measurement")
    loc, da = run_and_save_sweep(sweep, "data", f"RO_excited~{job_id}", return_data=True)
    logger.info("Measurement done, data in %s", loc)
    return loc, da


def plot_iq_scatter(loc_g, loc_e, plot_path: str):

    data_g = datadict_from_hdf5(loc_g/"data.ddh5")
    data_e = datadict_from_hdf5(loc_e/"data.ddh5")

    I_g = data_g["g"]["values"].T.real
    Q_g = data_g["g"]["values"].T.imag

    I_e = data_e["e"]["values"].T.real
    Q_e = data_e["e"]["values"].T.imag

    mean_I_g = np.mean(I_g)
    mean_Q_g = np.mean(Q_g)
    mean_I_e = np.mean(I_e)
    mean_Q_e = np.mean(Q_e)

    plots = [
        PlotItem(
            x=I_g, y=Q_g,
            plot_type="scatter",
            kwargs={"label": "g", "color": "b", "alpha": 0.1}
        ),
        PlotItem(
            x=I_e, y=Q_e,
            plot_type="scatter",
            kwargs={"label": "e", "color": "r", "alpha": 0.1}
        ),
        PlotItem(
            x=[mean_I_g], y=[mean_Q_g],
            plot_type="scatter",
            kwargs={"color": "k", "marker": "*", "s": 100, "label": f"g_mean: ({mean_I_g:.3f}, {mean_Q_g:.3f})"}
        ),
        PlotItem(
            x=[mean_I_e], y=[mean_Q_e],
            plot_type="scatter",
            kwargs={"color": "k", "marker": "o", "s": 100, "label": f"e_mean: ({mean_I_e:.3f}, {mean_Q_e:.3f})"}
        )
    ]

    plot_spec = PlotSpec(
        plot_path=plot_path,
        title="I/Q Scatter Plot - Ground vs Excited States",
        xlabel="I (a.u.)",
        ylabel="Q (a.u.)",
        legend=True,
        figsize=(8, 8),
        plots=plots
    )

    success = create_plot_in_subprocess(plot_spec)
    if success:
        logger.info(f"I/Q scatter plot saved to {plot_path}")
    else:
        logger.error(f"Failed to create I/Q scatter plot at {plot_path}")

    return success


def ro_cal(job_id: str, fake_calibration_data: bool = False):
    params = get_params()

    reps = 1
    steps = 1000

    old_reps = params.msmt.reps()
    old_steps = params.msmt.steps()
    try:
        params.msmt.reps(reps)
        params.msmt.steps(steps)

        loc_g, da_g = measure_ground(job_id)
        loc_e, da_e = measure_excited(job_id)

        if fake_calibration_data:
            measured_data_path_g = loc_g / "data.ddh5"
            measured_data_path_e = loc_e / "data.ddh5"

            if measured_data_path_g.exists():
                shutil.move(str(measured_data_path_g), str(loc_g/"empty_measured_g.ddh5"))

            if measured_data_path_e.exists():
                shutil.move(str(measured_data_path_e), str(loc_e/"empty_measured_e.ddh5"))

            fake_data_path_g = FAKEDATAG / "data.ddh5"
            fake_data_path_e = FAKEDATAE / "data.ddh5"

            if fake_data_path_g.exists():
                shutil.copy2(str(fake_data_path_g), str(loc_g/"data.ddh5"))
            else:
                raise FileNotFoundError(f"Fake data file not found at {fake_data_path_g}")

            if fake_data_path_e.exists():
                shutil.copy2(str(fake_data_path_e), str(loc_e/"data.ddh5"))
            else:
                raise FileNotFoundError(f"Fake data file not found at {fake_data_path_e}")

        # Create I/Q scatter plot
        iq_plot_path = loc_g / f"iq_scatter_plot_{job_id}.png"
        plot_iq_scatter(loc_g, loc_e, str(iq_plot_path))

        # Wait for the plot file to exist and then copy it to the excited measurement location
        timeout = 30  # Maximum wait time in seconds
        start_time = time.time()
        while not iq_plot_path.exists() and (time.time() - start_time) < timeout:
            time.sleep(0.1)  # Check every 100ms

        if iq_plot_path.exists():
            excited_plot_path = loc_e / f"iq_scatter_plot_{job_id}.png"
            shutil.copy2(str(iq_plot_path), str(excited_plot_path))
            logger.info(f"I/Q scatter plot copied to {excited_plot_path}")
        else:
            logger.warning(f"I/Q scatter plot file did not appear within {timeout} seconds")

    finally:
        params.msmt.reps(old_reps)
        params.msmt.steps(old_steps)
