"""
Service for executing already predefined measurements scripts and sequences. Usually dedicated to existing tuneup and characterization.
"""

import logging
from typing import Any
from pathlib import Path

import grpc

from qcui_measurement.qick.single_transmon_v2 import FreqSweepProgram
from labcore.measurement.storage import run_and_save_sweep

from hwman.grpc.protobufs_compiled.test_pb2_grpc import TestServicer  # type: ignore
from hwman.grpc.protobufs_compiled.test_pb2 import TestRequest, TestResponse, TestType  # type: ignore

from hwman.services import Service


logger = logging.getLogger(__name__)


# TODO: Implement health checks before running measurements.
#  At the moment everything is done assuming that all the external resources are available and ok.
class TestService(Service, TestServicer):
    def __init__(self, data_dir: Path, *args: Any, **kwargs: Any) -> None:
        logger.info("Initializing TestService")
        super().__init__(*args, **kwargs)
        self.data_dir = data_dir

    def _start(self) -> None:
        # Import is here and not at top because my_experiment_setup checks that the instrumentserver is running.
        # This happens before StandardService is initialized but after the server imports this module.
        try:
            from hwman.services.my_experiment_setup import conf
        except ImportError as e:
            logger.error("Could not import my_experiment_setup.py")
            raise e

        # Checks that the parameter manager is running and all of the correct parameters are present.
        try:
            conf.config()
        except Exception as e:
            logger.error("Could not configure parameter manager")
            raise e

        self.conf = conf
        logger.info(f"TestService initialized with data_dir: {self.data_dir}")

    def _perform_measurement(self, measurement_type: TestType, pid: str):
        from hwman.services import my_experiment_setup

        match measurement_type:
            case TestType.RESONATOR_SPEC:
                program = FreqSweepProgram()
                loc = run_and_save_sweep(program, self.data_dir, pid)

        return

    def StandardTest(
        self, request: TestRequest, context: grpc.ServicerContext
    ) -> TestResponse:
        test_type = request.test_type
        pid = request.pid
        self._perform_measurement(test_type, pid)
        ret = TestResponse(
            status=True,
            data_path=str(self.data_dir / pid),
            pid=pid,
        )
        return ret

    def start(
        self, request: TestRequest, context: grpc.ServicerContext
    ) -> TestResponse:
        self._start()
        return TestResponse()

    def cleanup(self) -> None: ...
