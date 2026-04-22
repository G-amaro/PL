from dataclasses import dataclass, field
from typing import Optional

# ---- Ficheiro / unidades ----

@dataclass
class FileNode:
    units: list  # [Program | Function | Subroutine]

@dataclass
class Program:
    name: str
    body: list  # [stmt]

@dataclass
class Function:
    rtype: str           # 'INTEGER' | 'REAL' | 'LOGICAL'
    name: str
    params: list         # [str]
    body: list           # [stmt]

@dataclass
class Subroutine:
    name: str
    params: list
    body: list

# ---- Declarações ----

@dataclass
class Decl:
    vtype: str              # 'INTEGER' | 'REAL' | 'LOGICAL'
    items: list             # [(name, size_or_None)]

# ---- Statements ----

@dataclass
class Labeled:
    label: str
    stmt: object

@dataclass
class Assign:
    target: object          # LVar | LIndex
    expr: object

@dataclass
class Read:
    target: object

@dataclass
class Print:
    items: list             # [expr | StrLit]

@dataclass
class If:
    cond: object
    then_body: list
    else_body: list         # [] if no else

@dataclass
class Goto:
    label: str

@dataclass
class Do:
    label: str
    var: str
    start: object
    end: object
    step: Optional[object]  # None → step 1

@dataclass
class Continue:
    pass

@dataclass
class Return:
    pass

@dataclass
class CallStmt:
    name: str
    args: list

# ---- Expressões / lvalues ----

@dataclass
class LVar:
    name: str

@dataclass
class LIndex:
    name: str
    index: object

@dataclass
class Num:
    value: int

@dataclass
class RealLit:
    value: float

@dataclass
class StrLit:
    value: str

@dataclass
class BoolLit:
    value: bool

@dataclass
class Ident:
    name: str

# name(args) — pode ser chamada de função ou acesso a array.
# A fase semântica desambigua olhando à tabela de símbolos.
@dataclass
class FuncOrIndex:
    name: str
    args: list

@dataclass
class BinOp:
    op: str
    lhs: object
    rhs: object

@dataclass
class UnaryOp:
    op: str                 # '-' | 'NOT'
    expr: object
