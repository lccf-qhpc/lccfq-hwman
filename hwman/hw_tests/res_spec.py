import logging
import uuid
from pathlib import Path

import numpy as np

from labcore.data.datadict import DataDict
from labcore.data.datadict_storage import datadict_from_hdf5

from qcui_measurement.qick.single_transmon_v2 import FreqSweepProgram
from qcui_analysis.fitfuncs.resonators import HangerResponseBruno


from hwman.hw_tests.utils import conf, run_measurement, set_bandpass_filters, generate_id, params
from hwman.utils.plotting import (
    create_plot_in_process,
    create_plot_in_subprocess,
    PlotSpec,
    PlotItem,
)


logger = logging.getLogger(__name__)


def calculate_and_set_teff():

    logger.info("Shifting frequency to off resonance")
    params.readout.start_f(params.readout.start_f() + 10)
    params.readout.end_f(params.readout.end_f() + 10)
    logger.info("SHIFT SUCCESFULL")

    try:
        teff_id = "AUTOMATIC_CALIBRATION_" + generate_id()
        logger.info(f"Calculating TEFF {teff_id}")
        loc, data = measure_res_spec(teff_id)

        if data is None:
            logger.warning("No data found, loading from file")
            data = datadict_from_hdf5(loc)
        logger.debug("Data acquired, calculating TEFF")
        signal = data["signal"]["values"]
        freq = data["freq"]["values"]

        phase_unwrap = np.unwrap(np.angle(signal))
        phase_slope = np.polyfit(freq, phase_unwrap, 1)[0]

        t_eff = phase_slope

        # phase = np.arctan2(signal.imag, signal.real)
        # phase_unwrap = np.unwrap(phase)/(2 * np.pi)
        # vals_matrix = np.vstack([freq, np.ones_like(freq)]).T
        # t_eff = np.linalg.lstsq(vals_matrix, phase_unwrap, rcond=None)[0][0]

        logger.debug("T_EFF calculated. Previous T_EFF %s us, new T_EFF, %s", params.msmt.t_eff(), t_eff)

        params.msmt.t_eff(t_eff)

        plot_path = loc/"image.png"
        # Create plot using the new generic utility
        plot_spec = PlotSpec(
            plot_path=str(plot_path),
            title="Phase_unwrap",
            xlabel="Frequency (MHz)",
            ylabel="Signal (A.U.)",
            legend=True,
            plots=[
                PlotItem(x=freq, y=phase_unwrap, kwargs={'label': 'Data'}),
            ]
        )
        create_plot_in_subprocess(plot_spec)

        plot_path = loc/"trace.png"
        plot_spec = PlotSpec(
            plot_path=str(plot_path),
            title="trace",
            xlabel="Frequency (MHz)",
            ylabel="Signal (A.U.)",
            legend=True,
            plots=[
                PlotItem(x=freq, y=np.abs(signal), kwargs={'label': 'Data'}),
            ]
        )
        create_plot_in_subprocess(plot_spec)

        # plot_path = loc / "phase.png"
        # plot_spec = PlotSpec(
        #     plot_path=str(plot_path),
        #     title="phase",
        #     xlabel="Frequency (MHz)",
        #     ylabel="Signal (A.U.)",
        #     legend=True,
        #     plots=[
        #         PlotItem(x=freq, y=phase, kwargs={'label': 'Data'}),
        #     ]
        # )
        # create_plot_in_subprocess(plot_spec)


    finally:
        logger.info("Shifting frequency to on resonance")
        params.readout.start_f(params.readout.start_f() - 10)
        params.readout.end_f(params.readout.end_f() - 10)


    return t_eff


def measure_res_spec(job_id: str | None):

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
    loc, da = run_measurement(sweep, f"resonator_spec~{job_id}", return_data=True)
    logger.info("Measurement done, data in %s", loc)

    return loc, da


def add_mag_and_unwind(data: DataDict):
    logger.debug("Adding mag and unwind")
    freq = data["freq"]["values"]
    signal_raw = data["signal"]["values"]
    logger.warning("TEFF IS %s", params.msmt.t_eff()/(2*np.pi))
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

def res_spec(job_id: str | None = None):
    if job_id is None:
        job_id = generate_id()

    loc, da = measure_res_spec(job_id)
    analyze_res_spec(loc)



