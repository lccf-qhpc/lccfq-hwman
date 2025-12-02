"""
QICK program code generator.

This module takes parsed instructions and generates QICK program code.
"""

from hwman.compiler.parser import Instruction, InstructionList
from typing import Optional
import numpy as np


class GateConfig:
    """Configuration for a quantum gate pulse."""

    def __init__(
        self,
        pulse_type: str,  # 'gauss', 'const', etc.
        phase: float = 0.0,
        length: Optional[int] = None,
        sigma: Optional[int] = None,
        gain: Optional[int] = None,
        freq_key: Optional[str] = None,  # e.g., 'q_ge', 'ro_freq'
    ):
        self.pulse_type = pulse_type
        self.phase = phase
        self.length = length
        self.sigma = sigma
        self.gain = gain
        self.freq_key = freq_key


# Standard gate definitions
GATE_LIBRARY = {
    'x': GateConfig(
        pulse_type='gauss',
        phase=0.0,
        sigma=None,  # Will use cfg['q_ge_sig']
        gain=None,   # Will use cfg['q_ge_gain'] (pi pulse)
        freq_key='q_ge',
    ),
    'y': GateConfig(
        pulse_type='gauss',
        phase=np.pi / 2,  # Y = X with 90° phase shift
        sigma=None,
        gain=None,
        freq_key='q_ge',
    ),
    'rx': GateConfig(
        pulse_type='gauss',
        phase=0.0,
        sigma=None,
        gain=None,  # Parametric - gain will be computed from params
        freq_key='q_ge',
    ),
    'ry': GateConfig(
        pulse_type='gauss',
        phase=np.pi / 2,
        sigma=None,
        gain=None,
        freq_key='q_ge',
    ),
    'measure': GateConfig(
        pulse_type='const',
        phase=0.0,
        length=None,  # Will use cfg['ro_len']
        gain=None,    # Will use cfg['ro_gain']
        freq_key='ro_freq',
    ),
}


class QICKProgramGenerator:
    """Generates QICK program code from parsed instructions."""

    def __init__(self, instruction_list: InstructionList):
        self.instructions = instruction_list.instructions
        self.unique_qubits = self._get_unique_qubits()
        self.pulse_counter = 0

    def _get_unique_qubits(self) -> set[int]:
        """Extract all unique qubit indices from instructions."""
        qubits = set()
        for instr in self.instructions:
            qubits.update(instr.targets)
            if instr.controls:
                qubits.update(instr.controls)
        return qubits

    def _generate_pulse_name(self, gate: str, qubit: int, params: Optional[list[float]] = None) -> str:
        """Generate a unique pulse name."""
        base_name = f"{gate}_q{qubit}"
        if params:
            param_str = "_".join([f"{p:.3f}".replace(".", "p") for p in params])
            base_name += f"_{param_str}"
        self.pulse_counter += 1
        return f"{base_name}_{self.pulse_counter}"

    def generate_initialize(self) -> str:
        """Generate the _initialize method code."""
        lines = []
        lines.append("    def _initialize(self, cfg):")
        lines.append("        # Extract configuration")
        lines.append("        ro_ch = cfg['ro_ch']")
        lines.append("        ro_gen_ch = cfg['ro_gen_ch']")

        # Declare qubit generator channels
        for q in sorted(self.unique_qubits):
            lines.append(f"        q{q}_gen_ch = cfg.get('q{q}_gen_ch', cfg['q_gen_ch'])")

        lines.append("")
        lines.append("        # Declare generators")
        for q in sorted(self.unique_qubits):
            lines.append(f"        self.declare_gen(ch=q{q}_gen_ch, nqz=cfg['q_nqz'])")
        lines.append("        self.declare_gen(ch=ro_gen_ch, nqz=cfg['ro_nqz'])")

        lines.append("")
        lines.append("        # Declare readout")
        lines.append("        self.declare_readout(ch=ro_ch, length=cfg['ro_len'])")

        lines.append("")
        lines.append("        # Add pulse envelopes")

        # Track which envelopes we've added
        added_envelopes = set()

        for instr in self.instructions:
            if instr.gate not in GATE_LIBRARY:
                continue

            gate_cfg = GATE_LIBRARY[instr.gate]

            # Add Gaussian envelopes for qubit gates
            if gate_cfg.pulse_type == 'gauss' and 'gauss' not in added_envelopes:
                lines.append("        self.add_gauss(ch=q0_gen_ch, name='gauss', sigma=cfg['q_ge_sig'], "
                           "length=4 * cfg['q_ge_sig'], even_length=True)")
                added_envelopes.add('gauss')

        lines.append("")
        lines.append("        # Add pulses")

        for instr in self.instructions:
            if instr.gate not in GATE_LIBRARY:
                lines.append(f"        # Warning: Unknown gate '{instr.gate}'")
                continue

            gate_cfg = GATE_LIBRARY[instr.gate]

            for target in instr.targets:
                pulse_name = self._generate_pulse_name(instr.gate, target, instr.params)

                if instr.gate == 'measure':
                    # Measurement pulse
                    lines.append(f"        self.add_pulse(ch=ro_gen_ch, name='{pulse_name}',")
                    lines.append("                       style='const',")
                    lines.append("                       freq=cfg['ro_freq'],")
                    lines.append("                       length=cfg['ro_len'],")
                    lines.append(f"                       phase={gate_cfg.phase},")
                    lines.append("                       gain=cfg['ro_gain'])")
                else:
                    # Qubit gate pulse
                    gain_expr = "cfg['q_ge_gain']"

                    # Handle parametric gates (like rx with angle parameter)
                    if instr.params and len(instr.params) > 0:
                        # Convert angle to gain (assuming params[0] is rotation angle in radians)
                        # For rx(theta), gain = (theta / pi) * pi_gain
                        angle = instr.params[0]
                        gain_expr = f"int(cfg['q_ge_gain'] * {angle} / np.pi)"

                    lines.append(f"        self.add_pulse(ch=q{target}_gen_ch, name='{pulse_name}',")
                    lines.append("                       style='arb',")
                    lines.append("                       envelope='gauss',")
                    lines.append(f"                       freq=cfg['q_ge'],")
                    lines.append(f"                       phase={gate_cfg.phase},")
                    lines.append(f"                       gain={gain_expr})")

        # Add readout configuration
        lines.append("")
        lines.append("        # Readout configuration")
        lines.append("        self.add_readoutconfig(ch=ro_ch, name='myro', freq=cfg['ro_freq'], gen_ch=ro_gen_ch)")

        return "\n".join(lines)

    def generate_body(self) -> str:
        """Generate the _body method code."""
        lines = []
        lines.append("    def _body(self, cfg):")
        lines.append("        ro_ch = cfg['ro_ch']")
        lines.append("        ro_gen_ch = cfg['ro_gen_ch']")

        for q in sorted(self.unique_qubits):
            lines.append(f"        q{q}_gen_ch = cfg.get('q{q}_gen_ch', cfg['q_gen_ch'])")

        lines.append("")
        lines.append("        # Send readout configuration")
        lines.append("        self.send_readoutconfig(ch=ro_ch, name='myro', t=0)")
        lines.append("")

        # Reset pulse counter to match initialization
        self.pulse_counter = 0

        lines.append("        # Execute gate sequence")
        for instr in self.instructions:
            if instr.gate not in GATE_LIBRARY:
                lines.append(f"        # Warning: Unknown gate '{instr.gate}'")
                continue

            if instr.gate == 'measure':
                # Measurement
                for target in instr.targets:
                    pulse_name = self._generate_pulse_name(instr.gate, target, instr.params)
                    lines.append(f"        self.pulse(ch=ro_gen_ch, name='{pulse_name}', t=0)")
                    lines.append(f"        self.trigger(ros=ro_ch, pins=[0], t=cfg['trig_time'])")
            else:
                # Qubit gate
                for target in instr.targets:
                    pulse_name = self._generate_pulse_name(instr.gate, target, instr.params)

                    # Handle controlled gates
                    if instr.controls:
                        lines.append(f"        # Controlled {instr.gate} gate (control qubits: {instr.controls})")
                        lines.append(f"        # TODO: Implement two-qubit gate logic")

                    lines.append(f"        self.pulse(ch=q{target}_gen_ch, name='{pulse_name}', t=0)")
                    lines.append("        self.delay_auto(t=0, gens=True, ros=True)")

        return "\n".join(lines)

    def generate_program(self, class_name: str = "CompiledProgram") -> str:
        """Generate complete QICK program class code."""
        lines = []
        lines.append('"""')
        lines.append(f"Compiled QICK program generated from instruction list.")
        lines.append('"""')
        lines.append("")
        lines.append("import numpy as np")
        lines.append("from qcui_measurement.qick.averager_program_v2 import AveragerProgramV2")
        lines.append("from qcui_measurement.qick.decorators import QickBoardSweep, independent, ComplexQICKData")
        lines.append("")
        lines.append("")
        lines.append("@QickBoardSweep(")
        lines.append("    independent('repetition'),")
        lines.append("    ComplexQICKData('signal', depends_on=['repetition'])")
        lines.append(")")
        lines.append(f"class {class_name}(AveragerProgramV2):")
        lines.append('    """Generated QICK program."""')
        lines.append("")

        # Add _initialize method
        lines.append(self.generate_initialize())
        lines.append("")

        # Add _body method
        lines.append(self.generate_body())

        return "\n".join(lines)


def compile_to_qick(instruction_str: str, class_name: str = "CompiledProgram") -> str:
    """
    Compile an instruction string to QICK program code.

    Args:
        instruction_str: Instruction string to parse
        class_name: Name for the generated program class

    Returns:
        Python source code for the QICK program
    """
    from hwman.compiler.parser import parse_instructions

    instruction_list = parse_instructions(instruction_str)
    generator = QICKProgramGenerator(instruction_list)
    return generator.generate_program(class_name)


if __name__ == '__main__':
    # Test program generation
    test_input = "[x @ [0] ctrl by None w/ params=None, rx @ [0] ctrl by None w/ params=[1.57], measure @ [0] ctrl by None w/ params=None]"

    print("Compiling instruction string to QICK program:")
    print(test_input)
    print("\n" + "="*80)
    print("Generated QICK Program:")
    print("="*80 + "\n")

    program_code = compile_to_qick(test_input, "TestProgram")
    print(program_code)