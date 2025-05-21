"""
Filename: setup_measurements.py
Author: Marcos Frenkel
Date: 2025-05-20
Version: 1.0
Description:
    This file holds all the code necessary to set a default environment for .

License: Apache 2.0
Contact: marcosf2@illinois.edu
"""

from pathlib import Path

from labcore.data.datadict import DataDict
from labcore.measurement.sweep import Sweep
from labcore.measurement.storage import run_and_save_sweep

DATADIR = "./data"


def execute_measurement(sweep: Sweep, name: str) -> tuple[Path, DataDict]:
    """
    Wrapper function to execute measurements.

    All measurements pass through this function to automate the collection of metadata at the beginning and end of the measurement.
    The location of the data is specified by the module level variable DATADIR.

    :param sweep: Sweep object to be executed.
    :param name: Name of the measurement.
    """

    # Metadata collection should happen before the measurement

    data_location, data = run_and_save_sweep(
        sweep=sweep, name=name, data_dir=DATADIR, return_data=True
    )

    assert data is not None
    data_location = Path(data_location)

    return data_location, data
    