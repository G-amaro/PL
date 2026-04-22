# Driver do compilador.
# Uso:
#     python main.py ficheiro.f               -> escreve VM no stdout
#     python main.py ficheiro.f -o saida.vm   -> escreve VM em saida.vm
#     python main.py ficheiro.f --no-opt      -> sem otimizações
#     python main.py ficheiro.f --show-ir     -> mostra a IR (debug)
# Pipeline: lex -> parse -> semântica -> IR -> otimizações -> codegen.

import argparse
import sys

from parser import parse
from semantic import analyze
from ir import lower, pretty as ir_pretty
from optimizer import optimize
from codegen import generate


def compile_source(source: str, do_optimize: bool = True):
    tree = parse(source)
    if tree is None:
        return None, ["Erro de sintaxe."], None

    errors = analyze(tree)
    if errors:
        return None, errors, None

    prog = lower(tree)
    stats = {}
    if do_optimize:
        prog, stats = optimize(prog)

    code = generate(prog)
    return code, [], {'ir': prog, 'opt_stats': stats}


def main():
    ap = argparse.ArgumentParser(description="Compilador Fortran 77 -> EWVM")
    ap.add_argument("source", help="ficheiro Fortran (.f)")
    ap.add_argument("-o", "--output", help="escreve assembly para este ficheiro")
    ap.add_argument("--no-opt", action="store_true", help="desliga as otimizações")
    ap.add_argument("--show-ir", action="store_true", help="mostra a IR no stderr")
    ap.add_argument("--stats", action="store_true", help="mostra contagem de otimizações")
    args = ap.parse_args()

    with open(args.source, encoding="utf-8") as f:
        src = f.read()

    result, errors, meta = compile_source(src, do_optimize=not args.no_opt)
    for e in errors:
        print(e, file=sys.stderr)
    if errors:
        sys.exit(1)

    if args.show_ir and meta is not None:
        print(ir_pretty(meta['ir']), file=sys.stderr)
    if args.stats and meta is not None:
        print("opt:", meta['opt_stats'], file=sys.stderr)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"-> escrito em {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
