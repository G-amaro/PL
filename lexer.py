import ply.lex as lex

# 1. Dicionário de palavras-chave reservadas
reserved = {
    'program': 'PROGRAM',
    'integer': 'INTEGER',
    'real': 'REAL',
    'logical': 'LOGICAL',
    'end': 'END',
    'if': 'IF',
    'then': 'THEN',
    'else': 'ELSE',
    'endif': 'ENDIF',
    'do': 'DO',
    'continue': 'CONTINUE',
    'goto': 'GOTO',
    'read': 'READ',
    'print': 'PRINT',
    'function': 'FUNCTION',
    'subroutine': 'SUBROUTINE',
    'return': 'RETURN',
    'call': 'CALL',
}

# 2. Lista completa de Tokens
tokens = [
    'ID',
    'NUMBER',
    'FLOAT',
    'STRING',

    # Operadores Matemáticos
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE',

    # Símbolos Estruturais
    'EQUALS', 'COMMA', 'LPAREN', 'RPAREN',

    # Operadores Lógicos e Relacionais do Fortran 77
    'TRUE', 'FALSE',
    'LE', 'GE', 'LT', 'GT', 'EQ', 'NE',
    'AND', 'OR', 'NOT',
] + list(reserved.values())

# 3. Regex para tokens simples
t_PLUS    = r'\+'
t_MINUS   = r'-'
t_TIMES   = r'\*'
t_DIVIDE  = r'/'
t_EQUALS  = r'='
t_COMMA   = r','
t_LPAREN  = r'\('
t_RPAREN  = r'\)'

# Operadores Lógicos e Relacionais (case-insensitive)
t_TRUE    = r'\.(TRUE|true)\.'
t_FALSE   = r'\.(FALSE|false)\.'
t_LE      = r'\.(LE|le)\.'
t_GE      = r'\.(GE|ge)\.'
t_LT      = r'\.(LT|lt)\.'
t_GT      = r'\.(GT|gt)\.'
t_EQ      = r'\.(EQ|eq)\.'
t_NE      = r'\.(NE|ne)\.'
t_AND     = r'\.(AND|and)\.'
t_OR      = r'\.(OR|or)\.'
t_NOT     = r'\.(NOT|not)\.'

t_ignore = ' \t'

# 4. Regras com funções

def t_COMMENT_INLINE(t):
    r'!.*'
    pass

def t_STRING(t):
    r"'[^']*'"
    t.value = t.value[1:-1]
    return t

def t_FLOAT(t):
    r'\d+\.\d+'
    t.value = float(t.value)
    return t

def t_NUMBER(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_ID(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'
    t.type = reserved.get(t.value.lower(), 'ID')
    return t

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

def t_error(t):
    print(f"Erro Léxico: Caractere ilegal '{t.value[0]}' na linha {t.lexer.lineno}")
    t.lexer.skip(1)

lexer = lex.lex()
