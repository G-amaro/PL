# Compilador Fortran 77 -> EWVM

Projeto de PL 2026. Compilador para um subconjunto de Fortran 77 (standard ANSI X3.9-1978) escrito em Python com `ply`, a gerar código para a EWVM (https://ewvm.epl.di.uminho.pt/).

## Correr

Requisitos: Python 3 e o pacote `ply`. No macOS/PEP 668 é preciso criar um venv:

```
python3 -m venv .venv
source .venv/bin/activate
pip install ply
```

Compilar um programa:

```
python main.py tests/02_fatorial.f -o tests/02_fatorial.vm
```

Correr o `.vm` gerado no interpretador que vai junto (útil para testes locais antes de submeter à EWVM web):

```
echo 5 | python vm.py tests/02_fatorial.vm
```

Flags úteis:

- `--no-opt` desliga as otimizações (emite código "cru")
- `--show-ir` imprime a IR no stderr
- `--stats` mostra quantas vezes cada passagem do optimizer mexeu

Bateria de testes end-to-end:

```
python run_tests.py
```

Corre cada programa de `tests/` duas vezes (com e sem optimizer) e confirma que o output é o mesmo.

## Organização do código

```
lexer.py        analisador léxico (ply.lex)
parser.py       analisador sintático (ply.yacc), devolve AST
ast_nodes.py    dataclasses da AST
semantic.py     verificações de tipos, declarações, labels, DO/CONTINUE
ir.py           IR em TAC (três endereços) + lowering AST -> IR
optimizer.py    5 passagens sobre a IR
codegen.py      emissão de assembly EWVM a partir da IR
vm.py           mini-interpretador EWVM para correr os testes localmente
main.py         driver CLI
run_tests.py    bateria de testes end-to-end
tests/          programas exemplo (.f) e o respetivo assembly gerado (.vm)
```

O pipeline é:

```
ficheiro.f
   -> lexer (tokens)
   -> parser (AST)
   -> semantic (erros acumulados)
   -> ir.lower (IR em TAC)
   -> optimizer.optimize (código mais curto)
   -> codegen.generate (assembly EWVM)
   -> ficheiro.vm
```

## O que está suportado

Do que o enunciado pede (aprovação mínima):

- declarações `INTEGER`, `REAL`, `LOGICAL`, com arrays de 1 dimensão (`INTEGER NUMS(5)`)
- expressões aritméticas, relacionais (`.LE.`, `.LT.`, `.GT.`, `.GE.`, `.EQ.`, `.NE.`) e lógicas (`.AND.`, `.OR.`, `.NOT.`, `.TRUE.`, `.FALSE.`)
- atribuição (escalares e elementos de array)
- `IF-THEN`, `IF-THEN-ELSE`, `GOTO`, `DO` com label (com passo opcional), `CONTINUE`
- I/O: `READ *, var` e `PRINT *, ...` com mistura de strings e expressões
- comentários inline `!`

Valorização:

- `FUNCTION` (com tipo de retorno declarado) e `SUBROUTINE` com `CALL`
- passagem de args por referência emulada (copy-in/copy-out) para variáveis escalares e elementos de array
- intrínsecas `MOD`, `ABS`, `MIN`, `MAX`
- representação intermédia (TAC) com operandos `V(nome)` / `K(valor)`
- 5 passagens de otimização sobre a IR (constant folding, simplificação algébrica, eliminação de código inalcançável, copy propagation e eliminação de temporários mortos), corridas até atingir fixpoint

## Checks semânticos

A fase `semantic.py` corre por cada unidade (PROGRAM, FUNCTION, SUBROUTINE) e acumula erros em vez de abortar. Verifica:

- variáveis declaradas antes de serem usadas, sem duplicados
- coerência de tipos em atribuições e expressões aritméticas
- condição de IF tem de ser LOGICAL
- variável do ciclo DO declarada
- labels referenciados por GOTO/DO estão definidos
- o label de cada DO termina mesmo num CONTINUE (requisito explícito do enunciado)
- paragem da contagem de args em funções pré-definidas (`MOD`/2, `ABS`/1, etc.)

## EWVM — convenções do backend

A EWVM é uma máquina de stack (spec em https://ewvm.epl.di.uminho.pt/manual). Escolhas que fiz no `codegen.py`:

- **Região de globais única.** Todas as variáveis, locais de função incluídas, ocupam slots globais. Os locais de uma função `CONVRT` são nomeados `CONVRT$VAL`, `CONVRT$QUOT`, etc, para evitar colisão. Isto simplifica bastante o backend mas não suporta recursão — o enunciado não pede.
- **Arrays** usam `alloc` para pedir memória no heap à entrada da unidade; o slot global guarda o endereço. Acessos fazem `pushg base; push idx; pushi 1; sub; padd; load 0` (ou `store 0` no caso de escrita). O `pushi 1; sub` converte o índice de 1-based para 0-based.
- **Valor de retorno das FUNCTION** vive no slot com o mesmo nome da função (a convenção Fortran é exatamente essa: dentro do corpo escreve-se `CONVRT = VAL`). O chamador faz `pushg` desse slot depois do `call`.
- **Passagem de args**: antes do `call`, cada arg é avaliado e armazenado no slot do parâmetro respetivo. Depois do `call`, há um passo de copy-out que, para cada arg que era uma variável escalar ou um elemento de array no chamador, escreve de volta o valor final do parâmetro. Assim emulamos o call-by-reference do Fortran 77 sem mexer na stack.
- **DO loops** são traduzidos com 3 labels internos (teste, corpo, saída) e dois temporários globais para guardar o fim e o passo (avaliados uma vez à entrada). O iterador vai sendo incrementado com o passo. O CONTINUE do utilizador dá o endereço do "fim" da iteração.

## Otimizações

Cada passagem devolve `(novo_corpo, mudou)` para o loop de fixpoint. Todas são neutras em semântica (garantido pelos testes). As passagens:

1. **Constant folding** — `BinOp(K, K)` e `UnaryOp(K)` são computados em tempo de compilação e substituídos por `Copy(dest, K(resultado))`. Cobre `+ - * / MOD`, comparações e AND/OR.
2. **Simplificação algébrica** — `x + 0`, `0 + x`, `x - 0`, `x * 1`, `1 * x`, `x / 1`, `x - x`, `x * 0`, e análogos para AND/OR.
3. **Eliminação de código inalcançável** — depois de um `Goto`, `Return` ou `Halt`, tudo até ao próximo `Label` é descartado.
4. **Copy propagation** — dentro de um bloco básico (entre labels/branches), se houve `Copy(__t, x)`, substitui usos subsequentes de `__t` por `x`. Invalida o mapping quando o alvo é redefinido. Limpa o estado ao cruzar fronteiras de bloco.
5. **Eliminação de temporários mortos** — remove atribuições a `__t*` que não são lidas depois. Conservadora: só mexe em temporários, nunca em variáveis do utilizador.

Exemplo de impacto (`tests/07_otimiza.f`, stress-test do optimizer): 62 linhas sem opt → 34 linhas com opt (45% de redução).

## Testes

`tests/` tem os 5 exemplos do enunciado (HELLO, FATORIAL, PRIMO, SOMAARR, CONVERSOR) mais dois meus: `06_subrotina.f` (SUBROUTINE com passagem por referência) e `07_otimiza.f` (stress-test do optimizer).

O `run_tests.py` corre cada programa com um stdin scriptado, compara o stdout com a saída esperada, e fá-lo duas vezes (com e sem opt). Se o optimizer alguma vez mudar o comportamento, este teste falha.

```
$ python run_tests.py
PASS  01_hello.f
PASS  01_hello.f [opt]
PASS  02_fatorial.f stdin=['5']
PASS  02_fatorial.f [opt] stdin=['5']
...
16/16 testes passaram.
```

Validei também:
- FATORIAL para 0, 1, 5, 10, 12
- PRIMO para {2, 3, 4, 5, 7, 9, 11, 15, 17, 25, 49, 97, 100} (o PRIMO(1) do enunciado dá "é primo" por o algoritmo do PDF não tratar N<2 — não é falha do compilador)
- SOMAARR com positivos, mistos, zeros e magnitudes grandes
- CONVERSOR para 0, 1, 7, 10, 100, 255, 1000 (todas as bases conferidas)

## Limitações conhecidas

- Não há recursão (o modelo de alocação global trampoliria os slots).
- I/O de REAL existe na parser+semantic mas o codegen emite `writei`/`atoi` por omissão — ficheiros com REAL compilam mas o output não está afinado para float.
- `READ *, A, B` (múltiplos alvos num único READ) não está suportado; o parser só aceita um alvo.
- Strings com aspa duplicada (o escape `''` do Fortran) não são tratadas no lexer.
