import logging
from pathlib import Path
import shutil

import numpy as np

from hwman.hw_tests.res_spec import add_mag_and_unwind, _fit_and_snr, plot_res_spec
from hwman.utils.fitting import serialize_params
from hwman.utils.plotting import PlotSpec, PlotItem, create_plot_in_subprocess
from labcore.analysis import DatasetAnalysis
from labcore.data.datadict import DataDict
from labcore.measurement.storage import run_and_save_sweep
from labcore.data.datadict_storage import datadict_from_hdf5
from qcui_measurement.qick.single_transmon_v2 import FreqGainSweepProgram

logger = logging.getLogger(__name__)

FAKEDATA = Path("test_data/2025-09-15T220653_32e06a30-resonator_spec_vs_gain~f98b5786")


def measure_res_spec_vs_gain(job_id: str):

    logger.info("Starting resonator spectroscopy vs gain for {}".format(job_id))
    sweep = FreqGainSweepProgram()
    logger.debug("Sweep created, running measurement")
    loc, da = run_and_save_sweep(sweep, "data", f"resonator_spec_vs_gain~{job_id}", return_data=True)
    logger.info("Measurement done, data in %s", loc)

    return loc, da


def analyze_res_spec_vs_gain(loc: Path):

    logger.info("Starting to analyze Resonator Spec Vs Gain")

    if not loc.exists():
        msg = f"Location {loc} does not exist"
        raise FileNotFoundError(msg)

    data = datadict_from_hdf5(loc/"data.ddh5")

    image_path = loc / "resonator_spec_vs_gain.png"

    # TODO: One can probably optimize the code such that you don't need to calculate the magnitude here and in the
    #   individual traces.
    # Create magnitude colorbar plot
    plot_res_spec_vs_gain_mag(data, image_path)

    # Go through each trace and fit individually.
    gains = data["gain"]["values"][0]
    res_f_arr = []
    for i, g in enumerate(gains):
        trace_signal = data["signal"]["values"].T[i]  # Transpose to achieve gain as axis 0 instead of freq.
        freqs = data["freq"]["values"].T[i]

        trace_dd = DataDict(signal=dict(unit=data["signal"]["unit"], axes=["freq"]), freq=dict(unit=data["freq"]["unit"]))
        trace_dd.add_data(signal=trace_signal, freq=freqs)

        folder_name = f"resonator_spec_vs_gain_i={i}_g={g}"
        with DatasetAnalysis(loc, folder_name) as ds:
            unwind_data = add_mag_and_unwind(trace_dd)
            fit_result, residuals, snr = _fit_and_snr(unwind_data)
            params = serialize_params(fit_result.params)
            params["snr"] = snr
            ds.add(params=params)
            savefolders = ds.savefolders

        for f in savefolders:
            plot_res_spec(unwind_data, fit_result, f/(folder_name + ".png"))
        logger.info("plots saved")
        res_f_arr.append(params["f_0"]["value"])

    slope = (res_f_arr[len(res_f_arr) - 1] - res_f_arr[0]) / (gains[len(res_f_arr) - 1] - gains[0])
    diff = []
    for g, f in zip(gains, res_f_arr):
        val = slope * (g - gains[0]) + res_f_arr[0]
        diff.append(np.abs(f - val))

    # Create gain vs resonance frequency plot
    gain_vs_freq_path = loc / "gain_vs_freq_change.png"
    plot_spec = PlotSpec(
        plot_path=str(gain_vs_freq_path),
        title="Gain vs Resonator Frequency",
        xlabel="Gain",
        ylabel="Resonance Frequency (MHz)",
        legend=True,
        plots=[
            PlotItem(x=gains, y=res_f_arr, kwargs={'marker': '.', 'linestyle': '-', 'label': 'Data'}),
            PlotItem(x=[gains[0], gains[-1]], y=[res_f_arr[0], res_f_arr[-1]], kwargs={'label': 'Linear Fit'}),
            PlotItem(x=[gains[np.argmax(diff)], gains[np.argmax(diff)]], y=[min(res_f_arr), max(res_f_arr)], kwargs={'linestyle': '--', 'color': 'red', 'label': 'Max Deviation'})
        ]
    )

    success = create_plot_in_subprocess(plot_spec)
    if success:
        logger.info(f"Gain vs frequency plot saved to {str(gain_vs_freq_path)}")
    else:
        logger.error("Failed to create gain vs frequency plot")

    logger.info("Finished analyzing Resonator Spec")

    return gains[np.argmax(diff)]

def plot_res_spec_vs_gain_mag(data: DataDict, image_path: Path) -> None:
    """
    Plots a color mesh plot of resonator spectroscopy vs gain
    """
    logger.info("Creating magnitude colorbar plot")

    # Calculate magnitude using the correct method
    mag = np.abs(data["signal"]["values"])
    
    # Get coordinates - assuming freq and gain are the sweep parameters
    freq_values = data["freq"]["values"]
    gain_values = data.get("gain", {}).get("values", np.arange(mag.shape[0]))
    
    # Create meshgrid for plotting
    if len(freq_values.shape) == 1:
        X, Y = np.meshgrid(freq_values, gain_values)
        Z = mag
        if Z.shape != X.shape:
            Z = Z.T  # Transpose if needed to match meshgrid
    else:
        X = freq_values
        Y = gain_values
        Z = mag
    
    # Create colorbar plot
    colorbar_item = PlotItem(
        x=X,
        y=Y,
        z=Z,
        plot_type="colorbar",
        kwargs={"cmap": "viridis", "colorbar_label": "Magnitude (A.U.)"}
    )

    plot_spec = PlotSpec(
        plot_path=str(image_path),
        title="Resonator Spectroscopy vs Gain Magnitude",
        xlabel="Frequency (MHz)",
        ylabel="Gain",
        plots=[colorbar_item]
    )
    
    success = create_plot_in_subprocess(plot_spec)
    
    if success:
        logger.info(f"Magnitude colorbar plot saved to {str(image_path)}")
    else:
        logger.error("Failed to create magnitude colorbar plot")
    
    return success


def res_spec_vs_gain(job_id: str, fake_calibration_data: bool = False):
    loc, da = measure_res_spec_vs_gain(job_id)
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

    gain = analyze_res_spec_vs_gain(loc)
    logger.info("gain should be set to %s", float(gain))

    return loc, da
