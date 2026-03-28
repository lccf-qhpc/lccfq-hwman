import logging
from pathlib import Path

import grpc

from hwman.grpc.protobufs_compiled.health_pb2_grpc import HealthStub  # type: ignore
from hwman.grpc.protobufs_compiled.health_pb2 import Ping, HealthRequest  # type: ignore
from hwman.grpc.protobufs_compiled.test_pb2_grpc import TestStub  # type: ignore
from hwman.grpc.protobufs_compiled.test_pb2 import TestRequest, TestType  # type: ignore
from hwman.grpc.protobufs_compiled.circuits_pb2_grpc import CircuitsStub  # type: ignore
from hwman.grpc.protobufs_compiled.circuits_pb2 import RunCircuitRequest, RunCircuitResponse, Gate  # type: ignore


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
        self.circuits_stub: CircuitsStub | None = None

        self._initialize_certificates()

        # Initialize the channel
        self.channel = None
        self.credentials = None
        if initialize_at_start:
            self.initialize()

    def _initialize_certificates(self) -> None:
        """
        Load client certificates for mTLS authentication.

        Required files:
        - CA certificate (ca.crt): The CA's public certificate to verify the server
        - Client certificate ({name}.crt): This client's certificate, signed by the CA
        - Client key ({name}.key): This client's private key

        Note: Client certificates must be pre-generated on the hwman server and
        distributed to clients. The CA private key should never leave the server.
        Use `CertificateManager.create_client_certificate(name)` on the server
        to generate client certificates.
        """
        # Check all required files exist before loading any
        missing_files = []

        if not self.ca_cert_path.exists():
            missing_files.append(f"CA certificate: {self.ca_cert_path}")

        if not self.client_cert_path.exists():
            missing_files.append(f"Client certificate: {self.client_cert_path}")

        if not self.client_key_path.exists():
            missing_files.append(f"Client key: {self.client_key_path}")

        if missing_files:
            error_msg = (
                "Missing required certificate files for mTLS authentication:\n"
                + "\n".join(f"  - {f}" for f in missing_files)
                + "\n\nClient certificates must be generated on the hwman server "
                "and copied to the client. On the server, run:\n"
                f"  CertificateManager(cert_dir).create_client_certificate('{self.name}')\n"
                "Then copy ca.crt and the client cert/key files to the client machine."
            )
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # Load the certificates
        with open(self.ca_cert_path, "rb") as f:
            self.ca_cert = f.read()
        logger.debug(f"Loaded CA certificate from {self.ca_cert_path}")

        with open(self.client_cert_path, "rb") as f:
            self.client_cert = f.read()
        logger.debug(f"Loaded client certificate from {self.client_cert_path}")

        with open(self.client_key_path, "rb") as f:
            self.client_key = f.read()
        logger.debug(f"Loaded client key from {self.client_key_path}")

        logger.info(f"Successfully loaded certificates for client '{self.name}'")

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
        self.circuits_stub = CircuitsStub(self.channel)

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

    def start_power_rabi(self) -> str | None:
        try:
            assert self.test_stub is not None, "Test stub is not initialized"
            ret = self.test_stub.PowerRabi(
                TestRequest()
            )
            return ret
        except grpc.RpcError as e:
            logger.error(f"Failed to start test: {e}")
            return None

    def start_pi_spec(self) -> str | None:
        try:
            assert self.test_stub is not None, "Test stub is not initialized"
            ret = self.test_stub.PiSpec(
                TestRequest()
            )
            return ret
        except grpc.RpcError as e:
            logger.error(f"Failed to start test: {e}")

    def start_res_spec_after_pi(self) -> str | None:
        try:
            assert self.test_stub is not None, "Test stub is not initialized"
            ret = self.test_stub.ResSpecAfterPi(
                TestRequest()
            )
            return ret
        except grpc.RpcError as e:
            logger.error(f"Failed to start test: {e}")

    def start_t1(self) -> str | None:
        try:
            assert self.test_stub is not None, "Test stub is not initialized"
            ret = self.test_stub.T1(
                TestRequest()
            )
            return ret
        except grpc.RpcError as e:
            logger.error(f"Failed to start test: {e}")

    def start_t2r(self) -> str | None:
        try:
            assert self.test_stub is not None, "Test stub is not initialized"
            ret = self.test_stub.T2R(
                TestRequest()
            )
            return ret
        except grpc.RpcError as e:
            logger.error(f"Failed to start test: {e}")

    def start_t2e(self) -> str | None:
        try:
            assert self.test_stub is not None, "Test stub is not initialized"
            ret = self.test_stub.T2E(
                TestRequest()
            )
            return ret
        except grpc.RpcError as e:
            logger.error(f"Failed to start test: {e}")

    def start_ro_cal(self) -> str | None:
        try:
            assert self.test_stub is not None, "Test stub is not initialized"
            ret = self.test_stub.ROCal(
                TestRequest()
            )
            return ret
        except grpc.RpcError as e:
            logger.error(f"Failed to start test: {e}")

    def start_tuneup_protocol(self):
        try:
            assert self.test_stub is not None, "Test stub is not initialized"
            ret = self.test_stub.TuneUpProtocol(
                TestRequest()
            )
            return ret
        except grpc.RpcError as e:
            logger.error(f"Failed to start test: {e}")

    def run_circuit(
        self,
        gates: list[dict],
        shots: int,
        pid: str = "",
    ) -> dict[str, int] | None:
        """
        Execute a quantum circuit on the QPU.

        Args:
            gates: List of gate dictionaries with keys:
                - symbol: Gate name (e.g., "H", "CNOT", "RZ")
                - target_qubits: List of target qubit indices
                - control_qubits: List of control qubit indices (optional)
                - params: List of gate parameters (optional)
            shots: Number of measurement shots
            pid: Optional process/job ID for tracking

        Returns:
            Dictionary mapping bitstring outcomes to counts, or None on error

        Example:
            >>> gates = [
            ...     {"symbol": "H", "target_qubits": [0], "control_qubits": [], "params": []},
            ...     {"symbol": "CNOT", "target_qubits": [1], "control_qubits": [0], "params": []},
            ... ]
            >>> result = client.run_circuit(gates, shots=1000)
            >>> print(result)  # {"00": 512, "11": 488}
        """
        try:
            assert self.circuits_stub is not None, "Circuits stub is not initialized"

            # Convert gate dicts to proto Gate messages
            proto_gates = [
                Gate(
                    symbol=g["symbol"],
                    target_qubits=g.get("target_qubits", []),
                    control_qubits=g.get("control_qubits", []),
                    params=g.get("params", []),
                )
                for g in gates
            ]

            request = RunCircuitRequest(
                pid=pid,
                gates=proto_gates,
                shots=shots,
            )

            response: RunCircuitResponse = self.circuits_stub.RunCircuit(request)

            if not response.success:
                logger.error(f"Circuit execution failed: {response.message}")
                return None

            # Convert distribution entries to dict
            distribution = {
                entry.bitstring: entry.count
                for entry in response.distribution
            }

            return distribution

        except grpc.RpcError as e:
            logger.error(f"Failed to run circuit: {e}")
            return None