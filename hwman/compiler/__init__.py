"""
Quantum instruction compiler for QICK programs.

This package compiles Circuit objects (containing Gate objects) into QICK programs.

Usage:
    from hwman.compiler import compile_circuit_to_qick
    from hwman.services.circuits import Circuit
    from lccfq_backend.model.tasks import Gate

    gates = [
        Gate(symbol="X", target_qubits=[0], control_qubits=[], params=[]),
        Gate(symbol="measure", target_qubits=[0], control_qubits=[], params=[]),
    ]
    circuit = Circuit(gates=gates, shots=1000, pid="my-circuit")
    program_code = compile_circuit_to_qick(circuit, class_name="MyProgram")

    # program_code now contains Python source for a QICK AveragerProgramV2 class
"""

from hwman.compiler.qick_codegen import compile_circuit_to_qick, QICKProgramGenerator

__all__ = ['compile_circuit_to_qick', 'QICKProgramGenerator']