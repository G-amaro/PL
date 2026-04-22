# Testes end-to-end: compila cada programa de tests/ e corre no vm.py
# com um stdin fixo, comparando com o output esperado.

import os
import sys

from main import compile_source
from vm import VM


CASES = [
    {
        "file": "tests/01_hello.f",
        "stdin": [],
        "expect": "Ola, Mundo!\n",
    },
    {
        "file": "tests/02_fatorial.f",
        "stdin": ["5"],
        "expect": "Introduza um numero inteiro positivo:\nFatorial de 5: 120\n",
    },
    {
        "file": "tests/03_primo.f",
        "stdin": ["7"],
        "expect": "Introduza um numero inteiro positivo:\n7 e um numero primo\n",
    },
    {
        "file": "tests/03_primo.f",
        "stdin": ["9"],
        "expect": "Introduza um numero inteiro positivo:\n9 nao e um numero primo\n",
    },
    {
        "file": "tests/04_somaarr.f",
        "stdin": ["1", "2", "3", "4", "5"],
        "expect": "Introduza 5 numeros inteiros:\nA soma dos numeros e: 15\n",
    },
    {
        "file": "tests/05_conversor.f",
        "stdin": ["10"],
        "expect": (
            "INTRODUZA UM NUMERO DECIMAL INTEIRO:\n"
            "BASE 2: 1010\nBASE 3: 101\nBASE 4: 22\nBASE 5: 20\n"
            "BASE 6: 14\nBASE 7: 13\nBASE 8: 12\nBASE 9: 11\n"
        ),
    },
    {
        "file": "tests/06_subrotina.f",
        "stdin": [],
        "expect": "Dobro guardado em X: 14\n",
    },
    {
        "file": "tests/07_otimiza.f",
        "stdin": [],
        "expect": "A=14 B=14 C=14 D=0 E=14\n",
    },
]


def run_case(case, do_optimize=True):
    with open(case["file"], encoding="utf-8") as f:
        src = f.read()
    code, errors, _ = compile_source(src, do_optimize=do_optimize)
    if errors:
        return False, f"compilation errors: {errors}"
    out_path = case["file"].replace(".f", ".vm")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)

    vm = VM(code, stdin_lines=case["stdin"])
    try:
        out = vm.run()
    except Exception as e:
        return False, f"VM crash: {e}"
    if out != case["expect"]:
        return False, f"output mismatch:\n--- expected ---\n{case['expect']!r}\n--- got ---\n{out!r}"
    return True, "ok"


def main():
    # corre cada caso duas vezes: sem e com otimizações. O output
    # tem de ser exatamente o mesmo — é a nossa garantia de que o
    # optimizer não mexe na semântica.
    passed = failed = 0
    for case in CASES:
        for label_suffix, opt in (("", False), (" [opt]", True)):
            ok, msg = run_case(case, do_optimize=opt)
            name = case["file"].split("/")[-1] + label_suffix
            stdin_tag = f" stdin={case['stdin']}" if case["stdin"] else ""
            if ok:
                print(f"PASS  {name}{stdin_tag}")
                passed += 1
            else:
                print(f"FAIL  {name}{stdin_tag} — {msg}")
                failed += 1
    total = passed + failed
    print(f"\n{passed}/{total} testes passaram.")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
