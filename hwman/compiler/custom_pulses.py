"""
Custom pulse envelopes, defined as named PCM (I/Q sample) data in JSON files.

A custom pulse is referenced from a circuit by using its ``name`` directly as
a gate symbol (e.g. ``Gate(symbol="my_drag_pulse", target_qubits=[0], ...)``).
:func:`~hwman.compiler.circuit_program.validate` accepts any symbol that is
either in ``GATE_LIBRARY`` or in the loaded custom pulse registry, and
:class:`~hwman.compiler.circuit_program.CircuitProgram` plays it as a
single-qubit drive pulse via QICK's ``add_envelope`` (the same mechanism used
for ``add_gauss``), scaled by the usual ``q_pi_gain``/params gain logic.

Each pulse lives in its own JSON file, one per file, in a directory pointed
to by ``HwmanSettings.custom_pulses_dir``. A pulse file looks like::

    {
      "name": "my_drag_pulse",
      "idata": [0.0, 0.2, 0.6, 1.0, 0.6, 0.2, 0.0],
      "qdata": [0.0, 0.05, 0.1, 0.0, -0.1, -0.05, 0.0],
      "sample_rate_msps": 1000.0
    }
"""

from pathlib import Path
from typing import Dict, List

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from hwman.errors import DuplicateCustomPulseError, InvalidCustomPulseError


class CustomPulseDefinition(BaseModel):
    """A named pulse envelope, given as raw I/Q PCM samples.

    ``idata``/``qdata`` are the normalized (unit-scale) in-phase and
    quadrature envelope samples; the overall pulse amplitude is applied
    on top of these by the gate's gain, exactly as with built-in envelopes.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1, description="Pulse name; gates reference it by this symbol")
    idata: List[float] = Field(..., min_length=1, description="In-phase (I) PCM samples")
    qdata: List[float] = Field(..., min_length=1, description="Quadrature (Q) PCM samples")
    sample_rate_msps: float = Field(
        default=1000.0,
        gt=0,
        description="Sample rate the data was recorded at, in samples per microsecond",
    )

    @model_validator(mode="after")
    def _check_equal_lengths(self) -> "CustomPulseDefinition":
        if len(self.idata) != len(self.qdata):
            raise ValueError(
                f"idata and qdata must have the same length, "
                f"got {len(self.idata)} and {len(self.qdata)}"
            )
        return self

    @property
    def duration_us(self) -> float:
        """Pulse duration in microseconds, derived from sample count and rate."""
        return len(self.idata) / self.sample_rate_msps

    def to_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(idata, qdata)`` as float arrays, ready for ``add_envelope``."""
        return np.asarray(self.idata, dtype=float), np.asarray(self.qdata, dtype=float)


def load_custom_pulse_file(path: Path) -> CustomPulseDefinition:
    """Load and validate a single custom pulse JSON file.

    Raises:
        InvalidCustomPulseError: If the file is missing, not valid JSON, or
            fails Pydantic validation.
    """
    try:
        text = path.read_text()
    except OSError as e:
        raise InvalidCustomPulseError(path, str(e)) from e

    try:
        return CustomPulseDefinition.model_validate_json(text)
    except ValidationError as e:
        raise InvalidCustomPulseError(path, str(e)) from e


def load_custom_pulses(directory: Path) -> Dict[str, CustomPulseDefinition]:
    """Load every ``*.json`` pulse file in ``directory`` into a name-keyed dict.

    Pulse names are matched case-insensitively against gate symbols, so they
    are stored lower-cased. Returns an empty dict if the directory does not
    exist (custom pulses are optional).

    Raises:
        InvalidCustomPulseError: If any file fails to load or validate.
        DuplicateCustomPulseError: If two files define the same pulse name.
    """
    pulses: Dict[str, CustomPulseDefinition] = {}
    sources: Dict[str, Path] = {}

    if not directory.exists():
        return pulses

    for path in sorted(directory.glob("*.json")):
        pulse = load_custom_pulse_file(path)
        key = pulse.name.lower()
        if key in pulses:
            raise DuplicateCustomPulseError(pulse.name, sources[key], path)
        pulses[key] = pulse
        sources[key] = path

    return pulses


# Module-level registry, populated once at server startup from
# HwmanSettings.custom_pulses_dir. Empty by default so existing circuits and
# tests that never touch custom pulses are unaffected.
_REGISTRY: Dict[str, CustomPulseDefinition] = {}


def set_custom_pulses(pulses: Dict[str, CustomPulseDefinition]) -> None:
    """Replace the active custom pulse registry (called once at startup)."""
    global _REGISTRY
    _REGISTRY = pulses


def get_custom_pulses() -> Dict[str, CustomPulseDefinition]:
    """Return the active custom pulse registry."""
    return _REGISTRY
