# Quantum Instruction Compiler for QICK

This compiler translates quantum gate instruction lists into QICK `AveragerProgramV2` programs that can be executed on QICK hardware.

## Overview

The compiler consists of three main components:

1. **Lexer** (`lexer.py`): Tokenizes the instruction format
2. **Parser** (`parser.py`): Builds an Abstract Syntax Tree (AST) from tokens
3. **Code Generator** (`qick_codegen.py`): Generates QICK program Python code

## Instruction Format

Instructions follow this format:

```
[gate @ [targets] ctrl by [controls] w/ params=[parameters], ...]
```

### Format Elements

- **`[...]`**: Outer brackets enclose the entire instruction list
- **`gate`**: Gate name (e.g., `x`, `y`, `rx`, `ry`, `cx`, `measure`)
- **`@`**: Separates gate from target qubits
- **`[targets]`**: List of target qubit indices (e.g., `[0]`, `[0, 1, 2]`)
- **`ctrl by`**: Keyword for control qubits
- **`[controls]`**: List of control qubit indices, or `None`
- **`w/ params=`**: Keyword for gate parameters
- **`[parameters]`**: List of numeric parameters, or `None`
- **`,`**: Separates multiple instructions

### Example Instructions

```python
# Single X gate on qubit 0, then measurement
"[x @ [0] ctrl by None w/ params=None, measure @ [0] ctrl by None w/ params=None]"

# Parametric rotation (Rx with angle π/2)
"[rx @ [0] ctrl by None w/ params=[1.5708], measure @ [0] ctrl by None w/ params=None]"

# Y gate with 90° phase shift
"[y @ [1] ctrl by None w/ params=None, measure @ [1] ctrl by None w/ params=None]"

# Controlled-X (CNOT) with control qubit 0, target qubit 1
"[cx @ [1] ctrl by [0] w/ params=None, measure @ [0, 1] ctrl by None w/ params=None]"

# Multi-qubit measurement
"[measure @ [0, 1, 2, 3] ctrl by None w/ params=None]"
```

## Supported Gates

### Single-Qubit Gates

| Gate | Description | Parameters | Phase |
|------|-------------|------------|-------|
| `x` | Pauli X (π rotation around X-axis) | None | 0° |
| `y` | Pauli Y (π rotation around Y-axis) | None | 90° |
| `rx` | Rotation around X-axis | `[angle]` in radians | 0° |
| `ry` | Rotation around Y-axis | `[angle]` in radians | 90° |

### Two-Qubit Gates

| Gate | Description | Control | Target |
|------|-------------|---------|--------|
| `cx` | Controlled-X (CNOT) | `ctrl by [qubit]` | `@ [qubit]` |

### Measurement

| Gate | Description | Targets |
|------|-------------|---------|
| `measure` | Readout measurement | `@ [qubits...]` |

## Usage

### Basic Usage

```python
from hwman.compiler import compile_to_qick

# Define instruction sequence
instructions = "[x @ [0] ctrl by None w/ params=None, measure @ [0] ctrl by None w/ params=None]"

# Compile to QICK program
program_code = compile_to_qick(instructions, class_name="MyProgram")

# Save to file
with open('my_program.py', 'w') as f:
    f.write(program_code)

# Import and use
from my_program import MyProgram
sweep = MyProgram()
```

### Using in Measurement Scripts

```python
from hwman.compiler import compile_to_qick
from labcore.measurement.storage import run_and_save_sweep

# Compile instructions
instructions = "[x @ [0] ctrl by None w/ params=None, measure @ [0] ctrl by None w/ params=None]"
program_code = compile_to_qick(instructions, "XGateMeasurement")

# Execute dynamically
exec(program_code)

# Run measurement
sweep = XGateMeasurement()  # Now available in current scope
loc, data = run_and_save_sweep(sweep, "data", "my_job_id", return_data=True)
```

### Parsing Only (AST)

If you only want to parse without generating code:

```python
from hwman.compiler import parse_instructions

instructions = "[x @ [0] ctrl by None w/ params=None, measure @ [0] ctrl by None w/ params=None]"
ast = parse_instructions(instructions)

for instr in ast.instructions:
    print(f"Gate: {instr.gate}")
    print(f"Targets: {instr.targets}")
    print(f"Controls: {instr.controls}")
    print(f"Parameters: {instr.params}")
```

## Generated QICK Program Structure

The compiler generates a complete `AveragerProgramV2` class with:

### `_initialize(self, cfg)` method

1. Declares generator channels for each qubit
2. Declares readout channels
3. Adds pulse envelopes (Gaussian for qubit gates, constant for readout)
4. Defines all pulses with appropriate parameters
5. Configures readout

### `_body(self, cfg)` method

1. Sends readout configuration
2. Executes gate sequence in order:
   - Qubit gates: `pulse()` followed by `delay_auto()`
   - Measurements: `pulse()` followed by `trigger()`

## Example Output

Input:
```
[x @ [0] ctrl by None w/ params=None, measure @ [0] ctrl by None w/ params=None]
```

Generated Program:
```python
@QickBoardSweep(
    independent('repetition'),
    ComplexQICKData('signal', depends_on=['repetition'])
)
class MyProgram(AveragerProgramV2):
    def _initialize(self, cfg):
        ro_ch = cfg['ro_ch']
        ro_gen_ch = cfg['ro_gen_ch']
        q0_gen_ch = cfg.get('q0_gen_ch', cfg['q_gen_ch'])

        self.declare_gen(ch=q0_gen_ch, nqz=cfg['q_nqz'])
        self.declare_gen(ch=ro_gen_ch, nqz=cfg['ro_nqz'])
        self.declare_readout(ch=ro_ch, length=cfg['ro_len'])

        self.add_gauss(ch=q0_gen_ch, name='gauss',
                      sigma=cfg['q_ge_sig'],
                      length=4 * cfg['q_ge_sig'],
                      even_length=True)

        self.add_pulse(ch=q0_gen_ch, name='x_q0_1',
                      style='arb',
                      envelope='gauss',
                      freq=cfg['q_ge'],
                      phase=0.0,
                      gain=cfg['q_ge_gain'])

        self.add_pulse(ch=ro_gen_ch, name='measure_q0_2',
                      style='const',
                      freq=cfg['ro_freq'],
                      length=cfg['ro_len'],
                      phase=0.0,
                      gain=cfg['ro_gain'])

        self.add_readoutconfig(ch=ro_ch, name='myro',
                             freq=cfg['ro_freq'],
                             gen_ch=ro_gen_ch)

    def _body(self, cfg):
        ro_ch = cfg['ro_ch']
        ro_gen_ch = cfg['ro_gen_ch']
        q0_gen_ch = cfg.get('q0_gen_ch', cfg['q_gen_ch'])

        self.send_readoutconfig(ch=ro_ch, name='myro', t=0)

        self.pulse(ch=q0_gen_ch, name='x_q0_1', t=0)
        self.delay_auto(t=0, gens=True, ros=True)
        self.pulse(ch=ro_gen_ch, name='measure_q0_2', t=0)
        self.trigger(ros=[ro_ch], pins=[0], t=cfg['trig_time'])
```

## Configuration Requirements

The generated programs expect the following configuration keys:

### Qubit Configuration
- `q_gen_ch`: Qubit generator channel
- `q_nqz`: Qubit Nyquist zone
- `q_ge`: Qubit transition frequency (GHz)
- `q_ge_sig`: Gaussian pulse sigma (clock cycles)
- `q_ge_gain`: Qubit pulse gain (for π pulse)
- `q_ge_phase`: Qubit pulse phase

### Readout Configuration
- `ro_ch`: Readout channel
- `ro_gen_ch`: Readout generator channel
- `ro_nqz`: Readout Nyquist zone
- `ro_freq`: Readout frequency (MHz)
- `ro_len`: Readout length (clock cycles)
- `ro_gain`: Readout gain
- `ro_phase`: Readout phase
- `trig_time`: Trigger time offset

### Multi-Qubit Configuration (optional)
- `q{N}_gen_ch`: Generator channel for qubit N

Falls back to `q_gen_ch` if not specified.

## Testing

Run the examples:

```bash
uv run python hwman/compiler/example.py
```

Test individual components:

```bash
# Test lexer
uv run python hwman/compiler/lexer.py

# Test parser
uv run python hwman/compiler/parser.py

# Test code generator
uv run python hwman/compiler/qick_codegen.py
```

## Implementation Details

### Lexer (PLY)

The lexer uses PLY (Python Lex-Yacc) with the following token types:

- `LBRACKET`, `RBRACKET`: `[` and `]`
- `COMMA`: `,`
- `AT`: `@`
- `GATE`: Gate identifier
- `CTRL_BY`: `ctrl by` keyword
- `W_PARAMS`: `w/ params=` keyword
- `NONE`: `None` keyword
- `INTEGER`: Integer qubit indices
- `FLOAT`: Floating-point parameters

### Parser Grammar

```
program : LBRACKET instruction_list RBRACKET

instruction_list : instruction
                 | instruction_list COMMA instruction

instruction : GATE AT target_list CTRL_BY control_spec W_PARAMS param_spec

target_list : LBRACKET integer_list RBRACKET
control_spec : NONE | LBRACKET integer_list RBRACKET
param_spec : NONE | LBRACKET number_list RBRACKET
```

### Code Generation

The code generator:

1. Analyzes all instructions to determine required qubits
2. Creates unique pulse names for each gate instance
3. Maps gates to QICK pulse types and parameters
4. Generates initialization code for all pulses
5. Generates body code that sequences pulses in order

## Extending the Compiler

### Adding New Gates

To add a new gate, update `GATE_LIBRARY` in `qick_codegen.py`:

```python
GATE_LIBRARY = {
    # ... existing gates ...
    'new_gate': GateConfig(
        pulse_type='gauss',  # or 'const', etc.
        phase=0.0,           # phase offset in radians
        sigma=None,          # pulse width (None = use cfg)
        gain=None,           # gain (None = use cfg)
        freq_key='q_ge',     # config key for frequency
    ),
}
```

### Custom Pulse Shapes

Modify `generate_initialize()` to add custom envelopes:

```python
lines.append("self.add_envelope(ch=q0_gen_ch, name='custom_shape', ...)")
```

## Limitations

1. **Two-qubit gates**: Currently generates TODO comments for CX gates. Full implementation requires:
   - Cross-resonance pulse definitions
   - Proper control/target qubit coordination
   - Timing synchronization

2. **Parametric gates**: Angle-to-gain conversion assumes linear relationship. May need calibration data.

3. **Timing**: Uses `delay_auto()` which adds automatic delays. Fixed timing requires explicit `t=` values.

4. **Error handling**: Basic error messages. Could be enhanced with better diagnostics.

## Future Enhancements

- [ ] Native two-qubit gate support (CX, CZ, etc.)
- [ ] Pulse shape library (DRAG, derivative, etc.)
- [ ] Timing optimization
- [ ] Gate decomposition (arbitrary unitaries)
- [ ] Qubit topology awareness
- [ ] Configuration validation
- [ ] Better error messages with line/column numbers
- [ ] Optimization passes (gate fusion, etc.)