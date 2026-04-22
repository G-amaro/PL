# Passagens de otimização sobre a IR. Corridas até fixpoint (ou cap
# de segurança). Cada passagem é neutra em semântica; os testes em
# run_tests.py garantem isso.
# Passagens:
#   - constant folding  (BinOp(K,K) e UnaryOp(K) -> Copy(K))
#   - simplificação algébrica  (x+0, x*1, x*0, x-0, x/1, x-x)
#   - eliminação de código inalcançável (depois de Goto/Return/Halt)
#   - copy propagation dentro do bloco básico
#   - eliminação de temporários não lidos
# Um bloco básico vai de label a label (ou a branch) — as passagens
# locais limpam estado nas fronteiras.

from dataclasses import replace
from typing import Iterable

from ir import (
    Program, Function,
    V, K,
    Copy, BinOp, UnaryOp, Label, Goto, IfFalse, Param, Call, Return,
    ArrLoad, ArrStore, AllocArr, ReadInt,
    PrintStr, PrintInt, PrintReal, PrintLn, Halt, Const,
)


# ---- helpers ----

def _is_tmp(name: str) -> bool:
    return name.startswith("__t")


def _k_int(op):
    return isinstance(op, K) and isinstance(op.value, (int, bool))


def _k_val(op, default=None):
    return op.value if isinstance(op, K) else default


# ---- pass: constant folding ----

def constant_fold(body):
    out = []
    changed = False
    for ins in body:
        if isinstance(ins, BinOp) and isinstance(ins.a, K) and isinstance(ins.b, K):
            folded = _fold_binop(ins.op, ins.a.value, ins.b.value)
            if folded is not None:
                out.append(Copy(ins.dest, K(folded)))
                changed = True
                continue
        if isinstance(ins, UnaryOp) and isinstance(ins.a, K):
            folded = _fold_unary(ins.op, ins.a.value)
            if folded is not None:
                out.append(Copy(ins.dest, K(folded)))
                changed = True
                continue
        out.append(ins)
    return out, changed


def _fold_binop(op, a, b):
    try:
        if op == '+': return a + b
        if op == '-': return a - b
        if op == '*': return a * b
        if op == '/':
            # Fortran truncating integer division
            if b == 0: return None  # undefined; let runtime crash
            q = abs(a) // abs(b)
            return -q if (a < 0) ^ (b < 0) else q
        if op == 'MOD':
            if b == 0: return None
            r = abs(a) % abs(b)
            return -r if a < 0 else r
        if op == 'LT': return 1 if a < b else 0
        if op == 'LE': return 1 if a <= b else 0
        if op == 'GT': return 1 if a > b else 0
        if op == 'GE': return 1 if a >= b else 0
        if op == 'EQ': return 1 if a == b else 0
        if op == 'NE': return 1 if a != b else 0
        if op == 'AND': return 1 if (a and b) else 0
        if op == 'OR':  return 1 if (a or b) else 0
    except Exception:
        return None
    return None


def _fold_unary(op, a):
    if op == 'NEG': return -a
    if op == 'NOT': return 0 if a else 1
    if op == 'ABS': return abs(a)
    return None


# ---- pass: algebraic simplification ----

def algebraic_simplify(body):
    out = []
    changed = False
    for ins in body:
        new = _simplify(ins)
        if new is not ins:
            changed = True
        out.append(new)
    return out, changed


def _simplify(ins):
    if not isinstance(ins, BinOp):
        return ins
    a, b, op = ins.a, ins.b, ins.op

    # x + 0, 0 + x -> x
    if op == '+' and _k_val(b) == 0: return Copy(ins.dest, a)
    if op == '+' and _k_val(a) == 0: return Copy(ins.dest, b)
    # x - 0 -> x
    if op == '-' and _k_val(b) == 0: return Copy(ins.dest, a)
    # x * 1, 1 * x -> x
    if op == '*' and _k_val(b) == 1: return Copy(ins.dest, a)
    if op == '*' and _k_val(a) == 1: return Copy(ins.dest, b)
    # x * 0, 0 * x -> 0
    if op == '*' and (_k_val(a) == 0 or _k_val(b) == 0):
        return Copy(ins.dest, K(0))
    # x / 1 -> x
    if op == '/' and _k_val(b) == 1: return Copy(ins.dest, a)
    # x - x -> 0 (same variable)
    if op == '-' and isinstance(a, V) and isinstance(b, V) and a.name == b.name:
        return Copy(ins.dest, K(0))
    # x AND 0 -> 0; x AND 1 -> x
    if op == 'AND':
        if _k_val(a) == 0 or _k_val(b) == 0: return Copy(ins.dest, K(0))
        if _k_val(a) == 1: return Copy(ins.dest, b)
        if _k_val(b) == 1: return Copy(ins.dest, a)
    # x OR 0 -> x; x OR 1 -> 1
    if op == 'OR':
        if _k_val(a) == 1 or _k_val(b) == 1: return Copy(ins.dest, K(1))
        if _k_val(a) == 0: return Copy(ins.dest, b)
        if _k_val(b) == 0: return Copy(ins.dest, a)
    return ins


# ---- pass: unreachable elimination ----

TERMINATORS = (Goto, Return, Halt)


def remove_unreachable(body):
    out = []
    unreachable = False
    changed = False
    for ins in body:
        if isinstance(ins, Label):
            unreachable = False
            out.append(ins)
            continue
        if unreachable:
            changed = True
            continue
        out.append(ins)
        if isinstance(ins, TERMINATORS):
            unreachable = True
    return out, changed


# ---- pass: copy propagation (basic-block local) ----

def copy_propagate(body):
    out = []
    subst = {}  # nome_temp -> operando fonte (V ou K)
    changed = False
    for ins in body:
        # substituir operandos de leitura com o que temos em subst
        new = _subst_operands(ins, subst)
        if new is not ins:
            changed = True
        out.append(new)

        # invalidar entradas antigas para o nome que esta instrução define
        # e quaisquer entradas cujo source dependa desse nome.
        defined = _defined_name(new)
        if defined is not None:
            subst.pop(defined, None)
            for k in list(subst):
                v = subst[k]
                if isinstance(v, V) and v.name == defined:
                    subst.pop(k, None)

        # se a nova instrução for Copy(t_temp, src), regista o alias
        if isinstance(new, Copy) and isinstance(new.dest, V) and _is_tmp(new.dest.name):
            src = new.src
            if isinstance(src, V) and src.name in subst:
                src = subst[src.name]
            subst[new.dest.name] = src

        # fronteira de bloco básico -> esquece tudo
        if isinstance(new, (Label, Goto, IfFalse, Call, Return, Halt)):
            subst.clear()

    return out, changed


def _defined_name(ins):
    if isinstance(ins, (Copy, BinOp, UnaryOp, ArrLoad, ReadInt)):
        return ins.dest.name
    if isinstance(ins, Call) and ins.dest is not None:
        return ins.dest.name
    return None


def _subst_operand(op, subst):
    if isinstance(op, V) and op.name in subst:
        return subst[op.name]
    return op


def _subst_operands(ins, subst):
    if not subst:
        return ins
    def s(x): return _subst_operand(x, subst)

    if isinstance(ins, BinOp):
        na, nb = s(ins.a), s(ins.b)
        if na is ins.a and nb is ins.b: return ins
        return BinOp(ins.dest, ins.op, na, nb)
    if isinstance(ins, UnaryOp):
        na = s(ins.a)
        if na is ins.a: return ins
        return UnaryOp(ins.dest, ins.op, na)
    if isinstance(ins, Copy):
        ns = s(ins.src)
        if ns is ins.src: return ins
        return Copy(ins.dest, ns)
    if isinstance(ins, IfFalse):
        nc = s(ins.cond)
        if nc is ins.cond: return ins
        return IfFalse(nc, ins.label)
    if isinstance(ins, Param):
        nv = s(ins.value)
        if nv is ins.value: return ins
        return Param(nv)
    if isinstance(ins, ArrLoad):
        ni = s(ins.idx)
        if ni is ins.idx: return ins
        return ArrLoad(ins.dest, ins.arr, ni)
    if isinstance(ins, ArrStore):
        ni = s(ins.idx); nv = s(ins.val)
        if ni is ins.idx and nv is ins.val: return ins
        return ArrStore(ins.arr, ni, nv)
    if isinstance(ins, PrintInt):
        nv = s(ins.value)
        if nv is ins.value: return ins
        return PrintInt(nv)
    if isinstance(ins, PrintReal):
        nv = s(ins.value)
        if nv is ins.value: return ins
        return PrintReal(nv)
    return ins


# ---- pass: dead temp elimination ----

def eliminate_dead_tmps(body):
    # compute set of temps that are ever read
    read = set()
    for ins in body:
        for op in _read_operands(ins):
            if isinstance(op, V) and _is_tmp(op.name):
                read.add(op.name)
    out = []
    changed = False
    for ins in body:
        defined = _defined_name(ins)
        if defined and _is_tmp(defined) and defined not in read:
            # side-effect-free defs of unread temps → drop
            if isinstance(ins, (Copy, BinOp, UnaryOp, ArrLoad)):
                changed = True
                continue
            # keep ReadInt / Call even if temp is unused — they have side effects
            # but we can still drop the destination (rewrite to no-dest form)
            if isinstance(ins, Call):
                ins = Call(None, ins.name, ins.nargs, ins.ref_vars, ins.ref_arrs)
                changed = True
        out.append(ins)
    return out, changed


def _read_operands(ins):
    if isinstance(ins, BinOp):   yield ins.a; yield ins.b
    elif isinstance(ins, UnaryOp): yield ins.a
    elif isinstance(ins, Copy):  yield ins.src
    elif isinstance(ins, IfFalse): yield ins.cond
    elif isinstance(ins, Param): yield ins.value
    elif isinstance(ins, ArrLoad): yield ins.idx
    elif isinstance(ins, ArrStore): yield ins.idx; yield ins.val
    elif isinstance(ins, PrintInt): yield ins.value
    elif isinstance(ins, PrintReal): yield ins.value


# ---- pass manager ----

def optimize_body(body, max_rounds=10):
    passes = [
        constant_fold,
        algebraic_simplify,
        remove_unreachable,
        copy_propagate,
        eliminate_dead_tmps,
    ]
    stats = {p.__name__: 0 for p in passes}
    for _ in range(max_rounds):
        changed_any = False
        for p in passes:
            body, changed = p(body)
            if changed:
                stats[p.__name__] += 1
                changed_any = True
        if not changed_any:
            break
    return body, stats


def optimize(prog: Program, max_rounds=10):
    """Returns the optimized Program plus aggregated change counts."""
    prog.main_body, main_stats = optimize_body(prog.main_body, max_rounds)
    all_stats = dict(main_stats)
    for fname, fn in prog.funcs.items():
        fn.body, fstats = optimize_body(fn.body, max_rounds)
        for k, v in fstats.items():
            all_stats[k] = all_stats.get(k, 0) + v
    return prog, all_stats
