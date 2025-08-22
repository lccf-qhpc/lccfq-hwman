
import os
import logging
import threading
import subprocess
import sys
import pickle
import tempfile
from pathlib import Path
from multiprocessing import Pool, cpu_count

# Set environment variables before importing scientific libraries
os.environ['HDF5_USE_FILE_LOCKING'] = 'FALSE'  # Disable HDF5 file locking
os.environ['OPENBLAS_NUM_THREADS'] = '1'  # Limit OpenBLAS threads
os.environ['MKL_NUM_THREADS'] = '1'  # Limit MKL threads
os.environ['OMP_NUM_THREADS'] = '1'  # Limit OpenMP threads
os.environ['NUMEXPR_NUM_THREADS'] = '1'  # Limit NumExpr threads

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

from labcore.data.datadict_storage import load_as_xr, datadict_from_hdf5

from qcui_analysis.fitfuncs.resonators import HangerResponseBruno

# Global process pool for plotting (more efficient than subprocess)
_plotting_pool = None

def _get_plotting_pool():
    """Get or create a process pool for plotting."""
    global _plotting_pool
    if _plotting_pool is None:
        # Use 2 processes for plotting to avoid overwhelming the system
        _plotting_pool = Pool(processes=min(2, cpu_count()), maxtasksperchild=10)
    return _plotting_pool

def _plot_worker(plot_data):
    """
    Worker function that runs in a separate process to create plots.
    This avoids matplotlib threading issues completely.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        
        freqs = plot_data['freqs']
        signal = plot_data['signal']
        fitcurve = plot_data['fitcurve']
        plot_path = plot_data['plot_path']
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.set_title("Resonator Fit")
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("Signal (A.U.)")
        ax.plot(freqs, np.abs(signal), label='Data')
        ax.plot(freqs, np.abs(fitcurve), label='Fit')
        ax.legend()
        
        fig.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return True
    except Exception as e:
        print(f"Error in plotting worker: {e}")
        return False

def create_plot_process_pool(freqs, signal, fitcurve, plot_path):
    """
    Create plot using multiprocessing pool - more efficient than subprocess.
    This avoids matplotlib threading issues while being faster than subprocesses.
    """
    try:
        pool = _get_plotting_pool()
        
        plot_data = {
            'freqs': freqs,
            'signal': signal,
            'fitcurve': fitcurve,
            'plot_path': str(plot_path)
        }
        
        # Use apply_async with timeout to avoid hanging
        result = pool.apply_async(_plot_worker, (plot_data,))
        
        # Wait for result with timeout
        success = result.get(timeout=30)
        return success
        
    except Exception as e:
        logger.error(f"Error in process pool plotting: {e}")
        return False

# Keep the old subprocess function as fallback
def create_plot_safe(freqs, signal, fitcurve, plot_path):
    """
    Thread-safe plotting using subprocess to completely isolate matplotlib.
    This is kept as a fallback option.
    """
    # Create a temporary file to pass data to subprocess
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pkl') as tmp_file:
        plot_data = {
            'freqs': freqs,
            'signal': signal,
            'fitcurve': fitcurve,
            'plot_path': str(plot_path)
        }
        pickle.dump(plot_data, tmp_file)
        tmp_path = tmp_file.name
    
    # Create a small Python script to run in subprocess
    plot_script = f'''
import pickle
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Load data
with open('{tmp_path}', 'rb') as f:
    data = pickle.load(f)

freqs = data['freqs']
signal = data['signal']
fitcurve = data['fitcurve']
plot_path = data['plot_path']

try:
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_title("Resonator Fit")
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Signal (A.U.)")
    ax.plot(freqs, np.abs(signal), label='Data')
    ax.plot(freqs, np.abs(fitcurve), label='Fit')
    ax.legend()
    
    fig.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {{e}}")
'''
    
    try:
        # Run the plotting in a separate process
        result = subprocess.run(
            [sys.executable, '-c', plot_script],
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )
        
        # Clean up temporary file
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        if result.returncode == 0 and "SUCCESS" in result.stdout:
            return True
        else:
            logger.error(f"Plotting subprocess failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("Plotting subprocess timed out")
        return False
    except Exception as e:
        logger.error(f"Error running plotting subprocess: {e}")
        return False

def cleanup_plotting_pool():
    """Clean up the plotting process pool."""
    global _plotting_pool
    if _plotting_pool is not None:
        _plotting_pool.close()
        _plotting_pool.join()
        _plotting_pool = None


@staticmethod
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

    data = datadict_from_hdf5(Path(loc/"data.ddh5"))
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

    # Try process pool plotting first, fallback to subprocess if needed
    plot_success = create_plot_process_pool(freqs, signal, fitcurve, plot_path)
    
    if not plot_success:
        logger.warning("Process pool plotting failed, trying subprocess fallback...")
        plot_success = create_plot_safe(freqs, signal, fitcurve, plot_path)
    
    if plot_success:
        logger.info(f"Plot saved to {plot_path}")
    else:
        logger.warning(f"Failed to create plot at {plot_path}")

    logger.info(f"Resonator spec completed successfully. Resonant frequency: {res_f} MHz")
    return {"resonant_frequency": res_f, "data_path": str(loc), "plot_path": str(plot_path)}
