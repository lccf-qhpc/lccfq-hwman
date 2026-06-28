"""
Tests for rendering pulse timelines, including custom pulse envelopes.
"""

import numpy as np
import pytest

from lccfq_backend.model.tasks import Gate

from hwman.compiler.circuit import Circuit
from hwman.compiler.custom_pulses import CustomPulseDefinition
from hwman.compiler.pulse_diagram import build_circuit_waveforms, build_pulse_events


def _custom_circuit() -> tuple[Circuit, dict[str, CustomPulseDefinition]]:
    pulse = CustomPulseDefinition(
        name="my_custom",
        idata=[0.0, 0.5, 1.0, 0.5, 0.0],
        qdata=[0.0, 0.0, 0.0, 0.0, 0.0],
        sample_rate_msps=1000.0,
    )
    gates = [
        Gate(symbol="my_custom", target_qubits=[0], control_qubits=[], params=[]),
        Gate(symbol="measure", target_qubits=[0], control_qubits=[], params=[]),
    ]
    circuit = Circuit(gates=gates, shots=10, pid="t")
    return circuit, {"my_custom": pulse}


def test_build_pulse_events_uses_custom_pulse_duration():
    circuit, custom_pulses = _custom_circuit()
    events = build_pulse_events(circuit, custom_pulses=custom_pulses)

    custom_event = next(e for e in events if e.row_key == "q0")
    assert custom_event.shape == "custom"
    assert custom_event.duration == pytest.approx(5 / 1000.0)
    assert custom_event.envelope is not None
    assert custom_event.envelope.name == "my_custom"


def test_build_circuit_waveforms_samples_custom_envelope():
    circuit, custom_pulses = _custom_circuit()
    waveforms = build_circuit_waveforms(circuit, custom_pulses=custom_pulses)

    custom_waveform = waveforms["q0"][0]
    assert custom_waveform.shape == "custom"
    # idata peaks at its middle sample (value 1.0); the rendered envelope
    # should peak near the middle too, scaled down by the default gain (<1).
    peak_idx = np.argmax(custom_waveform.samples)
    assert 0 < peak_idx < len(custom_waveform.samples) - 1
    assert 0 < custom_waveform.samples.max() < 1.0
