import logging
from pathlib import Path
from concurrent import futures

import grpc

from hwman.certificates.certificate_manager import CertificateManager
from hwman.grpc.protobufs_compiled import health_pb2_grpc
from hwman.services.health import HealthService

logger = logging.getLogger(__name__)


class Server:
    def __init__(self, address: str = "localhost", port: int=50001, cert_dir: str | Path = "./certs"):

        self.address = address
        self.port = port
        self.cert_dir = Path(cert_dir)

        self.server_cert = None
        self.server_key = None
        self.ca_cert = None

        self.grpc_server: grpc.Server | None = None

    def _initialize_certificates(self):

        logger.info("Initializing certificates...")

        # Initialize certificate manager
        cert_manager = CertificateManager(self.cert_dir)

        # Set up CA and server certificates (creates them if they don't exist)
        ca_cert_file, server_cert_file, server_key_file = cert_manager.setup_ca_and_server(
            self.address
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

    def serve(self):

        logger.info(f"Serving on {self.address}:{self.port}")

        server_credentials = grpc.ssl_server_credentials(
            private_key_certificate_chain_pairs=[(self.server_key, self.server_cert)],
            root_certificates=self.ca_cert,
            require_client_auth=True,
        )

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

        # Add services
        health_pb2_grpc.add_HealthDispatchServicer_to_server(HealthService(), server)

        logger.info("Server instantiated, adding mtls channel.")

        server.add_secure_port(f"[::]:{self.port}", server_credentials)

        logger.info(f"Secure port added: {self.address}:{self.port}. starting server.")

        server.start()

        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            logger.info("Server stopped by user.")
            server.stop(0)



















