import logging
import os
import pickle
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from multiprocessing import Pool, cpu_count
from typing import Any, Dict, List, Tuple, Union

import matplotlib

matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


@dataclass
class PlotItem:
    x: Any
    y: Any
    z: Any = None  # For 2D colorbar plots
    plot_type: str = "line"  # "line" or "colorbar"
    kwargs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlotSpec:
    plot_path: str
    title: str = ""
    xlabel: str = ""
    ylabel: str = ""
    legend: bool = False
    figsize: Tuple[float, float] = (10, 6)
    plots: List[PlotItem] = field(default_factory=list)


# Global process pool for plotting
_plotting_pool: Union[Pool, None] = None


def _get_plotting_pool():
    """Get or create a process pool for plotting."""
    global _plotting_pool
    if _plotting_pool is None:
        # Use 2 processes for plotting to avoid overwhelming the system
        _plotting_pool = Pool(processes=min(2, cpu_count()), maxtasksperchild=10)
    return _plotting_pool

def _plot_worker(plot_spec: PlotSpec):
    """
    Generic worker function that runs in a separate process to create plots.
    This avoids matplotlib threading issues.
    """
    try:
        fig, ax = plt.subplots(figsize=plot_spec.figsize)

        if plot_spec.title:
            ax.set_title(plot_spec.title)
        if plot_spec.xlabel:
            ax.set_xlabel(plot_spec.xlabel)
        if plot_spec.ylabel:
            ax.set_ylabel(plot_spec.ylabel)

        for plot_item in plot_spec.plots:
            if plot_item.plot_type == "colorbar":
                # For colorbar plots, x and y are coordinates, z is the values
                # Extract colorbar-specific kwargs
                colorbar_kwargs = {}
                plot_kwargs = plot_item.kwargs.copy()
                if 'colorbar_label' in plot_kwargs:
                    colorbar_kwargs['label'] = plot_kwargs.pop('colorbar_label')
                
                im = ax.pcolormesh(plot_item.x, plot_item.y, plot_item.z, **plot_kwargs)
                cbar = fig.colorbar(im, ax=ax)
                
                # Apply colorbar label if provided
                if 'label' in colorbar_kwargs:
                    cbar.set_label(colorbar_kwargs['label'])
            else:
                # Default line plot
                ax.plot(plot_item.x, plot_item.y, **plot_item.kwargs)

        if plot_spec.legend:
            ax.legend()

        fig.savefig(plot_spec.plot_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return True
    except Exception as e:
        print(f"Error in plotting worker: {e}")
        return False


def create_plot_in_subprocess(plot_spec: PlotSpec):
    """
    Fallback thread-safe plotting using a subprocess to isolate matplotlib.
    """
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pkl') as tmp_file:
        pickle.dump(plot_spec, tmp_file)
        tmp_path = tmp_file.name

    plot_script = f'''
import pickle
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

@dataclass
class PlotItem:
    x: Any
    y: Any
    z: Any = None  # For 2D colorbar plots
    plot_type: str = "line"  # "line" or "colorbar"
    kwargs: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PlotSpec:
    plot_path: str
    title: str = ""
    xlabel: str = ""
    ylabel: str = ""
    legend: bool = False
    figsize: Tuple[float, float] = (10, 6)
    plots: List[PlotItem] = field(default_factory=list)

try:
    with open(\'{tmp_path}\', \'rb\') as f:
        spec = pickle.load(f)

    fig, ax = plt.subplots(figsize=spec.figsize)
    if spec.title:
        ax.set_title(spec.title)
    if spec.xlabel:
        ax.set_xlabel(spec.xlabel)
    if spec.ylabel:
        ax.set_ylabel(spec.ylabel)
    for item in spec.plots:
        if item.plot_type == "colorbar":
            # For colorbar plots, x and y are coordinates, z is the values
            # Extract colorbar-specific kwargs
            colorbar_kwargs = {{}}
            plot_kwargs = item.kwargs.copy()
            if 'colorbar_label' in plot_kwargs:
                colorbar_kwargs['label'] = plot_kwargs.pop('colorbar_label')
            
            im = ax.pcolormesh(item.x, item.y, item.z, **plot_kwargs)
            cbar = fig.colorbar(im, ax=ax)
            
            # Apply colorbar label if provided
            if 'label' in colorbar_kwargs:
                cbar.set_label(colorbar_kwargs['label'])
        else:
            # Default line plot
            ax.plot(item.x, item.y, **item.kwargs)
    if spec.legend:
        ax.legend()
    fig.savefig(spec.plot_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {{e}}")
'''
    try:
        result = subprocess.run(
            [sys.executable, '-c', plot_script],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and "SUCCESS" in result.stdout:
            return True
        else:
            logger.error(f"Plotting subprocess failed: {result.stderr} \n result.stdout: {result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Plotting subprocess timed out")
        return False
    except Exception as e:
        logger.error(f"Error running plotting subprocess: {e}")
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def cleanup_plotting_pool():
    """Clean up the plotting process pool."""
    global _plotting_pool
    if _plotting_pool is not None:
        _plotting_pool.close()
        _plotting_pool.join()
        _plotting_pool = None
