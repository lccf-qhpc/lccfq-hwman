import logging
from pathlib import Path

from hwman.hw_tests.res_spec import res_spec


logger = logging.getLogger(__name__)


def render_report():
    ...


def full_calibration(job_id: str, fake_calibration_data: bool = False):



    res_spec_ret = res_spec(job_id, fake_calibration_data)













