
import os
import logging
from pathlib import Path

# Set environment variables before importing scientific libraries
os.environ['HDF5_USE_FILE_LOCKING'] = 'FALSE'  # Disable HDF5 file locking
os.environ['OPENBLAS_NUM_THREADS'] = '1'  # Limit OpenBLAS threads
os.environ['MKL_NUM_THREADS'] = '1'  # Limit MKL threads
os.environ['OMP_NUM_THREADS'] = '1'  # Limit OpenMP threads
os.environ['NUMEXPR_NUM_THREADS'] = '1'  # Limit NumExpr threads

import numpy as np
import xarray as xr

from hwman.utils.plotting import (
    create_plot_in_process,
    create_plot_in_subprocess,
    PlotSpec,
    PlotItem,
)

logger = logging.getLogger(__name__)

from labcore.data.datadict_storage import datadict_from_hdf5

from qcui_analysis.fitfuncs.resonators import HangerResponseBruno


def add_mag_and_phase(data: xr.Dataset):
    # FIXME: Make this a real exception instead of just exception
    if "signal_Re" not in data.dims or "signal_Im" not in data.dims:
        raise Exception("Signal and Imag dimensions not found.")

    data["signal"] = data["signal_Re"] + 1j * data["signal_Im"]
    data["magnitude"] = np.abs(data["signal"])
    data["phase"] = np.arctan2(data["signal_Im"], data["signal_Re"])
    return data


def analyze_res_spec(loc: Path, id_: str | None = None):
    logger.info("Starting to analyze Resonator Spec")

    # Generate ID if not provided
    import uuid
    if id_ is None:
        id_ = str(uuid.uuid4())[:8]

    data = datadict_from_hdf5(Path(loc / "data.ddh5"))
    logger.info(f"Resonator spectroscopy measurement done, data loaded from {loc}")

    # fit part
    signal = data["signal"]["values"]
    freqs = data["freq"]["values"]
    fit = HangerResponseBruno(freqs, signal)
    fitresult = fit.run(fit)
    fitcurve = fitresult.eval()
    res_f = fitresult.params["f_0"].value

    # Determine the directory to save the plot
    loc_path = Path(loc)
    if loc_path.is_dir():
        plot_dir = loc_path
    else:
        plot_dir = loc_path.parent

    plot_filename = f"resonator_spec_fit_{id_}.png"
    plot_path = plot_dir / plot_filename

    # Create plot using the new generic utility
    plot_spec = PlotSpec(
        plot_path=str(plot_path),
        title="Resonator Fit",
        xlabel="Frequency (MHz)",
        ylabel="Signal (A.U.)",
        legend=True,
        plots=[
            PlotItem(x=freqs, y=np.abs(signal), kwargs={'label': 'Data'}),
            PlotItem(x=freqs, y=np.abs(fitcurve), kwargs={'label': 'Fit'}),
        ]
    )

    # Try process pool plotting first, fallback to subprocess if needed
    plot_success = create_plot_in_process(plot_spec)

    if not plot_success:
        logger.warning("Process pool plotting failed, trying subprocess fallback...")
        plot_success = create_plot_in_subprocess(plot_spec)

    if plot_success:
        logger.info(f"Plot saved to {plot_path}")
    else:
        logger.warning(f"Failed to create plot at {plot_path}")

    logger.info(f"Resonator spec completed successfully. Resonant frequency: {res_f} MHz")
    return {"resonant_frequency": res_f, "data_path": str(loc), "plot_path": str(plot_path)}
