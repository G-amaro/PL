# Interpretador mínimo da EWVM — serve para correr localmente o que
# o compilador gera e validar comportamento antes de submeter à web.
# Só implementa as instruções que o nosso codegen emite.

import sys
from dataclasses import dataclass


@dataclass
class Addr:
    """Tagged heap pointer."""
    block: int
    offset: int = 0


class VM:

    def __init__(self, source: str, stdin_lines=None):
        self.instrs = []
        self.labels = {}
        self._parse(source)
        self.stack = []
        self.fp = 0
        self.heap = {}
        self.heap_next = 1
        self.pc = 0
        self.output = []
        self.stdin_lines = list(stdin_lines) if stdin_lines else []

    def _parse(self, source):
        for lineno, raw in enumerate(source.splitlines(), start=1):
            line = raw.split('//')[0].strip()
            if not line:
                continue
            if line.endswith(':'):
                self.labels[line[:-1]] = len(self.instrs)
                continue
            parts = line.split(None, 1)
            op = parts[0].lower()
            arg = parts[1].strip() if len(parts) == 2 else None
            self.instrs.append((op, arg, lineno))

    # ---- stack helpers ----

    def push(self, v): self.stack.append(v)
    def pop(self):
        if not self.stack:
            raise RuntimeError(f"stack underflow at pc={self.pc}")
        return self.stack.pop()

    def read_input(self):
        if self.stdin_lines:
            return self.stdin_lines.pop(0)
        try:
            return input()
        except EOFError:
            return ''

    # ---- runner ----

    def run(self, max_steps=10_000_000):
        steps = 0
        while self.pc < len(self.instrs):
            if steps > max_steps:
                raise RuntimeError("Exceeded max steps — likely infinite loop.")
            steps += 1
            op, arg, ln = self.instrs[self.pc]
            self.pc += 1
            handler = getattr(self, f"op_{op}", None)
            if handler is None:
                raise RuntimeError(f"Unimplemented op '{op}' (line {ln}).")
            if handler(arg) == 'STOP':
                return ''.join(self.output)
        return ''.join(self.output)

    # ---- ops ----

    def op_pushn(self, arg):
        for _ in range(int(arg)):
            self.stack.append(0)

    def op_pushi(self, arg): self.push(int(arg))
    def op_pushg(self, arg): self.push(self.stack[int(arg)])
    def op_storeg(self, arg): self.stack[int(arg)] = self.pop()
    def op_pushl(self, arg): self.push(self.stack[self.fp + int(arg)])
    def op_storel(self, arg): self.stack[self.fp + int(arg)] = self.pop()
    def op_pushs(self, arg):
        s = self._parse_str(arg)
        block = self.heap_next; self.heap_next += 1
        self.heap[block] = list(s) + ['\0']
        self.push(Addr(block, 0))

    def op_pusha(self, arg): self.push(('label', arg))

    def op_start(self, arg): self.fp = len(self.stack)
    def op_stop(self, arg): return 'STOP'
    def op_nop(self, arg): pass

    def op_add(self, arg):
        n = self.pop(); m = self.pop()
        self.push(m + n)
    def op_sub(self, arg):
        n = self.pop(); m = self.pop(); self.push(m - n)
    def op_mul(self, arg):
        n = self.pop(); m = self.pop(); self.push(m * n)
    def op_div(self, arg):
        n = self.pop(); m = self.pop()
        # Fortran integer division truncates toward zero
        q = abs(m) // abs(n)
        if (m < 0) ^ (n < 0): q = -q
        self.push(q)
    def op_mod(self, arg):
        n = self.pop(); m = self.pop()
        # Fortran MOD: result has sign of m
        r = abs(m) % abs(n)
        if m < 0: r = -r
        self.push(r)

    def op_dup(self, arg):
        n = int(arg) if arg else 1
        if n == 1:
            self.push(self.stack[-1])
        else:
            top = self.stack[-n:]
            self.stack.extend(top)

    def op_not(self, arg):
        v = self.pop()
        self.push(1 if v == 0 else 0)
    def op_and(self, arg):
        n = self.pop(); m = self.pop()
        self.push(1 if (m and n) else 0)
    def op_or(self, arg):
        n = self.pop(); m = self.pop()
        self.push(1 if (m or n) else 0)

    def op_equal(self, arg):
        n = self.pop(); m = self.pop(); self.push(1 if m == n else 0)
    def op_inf(self, arg):
        n = self.pop(); m = self.pop(); self.push(1 if m < n else 0)
    def op_sup(self, arg):
        n = self.pop(); m = self.pop(); self.push(1 if m > n else 0)
    def op_infeq(self, arg):
        n = self.pop(); m = self.pop(); self.push(1 if m <= n else 0)
    def op_supeq(self, arg):
        n = self.pop(); m = self.pop(); self.push(1 if m >= n else 0)

    def op_alloc(self, arg):
        size = int(arg)
        block = self.heap_next; self.heap_next += 1
        self.heap[block] = [0] * size
        self.push(Addr(block, 0))

    def op_padd(self, arg):
        n = self.pop(); a = self.pop()
        if not isinstance(a, Addr):
            raise RuntimeError(f"padd: expected address, got {a!r}")
        self.push(Addr(a.block, a.offset + n))

    def op_load(self, arg):
        off = int(arg)
        a = self.pop()
        self.push(self.heap[a.block][a.offset + off])
    def op_store(self, arg):
        off = int(arg)
        v = self.pop()
        a = self.pop()
        self.heap[a.block][a.offset + off] = v

    def op_jump(self, arg): self.pc = self.labels[arg]
    def op_jz(self, arg):
        v = self.pop()
        if v == 0: self.pc = self.labels[arg]

    def op_call(self, arg):
        addr = self.pop()
        if not (isinstance(addr, tuple) and addr[0] == 'label'):
            raise RuntimeError(f"call: expected label address, got {addr!r}")
        self.push(('retfp', self.fp))
        self.push(('retpc', self.pc))
        self.fp = len(self.stack)
        self.pc = self.labels[addr[1]]

    def op_return(self, arg):
        # discard any locals above fp
        self.stack = self.stack[:self.fp]
        ret_pc = self.pop()
        ret_fp = self.pop()
        self.fp = ret_fp[1]
        self.pc = ret_pc[1]

    def op_read(self, arg):
        s = self.read_input()
        block = self.heap_next; self.heap_next += 1
        self.heap[block] = list(s) + ['\0']
        self.push(Addr(block, 0))

    def op_atoi(self, arg):
        a = self.pop()
        cells = self.heap[a.block][a.offset:]
        s = ''.join(c for c in cells if c != '\0')
        try:
            self.push(int(s.strip()))
        except ValueError:
            self.push(0)

    def op_writei(self, arg):
        v = self.pop()
        self.output.append(str(v))
    def op_writes(self, arg):
        a = self.pop()
        cells = self.heap[a.block][a.offset:]
        s = ''.join(c for c in cells if c != '\0')
        self.output.append(s)
    def op_writeln(self, arg):
        self.output.append('\n')

    # ---- utilities ----

    def _parse_str(self, raw):
        raw = raw.strip()
        if raw.startswith('"') and raw.endswith('"'):
            return raw[1:-1]
        if raw.startswith("'") and raw.endswith("'"):
            return raw[1:-1]
        return raw


def run(source, stdin=None):
    vm = VM(source, stdin_lines=stdin or [])
    return vm.run()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python vm.py <file.vm> [input-file]", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1]) as f:
        src = f.read()
    stdin = None
    if len(sys.argv) >= 3:
        with open(sys.argv[2]) as f:
            stdin = f.read().splitlines()
    out = run(src, stdin)
    sys.stdout.write(out)
