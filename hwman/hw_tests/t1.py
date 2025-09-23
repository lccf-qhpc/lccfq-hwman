import shutil
import logging
from pathlib import Path

import numpy as np

from hwman.hw_tests.utils import get_params
from hwman.utils.plotting import PlotSpec, PlotItem, create_plot_in_subprocess
from labcore.data.datadict import DataDict
from labcore.analysis.fitfuncs.generic import ExponentialDecay
from labcore.measurement.storage import run_and_save_sweep
from labcore.data.datadict_storage import datadict_from_hdf5
from labcore.analysis import DatasetAnalysis

from qcui_measurement.qick.single_transmon_v2 import T1Program

from hwman.utils.fitting import FitSpec, fit_in_subprocess, serialize_params

logger = logging.getLogger(__name__)

FAKEDATA = Path("test_data/2025-09-15T220659_113a1912e-T1~5ba1ee50")


def measure_t1(job_id: str):

    logger.info("Starting T1 measurement for {}".format(job_id))

    sweep = T1Program()
    logger.debug("Sweep created, running measurement")
    loc, da = run_and_save_sweep(sweep, "data", f"t1~{job_id}", return_data=True)
    logger.info("Measurement done, data in %s", loc)
    return loc, da


def _fit_and_snr(data: DataDict):

    delays = data["t"]["values"]
    signal = data["signal"]["values"]

    # real fit
    fit_spec = FitSpec(
        coordinates=delays,
        data=signal.real,
        fit_class=ExponentialDecay,
    )

    result_re = fit_in_subprocess(fit_spec)

    # imag fit
    fit_spec = FitSpec(
        coordinates=delays,
        data=signal.imag,
        fit_class=ExponentialDecay,
    )
    result_imag = fit_in_subprocess(fit_spec)

    # mag fit
    fit_spec = FitSpec(
        coordinates=delays,
        data=np.abs(signal),
        fit_class=ExponentialDecay,
    )
    result_mag = fit_in_subprocess(fit_spec)

    return result_re, result_imag, result_mag


def plot_t1(x: np.ndarray, y: np.ndarray, fit_result, plot_path: Path, plot_type: str):
    fit_curve = fit_result.eval()

    plot_spec = PlotSpec(
        plot_path=str(plot_path),
        title=f"T1 ({plot_type})",
        xlabel="Delay (μs)",
        ylabel=f"Signal {plot_type} (A.U)",
        legend=True,
        plots=[
            PlotItem(x=x, y=y, kwargs={"label": "Data"}),
            PlotItem(x=x, y=fit_curve, kwargs={"label": "Fit"}),
        ]
    )

    create_plot_in_subprocess(plot_spec)


def analyze_t1(loc: Path):

    logger.info("Starting to analyze T1 for {}".format(loc))

    if not loc.exists():
        msg = f"T1 for {loc} does not exist"
        raise FileNotFoundError(msg)

    data = datadict_from_hdf5(loc/"data.ddh5")

    with DatasetAnalysis(loc, "t1") as ds:
        result_re, result_imag, result_mag = _fit_and_snr(data)

        fit_result_re, residuals_re, snr_re = result_re
        params_re = serialize_params(fit_result_re.params)
        params_re["snr"] = snr_re
        ds.add(fit_params_re=params_re)

        fit_result_imag, residuals_imag, snr_imag = result_imag
        params_imag = serialize_params(fit_result_imag.params)
        params_imag["snr"] = snr_imag
        ds.add(fit_params_imag=params_imag)

        fit_result_mag, residuals_mag, snr_mag = result_mag
        params_mag = serialize_params(fit_result_mag.params)
        params_mag["snr"] = snr_mag
        ds.add(fit_params_mag=params_mag)

        savefolders = ds.savefolders

    delays = data["t"]["values"]
    signal = data["signal"]["values"]
    signal_re = signal.real
    signal_imag = signal.imag
    signal_mag = np.abs(signal)

    for f in savefolders:
        plot_t1(x=delays, y=signal_re, fit_result=fit_result_re, plot_path=f / "real_fit.png" , plot_type="Real")
        plot_t1(x=delays, y=signal_imag, fit_result=fit_result_imag, plot_path=f / "imag_fit.png" , plot_type="Imaginary")
        plot_t1(x=delays, y=signal_mag, fit_result=fit_result_mag, plot_path=f / "mag_fit.png", plot_type="Magnitude")

    return result_re, result_imag, result_mag

def t1(job_id: str, fake_calibration_data: bool = False):
    params = get_params()
    old_echo = params.qubit.n_echo()
    # Make sure we return the instrumentserver back to the original state
    try:
        params.qubit.n_echo(0)

        loc, da = measure_t1(job_id)
        if fake_calibration_data:
            # Rename the measured data.ddh5 to empty_measured.ddh5
            measured_data_path = loc / "data.ddh5"
            if measured_data_path.exists():
                shutil.move(str(measured_data_path), str(loc / "empty_measured.ddh5"))

            # Copy the fake data.ddh5 from FAKEDATA to loc
            fake_data_path = FAKEDATA / "data.ddh5"
            if fake_data_path.exists():
                shutil.copy2(str(fake_data_path), str(loc / "data.ddh5"))
            else:
                raise FileNotFoundError(f"Fake data file not found at {fake_data_path}")

        ret_real, ret_imag, ret_mag = analyze_t1(loc)
    finally:
        params.qubit.n_echo(old_echo)
        del params
    return ret_real, ret_imag, ret_mag