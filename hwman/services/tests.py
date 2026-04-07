"""
Service for executing already predefined measurements scripts and sequences. Usually dedicated to existing tuneup and characterization.
"""

import logging
from typing import Any
from pathlib import Path
import time
import Pyro4

import grpc

import labcore.protocols.base as labcore_base
from labcore.protocols.base import PlatformTypes

from cqedtoolbox.protocols.operations import (
    ResonatorSpectroscopy,
    ResonatorSpectroscopyVsGain,
    SaturationSpectroscopy,
    PowerRabi as PowerRabiOperation,
    PiSpectroscopy,
    ResonatorSpectroscopyAfterPi,
    T1Operation,
    T2ROperation,
    T2EOperation,
    ReadoutCalibration,
)

from hwman.grpc.protobufs_compiled.test_pb2_grpc import TestServicer  # type: ignore
from hwman.grpc.protobufs_compiled.test_pb2 import TestRequest, TestResponse, TestType, FitParameter, ResSpecResponse  # type: ignore

from hwman.services import Service

from hwman.utils.hw_tests import setup_measurement_env, generate_id, set_bandpass_filters

logger = logging.getLogger(__name__)


# TODO: Implement health checks before running measurements.
#  At the moment everything is done assuming that all the external resources are available and ok.
class TestService(Service, TestServicer):
    NUMBER_OF_RETRIES = 10

    def __init__(self, data_dir: Path, params_file: Path | None = None, fake_calibration_data: bool = False, *args: Any, **kwargs: Any) -> None:
        logger.info("Initializing TestService")
        super().__init__(*args, **kwargs)
        self.data_dir = data_dir
        self.params_file = params_file
        self.fake_calibration_data = fake_calibration_data
        self.params = None

    def _start(self) -> None:
        if self.fake_calibration_data:
            self.params = None
            logger.info("Fake calibration mode: skipping hardware setup")
            return

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
        self.params = conf.params

        # Once connection to qick is OK, set the bandpass filters
        set_bandpass_filters(conf)

        logger.info(f"TestService initialized with data_dir: {self.data_dir}")

    def _make_operation(self, op_class):
        """Set the labcore global platform type and instantiate the operation.

        PLATFORMTYPE must be set before the operation class is instantiated because
        ProtocolParameterBase reads the global in __post_init__ to decide which
        hardware backend (QICK or DUMMY) each parameter will use. The platform is
        controlled by the `fake_calibration_data` flag in config.toml: when True,
        synthetic data is generated without any hardware; when False, real QICK
        hardware is used.
        """
        labcore_base.PLATFORMTYPE = (
            PlatformTypes.DUMMY if self.fake_calibration_data else PlatformTypes.QICK
        )
        return op_class(self.params)

    def StandardTest(
        self, request: TestRequest, context: grpc.ServicerContext
    ) -> TestResponse:
        logger.info(
            f"Received request to perform {request.test_type} test for {request.pid}"
        )

        test_type = request.test_type
        pid = request.pid
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

    def _save_params_if_requested(self, request: TestRequest) -> None:
        if request.save_to_file:
            logger.info(f"Saving parameters to {self.params_file}")
            self.params.toFile(filePath=self.params_file)

    def ResSpecCal(self, request: TestRequest, context: grpc.ServicerContext) -> ResSpecResponse:
        job_id = request.pid or generate_id()
        logger.info("ResSpecCal called")
        try:
            op = self._make_operation(ResonatorSpectroscopy)
            op.execute()
            self._save_params_if_requested(request)
            fit_params = self._assemble_fit_params(op.fit_result)
            return ResSpecResponse(
                pid=job_id, status=True,
                f=fit_params["f_0"].value,
                error=fit_params["f_0"].error,
                snr=op.snr,
            )
        except Exception as e:
            logger.error(e)
            return ResSpecResponse(status=False, pid=job_id)

    def ResSpecVsGainCal(self, request: TestRequest, context: grpc.ServicerContext) -> TestResponse:
        job_id = request.pid or generate_id()
        logger.info("ResSpecVsGainCal called")
        op = self._make_operation(ResonatorSpectroscopyVsGain)
        op.execute()
        self._save_params_if_requested(request)
        logger.info("ResSpecVsGainCal finished")
        return TestResponse(status=True)

    def SatSpec(self, request: TestRequest, context: grpc.ServicerContext) -> TestResponse:
        job_id = request.pid or generate_id()
        logger.info("SatSpec called")
        op = self._make_operation(SaturationSpectroscopy)
        op.execute()
        self._save_params_if_requested(request)
        logger.info("SatSpec finished")
        return TestResponse(status=True)

    def PowerRabi(self, request: TestRequest, context: grpc.ServicerContext) -> TestResponse:
        job_id = request.pid or generate_id()
        logger.info("PowerRabi called")
        op = self._make_operation(PowerRabiOperation)
        op.execute()
        self._save_params_if_requested(request)
        logger.info("PowerRabi finished")
        return TestResponse(status=True)

    def PiSpec(self, request: TestRequest, context: grpc.ServicerContext) -> TestResponse:
        job_id = request.pid or generate_id()
        logger.info("PiSpec called")
        op = self._make_operation(PiSpectroscopy)
        op.execute()
        self._save_params_if_requested(request)
        logger.info("PiSpec finished")
        return TestResponse(status=True)

    def ResSpecAfterPi(self, request, context):
        job_id = request.pid or generate_id()
        logger.info("ResSpecAfterPi called")
        op = self._make_operation(ResonatorSpectroscopyAfterPi)
        op.execute()
        self._save_params_if_requested(request)
        logger.info("ResSpecAfterPi finished")
        return TestResponse(status=True)

    def T1(self, request: TestRequest, context: grpc.ServicerContext) -> TestResponse:
        job_id = request.pid or generate_id()
        logger.info("T1 called")
        op = self._make_operation(T1Operation)
        op.execute()
        self._save_params_if_requested(request)
        logger.info("T1 finished")
        return TestResponse(status=True)

    def T2R(self, request: TestRequest, context: grpc.ServicerContext) -> TestResponse:
        job_id = request.pid or generate_id()
        logger.info("T2R called")
        op = self._make_operation(T2ROperation)
        op.execute()
        self._save_params_if_requested(request)
        logger.info("T2R finished")
        return TestResponse(status=True)

    def T2E(self, request: TestRequest, context: grpc.ServicerContext) -> TestResponse:
        job_id = request.pid or generate_id()
        logger.info("T2E called")
        op = self._make_operation(T2EOperation)
        op.execute()
        self._save_params_if_requested(request)
        logger.info("T2E finished")
        return TestResponse(status=True)

    def ROCal(self, request: TestRequest, context: grpc.ServicerContext) -> TestResponse:
        job_id = request.pid or generate_id()
        logger.info("ROCal called")
        op = self._make_operation(ReadoutCalibration)
        op.execute()
        self._save_params_if_requested(request)
        logger.info("ROCal finished")
        return TestResponse(status=True)

    def TuneUpProtocol(self, request, context):
        logger.info("TuneUpProtocol called")
        job_id = request.pid or generate_id()

        from cqedtoolbox.protocols.qubit_tuneup import QubitTuneup

        op = QubitTuneup(self.params)
        op.execute()
        self._save_params_if_requested(request)
        logger.info("TuneUpProtocol finished")
        return TestResponse(status=True, pid=job_id)
