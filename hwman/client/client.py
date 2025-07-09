import logging
from pathlib import Path

import grpc

from hwman.grpc.protobufs_compiled.health_pb2_grpc import HealthDispatchStub
from hwman.grpc.protobufs_compiled.health_pb2 import Ping
from hwman.certificates.certificate_manager import CertificateManager


logger = logging.getLogger(__name__)


class Client:

    def __init__(self, name: str = "default",
                 address: str = "localhost",
                 port: int = 50001,
                 clients_cert_dir: str | Path = "./certs/clients",
                 ca_cert_path: str | Path = "./certs/ca.crt",
                 initialize_at_start: bool = True):

        self.name = name
        self.address = address
        self.port = port

        self.ca_cert_path = Path(ca_cert_path)

        self.client_cert_path = Path(clients_cert_dir) / f"{name}.crt"
        self.client_key_path = Path(clients_cert_dir) / f"{name}.key"

        self.ca_cert = None
        self.client_cert = None
        self.client_key = None

        self._initialize_certificates()

        # Initialize the channel
        self.channel = None
        self.credentials = None
        if initialize_at_start:
            self.initialize()

    def _initialize_certificates(self):
        if not self.ca_cert_path.exists():
            logger.error(f"CA certificate file not found: {self.ca_cert_path}")
            raise FileNotFoundError(f"CA certificate file not found: {self.ca_cert_path}")

        if not self.client_cert_path.exists() or not self.client_key_path.exists():
            logger.info(F"Certificates files not found for client creating them: {self.client_cert_path}, {self.client_key_path}")

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

    def initialize(self):
        logger.info(f"Initializing {self.name} secure channel to {self.address}:{self.port}")

        self.credentials = grpc.ssl_channel_credentials(
            root_certificates=self.ca_cert,
            private_key=self.client_key,
            certificate_chain=self.client_cert,
        )

        self.channel = grpc.secure_channel(f"{self.address}:{self.port}", self.credentials)
        logger.info(f"Secure channel initialized for {self.name} to {self.address}:{self.port}")

    def ping_server(self):
        stub = HealthDispatchStub(self.channel)

        try:
            response = stub.TestPing(Ping(message="Ping from client"))
            return response.message
        except grpc.RpcError as e:
            logger.error(f"Failed to ping server: {e}")
            return None










