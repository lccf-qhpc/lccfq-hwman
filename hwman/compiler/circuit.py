"""
Internal representation of a quantum circuit for compilation.
"""

from dataclasses import dataclass
from typing import List

from lccfq_backend.model.tasks import Gate


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
    def from_proto(cls, request) -> "Circuit":
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
