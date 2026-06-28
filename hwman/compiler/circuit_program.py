"""
Data-driven QICK circuit program.

This module turns a :class:`~hwman.compiler.circuit.Circuit` directly into a
runnable QICK ``Sweep`` object by driving the standard QICK API
(``add_gauss``/``add_pulse``/``pulse``/``trigger``/``delay_auto``) from the gate
list at runtime.
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

import numpy as np

from qick.asm_v2 import AveragerProgramV2
from cqedtoolbox.instruments.qick.qick_sweep_v2 import QickBoardSweep, ComplexQICKData
from labcore.measurement import independent
from labcore.measurement.sweep import Sweep

from hwman.compiler.circuit import Circuit
from hwman.compiler.custom_pulses import CustomPulseDefinition, get_custom_pulses
from lccfq_backend.model.tasks import Gate
from hwman.errors import (
    UnsupportedGateError,
    CircuitMissingMeasurementError,
    TwoQubitGateNotImplementedError,
)


@dataclass
class GateConfig:
    """Configuration for a quantum gate pulse."""

    pulse_type: str  # 'gauss', 'const', etc.
    phase: float = 0.0
    freq_key: Optional[str] = None  # e.g., 'q_ge', 'ro_freq'


# Standard gate definitions. Gain/length/sigma are read from the QICK ``cfg``
# dict at runtime
GATE_LIBRARY = {
    "x": GateConfig(pulse_type="gauss", phase=0.0, freq_key="q_ge"),
    "y": GateConfig(pulse_type="gauss", phase=np.pi / 2, freq_key="q_ge"),  # Y = X + 90° phase
    "rx": GateConfig(pulse_type="gauss", phase=0.0, freq_key="q_ge"),
    "ry": GateConfig(pulse_type="gauss", phase=np.pi / 2, freq_key="q_ge"),
    "measure": GateConfig(pulse_type="const", phase=0.0, freq_key="ro_freq"),
}

MEASURE = "measure"


def validate(
    circuit: Circuit, custom_pulses: Optional[dict[str, CustomPulseDefinition]] = None
) -> None:
    """Validate a circuit before building a program.

    Args:
        circuit: Circuit to validate.
        custom_pulses: Custom pulse registry to accept gate symbols from, in
            addition to ``GATE_LIBRARY``. Defaults to the active registry
            loaded via :func:`~hwman.compiler.custom_pulses.set_custom_pulses`.

    Raises:
        TwoQubitGateNotImplementedError: If any gate has control qubits.
        UnsupportedGateError: If a gate symbol is not in ``GATE_LIBRARY`` and
            not a known custom pulse name.
        CircuitMissingMeasurementError: If the circuit has no measurement.
    """
    if custom_pulses is None:
        custom_pulses = get_custom_pulses()

    has_measure_gate = False
    for gate in circuit.gates:
        if len(gate.control_qubits) != 0:
            raise TwoQubitGateNotImplementedError("Two qubit gates are not yet implemented.")

        symbol = gate.symbol.lower()
        if symbol not in GATE_LIBRARY and symbol not in custom_pulses:
            raise UnsupportedGateError(
                symbol, list(GATE_LIBRARY.keys()) + list(custom_pulses.keys())
            )

        if symbol == MEASURE:
            has_measure_gate = True

    if not has_measure_gate:
        raise CircuitMissingMeasurementError()


def unique_qubits(circuit: Circuit) -> List[int]:
    """Return all qubit indices referenced by the circuit, sorted."""
    qubits: set[int] = set()
    for gate in circuit.gates:
        qubits.update(gate.target_qubits)
        qubits.update(gate.control_qubits)
    return sorted(qubits)


def measured_qubits_in_order(circuit: Circuit) -> List[int]:
    """Return measured qubit indices in measurement order.

    If a qubit is measured multiple times it appears multiple times. The order
    matches the ``ComplexQICKData('qubit_{q}')`` specs attached to the program.
    """
    measured: List[int] = []
    for gate in circuit.gates:
        if gate.symbol.lower() == MEASURE:
            measured.extend(gate.target_qubits)
    return measured


def _pulse_name(gate: Gate, qubit: int, index: int) -> str:
    """Build a deterministic, unique pulse name for a (gate, target) operation.

    ``index`` is the 1-based position of this operation in the flattened gate
    sequence, which keeps names stable between ``_initialize`` and ``_body``.
    """
    name = f"{gate.symbol.lower()}_q{qubit}"
    if gate.params:
        param_str = "_".join(f"{p:.3f}".replace(".", "p") for p in gate.params)
        name += f"_{param_str}"
    return f"{name}_{index}"


def _flatten_operations(circuit: Circuit) -> List[Tuple[Gate, int, str]]:
    """Flatten the circuit into per-target operations with stable pulse names.

    Returns a list of ``(gate, target_qubit, pulse_name)`` tuples in execution
    order. Used by both ``_initialize`` (to declare pulses) and ``_body`` (to
    play them) so the names always agree.
    """
    operations: List[Tuple[Gate, int, str]] = []
    index = 0
    for gate in circuit.gates:
        for target in gate.target_qubits:
            index += 1
            operations.append((gate, target, _pulse_name(gate, target, index)))
    return operations


class CircuitProgram(AveragerProgramV2):
    """QICK program that plays an arbitrary :class:`Circuit`.

    The circuit is supplied as the ``circuit`` class attribute (set per circuit
    via :func:`build_circuit_sweep`); tuning values are read from ``cfg`` at
    runtime. ``custom_pulses`` holds any pulses not in ``GATE_LIBRARY``: a gate
    symbol that matches a custom pulse name is played as a single-qubit drive
    pulse using that pulse's raw I/Q envelope (via ``add_envelope``), with
    phase 0 and the usual ``q_pi_gain``/params gain scaling.
    """

    circuit: Circuit
    custom_pulses: dict[str, CustomPulseDefinition] = {}

    @staticmethod
    def _qubit_gen_ch(cfg: dict, qubit: int) -> Any:
        """Resolve the DAC generator channel for a qubit (per-qubit override or default)."""
        return cfg.get(f"q{qubit}_dac_ch", cfg["q_dac_ch"])

    def _initialize(self, cfg: dict) -> None:
        ro_ch = cfg["ro_adc_ch"]
        ro_gen_ch = cfg["ro_dac_ch"]

        # Declare qubit generators
        for q in unique_qubits(self.circuit):
            self.declare_gen(ch=self._qubit_gen_ch(cfg, q), nqz=cfg["q_nqz"])

        # Declare readout generator and readout
        self.declare_gen(ch=ro_gen_ch, nqz=cfg["ro_nqz"])
        self.declare_readout(ch=ro_ch, length=cfg["ro_len"])

        # Shot loop (reps must be 1 in cfg for single-shot data)
        self.add_loop("shots_loop", self.circuit.shots)

        # Add the Gaussian envelope on every distinct generator channel that
        # plays a gauss-style pulse, and the raw I/Q envelope for every
        # distinct (custom pulse name, channel) pair (QICK envelopes are
        # per-channel).
        gauss_channels = set()
        custom_envelope_channels: dict[str, set] = {}
        for gate, target, _ in _flatten_operations(self.circuit):
            symbol = gate.symbol.lower()
            ch = self._qubit_gen_ch(cfg, target)
            if symbol in GATE_LIBRARY:
                if GATE_LIBRARY[symbol].pulse_type == "gauss":
                    gauss_channels.add(ch)
            else:
                custom_envelope_channels.setdefault(symbol, set()).add(ch)

        for ch in sorted(gauss_channels):
            self.add_gauss(
                ch=ch,
                name="gauss",
                sigma=cfg["q_pi_sigma"],
                length=cfg["q_pi_n_sigma"] * cfg["q_pi_sigma"],
                even_length=True,
            )
        for symbol, channels in custom_envelope_channels.items():
            idata, qdata = self.custom_pulses[symbol].to_arrays()
            for ch in sorted(channels):
                self.add_envelope(ch=ch, name=symbol, idata=idata, qdata=qdata)

        # Declare every pulse used by the circuit
        for gate, target, pulse_name in _flatten_operations(self.circuit):
            symbol = gate.symbol.lower()

            if symbol == MEASURE:
                gate_cfg = GATE_LIBRARY[symbol]
                self.add_pulse(
                    ch=ro_gen_ch,
                    name=pulse_name,
                    ro_ch=ro_ch,
                    style="const",
                    freq=cfg["ro_freq"],
                    length=cfg["ro_len"],
                    phase=gate_cfg.phase,
                    gain=cfg["ro_gain"],
                )
                continue

            gain = cfg["q_pi_gain"]
            # Parametric gates (e.g. rx(theta)): scale the pi-pulse gain by
            # the rotation angle. params[0] is the rotation angle in radians.
            if gate.params:
                gain = cfg["q_pi_gain"] * gate.params[0] / np.pi

            if symbol in GATE_LIBRARY:
                phase = GATE_LIBRARY[symbol].phase
                envelope = "gauss"
            else:
                phase = 0.0
                envelope = symbol

            self.add_pulse(
                ch=self._qubit_gen_ch(cfg, target),
                name=pulse_name,
                style="arb",
                envelope=envelope,
                freq=cfg["q_freq"],
                phase=phase,
                gain=gain,
            )

        # Readout configuration
        self.add_readoutconfig(ch=ro_ch, name="myro", freq=cfg["ro_freq"], gen_ch=ro_gen_ch)

    def _body(self, cfg: dict) -> None:
        ro_ch = cfg["ro_adc_ch"]
        ro_gen_ch = cfg["ro_dac_ch"]

        # Send readout configuration
        self.send_readoutconfig(ch=ro_ch, name="myro", t=0)

        # Execute the gate sequence
        for gate, target, pulse_name in _flatten_operations(self.circuit):
            if gate.symbol.lower() == MEASURE:
                self.pulse(ch=ro_gen_ch, name=pulse_name, t=0)
                self.trigger(ros=[ro_ch], pins=[0], t=cfg["trig_time"])
            else:
                self.pulse(ch=self._qubit_gen_ch(cfg, target), name=pulse_name, t=0)

            # Always insert a delay between operations
            self.delay_auto(t=0, gens=True, ros=True)


def build_circuit_sweep(
    circuit: Circuit, custom_pulses: Optional[dict[str, CustomPulseDefinition]] = None
) -> Sweep:
    """Compile a :class:`Circuit` into a runnable QICK ``Sweep``.

    Validates the circuit, builds the dynamic data specs (one
    ``ComplexQICKData`` per measured qubit, in measurement order), binds the
    circuit to a fresh :class:`CircuitProgram` subclass, and applies the
    ``QickBoardSweep`` decorator.

    Args:
        circuit: Circuit object containing gates, shots, and pid.
        custom_pulses: Custom pulse registry. Defaults to the active registry
            loaded via :func:`~hwman.compiler.custom_pulses.set_custom_pulses`.

    Returns:
        A ``Sweep`` ready to pass to ``run_and_save_sweep``.

    Raises:
        UnsupportedGateError, CircuitMissingMeasurementError,
        TwoQubitGateNotImplementedError: If the circuit is invalid.
    """
    if custom_pulses is None:
        custom_pulses = get_custom_pulses()

    validate(circuit, custom_pulses)

    specs: List[Any] = [independent("repetition")]
    for q in measured_qubits_in_order(circuit):
        specs.append(ComplexQICKData(f"qubit_{q}", depends_on=["repetition"]))

    # Bind the circuit to a per-circuit subclass so _initialize/_body can read it.
    program_cls = type(
        "CompiledProgram",
        (CircuitProgram,),
        {"circuit": circuit, "custom_pulses": custom_pulses},
    )

    decorated = QickBoardSweep(*specs)(program_cls)
    return decorated()
