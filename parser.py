import ply.yacc as yacc
from lexer import tokens 

# --- PRECEDÊNCIA DE OPERADORES ---
precedence = (
    ('left', 'AND'),
    ('left', 'EQ', 'LE', 'GT'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE'),
)

# 1. Regra principal (Axioma): O ficheiro pode ter várias unidades de código
def p_ficheiro(p):
    '''ficheiro : unidades'''

def p_unidades(p):
    '''unidades : unidades unidade
                | unidade'''
    pass

# Uma unidade pode ser o programa principal ou uma função
def p_unidade(p):
    '''unidade : programa_principal
               | funcao'''
    pass

def p_programa_principal(p):
    '''programa_principal : PROGRAM ID comandos END'''
    # Mantivemos o teu p[2] que está certíssimo para imprimir o ID!
    print(f"-> Programa principal '{p[2]}' validado!")

# NOVO: Regra para validar funções (Valorização da nota)
def p_funcao(p):
    '''funcao : tipo FUNCTION ID LPAREN lista_ids RPAREN comandos END'''
    print(f"-> Função '{p[3]}' validada!")

# 2. Lista de comandos
def p_comandos_lista(p):
    '''comandos : comandos comando
                | comando'''
    pass

def p_comando(p):
    '''comando : comando_base
               | NUMBER comando_base'''
    pass

# NOVO: Adicionado o 'return_stmt' à lista de comandos possíveis
def p_comando_base(p):
    '''comando_base : declaracao
                    | atribuicao
                    | print
                    | read
                    | if_then
                    | if_then_else
                    | goto
                    | do_loop
                    | continue_stmt
                    | return_stmt'''
    pass

# --- REGRAS PARA CADA COMANDO ---

def p_declaracao(p):
    '''declaracao : tipo lista_ids'''
    pass

def p_tipo(p):
    '''tipo : INTEGER
            | LOGICAL'''
    pass

def p_lista_ids(p):
    '''lista_ids : lista_ids COMMA elemento_decl
                 | elemento_decl'''
    pass

def p_elemento_decl(p):
    '''elemento_decl : ID
                     | ID LPAREN NUMBER RPAREN'''
    pass

def p_alvo(p):
    '''alvo : ID
            | ID LPAREN lista_args RPAREN'''
    pass

def p_atribuicao(p):
    '''atribuicao : alvo EQUALS expressao'''
    pass

def p_read(p):
    '''read : READ TIMES COMMA alvo'''
    pass

def p_print(p):
    '''print : PRINT TIMES COMMA lista_print'''
    pass

def p_lista_print(p):
    '''lista_print : lista_print COMMA elemento_print
                   | elemento_print'''
    pass

def p_elemento_print(p):
    '''elemento_print : STRING
                      | expressao'''
    pass

# --- CONTROLO DE FLUXO ---

def p_if_then(p):
    '''if_then : IF LPAREN expressao RPAREN THEN comandos ENDIF'''
    pass

def p_if_then_else(p):
    '''if_then_else : IF LPAREN expressao RPAREN THEN comandos ELSE comandos ENDIF'''
    pass

def p_goto(p):
    '''goto : GOTO NUMBER'''
    pass

def p_do_loop(p):
    '''do_loop : DO NUMBER ID EQUALS expressao COMMA expressao'''
    pass

def p_continue_stmt(p):
    '''continue_stmt : CONTINUE'''
    pass

# NOVO: Comando RETURN usado nas funções
def p_return_stmt(p):
    '''return_stmt : RETURN'''
    pass

# --- EXPRESSÕES (Incluído para garantir o funcionamento total) ---

def p_expressao_operacoes(p):
    '''expressao : expressao PLUS expressao
                 | expressao MINUS expressao
                 | expressao TIMES expressao
                 | expressao DIVIDE expressao
                 | expressao LE expressao
                 | expressao EQ expressao
                 | expressao AND expressao
                 | expressao GT expressao'''
    pass

def p_expressao_parenteses(p):
    '''expressao : LPAREN expressao RPAREN'''
    pass

def p_expressao_funcao_array(p):
    '''expressao : ID LPAREN lista_args RPAREN'''
    pass

def p_lista_args(p):
    '''lista_args : lista_args COMMA expressao
                  | expressao'''
    pass

def p_expressao_simples(p):
    '''expressao : NUMBER
                 | ID
                 | TRUE
                 | FALSE'''
    pass

# 4. Tratamento de erros
def p_error(p):
    if p:
        print(f"Erro de sintaxe perto do token '{p.value}' (linha {p.lineno})")
    else:
        print("Erro de sintaxe no final do ficheiro")

# Constrói o parser
parser = yacc.yacc()

# --- BLOCO DE TESTE (Exemplo 5 do Guião) ---
if __name__ == '__main__':
    from lexer import lexer
    
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
    parser.parse(codigo_teste, lexer=lexer)
