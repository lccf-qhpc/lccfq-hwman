import logging
from pathlib import Path

import grpc

from hwman.grpc.protobufs_compiled.health_pb2_grpc import HealthStub  # type: ignore
from hwman.grpc.protobufs_compiled.health_pb2 import Ping, HealthRequest  # type: ignore
from hwman.grpc.protobufs_compiled.test_pb2_grpc import TestStub  # type: ignore
from hwman.grpc.protobufs_compiled.test_pb2 import TestRequest, TestType  # type: ignore
from hwman.certificates.certificate_manager import CertificateManager


logger = logging.getLogger(__name__)


class Client:
    def __init__(
        self,
        name: str = "default",
        address: str = "localhost",
        port: int = 50222,
        clients_cert_dir: str | Path = "./certs/clients",
        ca_cert_path: str | Path = "./certs/ca.crt",
        initialize_at_start: bool = True,
    ):
        self.name = name
        self.address = address
        self.port = port

        self.ca_cert_path = Path(ca_cert_path)

        self.client_cert_path = Path(clients_cert_dir) / f"{name}.crt"
        self.client_key_path = Path(clients_cert_dir) / f"{name}.key"

        self.ca_cert: bytes | None = None
        self.client_cert: bytes | None = None
        self.client_key: bytes | None = None

        self.health_stub: HealthStub | None = None
        self.test_stub: TestStub | None = None

        self._initialize_certificates()

        # Initialize the channel
        self.channel = None
        self.credentials = None
        if initialize_at_start:
            self.initialize()

    def _initialize_certificates(self) -> None:
        if not self.ca_cert_path.exists():
            logger.error(f"CA certificate file not found: {self.ca_cert_path}")
            raise FileNotFoundError(
                f"CA certificate file not found: {self.ca_cert_path}"
            )

        if not self.client_cert_path.exists() or not self.client_key_path.exists():
            logger.info(
                f"Certificates files not found for client creating them: {self.client_cert_path}, {self.client_key_path}"
            )

            self.certificate_manager = CertificateManager(self.ca_cert_path.parent)
            self.certificate_manager.create_client_certificate(self.name)

        try:
            with open(self.ca_cert_path, "rb") as f:
                self.ca_cert = f.read()
        except FileNotFoundError as e:
            logger.error(f"CA certificate file not found: {self.ca_cert_path}")
            raise e
        try:
            with open(self.client_cert_path, "rb") as f:
                self.client_cert = f.read()
        except FileNotFoundError as e:
            logger.error(f"Client certificate file not found: {self.client_cert_path}")
            raise e
        try:
            with open(self.client_key_path, "rb") as f:
                self.client_key = f.read()
        except FileNotFoundError as e:
            logger.error(f"Client key file not found: {self.client_key_path}")
            raise e

    def initialize(self) -> None:
        logger.info(
            f"Initializing {self.name} secure channel to {self.address}:{self.port}"
        )

        self.credentials = grpc.ssl_channel_credentials(
            root_certificates=self.ca_cert,
            private_key=self.client_key,
            certificate_chain=self.client_cert,
        )

        self.channel = grpc.secure_channel(
            f"{self.address}:{self.port}", self.credentials
        )
        logger.info(
            f"Secure channel initialized for {self.name} to {self.address}:{self.port}"
        )

        self.health_stub = HealthStub(self.channel)
        self.test_stub = TestStub(self.channel)

    def ping_server(self) -> str | None:
        try:
            assert self.health_stub is not None, "Health stub is not initialized"
            response = self.health_stub.TestPing(Ping(message="Ping from client"))
            return response.message
        except grpc.RpcError as e:
            logger.error(f"Failed to ping server: {e}")
            return None

    def check_instrumentserver_status(self) -> str | None:
        """
        Check the status of the instrumentserver.
        This method should be implemented to interact with the instrumentserver.
        """
        try:
            assert self.health_stub is not None, "Health stub is not initialized"
            response = self.health_stub.GetInstrumentServerStatus(HealthRequest())
            if response.success:
                return f"Instrumentserver is running: {response.is_running}, Message: {response.message}"
            else:
                return f"Instrumentserver is not running, Message: {response.message}"
        except grpc.RpcError as e:
            logger.error(f"Failed to check instrumentserver status: {e}")
            return None

    def start_instrumentserver(self) -> str | None:
        """
        Start the instrumentserver.
        This method should be implemented to interact with the instrumentserver.
        """
        try:
            assert self.health_stub is not None, "Health stub is not initialized"
            response = self.health_stub.StartInstrumentServer(HealthRequest())
            if response.success:
                return f"Instrumentserver started successfully: {response.is_running}, Message: {response.message}"
            else:
                return f"Failed to start instrumentserver, Message: {response.message}"
        except grpc.RpcError as e:
            logger.error(f"Failed to start instrumentserver: {e}")
            return None

    def stop_instrumentserver(self) -> str | None:
        """
        Stop the instrumentserver.
        This method should be implemented to interact with the instrumentserver.
        """
        try:
            assert self.health_stub is not None, "Health stub is not initialized"
            response = self.health_stub.StopInstrumentServer(HealthRequest())
            if response.success:
                return f"Instrumentserver stopped successfully: {response.is_running}, Message: {response.message}"
            else:
                return f"Failed to stop instrumentserver, Message: {response.message}"
        except grpc.RpcError as e:
            logger.error(f"Failed to stop instrumentserver: {e}")
            return None

    def start_nameserver(self) -> str | None:
        """
        Start the nameserver.
        This method should be implemented to interact with the nameserver.
        """
        try:
            assert self.health_stub is not None, "Health stub is not initialized"
            response = self.health_stub.StartPyroNameserver(HealthRequest())
            if response.success:
                return f"Nameserver started successfully: {response.is_running}, Message: {response.message}"
            else:
                return f"Failed to start nameserver, Message: {response.message}"
        except grpc.RpcError as e:
            logger.error(f"Failed to start nameserver: {e}")
            return None

    def stop_nameserver(self) -> str | None:
        """
        Stop the nameserver.
        This method should be implemented to interact with the nameserver.
        """
        try:
            assert self.health_stub is not None, "Health stub is not initialized"
            response = self.health_stub.StopPyroNameserver(HealthRequest())
            if response.success:
                return f"Nameserver stopped successfully: {response.is_running}, Message: {response.message}"
            else:
                return f"Failed to stop nameserver, Message: {response.message}"
        except grpc.RpcError as e:
            logger.error(f"Failed to stop nameserver: {e}")
            return None

    def check_nameserver_status(self) -> str | None:
        """
        Check the status of the nameserver.
        This method should be implemented to interact with the nameserver.
        """
        try:
            assert self.health_stub is not None, "Health stub is not initialized"
            response = self.health_stub.GetPyroNameserverStatus(HealthRequest())
            if response.success:
                return f"Nameserver is running: {response.is_running}, Message: {response.message}"
            else:
                return f"Nameserver is not running, Message: {response.message}"
        except grpc.RpcError as e:
            logger.error(f"Failed to check nameserver status: {e}")
            return None

    def start_test(self, test_type: TestType, pid: str) -> str | None:
        try:
            assert self.test_stub is not None, "Test stub is not initialized"
            self.test_stub.StandardTest(
                TestRequest(test_type=test_type, pid=pid)
            )
            return None
        except grpc.RpcError as e:
            logger.error(f"Failed to start test: {e}")
            return None

    def start_res_spec(self) -> str | None:
        try:
            assert self.test_stub is not None, "Test stub is not initialized"
            ret = self.test_stub.ResSpecCal(
                TestRequest()
            )
            return ret
        except grpc.RpcError as e:
            logger.error(f"Failed to start test: {e}")
            return None

    def start_res_spec_vs_gain(self) -> str | None:
        try:
            assert self.test_stub is not None, "Test stub is not initialized"
            ret = self.test_stub.ResSpecVsGainCal(
                TestRequest()
            )
            return ret
        except grpc.RpcError as e:
            logger.error(f"Failed to start test: {e}")
            return None

    def start_sat_spec(self) -> str | None:
        try:
            assert self.test_stub is not None, "Test stub is not initialized"
            ret = self.test_stub.SatSpec(
                TestRequest()
            )
            return ret
        except grpc.RpcError as e:
            logger.error(f"Failed to start test: {e}")
            return None
