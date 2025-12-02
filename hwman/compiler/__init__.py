"""
Quantum instruction compiler for QICK programs.

This package provides tools to compile quantum gate instructions into QICK programs:
- lexer.py: Lexical analyzer for instruction format
- parser.py: Parser that creates AST from instructions
- qick_codegen.py: Code generator that produces QICK program classes

Usage:
    from hwman.compiler import compile_to_qick

    instructions = "[x @ [0] ctrl by None w/ params=None, measure @ [0] ctrl by None w/ params=None]"
    program_code = compile_to_qick(instructions, class_name="MyProgram")

    # program_code now contains Python source for a QICK AveragerProgramV2 class
"""

from hwman.compiler.qick_codegen import compile_to_qick
from hwman.compiler.parser import parse_instructions, Instruction, InstructionList

__all__ = ['compile_to_qick', 'parse_instructions', 'Instruction', 'InstructionList']