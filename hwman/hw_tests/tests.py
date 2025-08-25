import logging
import threading

from hwman.hw_tests.analysis.basic_analysis import analyze_res_spec
from hwman.hw_tests.measurements.calibration import Calibration

logger = logging.getLogger(__file__)

def res_spect():
    """
    Run resonator spectroscopy measurement and analysis.
    """
    try:
        cal = Calibration()
        loc, _ = cal.resonator_spec()
        result = analyze_res_spec(loc)
        logger.info("Resonator spectroscopy completed successfully")
        return result
    except Exception as e:
        logger.error(f"Resonator spectroscopy failed: {e}")
        raise




