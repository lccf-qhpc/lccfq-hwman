"""
Example usage of the quantum instruction compiler.

This demonstrates how to:
1. Parse instruction strings
2. Generate QICK programs
3. Use the compiled programs
"""

from hwman.compiler import compile_to_qick, parse_instructions


def example_simple_gate_sequence():
    """Example: Simple X gate followed by measurement."""
    print("="*80)
    print("Example 1: Simple X gate followed by measurement")
    print("="*80)

    instructions = "[x @ [0] ctrl by None w/ params=None, measure @ [0] ctrl by None w/ params=None]"

    # Parse the instructions
    parsed = parse_instructions(instructions)
    print(f"\nInput: {instructions}")
    print(f"\nParsed instructions:")
    for instr in parsed.instructions:
        print(f"  - {instr}")

    # Generate QICK program
    program = compile_to_qick(instructions, "SimpleXGate")
    print(f"\n\nGenerated QICK Program:\n")
    print(program)


def example_parametric_rotation():
    """Example: Parametric rotation (Rx) gate."""
    print("\n" + "="*80)
    print("Example 2: Parametric Rx rotation (pi/2)")
    print("="*80)

    instructions = "[rx @ [0] ctrl by None w/ params=[1.5708], measure @ [0] ctrl by None w/ params=None]"

    parsed = parse_instructions(instructions)
    print(f"\nInput: {instructions}")
    print(f"\nParsed instructions:")
    for instr in parsed.instructions:
        print(f"  - {instr}")

    program = compile_to_qick(instructions, "ParametricRotation")
    print(f"\n\nGenerated QICK Program:\n")
    print(program)


def example_multi_qubit():
    """Example: Multi-qubit gates and controlled operations."""
    print("\n" + "="*80)
    print("Example 3: Multi-qubit operations")
    print("="*80)

    instructions = (
        "[x @ [0] ctrl by None w/ params=None, "
        "y @ [1] ctrl by None w/ params=None, "
        "cx @ [1] ctrl by [0] w/ params=None, "
        "measure @ [0, 1] ctrl by None w/ params=None]"
    )

    parsed = parse_instructions(instructions)
    print(f"\nInput: {instructions}")
    print(f"\nParsed instructions:")
    for instr in parsed.instructions:
        print(f"  - {instr}")

    program = compile_to_qick(instructions, "MultiQubitProgram")
    print(f"\n\nGenerated QICK Program:\n")
    print(program)


def example_complex_sequence():
    """Example: Complex gate sequence from the original specification."""
    print("\n" + "="*80)
    print("Example 4: Complex gate sequence")
    print("="*80)

    instructions = (
        "[x @ [0] ctrl by None w/ params=None, "
        "y @ [2] ctrl by None w/ params=None, "
        "cx @ [1] ctrl by [0] w/ params=None, "
        "rx @ [3] ctrl by None w/ params=[1.57], "
        "measure @ [0, 1, 2, 3] ctrl by None w/ params=None]"
    )

    parsed = parse_instructions(instructions)
    print(f"\nInput: {instructions}")
    print(f"\nParsed instructions:")
    for instr in parsed.instructions:
        print(f"  - {instr}")

    program = compile_to_qick(instructions, "ComplexSequence")
    print(f"\n\nGenerated QICK Program:\n")
    print(program)


def example_usage_in_code():
    """Example: How to use the compiled program in your code."""
    print("\n" + "="*80)
    print("Example 5: Using compiled programs in measurement code")
    print("="*80)

    instructions = "[x @ [0] ctrl by None w/ params=None, measure @ [0] ctrl by None w/ params=None]"

    # Generate the program code
    program_code = compile_to_qick(instructions, "MyMeasurement")

    print("\nStep 1: Compile instructions to program")
    print(f"Instructions: {instructions}")

    print("\nStep 2: Execute or save the generated program")
    print("""
    # Option A: Save to a file
    with open('my_measurement.py', 'w') as f:
        f.write(program_code)

    # Then import and use:
    from my_measurement import MyMeasurement
    sweep = MyMeasurement()
    loc, da = run_and_save_sweep(sweep, "data", "my_job_id")

    # Option B: Execute dynamically
    exec(program_code)
    sweep = MyMeasurement()  # Now available in scope
    """)

    print("\nGenerated program preview (first 500 chars):")
    print(program_code[:500] + "...")


if __name__ == '__main__':
    example_simple_gate_sequence()
    example_parametric_rotation()
    example_multi_qubit()
    example_complex_sequence()
    example_usage_in_code()

    print("\n" + "="*80)
    print("Examples complete!")
    print("="*80)