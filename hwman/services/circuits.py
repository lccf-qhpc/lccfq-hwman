"""
Service for executing quantum circuits on the QPU hardware.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List
from pathlib import Path

import grpc

from hwman.grpc.protobufs_compiled.circuits_pb2_grpc import CircuitsServicer  # type: ignore
from hwman.grpc.protobufs_compiled.circuits_pb2 import (  # type: ignore
    RunCircuitRequest,
    RunCircuitResponse,
    DistributionEntry,
    Gate as ProtoGate,
)
from hwman.services import Service
from hwman.hw_tests.utils import generate_id

# Import Gate model from lccfq-backend for internal representation
from lccfq_backend.model.tasks import Gate

logger = logging.getLogger(__name__)


@dataclass
class Circuit:
    """
    Internal representation of a quantum circuit for compilation.

    This wraps the gates received from gRPC in a form suitable for
    passing to the QICK compiler.
    """

    gates: List[Gate]
    shots: int
    pid: str = ""

    def __len__(self) -> int:
        return len(self.gates)

    def __iter__(self):
        return iter(self.gates)

    @classmethod
    def from_proto(cls, request: RunCircuitRequest) -> "Circuit":
        """
        Create a Circuit from a gRPC RunCircuitRequest.

        Converts protobuf Gate messages to internal Gate models.
        """
        gates = [
            Gate(
                symbol=g.symbol,
                target_qubits=list(g.target_qubits),
                control_qubits=list(g.control_qubits),
                params=list(g.params),
            )
            for g in request.gates
        ]
        return cls(gates=gates, shots=request.shots, pid=request.pid)


class CircuitService(Service, CircuitsServicer):
    """Service for executing quantum circuits on QPU hardware."""

    def __init__(
        self,
        data_dir: Path,
        fake_circuit_data: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the CircuitService.

        Args:
            data_dir: Directory for storing circuit execution results
            fake_circuit_data: If True, return mock data instead of executing on hardware
        """
        logger.info("Initializing CircuitService")
        super().__init__(*args, **kwargs)
        self.data_dir = data_dir
        self.fake_circuit_data = fake_circuit_data

    def _start(self) -> None:
        """Initialize the circuit execution environment."""
        logger.info(f"CircuitService started with data_dir: {self.data_dir}")
        # TODO: Initialize QICK connection for circuit execution if needed
        # The TestService handles QICK connection setup, so we may be able to
        # reuse that connection or initialize separately here.

    def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("CircuitService cleanup")

    def RunCircuit(
        self, request: RunCircuitRequest, context: grpc.ServicerContext
    ) -> RunCircuitResponse:
        """
        Execute a quantum circuit on the QPU.

        Args:
            request: RunCircuitRequest containing gates and shots
            context: gRPC service context

        Returns:
            RunCircuitResponse with measurement distribution
        """
        pid = request.pid
        if not pid:
            pid = generate_id()

        logger.info(
            f"RunCircuit called: pid={pid}, gates={len(request.gates)}, shots={request.shots}"
        )

        # Log the gates for debugging
        for i, gate in enumerate(request.gates):
            logger.debug(
                f"  Gate {i}: {gate.symbol} "
                f"targets={list(gate.target_qubits)} "
                f"controls={list(gate.control_qubits)} "
                f"params={list(gate.params)}"
            )

        # Validate inputs
        if request.shots <= 0:
            logger.error(f"Invalid shots value: {request.shots}")
            return RunCircuitResponse(
                pid=pid,
                success=False,
                message=f"Invalid shots value: {request.shots}. Must be positive.",
                distribution=[],
            )

        if len(request.gates) == 0:
            logger.warning(f"Empty circuit received for pid={pid}")
            return RunCircuitResponse(
                pid=pid,
                success=False,
                message="Circuit must contain at least one gate.",
                distribution=[],
            )

        try:
            # Convert proto request to internal Circuit representation
            circuit = Circuit.from_proto(request)
            circuit.pid = pid  # Use generated pid if not provided

            if self.fake_circuit_data:
                # Return mock data for testing
                distribution = self._generate_fake_distribution(circuit.shots)
            else:
                # Execute on real hardware
                distribution = self._execute_circuit(circuit)

            # Convert distribution dict to proto format
            distribution_entries = [
                DistributionEntry(bitstring=bitstring, count=count)
                for bitstring, count in distribution.items()
            ]

            logger.info(f"Circuit execution completed: pid={pid}")
            return RunCircuitResponse(
                pid=pid,
                success=True,
                message="Circuit executed successfully",
                distribution=distribution_entries,
                data_path=str(self.data_dir / pid),
            )

        except Exception as e:
            logger.error(f"Circuit execution failed for pid={pid}: {e}", exc_info=True)
            return RunCircuitResponse(
                pid=pid,
                success=False,
                message=f"Circuit execution failed: {str(e)}",
                distribution=[],
            )

    def _execute_circuit(self, circuit: Circuit) -> Dict[str, int]:
        """
        Execute a circuit on the QICK hardware.

        Args:
            circuit: Circuit object containing gates, shots, and pid

        Returns:
            Dictionary mapping bitstrings to counts

        Raises:
            NotImplementedError: Circuit execution on real hardware not yet implemented
        """
        # TODO: Implement actual circuit execution on QICK hardware
        # This would involve:
        # 1. Transpiling gates to QICK-compatible pulse sequences
        # 2. Loading the program onto the QICK board
        # 3. Running the experiment with the specified shots
        # 4. Collecting and processing measurement results
        #
        # Example transpilation mapping:
        # - "H" (Hadamard) -> RY(π/2) pulse
        # - "X" -> RX(π) pulse
        # - "RZ" -> Virtual Z rotation (phase update)
        # - "CNOT" -> Cross-resonance or iSWAP decomposition
        #
        # For now, raise NotImplementedError to indicate this needs implementation
        raise NotImplementedError(
            "Circuit execution on real QICK hardware is not yet implemented. "
            "Set fake_circuit_data=True for testing with mock data."
        )

    def _generate_fake_distribution(self, shots: int) -> Dict[str, int]:
        """
        Generate a fake measurement distribution for testing.

        Args:
            shots: Number of measurement shots

        Returns:
            Dictionary mapping bitstrings to counts
        """
        # Generate a simple fake distribution (Bell state-like)
        counts_00 = shots // 2
        counts_11 = shots - counts_00
        return {"00": counts_00, "11": counts_11}