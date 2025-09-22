import logging
from pathlib import Path
import shutil

import numpy as np

from labcore.analysis import FitResult, DatasetAnalysis
from labcore.data.datadict import DataDict
from labcore.data.datadict_storage import datadict_from_hdf5
from labcore.measurement.storage import run_and_save_sweep

from qcui_measurement.qick.single_transmon_v2 import FreqSweepProgram
from qcui_analysis.fitfuncs.resonators import HangerResponseBruno

from hwman.utils.plotting import (
    create_plot_in_subprocess,
    PlotSpec,
    PlotItem,
)
from hwman.utils.fitting import fit_in_subprocess, FitSpec, serialize_params


from hwman.hw_tests.utils import generate_id

logger = logging.getLogger(__name__)

FAKEDATA = Path("test_data/2025-09-15T220651_316ab9b2-resonator_spec~3180264c")

def measure_res_spec(job_id: str | None):

    if job_id is None:
        job_id = generate_id()

    logger.info("Starting resonator spectroscopy for {}".format(job_id))

    sweep = FreqSweepProgram()
    logger.debug("Sweep created, running measurement")
    loc, da = run_and_save_sweep(sweep, "data", f"resonator_spec~{job_id}", return_data=True)
    logger.info("Measurement done, data in %s", loc)

    return loc, da


def add_mag_and_unwind(data: DataDict):
    logger.debug("Adding mag and unwind")
    freq = data["freq"]["values"]
    signal_raw = data["signal"]["values"]
    phase_unwrap = np.unwrap(np.angle(signal_raw))
    phase_slope = np.polyfit(freq, phase_unwrap, 1)[0]

    signal_unwind = signal_raw * np.exp(-1j*freq*phase_slope)
    mag = np.abs(data["signal"]["values"])
    phase = np.arctan2(signal_unwind.imag, signal_unwind.real)

    data["signal_unwind"] = {"values": signal_unwind}
    data["magnitude"] = {"values": mag}
    data["phase"] = {"values": phase}
    logger.debug("Mag and unwind data added")
    return data


def _fit_and_snr(data: DataDict):

    freqs = data["freq"]["values"]
    signal = data["signal_unwind"]["values"]

    fit_spec = FitSpec(
        coordinates=freqs,
        data=signal,
        fit_class=HangerResponseBruno
    )

    result = fit_in_subprocess(fit_spec)
    if result is None:
        raise RuntimeError("Fitting failed in subprocess")

    return result


def plot_res_spec(data, fit_result, plot_path):
    freqs = data["freq"]["values"]
    signal = data["signal_unwind"]["values"]
    fit_curve = fit_result.eval()

    # Create plot using the new generic utility
    plot_spec = PlotSpec(
        plot_path=str(plot_path),
        title="Resonator Fit",
        xlabel="Frequency (MHz)",
        ylabel="Signal (A.U.)",
        legend=True,
        plots=[
            PlotItem(x=freqs, y=np.abs(signal), kwargs={'label': 'Data'}),
            PlotItem(x=freqs, y=np.abs(fit_curve), kwargs={'label': 'Fit'}),
        ]
    )
    create_plot_in_subprocess(plot_spec)


def analyze_res_spec(loc: Path):

    logger.info("Starting to analyze Resonator Spec")

    if not loc.exists():
        msg = f"Location {loc} does not exist"
        raise FileNotFoundError(msg)

    data = datadict_from_hdf5(loc/"data.ddh5")

    with DatasetAnalysis(loc, "resonator_spec") as ds:
        data = add_mag_and_unwind(data)
        fit_result, residuals, snr = _fit_and_snr(data)
        params = serialize_params(fit_result.params)
        params["snr"] = snr
        ds.add(fit_params=params)
        savefolders = ds.savefolders

    for f in savefolders:
        plot_res_spec(data, fit_result, f/"res_spec_vs_freq.png")

    # FIXME: This should be a settable option instead of having it done every single time

    logger.info("Finished analyzing Resonator Spec")

    return fit_result, residuals, snr

def res_spec(job_id: str, fake_calibration_data: bool = False) -> tuple[Path, FitResult, float]:
    loc, da = measure_res_spec(job_id)
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

    fit_result, residuals, snr = analyze_res_spec(loc)
    return loc, fit_result, snr



