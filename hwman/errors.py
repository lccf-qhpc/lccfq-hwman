"""Custom exceptions for hwman."""

from pathlib import Path


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


class CustomPulseError(CompilerError):
    """Base exception for custom-pulse loading errors."""
    pass


class InvalidCustomPulseError(CustomPulseError):
    """Raised when a custom pulse JSON file fails Pydantic validation."""

    def __init__(self, path: Path, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Invalid custom pulse file '{path}': {reason}")


class DuplicateCustomPulseError(CustomPulseError):
    """Raised when two custom pulse files define the same pulse name."""

    def __init__(self, name: str, first_path: Path, second_path: Path):
        self.name = name
        self.first_path = first_path
        self.second_path = second_path
        super().__init__(
            f"Duplicate custom pulse name '{name}': defined in both "
            f"'{first_path}' and '{second_path}'"
        )

