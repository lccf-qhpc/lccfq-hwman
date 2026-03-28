"""
Tests for QICK code generation from Circuit objects.
"""

import numpy as np

from lccfq_backend.model.tasks import Gate
from hwman.services.circuits import Circuit
from hwman.compiler.qick_codegen import compile_circuit_to_qick


def test_rx_measure_circuit():
    """Test generating QICK code for RX(pi) followed by measurement."""
    g0 = Gate(symbol="rx", target_qubits=[0], control_qubits=[], params=[np.pi])
    g1 = Gate(symbol="measure", target_qubits=[0], control_qubits=[], params=[])
    circuit = Circuit(gates=[g0, g1], shots=1000, pid="test-rx-measure")

    code = compile_circuit_to_qick(circuit, "RXMeasureProgram")

    print("\n" + "=" * 80)
    print("Generated QICK Program:")
    print("=" * 80)
    print(code)
    print("=" * 80 + "\n")

    assert code is not None
    assert len(code) > 0


def test_multi_qubit_measurement_order():
    """Test that ComplexQICKData entries appear in measurement order."""
    # Measure qubit 2 first, then qubit 0
    g0 = Gate(symbol="x", target_qubits=[0], control_qubits=[], params=[])
    g1 = Gate(symbol="x", target_qubits=[2], control_qubits=[], params=[])
    g2 = Gate(symbol="measure", target_qubits=[2], control_qubits=[], params=[])
    g3 = Gate(symbol="measure", target_qubits=[0], control_qubits=[], params=[])
    circuit = Circuit(gates=[g0, g1, g2, g3], shots=1000, pid="test-multi-qubit")

    code = compile_circuit_to_qick(circuit, "MultiQubitProgram")

    print("\n" + "=" * 80)
    print("Generated QICK Program (Multi-Qubit Measurement Order):")
    print("=" * 80)
    print(code)
    print("=" * 80 + "\n")

    # Verify qubit_2 comes before qubit_0 in the decorator
    idx_qubit_2 = code.find("ComplexQICKData('qubit_2'")
    idx_qubit_0 = code.find("ComplexQICKData('qubit_0'")
    assert idx_qubit_2 < idx_qubit_0, "qubit_2 should be measured before qubit_0"