"""
Filename: dummy.py
Author: Marcos Frenkel
Date: 2025-08-18
Version: 1.0
Description:
    This file contains all the measurements needed to perform a full calibration and characterization.

License: Apache 2.0
Contact: marcosf2@illinois.edu
"""

import uuid
import logging
import threading



from labcore.setup_measurements import run_measurement
from qcui_measurement.qick.single_transmon_v2 import (
    FreqSweepProgram,
    PulseProbeSpectroscopy,
    AmplitudeRabiProgram,
    PiSpecProgram,
    ResProbeProgram,
    T1Program,
    T2RProgram,
    T2nProgram,
)

logger = logging.getLogger(__name__)



class Calibration:

    def __init__(self):
        logger.info("Initiating Calibration class")

        # Import statement needs to be in constructor because the server has not started when this file gets imported.
        # my_experiment_setup needs to be running once the server is responding
        from hwman.hw_tests.measurements.my_experiment_setup import conf
        self.conf = conf

        # FIXME: what can go wrong here? and how do we catch it?
        # Initialize the config
        self.conf.config()
        print("cmon soc", self.conf.soc)
        set_bandpass_filters(self.conf)

        logger.info("Done initiationg calibration class")

    def check_config_connection(self):
        return self.conf.config()


    def resonator_spec(self, id_: str | None = None):

        if id_ is None:
            id_ = generate_id()


        rspec = FreqSweepProgram()
        logger.info(f"Starting resonator spec with ID: {id_}")

        loc, da = run_measurement(rspec, f"Resonator_Spec~{id_}")
        logger.info(f"Measurement completed. Location: {loc}")

        return loc, da


