"""
Tests for loading and validating custom pulse definitions.
"""

import json
from pathlib import Path

import pytest

from hwman.compiler.custom_pulses import (
    CustomPulseDefinition,
    load_custom_pulse_file,
    load_custom_pulses,
)
from hwman.errors import DuplicateCustomPulseError, InvalidCustomPulseError


def _write_pulse(directory: Path, filename: str, **overrides) -> Path:
    payload = {
        "name": "my_pulse",
        "idata": [0.0, 0.5, 1.0, 0.5, 0.0],
        "qdata": [0.0, 0.1, 0.0, -0.1, 0.0],
    }
    payload.update(overrides)
    path = directory / filename
    path.write_text(json.dumps(payload))
    return path


def test_load_custom_pulse_file_valid(tmp_path: Path):
    path = _write_pulse(tmp_path, "my_pulse.json")
    pulse = load_custom_pulse_file(path)

    assert isinstance(pulse, CustomPulseDefinition)
    assert pulse.name == "my_pulse"
    assert len(pulse.idata) == 5
    assert pulse.sample_rate_msps == 1000.0
    assert pulse.duration_us == pytest.approx(5 / 1000.0)


def test_to_arrays_returns_float_ndarrays(tmp_path: Path):
    path = _write_pulse(tmp_path, "my_pulse.json")
    pulse = load_custom_pulse_file(path)
    idata, qdata = pulse.to_arrays()

    assert idata.tolist() == pulse.idata
    assert qdata.tolist() == pulse.qdata


def test_mismatched_lengths_rejected(tmp_path: Path):
    path = _write_pulse(tmp_path, "bad.json", qdata=[0.0, 0.1])
    with pytest.raises(InvalidCustomPulseError):
        load_custom_pulse_file(path)


def test_missing_file_rejected(tmp_path: Path):
    with pytest.raises(InvalidCustomPulseError):
        load_custom_pulse_file(tmp_path / "does_not_exist.json")


def test_load_custom_pulses_directory(tmp_path: Path):
    _write_pulse(tmp_path, "a.json", name="pulse_a")
    _write_pulse(tmp_path, "b.json", name="pulse_b")

    pulses = load_custom_pulses(tmp_path)

    assert set(pulses) == {"pulse_a", "pulse_b"}


def test_load_custom_pulses_missing_directory_returns_empty(tmp_path: Path):
    assert load_custom_pulses(tmp_path / "does_not_exist") == {}


def test_load_custom_pulses_rejects_duplicate_names(tmp_path: Path):
    _write_pulse(tmp_path, "a.json", name="dup")
    _write_pulse(tmp_path, "b.json", name="dup")

    with pytest.raises(DuplicateCustomPulseError):
        load_custom_pulses(tmp_path)


def test_pulse_names_match_case_insensitively(tmp_path: Path):
    _write_pulse(tmp_path, "a.json", name="MyPulse")
    pulses = load_custom_pulses(tmp_path)
    assert "mypulse" in pulses
