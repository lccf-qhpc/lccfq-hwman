"""
Yacc parser for quantum instruction language.

This parser takes instruction lists like:
[x @ [0] ctrl by None w/ params=None, y @ [2] ctrl by None w/ params=None]

and generates QICK program classes.
"""

from hwman.compiler import yac as yacc
from hwman.compiler import lex
from hwman.compiler.lexer import tokens, build_lexer
from typing import Optional, Union


# Data structures to represent parsed instructions
class Instruction:
    """Represents a single quantum gate instruction."""

    def __init__(
        self,
        gate: str,
        targets: list[int],
        controls: Optional[list[int]],
        params: Optional[list[float]]
    ):
        self.gate = gate
        self.targets = targets
        self.controls = controls
        self.params = params

    def __repr__(self):
        return f"Instruction(gate={self.gate}, targets={self.targets}, controls={self.controls}, params={self.params})"


class InstructionList:
    """Represents a list of quantum instructions."""

    def __init__(self, instructions: list[Instruction]):
        self.instructions = instructions

    def __repr__(self):
        return f"InstructionList({self.instructions})"


# Grammar rules
def p_program(p):
    """program : LBRACKET instruction_list RBRACKET"""
    p[0] = InstructionList(p[2])


def p_instruction_list(p):
    """instruction_list : instruction
                        | instruction_list COMMA instruction"""
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]


def p_instruction(p):
    """instruction : GATE AT target_list CTRL_BY control_spec W_PARAMS param_spec"""
    p[0] = Instruction(
        gate=p[1],
        targets=p[3],
        controls=p[5],
        params=p[7]
    )


def p_target_list(p):
    """target_list : LBRACKET integer_list RBRACKET"""
    p[0] = p[2]


def p_control_spec_none(p):
    """control_spec : NONE"""
    p[0] = None


def p_control_spec_list(p):
    """control_spec : LBRACKET integer_list RBRACKET"""
    p[0] = p[2]


def p_param_spec_none(p):
    """param_spec : NONE"""
    p[0] = None


def p_param_spec_list(p):
    """param_spec : LBRACKET number_list RBRACKET"""
    p[0] = p[2]


def p_integer_list_single(p):
    """integer_list : INTEGER"""
    p[0] = [p[1]]


def p_integer_list_multiple(p):
    """integer_list : integer_list COMMA INTEGER"""
    p[0] = p[1] + [p[3]]


def p_number_list_single(p):
    """number_list : number"""
    p[0] = [p[1]]


def p_number_list_multiple(p):
    """number_list : number_list COMMA number"""
    p[0] = p[1] + [p[3]]


def p_number_int(p):
    """number : INTEGER"""
    p[0] = float(p[1])


def p_number_float(p):
    """number : FLOAT"""
    p[0] = p[1]


def p_error(p):
    if p:
        print(f"Syntax error at token {p.type} ('{p.value}') at position {p.lexpos}")
    else:
        print("Syntax error at EOF")


# Build the parser
def build_parser(**kwargs):
    """Build and return a parser instance."""
    return yacc.yacc(**kwargs)


def parse_instructions(input_str: str) -> InstructionList:
    """
    Parse an instruction string and return an InstructionList.

    Args:
        input_str: String in format like "[x @ [0] ctrl by None w/ params=None, ...]"

    Returns:
        InstructionList containing parsed instructions
    """
    lexer = build_lexer()
    parser = build_parser()
    result = parser.parse(input_str, lexer=lexer)
    return result


if __name__ == '__main__':
    # Test the parser
    test_input = "[x @ [0] ctrl by None w/ params=None, y @ [2] ctrl by None w/ params=None, cx @ [1] ctrl by [0] w/ params=None, rx @ [3] ctrl by None w/ params=[1.57], measure @ [0, 1, 2, 3] ctrl by None w/ params=None]"

    print("Testing parser with input:")
    print(test_input)
    print("\nParsed result:")
    result = parse_instructions(test_input)
    print(result)
    print("\nIndividual instructions:")
    for instr in result.instructions:
        print(f"  {instr}")