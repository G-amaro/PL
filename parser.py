import ply.yacc as yacc

from lexer import tokens
from ast_nodes import (
    FileNode, Program, Function, Subroutine,
    Decl, Labeled, Assign, Read, Print, If, Goto, Do, Continue, Return, CallStmt,
    LVar, LIndex, Num, RealLit, StrLit, BoolLit, Ident, FuncOrIndex, BinOp, UnaryOp,
)

precedence = (
    ('left', 'OR'),
    ('left', 'AND'),
    ('right', 'NOT'),
    ('nonassoc', 'EQ', 'NE', 'LE', 'GE', 'LT', 'GT'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE'),
    ('right', 'UMINUS'),
)

# --- Ficheiro / unidades ---

def p_ficheiro(p):
    '''ficheiro : unidades'''
    p[0] = FileNode(units=p[1])

def p_unidades_many(p):
    '''unidades : unidades unidade'''
    p[0] = p[1] + [p[2]]

def p_unidades_one(p):
    '''unidades : unidade'''
    p[0] = [p[1]]

def p_unidade(p):
    '''unidade : programa_principal
               | funcao
               | subrotina'''
    p[0] = p[1]

def p_programa_principal(p):
    '''programa_principal : PROGRAM ID comandos END'''
    p[0] = Program(name=p[2], body=p[3])

def p_funcao(p):
    '''funcao : tipo FUNCTION ID LPAREN lista_params RPAREN comandos END'''
    p[0] = Function(rtype=p[1], name=p[3], params=p[5], body=p[7])

def p_subrotina(p):
    '''subrotina : SUBROUTINE ID LPAREN lista_params RPAREN comandos END
                 | SUBROUTINE ID LPAREN RPAREN comandos END'''
    if len(p) == 8:
        p[0] = Subroutine(name=p[2], params=p[4], body=p[6])
    else:
        p[0] = Subroutine(name=p[2], params=[], body=p[5])

def p_lista_params_many(p):
    '''lista_params : lista_params COMMA ID'''
    p[0] = p[1] + [p[3]]

def p_lista_params_one(p):
    '''lista_params : ID'''
    p[0] = [p[1]]

# --- Comandos ---

def p_comandos_many(p):
    '''comandos : comandos comando'''
    p[0] = p[1] + [p[2]]

def p_comandos_one(p):
    '''comandos : comando'''
    p[0] = [p[1]]

def p_comando_labeled(p):
    '''comando : NUMBER comando_base'''
    p[0] = Labeled(label=str(p[1]), stmt=p[2])

def p_comando_plain(p):
    '''comando : comando_base'''
    p[0] = p[1]

def p_comando_base(p):
    '''comando_base : declaracao
                    | atribuicao
                    | print_stmt
                    | read_stmt
                    | if_then
                    | if_then_else
                    | goto_stmt
                    | do_loop
                    | continue_stmt
                    | return_stmt
                    | call_stmt'''
    p[0] = p[1]

# --- Declarações ---

def p_declaracao(p):
    '''declaracao : tipo lista_decl'''
    p[0] = Decl(vtype=p[1], items=p[2])

def p_tipo(p):
    '''tipo : INTEGER
            | REAL
            | LOGICAL'''
    p[0] = p[1].upper()

def p_lista_decl_many(p):
    '''lista_decl : lista_decl COMMA elemento_decl'''
    p[0] = p[1] + [p[3]]

def p_lista_decl_one(p):
    '''lista_decl : elemento_decl'''
    p[0] = [p[1]]

def p_elemento_decl_scalar(p):
    '''elemento_decl : ID'''
    p[0] = (p[1], None)

def p_elemento_decl_array(p):
    '''elemento_decl : ID LPAREN NUMBER RPAREN'''
    p[0] = (p[1], p[3])

# --- Atribuição ---

def p_atribuicao(p):
    '''atribuicao : lvalue EQUALS expressao'''
    p[0] = Assign(target=p[1], expr=p[3])

def p_lvalue_scalar(p):
    '''lvalue : ID'''
    p[0] = LVar(name=p[1])

def p_lvalue_index(p):
    '''lvalue : ID LPAREN expressao RPAREN'''
    p[0] = LIndex(name=p[1], index=p[3])

# --- I/O ---

def p_read_stmt(p):
    '''read_stmt : READ TIMES COMMA lvalue'''
    p[0] = Read(target=p[4])

def p_print_stmt(p):
    '''print_stmt : PRINT TIMES COMMA lista_print'''
    p[0] = Print(items=p[4])

def p_lista_print_many(p):
    '''lista_print : lista_print COMMA elemento_print'''
    p[0] = p[1] + [p[3]]

def p_lista_print_one(p):
    '''lista_print : elemento_print'''
    p[0] = [p[1]]

def p_elemento_print_str(p):
    '''elemento_print : STRING'''
    p[0] = StrLit(value=p[1])

def p_elemento_print_expr(p):
    '''elemento_print : expressao'''
    p[0] = p[1]

# --- Controlo de fluxo ---

def p_goto_stmt(p):
    '''goto_stmt : GOTO NUMBER'''
    p[0] = Goto(label=str(p[2]))

def p_do_loop(p):
    '''do_loop : DO NUMBER ID EQUALS expressao COMMA expressao
               | DO NUMBER ID EQUALS expressao COMMA expressao COMMA expressao'''
    if len(p) == 8:
        p[0] = Do(label=str(p[2]), var=p[3], start=p[5], end=p[7], step=None)
    else:
        p[0] = Do(label=str(p[2]), var=p[3], start=p[5], end=p[7], step=p[9])

def p_if_then(p):
    '''if_then : IF LPAREN expressao RPAREN THEN comandos ENDIF'''
    p[0] = If(cond=p[3], then_body=p[6], else_body=[])

def p_if_then_else(p):
    '''if_then_else : IF LPAREN expressao RPAREN THEN comandos ELSE comandos ENDIF'''
    p[0] = If(cond=p[3], then_body=p[6], else_body=p[8])

def p_continue_stmt(p):
    '''continue_stmt : CONTINUE'''
    p[0] = Continue()

def p_return_stmt(p):
    '''return_stmt : RETURN'''
    p[0] = Return()

def p_call_stmt_args(p):
    '''call_stmt : CALL ID LPAREN lista_args RPAREN'''
    p[0] = CallStmt(name=p[2], args=p[4])

def p_call_stmt_noargs(p):
    '''call_stmt : CALL ID LPAREN RPAREN
                 | CALL ID'''
    p[0] = CallStmt(name=p[2], args=[])

# --- Expressões ---

def p_expr_binop(p):
    '''expressao : expressao PLUS expressao
                 | expressao MINUS expressao
                 | expressao TIMES expressao
                 | expressao DIVIDE expressao
                 | expressao LE expressao
                 | expressao GE expressao
                 | expressao LT expressao
                 | expressao GT expressao
                 | expressao EQ expressao
                 | expressao NE expressao
                 | expressao AND expressao
                 | expressao OR expressao'''
    # Normalise operator spelling — `.LE.` / `.le.` both become 'LE'.
    raw = p[2]
    op = raw.strip('.').upper() if raw.startswith('.') else raw
    p[0] = BinOp(op=op, lhs=p[1], rhs=p[3])

def p_expr_unary_minus(p):
    '''expressao : MINUS expressao %prec UMINUS'''
    p[0] = UnaryOp(op='-', expr=p[2])

def p_expr_not(p):
    '''expressao : NOT expressao'''
    p[0] = UnaryOp(op='NOT', expr=p[2])

def p_expr_parens(p):
    '''expressao : LPAREN expressao RPAREN'''
    p[0] = p[2]

def p_expr_func_or_index(p):
    '''expressao : ID LPAREN lista_args RPAREN'''
    p[0] = FuncOrIndex(name=p[1], args=p[3])

def p_lista_args_many(p):
    '''lista_args : lista_args COMMA expressao'''
    p[0] = p[1] + [p[3]]

def p_lista_args_one(p):
    '''lista_args : expressao'''
    p[0] = [p[1]]

def p_expr_number(p):
    '''expressao : NUMBER'''
    p[0] = Num(value=p[1])

def p_expr_float(p):
    '''expressao : FLOAT'''
    p[0] = RealLit(value=p[1])

def p_expr_true(p):
    '''expressao : TRUE'''
    p[0] = BoolLit(value=True)

def p_expr_false(p):
    '''expressao : FALSE'''
    p[0] = BoolLit(value=False)

def p_expr_id(p):
    '''expressao : ID'''
    p[0] = Ident(name=p[1])

# --- Erros ---

def p_error(p):
    if p:
        print(f"Erro de sintaxe perto do token '{p.value}' (linha {p.lineno})")
    else:
        print("Erro de sintaxe no final do ficheiro")

parser = yacc.yacc()

def parse(source: str):
    """Parses source code and returns the FileNode root."""
    from lexer import lexer as _lx
    _lx.lineno = 1
    return parser.parse(source, lexer=_lx)

if __name__ == '__main__':
    code = """
PROGRAM HELLO
PRINT *, 'Ola, Mundo!'
END
"""
    tree = parse(code)
    print(tree)
