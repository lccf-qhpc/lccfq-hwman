import logging
from pathlib import Path
from concurrent import futures

import grpc

from hwman.certificates.certificate_manager import CertificateManager
from hwman.grpc.protobufs_compiled import health_pb2_grpc, test_pb2_grpc
from hwman.services.health import HealthService
from hwman.services.tests import TestService

logger = logging.getLogger(__name__)


# FIXME: The default values for these should be with their respective services, not in the main server class.
class Server:
    def __init__(
        self,
        address: str = "localhost",
        port: int = 50001,
        cert_dir: str | Path = "./certs",
        instrumentserver_config_file: str | Path = "./configs/serverConfig.yml",
        instrumentserver_params_file: str
        | Path = "./configs/parameter_manager-parameter_manager.json",
        proxy_ns_name: str = "rfsoc",
        ns_host: str = "localhost",
        ns_port: int = 8888,
        data_dir: str | Path = "./data",
        fake_calibration_data: bool = False,
        start_external_services: bool = True,
    ):
        self.address = address
        self.port = port
        self.cert_dir = Path(cert_dir)
        self.instrumentserver_config_file = Path(instrumentserver_config_file)
        self.instrumentserver_params_file = Path(instrumentserver_params_file)
        self.proxy_ns_name = proxy_ns_name
        self.ns_host = ns_host
        self.ns_port = ns_port
        self.start_external_services = start_external_services

        self.fake_calibration_data = fake_calibration_data

        self.server_cert: bytes | None = None
        self.server_key: bytes | None = None
        self.ca_cert: bytes | None = None

        self.data_dir = Path(data_dir)

        self.health_service: HealthService | None = None
        self.test_service: TestService | None = None

        self.server: grpc.Server | None = None

    def _initialize_certificates(self) -> None:
        logger.info("Initializing certificates...")

        # Initialize certificate manager
        cert_manager = CertificateManager(self.cert_dir)

        # Set up CA and server certificates (creates them if they don't exist)
        ca_cert_file, server_cert_file, server_key_file = (
            cert_manager.setup_ca_and_server(self.address)
        )

        # Load the certificates for gRPC
        try:
            with open(server_cert_file, "rb") as f:
                self.server_cert = f.read()
        except FileNotFoundError as e:
            logger.error(f"Server certificate file not found: {server_cert_file}")
            raise e
        try:
            with open(server_key_file, "rb") as f:
                self.server_key = f.read()
        except FileNotFoundError as e:
            logger.error(f"Server key file not found: {server_key_file}")
            raise e
        try:
            with open(ca_cert_file, "rb") as f:
                self.ca_cert = f.read()
        except FileNotFoundError as e:
            logger.error(f"CA certificate file not found: {ca_cert_file}")
            raise e

        logger.info("Certificates initialized successfully.")

    def _initialize_services(self) -> None:
        # Add services

        logger.info("Initializing health service...")
        self.health_service = HealthService(
            self.instrumentserver_config_file,
            self.instrumentserver_params_file,
            self.proxy_ns_name,
            self.ns_host,
            self.ns_port,
        )
        health_pb2_grpc.add_HealthServicer_to_server(self.health_service, self.server)

        if self.start_external_services:
            self.health_service._start_instrumentserver()
            self.health_service._start_pyro_nameserver()
            self.health_service._start_qick_server()

        logger.info("Initializing test service...")
        self.test_service = TestService(self.data_dir, fake_calibration_data=self.fake_calibration_data)
        test_pb2_grpc.add_TestServicer_to_server(self.test_service, self.server)
        self.test_service._start()

        logger.info("Services initialized successfully.")

    def serve(self) -> None:
        try:
            logger.info(f"Serving on {self.address}:{self.port}")

            server_credentials = grpc.ssl_server_credentials(
                private_key_certificate_chain_pairs=[
                    (self.server_key, self.server_cert)
                ],
                root_certificates=self.ca_cert,
                require_client_auth=True,
            )

            self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

            logger.info("Server instantiated, adding mtls channel.")

            self.server.add_secure_port(f"[::]:{self.port}", server_credentials)

            logger.info(
                f"Secure port added: {self.address}:{self.port}. starting server."
            )

            self._initialize_services()

            logger.info("Starting health check...")
            assert self.health_service is not None, "Health service is not initialized"
            all_ok = self.health_service.health_check()
            logger.info(f"Health check result: {all_ok}")

            self.server.start()

            self.server.wait_for_termination()
        except KeyboardInterrupt:
            logger.info("Server stopped by user.")
        except Exception as e:
            logger.error(f"Server stopped with error: {e}")
            raise e
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up server resources.")
        if self.server:
            self.server.stop(0)
            self.server = None
        if self.health_service:
            self.health_service.cleanup()
            self.health_service = None
        logger.info("Server resources cleaned up successfully.")
