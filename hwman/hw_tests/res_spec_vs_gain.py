import logging
from pathlib import Path

import numpy as np

from hwman.hw_tests.utils import QickConfig
from hwman.utils.plotting import PlotSpec, PlotItem, create_plot_in_subprocess
from labcore.measurement.storage import run_and_save_sweep
from labcore.data.datadict_storage import datadict_from_hdf5
from qcui_measurement.qick.single_transmon_v2 import FreqGainSweepProgram

logger = logging.getLogger(__name__)


def measure_res_spec_vs_gain(job_id: str):

    logger.info("Starting resonator spectroscopy vs gain for {}".format(job_id))
    sweep = FreqGainSweepProgram()
    logger.debug("Sweep created, running measurement")
    loc, da = run_and_save_sweep(sweep, "data", f"resonator_spec_vs_gain~{job_id}", return_data=True)
    logger.info("Measurement done, data in %s", loc)

    return loc, da


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

def plot_magnitude_colorbar(loc: Path):
    """
    Load data and create a colorbar plot of the magnitude data.
    Similar to hvplot.quadmesh() but using our subprocess plotting system.
    """
    logger.info("Creating magnitude colorbar plot")
    
    if not loc.exists():
        msg = f"Location {loc} does not exist"
        raise FileNotFoundError(msg)
    
    # Load the data
    data = datadict_from_hdf5(loc/"data.ddh5")
    
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
    
    plot_filename = "magnitude_colorbar.png"
    plot_path = loc / plot_filename
    
    plot_spec = PlotSpec(
        plot_path=str(plot_path),
        title="Signal Magnitude",
        xlabel="Frequency (MHz)",
        ylabel="Gain",
        plots=[colorbar_item]
    )
    
    success = create_plot_in_subprocess(plot_spec)
    
    if success:
        logger.info(f"Magnitude colorbar plot saved to {plot_path}")
    else:
        logger.error("Failed to create magnitude colorbar plot")
    
    return success


def res_spec_vs_gain(job_id: str):
    loc, da = measure_res_spec_vs_gain(job_id)
    # fit_result, residuals, snr = analyze_res_spec(loc)
    
    # Create magnitude colorbar plot
    plot_magnitude_colorbar(loc)
    
    return loc, da
