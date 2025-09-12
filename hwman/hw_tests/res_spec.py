import os
import logging
from pathlib import Path

import numpy as np

from labcore.analysis import FitResult
from labcore.data.datadict import DataDict
from labcore.data.datadict_storage import datadict_from_hdf5
from labcore.measurement.storage import run_and_save_sweep

os.environ['HDF5_USE_FILE_LOCKING'] = 'FALSE'  # Disable HDF5 file locking
os.environ['OPENBLAS_NUM_THREADS'] = '1'  # Limit OpenBLAS threads
os.environ['MKL_NUM_THREADS'] = '1'  # Limit MKL threads
os.environ['OMP_NUM_THREADS'] = '1'  # Limit OpenMP threads
os.environ['NUMEXPR_NUM_THREADS'] = '1'  # Limit NumExpr threads


from hwman.utils.plotting import (
    create_plot_in_subprocess,
    PlotSpec,
    PlotItem,
)

from qcui_measurement.qick.single_transmon_v2 import FreqSweepProgram
from qcui_analysis.fitfuncs.resonators import HangerResponseBruno

from hwman.hw_tests.utils import set_bandpass_filters, generate_id, QickConfig, setup_measurement_env

logger = logging.getLogger(__name__)


def measure_res_spec(conf: QickConfig, job_id: str | None):

    if job_id is None:
        job_id = generate_id()

    logger.info("Starting resonator spectroscopy for {}".format(job_id))
    logger.debug("Checking configuration")
    conf.config()
    logger.debug("Configuration OK, setting bandpass filters")
    set_bandpass_filters(conf)
    logger.debug("bandpass filters set")

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

    fit = HangerResponseBruno(freqs, signal)
    fit_result = fit.run(fit)
    fit_curve = fit_result.eval()
    residuals = signal - fit_curve

    amp = fit_result.params["A"].value
    noise = np.std(residuals)
    snr = amp/noise

    return fit_result, residuals, snr


def analyze_res_spec(loc: Path):

    logger.info("Starting to analyze Resonator Spec")

    if not loc.exists():
        msg = f"Location {loc} does not exist"
        raise FileNotFoundError(msg)

    data = datadict_from_hdf5(loc/"data.ddh5")

    data = add_mag_and_unwind(data)

    fit_result, residuals, snr = _fit_and_snr(data)

    # FIXME: This should be a settable option instead of having it done every single time

    freqs = data["freq"]["values"]
    signal = data["signal_unwind"]["values"]
    fit_curve = fit_result.eval()
    plot_filename = f"resonator_spec_fit.png"
    plot_path = loc / plot_filename

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

    logger.info("Finished analyzing Resonator Spec")

    return fit_result, residuals, snr

def res_spec(conf: QickConfig, job_id: str) -> tuple[Path, FitResult, float]:
    loc, da = measure_res_spec(conf, job_id)
    fit_result, residuals, snr = analyze_res_spec(loc)
    return loc, fit_result, snr



