import logging
from pathlib import Path
import shutil
import time

import numpy as np

from labcore.analysis import DatasetAnalysis
from labcore.data.datadict import DataDict
from labcore.data.datadict_storage import datadict_from_hdf5
from labcore.measurement.storage import run_and_save_sweep

from qcui_measurement.qick.single_transmon_v2 import FreqSweepProgram

from hwman.utils.plotting import (
    create_plot_in_subprocess,
    PlotSpec,
    PlotItem,
)
from hwman.hw_tests.res_spec import add_mag_and_unwind, _fit_and_snr, plot_res_spec, analyze_res_spec, measure_res_spec
from hwman.hw_tests.utils import generate_id

logger = logging.getLogger(__name__)

FAKEDATABEFORE = Path("test_data/2025-09-15T220657_941fe156-Res_spec_readout_pre_pi~f5669779")
FAKEDATAAFTER = Path("test_data/2025-09-15T220658_2689d6ce-Res_spec_readout_post_pi~e19a85a2")


# def measure_res_spec_before_pi(job_id: str):
#     """Measure resonator spectroscopy before pi pulse"""
#     logger.info("Starting resonator spectroscopy before pi for {}".format(job_id))
#
#     sweep = FreqSweepProgram()
#     logger.debug("Sweep created, running measurement")
#     loc, da = run_and_save_sweep(sweep, "data", f"resonator_spec_before_pi~{job_id}", return_data=True)
#     logger.info("Measurement done, data in %s", loc)
#
#     return loc, da


def measure_res_spec_after_pi_pulse(job_id: str):
    """Measure resonator spectroscopy after pi pulse"""
    logger.info("Starting resonator spectroscopy after pi for {}".format(job_id))

    sweep = FreqSweepProgram()
    logger.debug("Sweep created, running measurement")
    loc, da = run_and_save_sweep(sweep, "data", f"resonator_spec_after_pi~{job_id}", return_data=True)
    logger.info("Measurement done, data in %s", loc)

    return loc, da


def plot_both_measurements(data_before: DataDict, data_after: DataDict,
                          fit_before, fit_after, plot_path: Path,
                          f0_before: float, f0_after: float):
    """Plot both measurements in magnitude and show f_0 difference"""

    freqs_before = data_before["freq"]["values"]
    freqs_after = data_after["freq"]["values"]
    signal_before = data_before["signal_unwind"]["values"]
    signal_after = data_after["signal_unwind"]["values"]

    fit_curve_before = fit_before.eval()
    fit_curve_after = fit_after.eval()

    f0_diff = f0_before - f0_after

    plot_spec = PlotSpec(
        plot_path=str(plot_path),
        title=f"Resonator Spec Before/After Pi ($\chi$ = {f0_diff:.3f} MHz)",
        xlabel="Frequency (MHz)",
        ylabel="Signal Magnitude (A.U.)",
        legend=True,
        plots=[
            PlotItem(x=freqs_before, y=np.abs(signal_before), kwargs={'label': 'Before Pi', 'alpha': 0.7}),
            PlotItem(x=freqs_before, y=np.abs(fit_curve_before), kwargs={'label': 'Before Pi Fit', 'linestyle': '--'}),
            PlotItem(x=freqs_after, y=np.abs(signal_after), kwargs={'label': 'After Pi', 'alpha': 0.7}),
            PlotItem(x=freqs_after, y=np.abs(fit_curve_after), kwargs={'label': 'After Pi Fit', 'linestyle': '--'}),
        ]
    )

    success = create_plot_in_subprocess(plot_spec)
    if success:
        logger.info(f"Combined plot saved to {plot_path}")
    else:
        logger.error("Failed to create combined plot")

    return success


def res_spec_after_pi(job_id: str, fake_calibration_data: bool = False):
    """
    Perform resonator spectroscopy before and after pi pulse, then analyze both measurements
    """

    # First measurement: before pi
    loc_before, da_before = measure_res_spec(job_id + "_before")
    if fake_calibration_data:
        # Rename the measured data.ddh5 to empty_measured.ddh5
        measured_data_path = loc_before / "data.ddh5"
        if measured_data_path.exists():
            shutil.move(str(measured_data_path), str(loc_before / "empty_measured_before.ddh5"))

        # Copy the fake data.ddh5 from FAKEDATABEFORE to loc
        fake_data_path = FAKEDATABEFORE / "data.ddh5"
        if fake_data_path.exists():
            shutil.copy2(str(fake_data_path), str(loc_before / "data.ddh5"))
        else:
            raise FileNotFoundError(f"Fake data file not found at {fake_data_path}")

    # Second measurement: after pi
    loc_after, da_after = measure_res_spec_after_pi_pulse(job_id + "_after")
    if fake_calibration_data:
        # Rename the measured data.ddh5 to empty_measured.ddh5
        measured_data_path = loc_after / "data.ddh5"
        if measured_data_path.exists():
            shutil.move(str(measured_data_path), str(loc_after / "empty_measured_after.ddh5"))

        # Copy the fake data.ddh5 from FAKEDATAAFTER to loc
        fake_data_path = FAKEDATAAFTER / "data.ddh5"
        if fake_data_path.exists():
            shutil.copy2(str(fake_data_path), str(loc_after / "data.ddh5"))
        else:
            raise FileNotFoundError(f"Fake data file not found at {fake_data_path}")

    # Analyze both measurements using res_spec functions
    fit_result_before, residuals_before, snr_before, unwind_data_before = analyze_res_spec(loc_before)
    fit_result_after, residuals_after, snr_after, unwind_data_after = analyze_res_spec(loc_after)


    # Get f_0 values from fit parameters
    f0_before = fit_result_before.params['f_0'].value
    f0_after = fit_result_after.params['f_0'].value
    f0_difference = f0_before-f0_after

    # Create combined plot
    combined_plot_path = loc_before / f"res_spec_before_after_pi_{job_id}.png"
    plot_both_measurements(unwind_data_before, unwind_data_after, fit_result_before, fit_result_after,
                          combined_plot_path, f0_before, f0_after)

    # Wait for the plot file to exist and then copy it to the after measurement location
    timeout = 30  # Maximum wait time in seconds
    start_time = time.time()
    while not combined_plot_path.exists() and (time.time() - start_time) < timeout:
        time.sleep(0.1)  # Check every 100ms

    if combined_plot_path.exists():
        after_plot_path = loc_after / f"res_spec_before_after_pi_{job_id}.png"
        shutil.copy2(str(combined_plot_path), str(after_plot_path))
        logger.info(f"Combined plot copied to {after_plot_path}")
    else:
        logger.warning(f"Combined plot file did not appear within {timeout} seconds")

    logger.info(f"f_0 before pi: {f0_before:.6f} MHz")
    logger.info(f"f_0 after pi: {f0_after:.6f} MHz")
    logger.info(f"χ (before - after): {f0_difference:.6f} MHz")

    return {
        "loc_before": loc_before,
        "loc_after": loc_after,
        "fit_before": fit_result_before,
        "fit_after": fit_result_after,
        "f0_before": f0_before,
        "f0_after": f0_after,
        "f0_difference": f0_difference,
        "snr_before": snr_before,
        "snr_after": snr_after
    }