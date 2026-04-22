# Representação intermédia em código de 3 endereços (TAC), entre o
# AST e a EWVM. Operandos são V(nome) ou K(valor literal) — ter isto
# separado facilita o constant folding. Temporários começam por "__t"
# e vivem como globais; o optimizer apaga os que não são usados.

from dataclasses import dataclass, field
from typing import Optional, Union

from ast_nodes import (
    FileNode, Program as AProgram, Function as AFunction, Subroutine as ASubroutine,
    Decl, Labeled, Assign, Read as ARead, Print as APrint, If, Goto as AGoto,
    Do, Continue, Return as AReturn, CallStmt,
    LVar, LIndex, Num, RealLit, StrLit, BoolLit, Ident, FuncOrIndex,
    BinOp as ABinOp, UnaryOp as AUnaryOp,
)


# ---- Operands ----

@dataclass(frozen=True)
class V:
    """Variable or temporary operand, referenced by name."""
    name: str

@dataclass(frozen=True)
class K:
    """Compile-time constant — int, float, bool, or str."""
    value: object


Operand = Union[V, K]


def is_const(op) -> bool:
    return isinstance(op, K)


# ---- Instructions ----

@dataclass
class Const:       # dest = <literal>
    dest: V
    value: object

@dataclass
class Copy:        # dest = src
    dest: V
    src: Operand

@dataclass
class BinOp:       # dest = a <op> b
    dest: V
    op: str        # '+','-','*','/','LT','LE','GT','GE','EQ','NE','AND','OR'
    a: Operand
    b: Operand

@dataclass
class UnaryOp:     # dest = <op> a
    dest: V
    op: str        # 'NEG', 'NOT'
    a: Operand

@dataclass
class Label:
    name: str

@dataclass
class Goto:
    label: str

@dataclass
class IfFalse:     # if cond == 0, jump to label
    cond: Operand
    label: str

@dataclass
class Param:       # push an argument for the next Call
    value: Operand

@dataclass
class Call:        # optionally stores return value into dest
    dest: Optional[V]
    name: str
    nargs: int
    # caller-level scalar var names (for pass-by-ref copy-out); None means ignore.
    # One entry per positional arg, in order.
    ref_vars: list = field(default_factory=list)
    # and for array-element args: (arr_name, idx_operand) tuples or None
    ref_arrs: list = field(default_factory=list)

@dataclass
class Return:
    pass

@dataclass
class ArrLoad:     # dest = arr[idx - 1]
    dest: V
    arr: V
    idx: Operand

@dataclass
class ArrStore:    # arr[idx - 1] = val
    arr: V
    idx: Operand
    val: Operand

@dataclass
class AllocArr:    # allocate heap block for arr
    arr: V
    size: int

@dataclass
class ReadInt:
    dest: V

@dataclass
class PrintStr:
    value: str     # literal string (already the actual text, no quotes)

@dataclass
class PrintInt:
    value: Operand

@dataclass
class PrintReal:
    value: Operand

@dataclass
class PrintLn:
    pass

@dataclass
class Halt:
    pass


# ---- Units ----

@dataclass
class Function:
    name: str
    params: list        # [str] — param variable names (mangled)
    locals: list        # [str] — local variable names (mangled, includes return slot)
    body: list          # [Instr]
    return_var: Optional[str]
    is_subroutine: bool = False


@dataclass
class Program:
    globals: list       # [str]  — names of main-program scalars
    arrays: dict        # name -> size (across all units, keyed by mangled name)
    var_types: dict     # name -> 'INTEGER'/'REAL'/'LOGICAL' (across all units)
    main_body: list     # [Instr]
    funcs: dict         # name -> Function


# ---- Lowerer: AST → IR ----

class Lowerer:

    def __init__(self):
        self.tmp_counter = 0
        self.label_counter = 0
        self.globals = []
        self.arrays = {}
        self.var_types = {}
        self.current_unit = 'MAIN'   # name prefix for locals
        self.callables = {}          # name -> ('FUNCTION'|'SUBROUTINE', rtype_or_None, params)
        self.do_stack = []           # per-unit stack during lowering

    # -- name mangling mirrors codegen for consistency --
    def mangle(self, var_name):
        if self.current_unit == 'MAIN':
            return var_name.upper()
        return f"{self.current_unit.upper()}${var_name.upper()}"

    def fresh_tmp(self):
        self.tmp_counter += 1
        return V(f"__t{self.tmp_counter}")

    def fresh_label(self, tag):
        self.label_counter += 1
        if self.current_unit == 'MAIN':
            return f"{tag}{self.label_counter}"
        return f"{self.current_unit.upper()}_{tag}{self.label_counter}"

    def user_label(self, lbl):
        if self.current_unit == 'MAIN':
            return f"L{lbl}"
        return f"{self.current_unit.upper()}_L{lbl}"

    # -- entry --
    def lower(self, file_node: FileNode) -> Program:
        # first pass: record callable signatures
        for unit in file_node.units:
            if isinstance(unit, AFunction):
                self.callables[unit.name.upper()] = ('FUNCTION', unit.rtype, list(unit.params))
            elif isinstance(unit, ASubroutine):
                self.callables[unit.name.upper()] = ('SUBROUTINE', None, list(unit.params))

        # second pass: collect types and arrays
        for unit in file_node.units:
            self._collect_types(unit)

        # third pass: lower each unit
        main_body = []
        funcs = {}
        for unit in file_node.units:
            if isinstance(unit, AProgram):
                self.current_unit = 'MAIN'
                self.do_stack = []
                # allocate arrays up front
                for key, size in self.arrays.items():
                    if '$' not in key:  # main's arrays
                        main_body.append(AllocArr(V(key), size))
                self._lower_body(unit.body, main_body)
                main_body.append(Halt())
            elif isinstance(unit, (AFunction, ASubroutine)):
                self.current_unit = unit.name
                self.do_stack = []
                body = []
                prefix = f"{unit.name.upper()}$"
                for key, size in self.arrays.items():
                    if key.startswith(prefix):
                        body.append(AllocArr(V(key), size))
                self._lower_body(unit.body, body)
                body.append(Return())

                params_mangled = [self.mangle(p) for p in unit.params]
                # locals = every variable mangled with this unit's prefix,
                # minus params (ordered).
                locs = [k for k in self.var_types if k.startswith(prefix)]
                return_var = None
                if isinstance(unit, AFunction):
                    return_var = self.mangle(unit.name)
                funcs[unit.name.upper()] = Function(
                    name=unit.name.upper(),
                    params=params_mangled,
                    locals=locs,
                    body=body,
                    return_var=return_var,
                    is_subroutine=isinstance(unit, ASubroutine),
                )

        return Program(
            globals=list(self.globals),
            arrays=dict(self.arrays),
            var_types=dict(self.var_types),
            main_body=main_body,
            funcs=funcs,
        )

    # -- gather variable types & array sizes --
    def _collect_types(self, unit):
        if isinstance(unit, AProgram):
            self.current_unit = 'MAIN'
        elif isinstance(unit, AFunction):
            self.current_unit = unit.name
            # function's own name is its return variable
            key = self.mangle(unit.name)
            self.var_types[key] = unit.rtype
        elif isinstance(unit, ASubroutine):
            self.current_unit = unit.name
        # params default to INTEGER unless a later declaration overrides
        for p in getattr(unit, 'params', []):
            key = self.mangle(p)
            self.var_types.setdefault(key, 'INTEGER')
        self._walk_decls(unit.body)

        if isinstance(unit, AProgram):
            # exactly the main program's scalars (non-array)
            for k, t in self.var_types.items():
                if '$' not in k and k not in self.arrays and k not in self.globals:
                    self.globals.append(k)

    def _walk_decls(self, body):
        for stmt in body:
            if isinstance(stmt, Decl):
                for name, size in stmt.items:
                    key = self.mangle(name)
                    self.var_types[key] = stmt.vtype
                    if size is not None:
                        self.arrays[key] = size
            elif isinstance(stmt, If):
                self._walk_decls(stmt.then_body)
                self._walk_decls(stmt.else_body)
            elif isinstance(stmt, Labeled):
                self._walk_decls([stmt.stmt])

    # -- lower body of statements --
    def _lower_body(self, body, out):
        for stmt in body:
            self._lower_stmt(stmt, out)

    def _lower_stmt(self, stmt, out):
        if isinstance(stmt, Decl):
            return

        if isinstance(stmt, Labeled):
            out.append(Label(self.user_label(stmt.label)))
            if self.do_stack and self.do_stack[-1]['label'] == stmt.label:
                # inner statement of the DO terminator is typically CONTINUE;
                # lower it as a no-op then emit the loop footer
                self._lower_stmt(stmt.stmt, out)
                self._emit_do_footer(self.do_stack.pop(), out)
            else:
                self._lower_stmt(stmt.stmt, out)
            return

        if isinstance(stmt, Assign):
            self._lower_assign(stmt, out)
            return

        if isinstance(stmt, ARead):
            self._lower_read(stmt, out)
            return

        if isinstance(stmt, APrint):
            self._lower_print(stmt, out)
            return

        if isinstance(stmt, If):
            self._lower_if(stmt, out)
            return

        if isinstance(stmt, AGoto):
            out.append(Goto(self.user_label(stmt.label)))
            return

        if isinstance(stmt, Do):
            self._lower_do_header(stmt, out)
            return

        if isinstance(stmt, Continue):
            return  # no-op

        if isinstance(stmt, AReturn):
            out.append(Return())
            return

        if isinstance(stmt, CallStmt):
            self._lower_call(stmt.name, stmt.args, None, out)
            return

        raise RuntimeError(f"ir.lower: stmt {type(stmt).__name__} not implemented")

    # -- assignment --
    def _lower_assign(self, stmt, out):
        rhs = self._lower_expr(stmt.expr, out)
        t = stmt.target
        if isinstance(t, LVar):
            dest = V(self._resolve_name(t.name))
            out.append(Copy(dest, rhs))
        else:  # LIndex
            idx = self._lower_expr(t.index, out)
            out.append(ArrStore(V(self._resolve_name(t.name)), idx, rhs))

    def _lower_read(self, stmt, out):
        t = stmt.target
        if isinstance(t, LVar):
            out.append(ReadInt(V(self._resolve_name(t.name))))
        else:
            tmp = self.fresh_tmp()
            out.append(ReadInt(tmp))
            idx = self._lower_expr(t.index, out)
            out.append(ArrStore(V(self._resolve_name(t.name)), idx, tmp))

    def _lower_print(self, stmt, out):
        for item in stmt.items:
            if isinstance(item, StrLit):
                out.append(PrintStr(item.value))
            else:
                val = self._lower_expr(item, out)
                # best-effort type inference — defaulting to INT is fine for the
                # PDF's example programs which never print REALs.
                out.append(PrintInt(val))
        out.append(PrintLn())

    def _lower_if(self, stmt, out):
        if stmt.else_body:
            else_lbl = self.fresh_label("ELSE")
            end_lbl = self.fresh_label("ENDIF")
            cond = self._lower_expr(stmt.cond, out)
            out.append(IfFalse(cond, else_lbl))
            self._lower_body(stmt.then_body, out)
            out.append(Goto(end_lbl))
            out.append(Label(else_lbl))
            self._lower_body(stmt.else_body, out)
            out.append(Label(end_lbl))
        else:
            end_lbl = self.fresh_label("ENDIF")
            cond = self._lower_expr(stmt.cond, out)
            out.append(IfFalse(cond, end_lbl))
            self._lower_body(stmt.then_body, out)
            out.append(Label(end_lbl))

    # -- DO loop header / footer --
    def _lower_do_header(self, d, out):
        var_key = self._resolve_name(d.var)
        end_tmp = f"__DOEND_{self.label_counter}_{d.label}"
        step_tmp = f"__DOSTP_{self.label_counter}_{d.label}"
        # temporaries become new globals/locals via var_types to reserve slots
        self.var_types[end_tmp] = 'INTEGER'
        self.var_types[step_tmp] = 'INTEGER'
        if self.current_unit == 'MAIN':
            if end_tmp not in self.globals: self.globals.append(end_tmp)
            if step_tmp not in self.globals: self.globals.append(step_tmp)

        start = self._lower_expr(d.start, out)
        out.append(Copy(V(var_key), start))
        end = self._lower_expr(d.end, out)
        out.append(Copy(V(end_tmp), end))
        if d.step is None:
            out.append(Copy(V(step_tmp), K(1)))
        else:
            step = self._lower_expr(d.step, out)
            out.append(Copy(V(step_tmp), step))

        test_lbl = self.fresh_label("DOTEST")
        exit_lbl = self.fresh_label("DOEXIT")
        out.append(Label(test_lbl))

        tcond = self.fresh_tmp()
        out.append(BinOp(tcond, 'LE', V(var_key), V(end_tmp)))
        out.append(IfFalse(tcond, exit_lbl))

        self.do_stack.append({
            'label': d.label,
            'var': var_key,
            'step': step_tmp,
            'test': test_lbl,
            'exit': exit_lbl,
        })

    def _emit_do_footer(self, ctx, out):
        step = V(ctx['step'])
        var = V(ctx['var'])
        tsum = self.fresh_tmp()
        out.append(BinOp(tsum, '+', var, step))
        out.append(Copy(var, tsum))
        out.append(Goto(ctx['test']))
        out.append(Label(ctx['exit']))

    # -- function / subroutine calls --
    def _lower_call(self, name, args, dest_var: Optional[V], out):
        nu = name.upper()
        # built-ins: MOD, ABS, MIN, MAX → inline via BinOp/UnaryOp
        if nu == 'MOD':
            a = self._lower_expr(args[0], out)
            b = self._lower_expr(args[1], out)
            t = dest_var or self.fresh_tmp()
            out.append(BinOp(t, 'MOD', a, b))
            return t
        if nu == 'ABS':
            a = self._lower_expr(args[0], out)
            t = dest_var or self.fresh_tmp()
            out.append(UnaryOp(t, 'ABS', a))
            return t

        ref_vars = []
        ref_arrs = []
        for arg in args:
            val = self._lower_expr(arg, out)
            out.append(Param(val))
            if isinstance(arg, Ident):
                key = self._resolve_name(arg.name)
                if key not in self.arrays:
                    ref_vars.append(key)
                    ref_arrs.append(None)
                else:
                    ref_vars.append(None)
                    ref_arrs.append(None)
            elif isinstance(arg, FuncOrIndex):
                key = self._resolve_name(arg.name)
                if key in self.arrays:
                    idx = self._lower_expr(arg.args[0], out)
                    ref_vars.append(None)
                    ref_arrs.append((key, idx))
                else:
                    ref_vars.append(None)
                    ref_arrs.append(None)
            else:
                ref_vars.append(None)
                ref_arrs.append(None)

        t = dest_var or (self.fresh_tmp() if dest_var is None and nu in self.callables
                         and self.callables[nu][0] == 'FUNCTION' else None)
        out.append(Call(t, nu, len(args), ref_vars=ref_vars, ref_arrs=ref_arrs))
        return t

    # -- expressions --
    def _lower_expr(self, e, out) -> Operand:
        if isinstance(e, Num):     return K(e.value)
        if isinstance(e, RealLit): return K(e.value)
        if isinstance(e, StrLit):  return K(e.value)
        if isinstance(e, BoolLit): return K(1 if e.value else 0)

        if isinstance(e, Ident):
            return V(self._resolve_name(e.name))

        if isinstance(e, FuncOrIndex):
            key = self._resolve_name(e.name)
            if key in self.arrays:
                idx = self._lower_expr(e.args[0], out)
                t = self.fresh_tmp()
                out.append(ArrLoad(t, V(key), idx))
                return t
            # function call returning a value
            return self._lower_call(e.name, e.args, None, out)

        if isinstance(e, AUnaryOp):
            a = self._lower_expr(e.expr, out)
            t = self.fresh_tmp()
            op = 'NEG' if e.op == '-' else 'NOT'
            out.append(UnaryOp(t, op, a))
            return t

        if isinstance(e, ABinOp):
            a = self._lower_expr(e.lhs, out)
            b = self._lower_expr(e.rhs, out)
            t = self.fresh_tmp()
            out.append(BinOp(t, e.op, a, b))
            return t

        raise RuntimeError(f"ir.lower: expr {type(e).__name__} not implemented")

    def _resolve_name(self, name):
        mangled = self.mangle(name)
        if mangled in self.var_types:
            return mangled
        # fall back to main-scope name (e.g., function name from caller site)
        up = name.upper()
        if up in self.var_types:
            return up
        # could be a function name being used as a callable; return mangled
        return mangled


def lower(file_node: FileNode) -> Program:
    return Lowerer().lower(file_node)


# ---- Pretty printer (for debug / report) ----

def pretty(prog: Program) -> str:
    lines = []
    lines.append("# globals: " + ", ".join(prog.globals))
    if prog.arrays:
        lines.append("# arrays:  " + ", ".join(f"{k}[{v}]" for k, v in prog.arrays.items()))
    lines.append("")
    lines.append("MAIN:")
    for ins in prog.main_body:
        lines.append("  " + _fmt_instr(ins))
    for fname, fn in prog.funcs.items():
        lines.append("")
        kind = "SUB" if fn.is_subroutine else "FUN"
        lines.append(f"{kind} {fname}({', '.join(fn.params)}) -> {fn.return_var}:")
        for ins in fn.body:
            lines.append("  " + _fmt_instr(ins))
    return "\n".join(lines)


def _fmt_op(op):
    if isinstance(op, V): return op.name
    if isinstance(op, K):
        v = op.value
        if isinstance(v, str): return repr(v)
        return str(v)
    return str(op)


def _fmt_instr(ins):
    if isinstance(ins, Const):    return f"{ins.dest.name} = {ins.value!r}"
    if isinstance(ins, Copy):     return f"{ins.dest.name} = {_fmt_op(ins.src)}"
    if isinstance(ins, BinOp):    return f"{ins.dest.name} = {_fmt_op(ins.a)} {ins.op} {_fmt_op(ins.b)}"
    if isinstance(ins, UnaryOp):  return f"{ins.dest.name} = {ins.op} {_fmt_op(ins.a)}"
    if isinstance(ins, Label):    return f"{ins.name}:"
    if isinstance(ins, Goto):     return f"goto {ins.label}"
    if isinstance(ins, IfFalse):  return f"ifnot {_fmt_op(ins.cond)} goto {ins.label}"
    if isinstance(ins, Param):    return f"param {_fmt_op(ins.value)}"
    if isinstance(ins, Call):
        dst = f"{ins.dest.name} = " if ins.dest else ""
        return f"{dst}call {ins.name}/{ins.nargs}"
    if isinstance(ins, Return):   return "return"
    if isinstance(ins, ArrLoad):  return f"{ins.dest.name} = {ins.arr.name}[{_fmt_op(ins.idx)}]"
    if isinstance(ins, ArrStore): return f"{ins.arr.name}[{_fmt_op(ins.idx)}] = {_fmt_op(ins.val)}"
    if isinstance(ins, AllocArr): return f"alloc {ins.arr.name}[{ins.size}]"
    if isinstance(ins, ReadInt):  return f"read {ins.dest.name}"
    if isinstance(ins, PrintStr): return f"prints {ins.value!r}"
    if isinstance(ins, PrintInt): return f"printi {_fmt_op(ins.value)}"
    if isinstance(ins, PrintReal): return f"printr {_fmt_op(ins.value)}"
    if isinstance(ins, PrintLn):  return "println"
    if isinstance(ins, Halt):     return "halt"
    return f"<{type(ins).__name__}>"
