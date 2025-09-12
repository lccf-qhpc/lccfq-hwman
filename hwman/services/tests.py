"""
Service for executing already predefined measurements scripts and sequences. Usually dedicated to existing tuneup and characterization.
"""

import logging
from typing import Any
from pathlib import Path
import time
import Pyro4

import grpc

from labcore.measurement.storage import run_and_save_sweep

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

# This needs to be imported before any other subprocesses start.
from qcui_analysis.fitfuncs.resonators import HangerResponseBruno  # noqa: F401  # Required for side effects

from hwman.grpc.protobufs_compiled.test_pb2_grpc import TestServicer  # type: ignore
from hwman.grpc.protobufs_compiled.test_pb2 import TestRequest, TestResponse, TestType, FitParameter  # type: ignore


from hwman.services import Service
from hwman.hw_tests.res_spec import res_spec
from hwman.hw_tests.utils import setup_measurement_env, generate_id

logger = logging.getLogger(__name__)


# TODO: Implement health checks before running measurements.
#  At the moment everything is done assuming that all the external resources are available and ok.
class TestService(Service, TestServicer):
    NUMBER_OF_RETRIES = 10

    def __init__(self, data_dir: Path, *args: Any, **kwargs: Any) -> None:
        logger.info("Initializing TestService")
        super().__init__(*args, **kwargs)
        self.data_dir = data_dir

    def _start(self) -> None:
        try:
            conf = setup_measurement_env()
        except Exception as e:
            logger.error("Could not import my_experiment_setup.py")
            raise e

        # Checks connection to qick is ok.
        retries = 0
        while retries < self.NUMBER_OF_RETRIES:
            try:
                logger.info("Attempting to connect to qick")
                conf.config()
                logger.info("Connected to qick")
            except Pyro4.errors.NamingError:
                logger.warning(
                    f"Could not connect to qick, Probably still starting up, retrying in 1 second. Times attempted: {retries}"
                )
                time.sleep(5)
                retries += 1
            else:
                break

        self.conf = conf

        logger.info(f"TestService initialized with data_dir: {self.data_dir}")

    def _perform_measurement(self, measurement_type: TestType, pid: str) -> None:

        match measurement_type:
            case TestType.RESONATOR_SPEC:
                program = FreqSweepProgram()
            case TestType.PULSE_PROBE_SPECTROSCOPY:
                program = PulseProbeSpectroscopy()
            case TestType.POWER_RABI:
                program = AmplitudeRabiProgram()
            case TestType.PI_SPEC:
                program = PiSpecProgram()
            case TestType.RESONATOR_SPEC_AFTER_PI:
                program = ResProbeProgram()
            case TestType.T1:
                program = T1Program()
            case TestType.T2R:
                program = T2RProgram()
            case TestType.T2E:
                program = T2nProgram()

        run_and_save_sweep(program, str(self.data_dir), pid)

        return

    def StandardTest(
        self, request: TestRequest, context: grpc.ServicerContext
    ) -> TestResponse:
        logger.info(
            f"Received request to perform {request.test_type} test for {request.pid}"
        )

        test_type = request.test_type
        pid = request.pid
        self._perform_measurement(test_type, pid)
        ret = TestResponse(
            status=True,
            data_path=str(self.data_dir / pid),
            pid=pid,
        )
        logger.info(f"Test completed for {request.pid} data in {self.data_dir / pid}")
        return ret

    def start(
        self, request: TestRequest, context: grpc.ServicerContext
    ) -> TestResponse:
        self._start()
        return TestResponse()

    def cleanup(self) -> None: ...

    @staticmethod
    def _assemble_fit_params(fit_result) -> dict:
        """Convert lmfit ModelResult to protobuf FitParameter format."""
        fit_params = {}
        for name, param in fit_result.params.items():
            fit_params[name] = FitParameter(
                name=name,
                value=param.value,
                error=param.stderr if param.stderr is not None else 0.0
            )
        return fit_params


    def ResSpecCal(self, request: TestRequest, context: grpc.ServicerContext) -> TestResponse:
        job_id = request.pid
        if job_id is None or "":
            job_id = generate_id()
        logger.info("ResSpecCal called")

        try:
            loc, fit_result, snr = res_spec(self.conf, job_id)
            logger.info("ResSpecCal finished")
            fit_params = self._assemble_fit_params(fit_result)

            return TestResponse(pid=job_id, status=True, data_path=str(loc), snr=snr, fit_parameters=fit_params)
        except Exception as e:
            logger.error(e)
            return TestResponse(status=False, data_path=str(self.data_dir), pid=job_id)


