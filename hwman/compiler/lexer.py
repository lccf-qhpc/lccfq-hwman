"""
Lexer for quantum instruction language.

Example input:
[x @ [0] ctrl by None w/ params=None, y @ [2] ctrl by None w/ params=None]
"""

import lex as lex

# Token list - required by PLY
tokens = (
    'LBRACKET',
    'RBRACKET',
    'COMMA',
    'AT',
    'NONE',
    'GATE',
    'CTRL_BY',
    'W_PARAMS',
    'INTEGER',
    'FLOAT',
)

# Simple tokens defined as strings
t_LBRACKET = r'\['
t_RBRACKET = r'\]'
t_COMMA = r','
t_AT = r'@'

# Keywords that are multiple words
def t_CTRL_BY(t):
    r'ctrl\s+by'
    return t

def t_W_PARAMS(t):
    r'w/\s+params='
    return t

# None keyword
def t_NONE(t):
    r'None'
    return t

# Numbers - floats must come before integers due to rule ordering
def t_FLOAT(t):
    r'-?\d+\.\d+'
    t.value = float(t.value)
    return t

def t_INTEGER(t):
    r'-?\d+'
    t.value = int(t.value)
    return t

# Gate names (identifiers) - any sequence of lowercase letters and underscores
# This should come after keywords to ensure keywords are matched first
def t_GATE(t):
    r'[a-z_][a-z_0-9]*'
    # Reserved words are already handled by specific token rules above
    return t

# Ignored characters (whitespace)
t_ignore = ' \t\n'

# Error handling
def t_error(t):
    print(f"Illegal character '{t.value[0]}' at position {t.lexpos}")
    t.lexer.skip(1)

# Build the lexer
def build_lexer(**kwargs):
    """Build and return a lexer instance."""
    return lex.lex(**kwargs)


# Test function
def test_lexer(data):
    """Test the lexer with sample input."""
    lexer = build_lexer()
    lexer.input(data)

    tokens_list = []
    while True:
        tok = lexer.token()
        if not tok:
            break
        tokens_list.append(tok)
        print(tok)

    return tokens_list


if __name__ == '__main__':
    # Test with your example
    test_input = "[x @ [0] ctrl by None w/ params=None, y @ [2] ctrl by None w/ params=None, cx @ [1] ctrl by [0] w/ params=None, rx @ [3] ctrl by None w/ params=[1.57], measure @ [0, 1, 2, 3] ctrl by None w/ params=None]"

    print("Testing lexer with input:")
    print(test_input)
    print("\nTokens:")
    test_lexer(test_input)