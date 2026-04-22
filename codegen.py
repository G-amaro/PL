# Backend EWVM — consome IR (ir.Program) e gera assembly da máquina
# virtual (https://ewvm.epl.di.uminho.pt/). Convenções:
#   - Tudo é global. Cada V(nome) recebe um slot único.
#   - Arrays: o slot guarda o endereço devolvido pelo ALLOC; acesso
#     via PADD + LOAD/STORE (índice 1-based convertido em runtime).
#   - Chamadas: os args são escritos nos slots dos params da callee
#     antes do CALL, e há copy-out dos que são variáveis escalares ou
#     elementos de array (emula pass-by-reference do Fortran 77).
#   - O valor de retorno da FUNCTION vive no slot com o nome da função.

from ir import (
    Program, Function, V, K,
    Copy, BinOp, UnaryOp, Label, Goto, IfFalse, Param, Call, Return,
    ArrLoad, ArrStore, AllocArr, ReadInt,
    PrintStr, PrintInt, PrintReal, PrintLn, Halt, Const,
)


BINOP = {
    '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', 'MOD': 'mod',
    'LT': 'inf', 'GT': 'sup', 'LE': 'infeq', 'GE': 'supeq',
    'EQ': 'equal',
    'AND': 'and', 'OR': 'or',
}


class Backend:

    def __init__(self, prog: Program):
        self.prog = prog
        self.slots = {}        # nome -> índice do slot global
        self.n_slots = 0
        self.lines = []
        self.pending_params = []   # buffer entre Param e Call

    # ---- alocação de slots ----

    def _slot(self, name):
        if name not in self.slots:
            self.slots[name] = self.n_slots
            self.n_slots += 1
        return self.slots[name]

    def _alloc_all_slots(self):
        # começa pelos nomes declarados (var_types mantém a ordem de inserção),
        # depois qualquer temporário ou tmp de DO usado nas bodies
        for name in self.prog.var_types:
            self._slot(name)
        self._scan_body(self.prog.main_body)
        for fn in self.prog.funcs.values():
            self._scan_body(fn.body)

    def _scan_body(self, body):
        def visit(op):
            if isinstance(op, V):
                self._slot(op.name)
        for ins in body:
            for attr in ('dest', 'src', 'a', 'b', 'cond', 'value', 'arr', 'idx', 'val'):
                if hasattr(ins, attr):
                    visit(getattr(ins, attr))

    # ---- emissão ----

    def emit(self, s):
        self.lines.append(s)

    def _push(self, op):
        if isinstance(op, K):
            v = op.value
            if isinstance(v, bool):
                self.emit(f"pushi {1 if v else 0}")
            elif isinstance(v, int):
                self.emit(f"pushi {v}")
            elif isinstance(v, float):
                self.emit(f"pushf {v}")
            elif isinstance(v, str):
                self.emit(f'pushs "{v}"')
            else:
                raise RuntimeError(f"constante não suportada: {v!r}")
        elif isinstance(op, V):
            self.emit(f"pushg {self._slot(op.name)}")
        else:
            raise RuntimeError(f"operando não reconhecido: {op!r}")

    def compile(self):
        self._alloc_all_slots()

        # corpo do programa principal
        body_lines_marker = len(self.lines)  # apenas para clareza
        for ins in self.prog.main_body:
            self._emit(ins)

        # bodies das funções/subrotinas
        for name, fn in self.prog.funcs.items():
            self.emit(f"FN_{name}:")
            for ins in fn.body:
                self._emit(ins)

        # prologue — só agora sabemos n_slots final
        prologue = []
        if self.n_slots:
            prologue.append(f"pushn {self.n_slots}")
        prologue.append("start")
        return "\n".join(prologue + self.lines) + "\n"

    def _emit(self, ins):
        if isinstance(ins, Copy):
            self._push(ins.src)
            self.emit(f"storeg {self._slot(ins.dest.name)}")
            return

        if isinstance(ins, BinOp):
            self._push(ins.a)
            self._push(ins.b)
            if ins.op == 'NE':
                self.emit("equal")
                self.emit("not")
            else:
                mnem = BINOP.get(ins.op)
                if mnem is None:
                    raise RuntimeError(f"operador não suportado: {ins.op}")
                self.emit(mnem)
            self.emit(f"storeg {self._slot(ins.dest.name)}")
            return

        if isinstance(ins, UnaryOp):
            self._push(ins.a)
            if ins.op == 'NEG':
                self.emit("pushi -1"); self.emit("mul")
            elif ins.op == 'NOT':
                self.emit("not")
            elif ins.op == 'ABS':
                # dup, pushi 0, inf -> se negativo, multiplica por -1
                self.emit("dup 1")
                self.emit("pushi 0")
                self.emit("inf")
                done = f"ABSDONE_{id(ins)}"
                self.emit(f"jz {done}")
                self.emit("pushi -1")
                self.emit("mul")
                self.emit(f"{done}:")
            else:
                raise RuntimeError(f"unário não suportado: {ins.op}")
            self.emit(f"storeg {self._slot(ins.dest.name)}")
            return

        if isinstance(ins, Label):
            self.emit(f"{ins.name}:")
            return

        if isinstance(ins, Goto):
            self.emit(f"jump {ins.label}")
            return

        if isinstance(ins, IfFalse):
            self._push(ins.cond)
            self.emit(f"jz {ins.label}")
            return

        if isinstance(ins, Param):
            self.pending_params.append(ins.value)
            return

        if isinstance(ins, Call):
            self._emit_call(ins)
            return

        if isinstance(ins, Return):
            self.emit("return")
            return

        if isinstance(ins, ArrLoad):
            self.emit(f"pushg {self._slot(ins.arr.name)}")
            self._push(ins.idx)
            self.emit("pushi 1"); self.emit("sub")
            self.emit("padd")
            self.emit("load 0")
            self.emit(f"storeg {self._slot(ins.dest.name)}")
            return

        if isinstance(ins, ArrStore):
            self.emit(f"pushg {self._slot(ins.arr.name)}")
            self._push(ins.idx)
            self.emit("pushi 1"); self.emit("sub")
            self.emit("padd")
            self._push(ins.val)
            self.emit("store 0")
            return

        if isinstance(ins, AllocArr):
            self.emit(f"alloc {ins.size}")
            self.emit(f"storeg {self._slot(ins.arr.name)}")
            return

        if isinstance(ins, ReadInt):
            self.emit("read")
            self.emit("atoi")
            self.emit(f"storeg {self._slot(ins.dest.name)}")
            return

        if isinstance(ins, PrintStr):
            self.emit(f'pushs "{ins.value}"')
            self.emit("writes")
            return

        if isinstance(ins, PrintInt):
            self._push(ins.value)
            self.emit("writei")
            return

        if isinstance(ins, PrintReal):
            self._push(ins.value)
            self.emit("writef")
            return

        if isinstance(ins, PrintLn):
            self.emit("writeln")
            return

        if isinstance(ins, Halt):
            self.emit("stop")
            return

        if isinstance(ins, Const):
            self.emit(f"pushi {ins.value}")
            self.emit(f"storeg {self._slot(ins.dest.name)}")
            return

        raise RuntimeError(f"codegen: instrução IR não tratada: {type(ins).__name__}")

    def _emit_call(self, ins: Call):
        # ao passar pela fase Param, os valores ficam em pending_params
        params = self.pending_params[:ins.nargs]
        self.pending_params = self.pending_params[ins.nargs:]

        fn = self.prog.funcs.get(ins.name)
        if fn is None:
            raise RuntimeError(f"codegen: função/subrotina desconhecida '{ins.name}'")

        # coloca cada arg no slot do param respetivo
        for val, pname in zip(params, fn.params):
            self._push(val)
            self.emit(f"storeg {self._slot(pname)}")

        self.emit(f"pusha FN_{ins.name}")
        self.emit("call")

        # copy-out (pass-by-reference): se o arg era uma variável ou
        # elemento de array do chamador, escreve de volta o valor
        # que o param ficou a ter
        for pname, refvar, refarr in zip(fn.params, ins.ref_vars, ins.ref_arrs):
            if refvar is not None:
                self.emit(f"pushg {self._slot(pname)}")
                self.emit(f"storeg {self._slot(refvar)}")
            elif refarr is not None:
                arr_name, idx = refarr
                self.emit(f"pushg {self._slot(arr_name)}")
                self._push(idx)
                self.emit("pushi 1"); self.emit("sub")
                self.emit("padd")
                self.emit(f"pushg {self._slot(pname)}")
                self.emit("store 0")

        # valor de retorno, se houver dest
        if ins.dest is not None and fn.return_var is not None:
            self.emit(f"pushg {self._slot(fn.return_var)}")
            self.emit(f"storeg {self._slot(ins.dest.name)}")


def generate(prog: Program) -> str:
    return Backend(prog).compile()
