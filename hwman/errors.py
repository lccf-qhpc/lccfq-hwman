"""Custom exceptions for hwman."""

class HwmanError(Exception):
    """Base exception for all hwman errors."""
    pass


class CompilerError(HwmanError):
    """Base exception for compiler-related errors."""
    pass


class UnsupportedGateError(CompilerError):
    """Raised when a gate symbol is not in the GATE_LIBRARY."""

    def __init__(self, gate_symbol: str, supported_gates: list[str]):
        self.gate_symbol = gate_symbol
        self.supported_gates = supported_gates
        super().__init__(
            f"Unsupported gate '{gate_symbol}'. "
            f"Supported gates: {', '.join(supported_gates)}"
        )


class TwoQubitGateNotImplementedError(CompilerError):
    """Raised when a gate is not implemented for two-qubit gates."""
    pass


class CircuitMissingMeasurementError(CompilerError):
    """Raised when a circuit is missing a measurement gate."""
    pass

