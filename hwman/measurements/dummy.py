"""
Filename: dummy.py
Author: Marcos Frenkel
Date: 2025-05-20
Version: 1.0
Description:
    This file holds dummy measurements for the LCCF Hardware manager.

License: Apache 2.0
Contact: marcosf2@illinois.edu
"""

from random import randint

from labcore.measurement.sweep import sweep_parameter
from labcore.measurement.record import recording, dependent


def generate_dummy_sweep():
    @recording(dependent("dummy_data"))
    def dummy_data_generator():
        return randint(0, 10)

    sweep = sweep_parameter("dummy_axis", range(0, 10), dummy_data_generator)
    return sweep
