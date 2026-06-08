"""
Pulse-diagram rendering for QICK circuits.

This module turns a :class:`~hwman.compiler.circuit.Circuit` into a true
waveform diagram: one row per physical channel (qubit DAC generators, the
readout DAC, and the readout ADC), with each pulse drawn as its actual
envelope (gaussian for qubit gates, constant for readout) along a shared time
axis.

The timeline is reconstructed directly from the gate list rather than from a
built QICK program, so no hardware or ``soccfg`` is required. This mirrors the
data-driven compilation in :mod:`hwman.compiler.circuit_program`: the same
``validate``/``_flatten_operations``/``_qubit_gen_ch`` helpers and
``GATE_LIBRARY`` are reused so the diagram always tracks the real gate
semantics.

Crucially, every ``(gate, target)`` operation in
:func:`~hwman.compiler.circuit_program.CircuitProgram._body` is followed by its
own ``delay_auto`` barrier, which serializes the entire circuit. We replay that
serialization with a single running time cursor.
"""

from dataclasses import dataclass
import pprint
from typing import Any, Dict, List, Optional

import numpy as np
import matplotlib
from matplotlib.figure import Figure

from hwman.compiler.circuit import Circuit
from hwman.compiler.circuit_program import (
    GATE_LIBRARY,
    MEASURE,
    CircuitProgram,
    _flatten_operations,
    unique_qubits,
    validate,
)

# Default tuning values, used to fill any keys missing from the caller's cfg so
# the diagram renders even with no config. Times are in microseconds, gains are
# normalized (0..1), frequencies in MHz. These are display defaults only and do
# not need to match any particular hardware.
_DEFAULT_CFG: Dict[str, Any] = {
    "q_pi_sigma": 0.05,
    "q_pi_n_sigma": 4,
    "q_pi_gain": 0.8,
    "q_freq": 4000.0,
    "ro_freq": 6000.0,
    "ro_gain": 0.4,
    "ro_len": 2.0,
    "trig_time": 0.5,
    "q_dac_ch": 0,
    "ro_dac_ch": 1,
    "ro_adc_ch": 0,
    # Sample rate for raw-waveform export, in samples per microsecond (Msps).
    "sample_rate_msps": 1000.0,
}

# Number of samples used to render a gaussian envelope.
_GAUSS_SAMPLES = 200

# Identifiers for the non-qubit rows so they sort after the qubit rows.
_RO_DAC_KEY = "ro_dac"
_RO_ADC_KEY = "ro_adc"


@dataclass
class PulseEvent:
    """A single pulse (or acquisition window) to draw on one channel row."""

    row_key: str  # grouping key: f"q{ch}", _RO_DAC_KEY, or _RO_ADC_KEY
    row_label: str  # human-readable y-axis label
    t_start: float  # microseconds
    duration: float  # microseconds
    amplitude: float  # normalized gain (0..1)
    shape: str  # 'gauss', 'const', or 'acquire'
    label: str  # gate annotation, e.g. "x", "rx", "y (φ=90°)"
    freq: float  # MHz (informational)
    phase: float  # radians (informational)


@dataclass
class Waveform:
    """Raw PCM samples for a single played pulse, with its start time.

    The samples are the real amplitude envelope (gaussian array or constant
    rectangle); ``freq`` and ``phase`` are carried as metadata rather than mixed
    into the samples. Only the played region is stored, so a channel's full
    timeline is the sparse list of these objects (no zeros in between).
    """

    row_key: str  # grouping key matching :class:`PulseEvent.row_key`
    row_label: str  # human-readable channel label
    t_start: float  # microseconds
    sample_rate: float  # samples per microsecond (Msps)
    samples: np.ndarray  # real envelope amplitudes (0..1)
    shape: str  # 'gauss' or 'const'
    label: str  # gate annotation
    freq: float  # MHz (informational)
    phase: float  # radians (informational)

    @property
    def t_end(self) -> float:
        """End time of the played region, in microseconds."""
        return self.t_start + len(self.samples) / self.sample_rate


def _resolve_cfg(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge the caller's cfg over the display defaults."""
    merged = dict(_DEFAULT_CFG)
    if cfg:
        merged.update(cfg)
    return merged


def _gate_label(symbol: str, phase: float) -> str:
    """Build a short annotation for a gate, noting non-zero phase."""
    if phase:
        return f"{symbol} (φ={np.degrees(phase):.0f}°)"
    return symbol


def build_pulse_events(circuit: Circuit, cfg: Optional[Dict[str, Any]] = None) -> List[PulseEvent]:
    """Reconstruct the per-channel pulse timeline for a circuit.

    Walks the flattened operation list exactly as
    :func:`~hwman.compiler.circuit_program.CircuitProgram._body` does, advancing
    a single time cursor past each pulse (replaying the ``delay_auto`` barrier
    that serializes every operation).

    Args:
        circuit: Circuit to render. Validated before use.
        cfg: Optional tuning values; missing keys fall back to display defaults.

    Returns:
        A list of :class:`PulseEvent` in execution order.
    """
    validate(circuit)
    cfg = _resolve_cfg(cfg)

    gauss_len = cfg["q_pi_n_sigma"] * cfg["q_pi_sigma"]
    events: List[PulseEvent] = []
    cursor = 0.0

    for gate, target, _ in _flatten_operations(circuit):
        symbol = gate.symbol.lower()
        gate_cfg = GATE_LIBRARY[symbol]

        if symbol == MEASURE:
            # Readout drive pulse on the readout DAC.
            events.append(
                PulseEvent(
                    row_key=_RO_DAC_KEY,
                    row_label=f"readout DAC (q{target})",
                    t_start=cursor,
                    duration=cfg["ro_len"],
                    amplitude=cfg["ro_gain"],
                    shape="const",
                    label="measure",
                    freq=cfg["ro_freq"],
                    phase=gate_cfg.phase,
                )
            )
            # ADC acquisition window, opened by the trigger at trig_time.
            events.append(
                PulseEvent(
                    row_key=_RO_ADC_KEY,
                    row_label="readout ADC",
                    t_start=cursor + cfg["trig_time"],
                    duration=cfg["ro_len"],
                    amplitude=1.0,
                    shape="acquire",
                    label=f"acquire (q{target})",
                    freq=cfg["ro_freq"],
                    phase=0.0,
                )
            )
            duration = cfg["ro_len"]
        else:
            gain = cfg["q_pi_gain"]
            if gate.params:
                gain = cfg["q_pi_gain"] * gate.params[0] / np.pi
            ch = CircuitProgram._qubit_gen_ch(cfg, target)
            events.append(
                PulseEvent(
                    row_key=f"q{ch}",
                    row_label=f"qubit DAC ch{ch} (q{target})",
                    t_start=cursor,
                    duration=gauss_len,
                    amplitude=gain,
                    shape="gauss",
                    label=_gate_label(symbol, gate_cfg.phase),
                    freq=cfg["q_freq"],
                    phase=gate_cfg.phase,
                )
            )
            duration = gauss_len

        # delay_auto barrier: the next operation starts after this one ends.
        cursor += duration

    return events


def _sample_event(event: PulseEvent, cfg: Dict[str, Any], sample_rate: float) -> np.ndarray:
    """Render one pulse event to a real amplitude-envelope sample array.

    Returns an empty array for events that are not played waveforms (e.g. the
    ADC ``acquire`` window).
    """
    n = max(1, int(round(event.duration * sample_rate)))
    t = event.t_start + np.arange(n) / sample_rate
    if event.shape == "gauss":
        sigma = cfg["q_pi_sigma"]
        center = event.t_start + event.duration / 2.0
        return event.amplitude * np.exp(-((t - center) ** 2) / (2.0 * sigma**2))
    if event.shape == "const":
        return np.full(n, float(event.amplitude))
    return np.empty(0)


def build_circuit_waveforms(
    circuit: Circuit, cfg: Optional[Dict[str, Any]] = None
) -> Dict[str, List[Waveform]]:
    """Reconstruct the sparse raw-waveform (PCM) data for a circuit.

    Each played pulse is sampled to a real amplitude envelope and returned with
    its start time. The result is grouped by channel and is sparse: only the
    played regions are stored (no zero-fill between pulses), so a qubit that
    plays two pulses yields a list of two :class:`Waveform` objects on its row.

    The sample rate is read from ``cfg['sample_rate_msps']`` (samples per
    microsecond), falling back to the module default. ADC acquisition windows
    are not played waveforms and are excluded.

    Args:
        circuit: Circuit to render. Validated before use.
        cfg: Optional tuning values; missing keys fall back to display defaults.

    Returns:
        A dict mapping channel ``row_key`` to a list of :class:`Waveform`
        objects in execution order.
    """
    resolved = _resolve_cfg(cfg)
    sample_rate = resolved["sample_rate_msps"]
    events = build_pulse_events(circuit, resolved)

    waveforms: Dict[str, List[Waveform]] = {}
    for event in events:
        if event.shape == "acquire":
            continue
        waveforms.setdefault(event.row_key, []).append(
            Waveform(
                row_key=event.row_key,
                row_label=event.row_label,
                t_start=event.t_start,
                sample_rate=sample_rate,
                samples=_sample_event(event, resolved, sample_rate),
                shape=event.shape,
                label=event.label,
                freq=event.freq,
                phase=event.phase,
            )
        )
    return waveforms


def _row_order(events: List[PulseEvent], circuit: Circuit, cfg: Dict[str, Any]) -> List[str]:
    """Return row keys top-to-bottom: qubit DACs (by channel), RO DAC, RO ADC."""
    qubit_chs = sorted({CircuitProgram._qubit_gen_ch(cfg, q) for q in unique_qubits(circuit)})
    order = [f"q{ch}" for ch in qubit_chs]
    present = {e.row_key for e in events}
    for key in (_RO_DAC_KEY, _RO_ADC_KEY):
        if key in present:
            order.append(key)
    # Keep only rows that actually have events, preserving order.
    return [k for k in order if k in present]


def _draw_event(ax: "matplotlib.axes.Axes", event: PulseEvent, cfg: Dict[str, Any]) -> None:
    """Draw a single pulse envelope onto its row axis."""
    if event.shape == "gauss":
        sigma = cfg["q_pi_sigma"]
        center = event.t_start + event.duration / 2.0
        t = np.linspace(event.t_start, event.t_start + event.duration, _GAUSS_SAMPLES)
        y = event.amplitude * np.exp(-((t - center) ** 2) / (2.0 * sigma**2))
        ax.fill_between(t, 0, y, alpha=0.4, color="tab:blue")
        ax.plot(t, y, color="tab:blue", linewidth=1.2)
    elif event.shape == "const":
        ax.fill_between(
            [event.t_start, event.t_start + event.duration],
            0,
            event.amplitude,
            alpha=0.4,
            color="tab:green",
            step="pre",
        )
        ax.plot(
            [event.t_start, event.t_start, event.t_start + event.duration, event.t_start + event.duration],
            [0, event.amplitude, event.amplitude, 0],
            color="tab:green",
            linewidth=1.2,
        )
    elif event.shape == "acquire":
        ax.axvspan(
            event.t_start,
            event.t_start + event.duration,
            color="tab:orange",
            alpha=0.25,
            hatch="//",
        )
        # Trigger marker at the start of the acquisition window.
        ax.axvline(event.t_start, color="tab:red", linewidth=1.0, linestyle="--")

    # Annotate the gate symbol above the pulse.
    peak = event.amplitude if event.shape != "acquire" else 1.0
    ax.annotate(
        event.label,
        xy=(event.t_start + event.duration / 2.0, peak),
        xytext=(0, 3),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=8,
    )


def plot_circuit_pulses(circuit: Circuit, cfg: Optional[Dict[str, Any]] = None) -> Figure:
    """Render a pulse diagram for a circuit and return the matplotlib Figure.

    Builds one stacked row per physical channel (qubit DAC generators, the
    readout DAC, and the readout ADC) and draws each pulse as its actual
    envelope along a shared time axis. No QICK hardware or ``soccfg`` is needed;
    timing and magnitudes are reconstructed from the gate list and ``cfg``.

    The caller is responsible for displaying or saving the returned Figure (the
    function never calls ``show``), so it works under any matplotlib backend.

    Args:
        circuit: Circuit to render. Validated before use.
        cfg: Optional tuning values (same keys read by
            :mod:`hwman.compiler.circuit_program`); missing keys fall back to
            display defaults.

    Returns:
        A :class:`matplotlib.figure.Figure` containing the pulse diagram.

    Raises:
        UnsupportedGateError, CircuitMissingMeasurementError,
        TwoQubitGateNotImplementedError: If the circuit is invalid.
    """
    import matplotlib.pyplot as plt

    resolved = _resolve_cfg(cfg)
    events = build_pulse_events(circuit, resolved)
    row_keys = _row_order(events, circuit, resolved)

    labels = {e.row_key: e.row_label for e in events}
    total_time = max((e.t_start + e.duration for e in events), default=1.0)

    fig, axes = plt.subplots(
        len(row_keys),
        1,
        sharex=True,
        figsize=(max(8.0, total_time * 1.5), 1.6 * len(row_keys) + 1.0),
        squeeze=False,
    )
    axes = axes[:, 0]

    row_to_ax = {key: axes[i] for i, key in enumerate(row_keys)}
    for event in events:
        if event.row_key in row_to_ax:
            _draw_event(row_to_ax[event.row_key], event, resolved)

    for key, ax in row_to_ax.items():
        ax.set_ylabel(labels[key], rotation=0, ha="right", va="center", fontsize=9)
        ax.set_yticks([])
        ax.set_xlim(-0.05 * total_time, total_time * 1.05)
        ax.grid(axis="x", linestyle=":", alpha=0.5)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.axhline(0, color="black", linewidth=0.8)

    axes[-1].set_xlabel("Time (µs)")
    title = "Pulse diagram"
    if circuit.pid:
        title += f"  ·  pid={circuit.pid}"
    title += f"  ·  shots={circuit.shots}"
    fig.suptitle(title, fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    return fig


if __name__ == "__main__":
    # Render the same sample circuit used by circuit_program.py to a PNG.
    matplotlib.use("Agg")
    from lccfq_backend.model.tasks import Gate

    test_gates = [
        Gate(symbol="X", target_qubits=[0], control_qubits=[], params=[]),
        Gate(symbol="X", target_qubits=[1], control_qubits=[], params=[]),
        Gate(symbol="Y", target_qubits=[2], control_qubits=[], params=[]),
        Gate(symbol="RX", target_qubits=[0], control_qubits=[], params=[1.57]),
        Gate(symbol="measure", target_qubits=[0], control_qubits=[], params=[]),
    ]
    test_circuit = Circuit(gates=test_gates, shots=1000, pid="test-001")

    # Give each qubit its own DAC channel so they render on separate rows.
    demo_cfg = {"q0_dac_ch": 0, "q1_dac_ch": 2, "q2_dac_ch": 3}

    figure = plot_circuit_pulses(test_circuit, demo_cfg)
    out_path = "pulse_diagram.png"
    figure.savefig(out_path, dpi=150)
    print(f"Wrote pulse diagram to {out_path}")

    # Sparse raw-waveform (PCM) export: one list of Waveforms per channel.
    waveforms = build_circuit_waveforms(test_circuit, demo_cfg)
    print("\nRaw waveforms (sparse):")
    for row_key, wfs in waveforms.items():
        print(f"  {row_key}:")
        for wf in wfs:
            print(
                f"    {wf.label:>12}  t=[{wf.t_start:.3f}, {wf.t_end:.3f}] µs"
                f"  {len(wf.samples)} samples @ {wf.sample_rate:g} Msps"
                f"  peak={wf.samples.max():.3f}"
            )

    pprint.pp(waveforms)
