import ply.lex as lex

# 1. Dicionário de palavras-chave reservadas [1]
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
    'return': 'RETURN'
}

# 2. Lista completa de Tokens [1]
tokens = [
    'ID',       # Identificadores (nomes de variáveis, funções)
    'NUMBER',   # Números inteiros
    'STRING',   # Strings de texto (ex: 'Ola, Mundo!')
    
    # Operadores Matemáticos
    'PLUS',     # +
    'MINUS',    # -
    'TIMES',    # *
    'DIVIDE',   # /
    
    # Símbolos Estruturais e Especiais
    'EQUALS',   # =
    'COMMA',    # ,
    'LPAREN',   # (
    'RPAREN',   # )
    
    # Operadores Lógicos e Relacionais do Fortran
    'TRUE',     # .TRUE.
    'FALSE',    # .FALSE.
    'LE',       # .LE.
    'AND',      # .AND.
    'EQ',       # .EQ.
    'GT'        # .GT.
] + list(reserved.values())

# 3. Expressões Regulares (RegEx) para Tokens Simples
# Símbolos matemáticos e estruturais usados nos exemplos [2-4]
t_PLUS    = r'\+'
t_MINUS   = r'-'
t_TIMES   = r'\*'
t_DIVIDE  = r'/'
t_EQUALS  = r'='
t_COMMA   = r','
t_LPAREN  = r'\('
t_RPAREN  = r'\)'

# Operadores Lógicos e Relacionais [3, 4]
t_TRUE    = r'\.TRUE\.'
t_FALSE   = r'\.FALSE\.'
t_LE      = r'\.LE\.'
t_AND     = r'\.AND\.'
t_EQ      = r'\.EQ\.'
t_GT      = r'\.GT\.'

# Ignorar espaços em branco e tabulações (opção pelo Formato Livre) [1]
t_ignore = ' \t'

# 4. Expressões Regulares com Funções (Para processamento adicional)

# Regra para Strings (texto entre aspas simples) [2]
def t_STRING(t):
    r"'.*?'"
    t.value = t.value[1:-1] # Remove as aspas simples do início e fim
    return t

# Regra para Números (Inteiros) [2]
def t_NUMBER(t):
    r'\d+'
    t.value = int(t.value) # Converte o valor lido para um inteiro Python
    return t

# Regra para Identificadores e Palavras-Chave [1]
def t_ID(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'
    # Converte para minúsculas para verificar o dicionário (Fortran é case-insensitive)
    t.type = reserved.get(t.value.lower(), 'ID') 
    return t

# Regra para rastrear o número de linhas (útil para debug)
def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

# Regra de tratamento de erros no lexer
def t_error(t):
    print(f"Erro Léxico: Caractere ilegal '{t.value}' na linha {t.lexer.lineno}")
    t.lexer.skip(1)

# 5. Construção do Lexer [1]
lexer = lex.lex()

# --- BLOCO DE TESTE ---
# Este bloco corre apenas se executares o ficheiro diretamente.
"""
if __name__ == '__main__':
    # Exemplo 1 do guião: Olá, Mundo! [2]
    codigo_teste = '''
    PROGRAM CONVERSOR
INTEGER NUM, BASE, RESULT, CONVRT
PRINT *, 'INTRODUZA UM NUMERO DECIMAL INTEIRO:'
READ *, NUM
DO 10 BASE = 2, 9
RESULT = CONVRT(NUM, BASE)
PRINT *, 'BASE ', BASE, ': ', RESULT
10 CONTINUE
END
INTEGER FUNCTION CONVRT(N, B)
INTEGER N, B, QUOT, REM, POT, VAL
VAL = 0
POT = 1
QUOT = N
20 IF (QUOT .GT. 0) THEN
REM = MOD(QUOT, B)
VAL = VAL + (REM * POT)
QUOT = QUOT / B
POT = POT * 10
GOTO 20
ENDIF
CONVRT = VAL
RETURN
END
    '''

    lexer.input(codigo_teste)
    
    # Imprime todos os tokens encontrados
    for token in lexer:
        print(token)
        """
