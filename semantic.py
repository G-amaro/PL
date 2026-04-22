# Análise semântica sobre a AST. Corre uma passagem por cada unidade
# (PROGRAM, FUNCTION, SUBROUTINE) e verifica:
#   - declarações sem duplicados e usadas só depois de declaradas
#   - coerência de tipos em atribuições e expressões
#   - condição do IF tem de ser LOGICAL
#   - variável do ciclo DO declarada
#   - todos os labels referenciados estão definidos
#   - os labels dos DO terminam num CONTINUE (pedido no enunciado)
# Os erros são acumulados numa lista e devolvidos; não atiram excepção.

from ast_nodes import (
    FileNode, Program, Function, Subroutine,
    Decl, Labeled, Assign, Read, Print, If, Goto, Do, Continue, Return, CallStmt,
    LVar, LIndex, Num, RealLit, StrLit, BoolLit, Ident, FuncOrIndex, BinOp, UnaryOp,
)

# funções intrínsecas do Fortran 77 que aceitamos como já declaradas
BUILTINS = {
    'MOD': ('INTEGER', 2),
    'ABS': ('INTEGER', 1),
    'MIN': ('INTEGER', 2),
    'MAX': ('INTEGER', 2),
}


class Scope:
    def __init__(self):
        self.vars = {}        # NAME -> {'type', 'is_array', 'size'}
        self.labels = {}      # '10' -> the labelled inner stmt
        self.do_labels = set()  # labels used as DO terminators


def analyze(file_node):
    errors = []
    # assinaturas das funções/subrotinas visíveis
    sigs = dict(BUILTINS)
    for unit in file_node.units:
        if isinstance(unit, Function):
            sigs[unit.name.upper()] = (unit.rtype, len(unit.params))
        elif isinstance(unit, Subroutine):
            sigs[unit.name.upper()] = ('SUBROUTINE', len(unit.params))
    for unit in file_node.units:
        _analyze_unit(unit, sigs, errors)
    return errors


def _analyze_unit(unit, sigs, errors):
    scope = Scope()
    # dentro da FUNCTION, o nome da função dá para atribuir o valor de retorno
    if isinstance(unit, Function):
        scope.vars[unit.name.upper()] = {'type': unit.rtype, 'is_array': False, 'size': None}
    # params registados sem tipo; são preenchidos pelas declarações a seguir
    params = getattr(unit, 'params', [])
    for pn in params:
        scope.vars[pn.upper()] = {'type': None, 'is_array': False, 'size': None}

    # primeira passagem: recolher labels
    _collect_labels(unit.body, scope, errors)

    # segunda passagem: percorrer os comandos
    for stmt in unit.body:
        _check_stmt(stmt, scope, sigs, errors)

    # valida que o label do DO aterra num CONTINUE
    for lbl in scope.do_labels:
        target = scope.labels.get(lbl)
        if target is None:
            errors.append(f"ERRO SEMÂNTICO: label {lbl} usado em DO não está definido.")
        elif not isinstance(target, Continue):
            errors.append(
                f"ERRO SEMÂNTICO: label {lbl} do ciclo DO deveria marcar um CONTINUE."
            )


def _collect_labels(body, scope, errors):
    for stmt in body:
        if isinstance(stmt, Labeled):
            if stmt.label in scope.labels:
                errors.append(f"ERRO SEMÂNTICO: label {stmt.label} duplicado.")
            scope.labels[stmt.label] = stmt.stmt
            # recorre ao stmt que leva o label — pode ser um IF
            _collect_labels([stmt.stmt], scope, errors)
        elif isinstance(stmt, If):
            # labels dentro do then/else também têm de ser registados
            _collect_labels(stmt.then_body, scope, errors)
            _collect_labels(stmt.else_body, scope, errors)


def _check_stmt(stmt, scope, sigs, errors):
    if isinstance(stmt, Labeled):
        _check_stmt(stmt.stmt, scope, sigs, errors)
        return

    if isinstance(stmt, Decl):
        for name, size in stmt.items:
            nu = name.upper()
            existing = scope.vars.get(nu)
            if existing and existing['type'] is not None:
                errors.append(f"ERRO SEMÂNTICO: variável '{name}' já declarada.")
            scope.vars[nu] = {'type': stmt.vtype, 'is_array': size is not None, 'size': size}
        return

    if isinstance(stmt, Assign):
        tgt_type = _lvalue_type(stmt.target, scope, errors)
        exp_type = _expr_type(stmt.expr, scope, sigs, errors)
        if tgt_type and exp_type and tgt_type != exp_type and exp_type != 'ERROR':
            errors.append(
                f"ERRO SEMÂNTICO: coerência de tipos — atribuição a '{_lvalue_name(stmt.target)}' "
                f"({tgt_type}) recebe {exp_type}."
            )
        return

    if isinstance(stmt, Read):
        _lvalue_type(stmt.target, scope, errors)
        return

    if isinstance(stmt, Print):
        for item in stmt.items:
            if isinstance(item, StrLit):
                continue
            _expr_type(item, scope, sigs, errors)
        return

    if isinstance(stmt, If):
        ct = _expr_type(stmt.cond, scope, sigs, errors)
        if ct and ct != 'LOGICAL' and ct != 'ERROR':
            errors.append("ERRO SEMÂNTICO: condição do IF deve ser LOGICAL.")
        for s in stmt.then_body: _check_stmt(s, scope, sigs, errors)
        for s in stmt.else_body: _check_stmt(s, scope, sigs, errors)
        return

    if isinstance(stmt, Goto):
        if stmt.label not in scope.labels:
            errors.append(f"ERRO SEMÂNTICO: label {stmt.label} referenciado por GOTO não existe.")
        return

    if isinstance(stmt, Do):
        scope.do_labels.add(stmt.label)
        v = scope.vars.get(stmt.var.upper())
        if not v or v['type'] is None:
            errors.append(f"ERRO SEMÂNTICO: variável de ciclo '{stmt.var}' não declarada.")
        _expr_type(stmt.start, scope, sigs, errors)
        _expr_type(stmt.end, scope, sigs, errors)
        if stmt.step is not None:
            _expr_type(stmt.step, scope, sigs, errors)
        return

    if isinstance(stmt, (Continue, Return)):
        return

    if isinstance(stmt, CallStmt):
        sig = sigs.get(stmt.name.upper())
        if not sig:
            errors.append(f"ERRO SEMÂNTICO: subrotina '{stmt.name}' não definida.")
        for a in stmt.args:
            _expr_type(a, scope, sigs, errors)
        return


def _lvalue_name(lv):
    return lv.name

def _lvalue_type(lv, scope, errors):
    nu = lv.name.upper()
    v = scope.vars.get(nu)
    if not v or v['type'] is None:
        errors.append(f"ERRO SEMÂNTICO: variável '{lv.name}' não declarada.")
        return None
    if isinstance(lv, LIndex) and not v['is_array']:
        errors.append(f"ERRO SEMÂNTICO: '{lv.name}' não é um array.")
    return v['type']


def _expr_type(e, scope, sigs, errors):
    if isinstance(e, Num): return 'INTEGER'
    if isinstance(e, RealLit): return 'REAL'
    if isinstance(e, BoolLit): return 'LOGICAL'
    if isinstance(e, StrLit): return 'STRING'

    if isinstance(e, Ident):
        v = scope.vars.get(e.name.upper())
        if not v or v['type'] is None:
            errors.append(f"ERRO SEMÂNTICO: variável '{e.name}' não declarada.")
            return 'ERROR'
        return v['type']

    if isinstance(e, FuncOrIndex):
        nu = e.name.upper()
        # array indexing wins if declared
        v = scope.vars.get(nu)
        if v and v['is_array']:
            for a in e.args: _expr_type(a, scope, sigs, errors)
            return v['type']
        # otherwise must be a function
        sig = sigs.get(nu)
        if not sig:
            errors.append(f"ERRO SEMÂNTICO: função/array '{e.name}' não declarado.")
            return 'ERROR'
        for a in e.args: _expr_type(a, scope, sigs, errors)
        rtype = sig[0]
        return rtype if rtype != 'SUBROUTINE' else 'ERROR'

    if isinstance(e, UnaryOp):
        t = _expr_type(e.expr, scope, sigs, errors)
        if e.op == '-':
            if t in ('INTEGER', 'REAL'): return t
            errors.append(f"ERRO SEMÂNTICO: '-' unário requer numérico (recebeu {t}).")
            return 'ERROR'
        if e.op == 'NOT':
            if t == 'LOGICAL': return 'LOGICAL'
            errors.append(f"ERRO SEMÂNTICO: '.NOT.' requer LOGICAL (recebeu {t}).")
            return 'ERROR'

    if isinstance(e, BinOp):
        lt = _expr_type(e.lhs, scope, sigs, errors)
        rt = _expr_type(e.rhs, scope, sigs, errors)
        op = e.op
        if op in ('+', '-', '*', '/'):
            if lt == 'INTEGER' and rt == 'INTEGER': return 'INTEGER'
            if lt in ('INTEGER', 'REAL') and rt in ('INTEGER', 'REAL'):
                return 'REAL'
            errors.append(f"ERRO SEMÂNTICO: aritmética requer numérico ({lt} {op} {rt}).")
            return 'ERROR'
        if op in ('LE', 'GE', 'LT', 'GT', 'EQ', 'NE'):
            return 'LOGICAL'
        if op in ('AND', 'OR'):
            if lt == 'LOGICAL' and rt == 'LOGICAL': return 'LOGICAL'
            if 'ERROR' in (lt, rt): return 'ERROR'
            errors.append(f"ERRO SEMÂNTICO: '{op}' requer LOGICAL ({lt} {op} {rt}).")
            return 'ERROR'
        return 'ERROR'

    return 'ERROR'
