import ply.yacc as yacc
from lexer import tokens 

# --- VARIÁVEIS GLOBAIS PARA ANÁLISE SEMÂNTICA ---
tabela_variaveis = {}
labels_definidos = set()
labels_referenciados = set()

precedence = (
    ('left', 'AND'),
    ('left', 'EQ', 'LE', 'GT'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE'),
)

def p_ficheiro(p):
    '''ficheiro : unidades'''
    for lb in labels_referenciados:
        if lb not in labels_definidos:
            print(f"ERRO SEMÂNTICO: Label {lb} referenciado mas não definido!")

def p_unidades(p):
    '''unidades : unidades unidade
                | unidade'''
    pass

def p_unidade(p):
    '''unidade : programa_principal
               | funcao'''
    # Limpa o contexto para a próxima unidade
    tabela_variaveis.clear()
    labels_definidos.clear()
    labels_referenciados.clear()

def p_programa_principal(p):
    '''programa_principal : PROGRAM ID comandos END'''
    print(f"-> Programa principal '{p[2]}' validado!")

# AJUSTE: Adicionada a regra vazia 'registo_func' para registar o nome da função antes dos comandos
def p_funcao(p):
    '''funcao : tipo FUNCTION ID LPAREN lista_ids RPAREN registo_func comandos END'''
    print(f"-> Função '{p[3]}' validada!")

def p_registo_func(p):
    '''registo_func :'''
    # p[-4] é o ID da função, p[-6] é o tipo. Registamos para permitir atribuição de retorno.
    nome_f = p[-4].upper()
    tabela_variaveis[nome_f] = p[-6]
    pass

def p_comandos_lista(p):
    '''comandos : comandos comando
                | comando'''
    pass

def p_comando(p):
    '''comando : comando_base
               | NUMBER comando_base'''
    if len(p) == 3:
        labels_definidos.add(str(p[1]))

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

# --- REGRAS DE DECLARAÇÃO ---

def p_declaracao(p):
    '''declaracao : tipo lista_ids'''
    tipo_var = p[1]
    for var in p[2]:
        nome_n = var.upper() # Normalizamos para evitar erros de case
        if nome_n in tabela_variaveis:
            print(f"ERRO SEMÂNTICO: Variável '{var}' já declarada!")
        else:
            tabela_variaveis[nome_n] = tipo_var
            print(f"-> Semântica: Variável '{var}' registada como {tipo_var}.")

def p_tipo(p):
    '''tipo : INTEGER
            | LOGICAL'''
    p[0] = p[1]

def p_lista_ids(p):
    '''lista_ids : lista_ids COMMA elemento_decl
                 | elemento_decl'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_elemento_decl(p):
    '''elemento_decl : ID
                     | ID LPAREN NUMBER RPAREN'''
    p[0] = p[1]

# --- ATRIBUIÇÃO E COERÊNCIA ---

def p_atribuicao(p):
    '''atribuicao : alvo EQUALS expressao'''
    nome_v = p[1].upper()
    tipo_e = p[3]
    
    if nome_v not in tabela_variaveis:
        print(f"ERRO SEMÂNTICO: Variável '{p[1]}' não declarada!")
    elif tipo_e != "ERROR" and tabela_variaveis[nome_v] != tipo_e:
        print(f"ERRO SEMÂNTICO: Coerência de tipos falhou em '{p[1]}' ({tabela_variaveis[nome_v]} != {tipo_e})")

def p_alvo(p):
    '''alvo : ID
            | ID LPAREN lista_args RPAREN'''
    p[0] = p[1]

def p_read(p):
    '''read : READ TIMES COMMA alvo'''
    if p[4].upper() not in tabela_variaveis:
        print(f"ERRO SEMÂNTICO: Variável '{p[4]}' no READ não declarada!")

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

def p_goto(p):
    '''goto : GOTO NUMBER'''
    labels_referenciados.add(str(p[2]))

def p_do_loop(p):
    '''do_loop : DO NUMBER ID EQUALS expressao COMMA expressao'''
    labels_referenciados.add(str(p[2]))
    if p[3].upper() not in tabela_variaveis:
        print(f"ERRO SEMÂNTICO: Variável de ciclo '{p[3]}' não declarada!")

def p_if_then(p):
    '''if_then : IF LPAREN expressao RPAREN THEN comandos ENDIF'''
    if p[3] != 'LOGICAL' and p[3] != 'ERROR':
        print("ERRO SEMÂNTICO: Condição do IF deve ser LOGICAL.")

def p_if_then_else(p):
    '''if_then_else : IF LPAREN expressao RPAREN THEN comandos ELSE comandos ENDIF'''
    if p[3] != 'LOGICAL' and p[3] != 'ERROR':
        print("ERRO SEMÂNTICO: Condição do IF deve ser LOGICAL.")

def p_continue_stmt(p):
    '''continue_stmt : CONTINUE'''
    pass

def p_return_stmt(p):
    '''return_stmt : RETURN'''
    pass

# --- EXPRESSÕES ---

def p_expressao_operacoes(p):
    '''expressao : expressao PLUS expressao
                 | expressao MINUS expressao
                 | expressao TIMES expressao
                 | expressao DIVIDE expressao'''
    if p[1] == 'INTEGER' and p[3] == 'INTEGER':
        p[0] = 'INTEGER'
    else:
        print(f"ERRO SEMÂNTICO: Operação aritmética requer INTEGER (recebeu {p[1]} e {p[3]})")
        p[0] = 'ERROR'

def p_expressao_logica(p):
    '''expressao : expressao LE expressao
                 | expressao EQ expressao
                 | expressao GT expressao
                 | expressao AND expressao'''
    p[0] = 'LOGICAL'

def p_expressao_parenteses(p):
    '''expressao : LPAREN expressao RPAREN'''
    p[0] = p[2]

def p_expressao_funcao_array(p):
    '''expressao : ID LPAREN lista_args RPAREN'''
    p[0] = 'INTEGER'

def p_lista_args(p):
    '''lista_args : lista_args COMMA expressao
                  | expressao'''
    pass

def p_expressao_simples(p):
    '''expressao : NUMBER
                 | ID
                 | TRUE
                 | FALSE'''
    val_s = str(p[1])
    if val_s.isdigit():
        p[0] = 'INTEGER'
    elif val_s.upper() in ['.TRUE.', '.FALSE.']:
        p[0] = 'LOGICAL'
    else: 
        nome_v = val_s.upper()
        p[0] = tabela_variaveis.get(nome_v, 'ERROR')
        if p[0] == 'ERROR':
            print(f"ERRO SEMÂNTICO: Variável '{p[1]}' não declarada!")

def p_error(p):
    if p:
        print(f"Erro de sintaxe perto do token '{p.value}' (linha {p.lineno})")
    else:
        print("Erro de sintaxe no final do ficheiro")

parser = yacc.yacc()

if __name__ == '__main__':
    from lexer import lexer
    codigo_teste = '''
PROGRAM HELLO
PRINT *, 'Ola, Mundo!'
END
'''
    parser.parse(codigo_teste, lexer=lexer)