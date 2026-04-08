"""
Service for executing quantum circuits on the QPU hardware.
"""

import logging
from collections import Counter
from typing import Any, Dict, List
from pathlib import Path

import grpc

from labcore.measurement.storage import run_and_save_sweep
from labcore.data.datadict_storage import datadict_from_hdf5

from hwman.grpc.protobufs_compiled.circuits_pb2_grpc import CircuitsServicer  # type: ignore
from hwman.grpc.protobufs_compiled.circuits_pb2 import (  # type: ignore
    RunCircuitRequest,
    RunCircuitResponse,
    DistributionEntry,
    Gate as ProtoGate,
)
from hwman.services import Service
from hwman.services.readout_calibrator import ReadoutCalibrator
from hwman.utils.hw_tests import generate_id
from hwman.compiler.circuit import Circuit
from hwman.compiler.qick_codegen import QICKProgramGenerator, compile_circuit_to_qick

logger = logging.getLogger(__name__)


class CircuitService(Service, CircuitsServicer):
    """Service for executing quantum circuits on QPU hardware."""

    def __init__(
        self,
        data_dir: Path,
        fake_circuit_data: bool = False,
        calibrator: ReadoutCalibrator | None = None,
        conf: Any = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the CircuitService.

        Args:
            data_dir: Directory for storing circuit execution results
            fake_circuit_data: If True, return mock data instead of executing on hardware
            calibrator: Fitted ReadoutCalibrator for shot classification
            conf: QickConfig object providing the QICK hardware connection
        """
        logger.info("Initializing CircuitService")
        super().__init__(*args, **kwargs)
        self.data_dir = data_dir
        self.fake_circuit_data = fake_circuit_data
        self.calibrator = calibrator
        self.conf = conf

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
                distribution, raw_bitstream = self._generate_fake_distribution(circuit.shots)
            else:
                # Execute on real hardware
                distribution, raw_bitstream = self._execute_circuit(circuit)

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
                raw_bitstream=raw_bitstream,
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

    def _execute_circuit(self, circuit: Circuit) -> tuple[Dict[str, int], List[str]]:
        """
        Execute a circuit on the QICK hardware.

        Args:
            circuit: Circuit object containing gates, shots, and pid

        Returns:
            Dictionary mapping bitstrings to counts
        """
        if self.calibrator is None:
            raise RuntimeError(
                "ReadoutCalibrator is not fitted. Run ROCal before executing circuits."
            )
        if self.conf is None:
            raise RuntimeError(
                "No QICK connection available. Provide a conf object at initialization."
            )
        generator = QICKProgramGenerator(circuit)
        measured_qubits = generator._get_measured_qubits_in_order()

        source = compile_circuit_to_qick(circuit)

        ns: Dict[str, Any] = {}
        exec(source, ns)
        prev_reps = self.conf.params.qick.default_reps()
        self.conf.params.qick.default_reps(1)
        try:
            sweep = ns["CompiledProgram"]()
            data_loc, _ = run_and_save_sweep(sweep, str(self.data_dir), circuit.pid, source_code=str({source}))
        finally:
            self.conf.params.qick.default_reps(prev_reps)

        data = datadict_from_hdf5(Path(data_loc) / "data.ddh5")
        return self._label_shots(data, measured_qubits)

    def _label_shots(self, data: dict, measured_qubits: List[int]) -> tuple[Dict[str, int], List[str]]:
        """Convert raw QICK IQ data into a bitstring count distribution.

        Args:
            data: datadict from datadict_from_hdf5. Keys are "qubit_{q}"; each
                  entry's ["values"] is a complex numpy array of shape (shots,).
            measured_qubits: qubit indices in measurement order, matching the
                             ComplexQICKData variables in the generated program.

        Returns:
            Tuple of (counts dict mapping bitstrings to shot counts, raw per-shot bitstring list).

        Raises:
            RuntimeError: If the calibrator has not been fitted via ROCal.
        """
        labels_per_qubit = []
        for q in measured_qubits:
            raw = data[f"qubit_{q}"]["values"]  # complex array, shape (shots,)
            labels_per_qubit.append(self.calibrator.label(raw.real.flatten(), raw.imag.flatten()))

        n_shots = len(labels_per_qubit[0])
        bitstrings = [
            "".join(str(labels_per_qubit[qi][s]) for qi in range(len(measured_qubits)))
            for s in range(n_shots)
        ]

        return dict(Counter(bitstrings)), bitstrings

    def _generate_fake_distribution(self, shots: int) -> tuple[Dict[str, int], List[str]]:
        """
        Generate a fake measurement distribution for testing.

        Args:
            shots: Number of measurement shots

        Returns:
            Tuple of (counts dict, raw per-shot bitstring list).
        """
        counts_00 = shots // 2
        counts_11 = shots - counts_00
        raw_bitstream = ["00"] * counts_00 + ["11"] * counts_11
        return {"00": counts_00, "11": counts_11}, raw_bitstream