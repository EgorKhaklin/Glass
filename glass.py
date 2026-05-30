"""
Glass v5.33 — reference implementation.

A pure functional language designed for transparent local reasoning.
Single-file tree-walking interpreter: lexer → parser → type checker → evaluator.

v0.8 adds records with named fields. Record literals `User { id: 1, name: "x" }`,
field access `user.name`, and record patterns `match u { User { id, name } => ... }`
in match arms. Polymorphic records (`Container<T>`) work too. Records are
nominal — two records with identical field shapes but different names are
distinct types. Combined with v0.7's effect polymorphism and v0.4's
refinements, a single fn signature now carries the full trust model:
data shape, side-effects, and value constraints, all visible at the call
site without reading the body.

Installable: `pip install -e . --break-system-packages` from the repo
root provides a `glass` console script.

Usage:
    glass path/to/file.glass    # run a file
    glass                        # start the REPL
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
import sys
import os
import re
import subprocess

sys.setrecursionlimit(20000)

# Perf: dataclass(slots=True) speeds the hot runtime value classes — attribute
# reads (tens of millions of `.v`) and allocation (millions of IntV) — on Python
# 3.10+. On 3.9 it degrades to a plain dataclass: still correct, just no slots.
_SLOTS = {"slots": True} if sys.version_info >= (3, 10) else {}


# =============================================================================
# Tokens
# =============================================================================

@dataclass
class Token:
    kind: str
    value: Any
    line: int
    col: int

    def __repr__(self) -> str:
        return f"Tok({self.kind}, {self.value!r})"


KEYWORDS = {
    "let", "fn", "in", "if", "then", "else", "match", "true", "false",
    "type", "where", "import",
}

# Order matters: longest match first.
TOKEN_SPEC = [
    ("COMMENT",  r"#[^\n]*"),
    ("NEWLINE",  r"\n"),
    ("WS",       r"[ \t\r]+"),
    ("STRING",   r'"(?:[^"\\]|\\.)*"'),
    ("INT",      r"-?\d+"),
    ("ARROW",    r"->"),
    ("FATARROW", r"=>"),
    ("PIPE",     r"\|>"),
    ("OROR",     r"\|\|"),
    ("BAR",      r"\|"),
    ("CONCAT",   r"\+\+"),
    ("ELLIPSIS", r"\.\.\."),
    ("DOT",      r"\."),
    ("LE",       r"<="),
    ("GE",       r">="),
    ("EQ",       r"=="),
    ("NEQ",      r"!="),
    ("ANDAND",   r"&&"),
    ("BANG",     r"!"),
    ("QMARK",    r"\?"),
    ("LT",       r"<"),
    ("GT",       r">"),
    ("ASSIGN",   r"="),
    ("PLUS",     r"\+"),
    ("MINUS",    r"-"),
    ("STAR",     r"\*"),
    ("SLASH",    r"/"),
    ("PERCENT",  r"%"),
    ("LPAREN",   r"\("),
    ("RPAREN",   r"\)"),
    ("LBRACK",   r"\["),
    ("RBRACK",   r"\]"),
    ("LBRACE",   r"\{"),
    ("RBRACE",   r"\}"),
    ("COMMA",    r","),
    ("COLON",    r":"),
    ("SEMI",     r";"),
    ("IDENT",    r"[A-Za-z_][A-Za-z0-9_]*"),
]

TOKEN_REGEX = re.compile(
    "|".join(f"(?P<{name}>{pat})" for name, pat in TOKEN_SPEC)
)


def tokenize(src: str) -> list[Token]:
    tokens: list[Token] = []
    line, line_start = 1, 0
    pos = 0
    while pos < len(src):
        m = TOKEN_REGEX.match(src, pos)
        if not m:
            raise SyntaxError(f"unexpected char {src[pos]!r} at line {line}")
        kind = m.lastgroup
        text = m.group()
        col = pos - line_start + 1
        if kind == "NEWLINE":
            line += 1
            line_start = pos + 1
        elif kind in ("WS", "COMMENT"):
            pass
        elif kind == "IDENT" and text in KEYWORDS:
            tokens.append(Token(text, text, line, col))
        elif kind == "INT":
            tokens.append(Token("INT", int(text), line, col))
        elif kind == "STRING":
            # strip quotes, handle minimal escapes
            inner = text[1:-1]
            inner = inner.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
            tokens.append(Token("STRING", inner, line, col))
        else:
            tokens.append(Token(kind, text, line, col))
        pos = m.end()
    tokens.append(Token("EOF", None, line, pos - line_start + 1))
    return tokens


# =============================================================================
# Types (the type-system AST)
# =============================================================================

class Ty:
    pass

@dataclass(frozen=True)
class TyInt(Ty):
    def __str__(self) -> str: return "Int"

@dataclass(frozen=True)
class TyString(Ty):
    def __str__(self) -> str: return "String"

@dataclass(frozen=True)
class TyBool(Ty):
    def __str__(self) -> str: return "Bool"

@dataclass(frozen=True)
class TyList(Ty):
    elem: Ty
    def __str__(self) -> str: return f"List<{self.elem}>"

@dataclass(frozen=True)
class EffectRow:
    """An effect row: a concrete set of effect labels plus an optional row
    variable for polymorphism.

    {IO}        →  EffectRow({IO}, var=None)         — concrete
    {IO, E}     →  EffectRow({IO}, var="E")          — at least IO, plus E
    {E}         →  EffectRow(frozenset(), var="E")   — polymorphic
    {}          →  EffectRow(frozenset(), var=None)  — pure

    Substitution of row variables happens at call sites (effect polymorphism),
    similar to how TyVars are bound for parametric polymorphism."""
    concrete: frozenset[str]
    var: str | None = None

    def is_pure(self) -> bool:
        return not self.concrete and self.var is None

    def __str__(self) -> str:
        parts = sorted(self.concrete)
        if self.var: parts.append(self.var)
        if not parts: return ""
        return " !{" + ", ".join(parts) + "}"


PURE = EffectRow(frozenset(), None)


@dataclass(frozen=True)
class TyFn(Ty):
    """A function type with parametric effects. effects is an EffectRow;
    PURE for pure functions. Effects propagate to callers when invoked."""
    params: tuple[Ty, ...]
    ret: Ty
    effects: EffectRow = PURE
    def __str__(self) -> str:
        ps = ", ".join(str(p) for p in self.params)
        return f"({ps}) -> {self.ret}{self.effects}"

@dataclass(frozen=True)
class TyVar(Ty):
    """A type variable. Two flavours:
    - Non-rigid (default): can be bound by unification at call/let-binding sites.
      Built-ins, constructors, and the *exterior view* of polymorphic fns use these.
    - Rigid: only unifies with itself (same name). Used *inside* the body of a
      polymorphic fn so that type params behave as opaque types — preventing
      e.g. `let y : A = 42` from silently treating A as Int."""
    name: str
    rigid: bool = False
    def __str__(self) -> str: return self.name


@dataclass(frozen=True)
class TyADT(Ty):
    """An applied algebraic data type, e.g. Option<Int>, Result<Int, String>.
    The variant structure lives in the TypeChecker's adt_registry."""
    name: str
    args: tuple[Ty, ...]
    def __str__(self) -> str:
        if not self.args:
            return self.name
        return f"{self.name}<{', '.join(str(a) for a in self.args)}>"


@dataclass(frozen=True)
class TyTuple(Ty):
    """A fixed-arity heterogeneous tuple: (Int, String, Bool).
    Disambiguated from (Type) -> Type at parse time by the absence of '->'."""
    items: tuple[Ty, ...]
    def __str__(self) -> str:
        return "(" + ", ".join(str(t) for t in self.items) + ")"


@dataclass
class TyRefine(Ty):
    """A refinement type: a base type plus a Bool predicate that must hold of
    every inhabitant. Refinements are TRANSPARENT to the static type system
    (unify, resolve, instantiate all strip them) and ENFORCED at runtime via
    inserted predicate checks at param/let binding sites.

    The predicate is a Glass expression that references the surrounding
    binder's name (the fn parameter name or the let-bound name). It's
    evaluated against an env where that name maps to the bound value.

    v0.4 supports refinements only at fn-parameter types and let-binding
    types. Return-type refinements and refinements inside generic args
    are deferred to later versions."""
    base: Ty
    pred: "Node"  # Bool-typed expression

    def __str__(self) -> str:
        return f"{self.base} where ({pp_expr(self.pred)})"

    # Non-frozen so we don't need to hash a Node. Don't use TyRefine as a dict key.


def base_of(t: Ty) -> Ty:
    """Strip refinements to reach the underlying base type."""
    while isinstance(t, TyRefine):
        t = t.base
    return t


# =============================================================================
# Expression / Declaration AST
# =============================================================================

class Node:
    pass

@dataclass
class IntLit(Node):
    value: int

@dataclass
class StringLit(Node):
    value: str

@dataclass
class BoolLit(Node):
    value: bool

@dataclass
class ListLit(Node):
    items: list[Node]

@dataclass
class TupleLit(Node):
    items: list[Node]

@dataclass
class RecordLit(Node):
    """A record-construction expression: User { id: 1, name: "Alice" }.
    The type name and the field name-value pairs are explicit; the type
    checker resolves which record type this refers to and which type args
    bind to which positions."""
    name: str
    fields: list[tuple[str, Node]]

@dataclass
class FieldAccess(Node):
    """expr.field — projects a single field out of a record value."""
    record: Node
    field: str

@dataclass
class Ident(Node):
    name: str

@dataclass
class Call(Node):
    fn: Node
    args: list[Node]

@dataclass
class BinOp(Node):
    op: str
    lhs: Node
    rhs: Node

# v4.54: logical NOT. The third boolean operator after && (v4.51) and
# || (v4.52). Parses as a unary prefix in expression context; the !{...}
# effect-row syntax only occurs in type context, so the BANG token is
# now overloaded but unambiguous at parse time.
@dataclass
class UnaryNot(Node):
    expr: Node

@dataclass
class If(Node):
    cond: Node
    then_b: Node
    else_b: Node

@dataclass
class LetIn(Node):
    name: str
    ann: Ty | None
    value: Node
    body: Node
    # v4.67: `let lin x = ...` marks x as a LINEAR resource — it must be
    # consumed exactly once in the body (no cloning, no dropping). The
    # checker enforces this with a path-aware use count; eval is unchanged.
    linear: bool = False

@dataclass
class Lambda(Node):
    params: list[tuple[str, Ty]]
    ret: Ty
    body: Node

@dataclass
class Pattern:
    kind: str
    value: Any = None
    head: "Pattern | None" = None
    tail: "Pattern | None" = None
    args: "list[Pattern] | None" = None   # for ctor patterns: Some(x), Node(l, v, r)

@dataclass
class Match(Node):
    scrutinee: Node
    arms: list[tuple[Pattern, Node]]

@dataclass
class LetDecl(Node):
    name: str
    ann: Ty | None
    value: Node

@dataclass
class FnDecl(Node):
    name: str
    params: list[tuple[str, Ty]]
    ret: Ty
    body: Node
    type_params: list[str] = field(default_factory=list)
    effects: EffectRow = field(default_factory=lambda: PURE)


@dataclass
class Variant:
    """One variant of a sum type, e.g. `Some(T)` or `None`."""
    name: str
    fields: list[Ty]   # field types, possibly referring to the type's params
    # v4.69: optional per-field binder names, parallel to `fields`. A
    # named field can carry a refinement (`Pos(n: Int where (n > 0))`)
    # whose binder is that name; the refinement is checked when the
    # constructor is applied. Unnamed fields get None.
    field_names: list = field(default_factory=list)


@dataclass
class TypeDecl(Node):
    """A sum-type declaration: `type Option<T> = | None | Some(T)`."""
    name: str
    params: list[str]            # type parameter names (TyVar names within fields)
    variants: list[Variant]


@dataclass
class RecordDecl(Node):
    """A record-type declaration: `type User = { id: Int, name: String }`.
    Like TypeDecl, may be polymorphic in type parameters."""
    name: str
    params: list[str]
    fields: list[tuple[str, Ty]]


@dataclass
class Import(Node):
    """v4.70: `import "path/to/lib.glass"` — pulls in the DEFINITIONS
    (type / record / fn decls) of another file, skipping its top-level
    `let`s and final expression (so a file's demos don't run on import).
    Expanded before installation; the host has no module system beyond
    this flat merge (no namespacing) — enough to share a stdlib core."""
    path: str


# =============================================================================
# Linear / resource typing (v4.67)
# =============================================================================
# A `let lin x = ...` binding marks x as a linear resource: it must be
# consumed EXACTLY once in the body — no cloning (used twice), no dropping
# (never used). Enforcement is a static, path-aware use count below.

def _pattern_binds(pat: "Pattern | None", name: str) -> bool:
    """Does `pat` introduce a binding called `name`? (Used to detect a
    match arm that shadows a linear variable.)"""
    if pat is None:
        return False
    if pat.kind == "ident":
        return pat.value == name
    if pat.kind == "record":
        # args is a list of bound field-name strings
        return bool(pat.args) and name in pat.args
    if pat.kind == "ctor":
        return bool(pat.args) and any(_pattern_binds(a, name) for a in pat.args)
    if pat.head is not None or pat.tail is not None:   # list/cons pattern
        return _pattern_binds(pat.head, name) or _pattern_binds(pat.tail, name)
    return False


def linear_uses(e: "Node", name: str) -> int:
    """Count uses of linear variable `name` along ONE execution path.

    Branches must consume it identically: a value used in one `if` branch
    but not the other (or unequally across `match` arms) is a linearity
    violation, because exactly one branch runs. Capturing a linear value
    in a lambda is refused outright — a closure may be called any number
    of times, so single use can't be guaranteed statically. Raises
    TypeError_ on either problem."""
    t = type(e)
    if t is Ident:
        return 1 if e.name == name else 0
    if t in (IntLit, StringLit, BoolLit):
        return 0
    if t is BinOp:
        return linear_uses(e.lhs, name) + linear_uses(e.rhs, name)
    if t is UnaryNot:
        return linear_uses(e.expr, name)
    if t is If:
        tt = linear_uses(e.then_b, name)
        ft = linear_uses(e.else_b, name)
        if tt != ft:
            raise TypeError_(
                f"linear variable {name!r} used {tt}x in the `then` branch "
                f"but {ft}x in `else` — a linear resource must be consumed "
                f"identically on every path")
        return linear_uses(e.cond, name) + tt
    if t is LetIn:
        vc = linear_uses(e.value, name)
        if e.name == name:           # inner let shadows it in the body
            return vc
        return vc + linear_uses(e.body, name)
    if t is Lambda:
        if any(p == name for p, _ in e.params):
            return 0                 # shadowed by a lambda parameter
        if linear_uses(e.body, name) > 0:
            raise TypeError_(
                f"linear variable {name!r} captured in a lambda — single "
                f"use cannot be guaranteed (a closure may run any number "
                f"of times)")
        return 0
    if t is Call:
        return linear_uses(e.fn, name) + sum(linear_uses(a, name) for a in e.args)
    if t is Match:
        arm_counts = []
        for pat, body in e.arms:
            arm_counts.append(0 if _pattern_binds(pat, name)
                              else linear_uses(body, name))
        if arm_counts:
            first = arm_counts[0]
            for c in arm_counts[1:]:
                if c != first:
                    raise TypeError_(
                        f"linear variable {name!r} used unequally across "
                        f"match arms — must be consumed identically on every "
                        f"path")
            return linear_uses(e.scrutinee, name) + first
        return linear_uses(e.scrutinee, name)
    if t is ListLit or t is TupleLit:
        return sum(linear_uses(it, name) for it in e.items)
    if t is RecordLit:
        return sum(linear_uses(v, name) for _, v in e.fields)
    if t is FieldAccess:
        return linear_uses(e.record, name)
    return 0   # literals / unknown leaves contribute nothing


def pp_expr(e: "Node") -> str:
    """Compact pretty-printer for AST expressions. Used by TyRefine.__str__
    for diagnostics — keep it terse, not round-trippable."""
    if isinstance(e, IntLit):    return str(e.value)
    if isinstance(e, StringLit): return repr(e.value)
    if isinstance(e, BoolLit):   return "true" if e.value else "false"
    if isinstance(e, Ident):     return e.name
    if isinstance(e, BinOp):     return f"{pp_expr(e.lhs)} {e.op} {pp_expr(e.rhs)}"
    if isinstance(e, UnaryNot):
        # Always parenthesize so the printed shape reads back correctly.
        # Otherwise `!(n == 0)` would print as `!n == 0`, which the
        # parser would read as `(!n) == 0` — wrong scope.
        return f"!({pp_expr(e.expr)})"
    if isinstance(e, Call):
        return f"{pp_expr(e.fn)}({', '.join(pp_expr(a) for a in e.args)})"
    if isinstance(e, If):
        return f"if {pp_expr(e.cond)} then {pp_expr(e.then_b)} else {pp_expr(e.else_b)}"
    return f"<{type(e).__name__}>"


# =============================================================================
# Parser (recursive descent + Pratt for binary expressions)
# =============================================================================

# Binary operator precedence table (higher = binds tighter).
BIN_PREC = {
    "PIPE":   1,
    # v4.51: boolean combinators. Standard precedence — `||` binds
    # tightest of the very low operators, `&&` above it, comparisons
    # above that. Matches C / Glass intuition: `a > 0 && b < 100`
    # parses as `(a > 0) && (b < 100)`, not `a > (0 && b) < 100`.
    "OROR":   2,
    "ANDAND": 3,
    "EQ": 4, "NEQ": 4, "LT": 4, "GT": 4, "LE": 4, "GE": 4,
    "CONCAT": 5,
    "PLUS":   6, "MINUS": 6,
    "STAR":   7, "SLASH": 7, "PERCENT": 7,
}
RIGHT_ASSOC = {"CONCAT"}
# Comparison operators do not associate: `a == b == c` is a parse error (write
# `(a == b) == c`). glass.py's precedence climber would happily chain them, but
# prism's front end rejects the chain — so the reference matches the self-hosted
# compiler, and a program that runs here is one that self-hosts.
COMPARISON_OPS = {"EQ", "NEQ", "LT", "GT", "LE", "GE"}
OP_NAME = {
    "PLUS": "+", "MINUS": "-", "STAR": "*", "SLASH": "/",
    "EQ": "==", "NEQ": "!=", "LT": "<", "GT": ">", "LE": "<=", "GE": ">=",
    "CONCAT": "++", "PIPE": "|>",
    "ANDAND": "&&", "OROR": "||",
    # v4.53: modulo at the same precedence as `*` and `/`.
    "PERCENT": "%",
}


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        # Stack of in-scope type-parameter names. Pushed on entering a
        # polymorphic fn declaration so any type annotation inside the body
        # (lambda params, let-in annotations, etc.) can reference them.
        self.type_params_stack: list[list[str]] = []

    def current_type_params(self) -> list[str]:
        return [tp for frame in self.type_params_stack for tp in frame]

    def peek(self, k: int = 0) -> Token:
        return self.tokens[self.pos + k]

    def eat(self, kind: str) -> Token:
        t = self.peek()
        if t.kind != kind:
            raise SyntaxError(
                f"expected {kind} but got {t.kind} ({t.value!r}) at line {t.line}"
            )
        self.pos += 1
        return t

    def accept(self, kind: str) -> Token | None:
        if self.peek().kind == kind:
            t = self.peek()
            self.pos += 1
            return t
        return None

    # ---- programs ----
    def parse_program(self) -> list[Node]:
        decls: list[Node] = []
        while self.peek().kind != "EOF":
            decls.append(self.parse_decl())
        return decls

    def parse_decl(self) -> Node:
        t = self.peek()
        if t.kind == "import":
            self.eat("import")
            path = self.eat("STRING").value
            return Import(path=path)
        if t.kind == "let":
            return self.parse_let_decl()
        if t.kind == "fn":
            return self.parse_fn_decl()
        if t.kind == "type":
            return self.parse_type_decl()
        # treat top-level expression as anonymous let for REPL convenience
        return LetDecl(name="_", ann=None, value=self.parse_expr())

    def parse_let_decl(self) -> LetDecl:
        self.eat("let")
        name = self.eat("IDENT").value
        # A value binding must be lowercase: Glass reads an uppercase-leading
        # identifier as a constructor, and the self-hosted compiler compiles a
        # reference to it as one (so `let C = 5; ... C ...` silently stringifies
        # a constructor, not 5). Reject it here so the reference interpreter and
        # the compiler agree — the convention, enforced at the binding site.
        if name != "_" and name[:1].isupper():
            raise SyntaxError(
                f"top-level `let {name} = ...`: a value binding must be "
                f"lowercase — {name!r} is uppercase, which Glass reads as a "
                f"constructor. Rename it (e.g. {name.lower()!r})."
            )
        ann: Ty | None = None
        if self.accept("COLON"):
            ann = self.parse_type(accept_refinement=True)
        self.eat("ASSIGN")
        value = self.parse_expr()
        return LetDecl(name=name, ann=ann, value=value)

    def _consume_effect_set(self, scoped: list[str] | None = None) -> EffectRow:
        """Parse an optional !{Eff1, Eff2, ...} clause; return PURE if absent.

        A name that's in `scoped` (the type params in scope for this
        signature) is treated as an effect-row variable rather than a
        concrete label. v0.7 supports at most one row variable per row."""
        if not self.accept("BANG"):
            return PURE
        self.eat("LBRACE")
        concrete: set[str] = set()
        var: str | None = None
        scope = scoped if scoped is not None else self._current_scope()
        if self.peek().kind != "RBRACE":
            first = self.eat("IDENT").value
            if first in scope:
                var = first
            else:
                concrete.add(first)
            while self.accept("COMMA"):
                nxt = self.eat("IDENT").value
                if nxt in scope:
                    if var is not None and var != nxt:
                        raise SyntaxError(
                            f"effect row may have at most one row variable "
                            f"in v0.7 (saw {var!r} and {nxt!r})"
                        )
                    var = nxt
                else:
                    concrete.add(nxt)
        self.eat("RBRACE")
        return EffectRow(frozenset(concrete), var)

    def _current_scope(self) -> list[str]:
        """Flatten the type-params stack into a single list."""
        out: list[str] = []
        for frame in getattr(self, "type_params_stack", []):
            out.extend(frame)
        return out

    def parse_fn_decl(self) -> FnDecl:
        self.eat("fn")
        name = self.eat("IDENT").value
        # Optional type parameters: fn name<T1, T2>(...)
        type_params: list[str] = []
        if self.accept("LT"):
            type_params.append(self.eat("IDENT").value)
            while self.accept("COMMA"):
                type_params.append(self.eat("IDENT").value)
            self.eat("GT")
        self.type_params_stack.append(type_params)
        try:
            self.eat("LPAREN")
            params = self.parse_params(accept_refinement=True)
            self.eat("RPAREN")
            self.eat("COLON")
            ret = self.parse_type(accept_refinement=True)
            # Optional effect set after the return type: `: T !{IO, Random}`
            # or `: T !{IO, E}` where E is an effect-row variable bound by
            # the fn's type parameters. To put effects on a returned fn
            # type, wrap it in parens: `fn f() : ((Int) -> Int !{IO}) = ...`.
            effects = self._consume_effect_set(scoped=type_params)
            self.eat("ASSIGN")
            body = self.parse_expr()
        finally:
            self.type_params_stack.pop()
        return FnDecl(
            name=name, params=params, ret=ret, body=body,
            type_params=type_params, effects=effects,
        )

    def parse_type_decl(self) -> Node:
        """Parse either a sum-type declaration:
            type Name<T1> = | Var1 | Var2(T1)
        or a record-type declaration:
            type Name<T1> = { field1: T1, field2: Int }

        The token immediately after `=` discriminates: `{` → record,
        anything else → sum (with optional leading `|`)."""
        self.eat("type")
        name = self.eat("IDENT").value
        params: list[str] = []
        if self.accept("LT"):
            params.append(self.eat("IDENT").value)
            while self.accept("COMMA"):
                params.append(self.eat("IDENT").value)
            self.eat("GT")
        self.eat("ASSIGN")
        # Record form.
        if self.accept("LBRACE"):
            fields: list[tuple[str, Ty]] = []
            if self.peek().kind != "RBRACE":
                fname = self.eat("IDENT").value
                self.eat("COLON")
                fty = self.parse_type(params)
                fields.append((fname, fty))
                while self.accept("COMMA"):
                    fname = self.eat("IDENT").value
                    self.eat("COLON")
                    fty = self.parse_type(params)
                    fields.append((fname, fty))
            self.eat("RBRACE")
            return RecordDecl(name=name, params=params, fields=fields)
        # Sum form.
        variants: list[Variant] = []
        # The leading | before the first variant is optional but encouraged.
        self.accept("BAR")
        variants.append(self.parse_variant(params))
        while self.accept("BAR"):
            variants.append(self.parse_variant(params))
        return TypeDecl(name=name, params=params, variants=variants)

    def parse_variant(self, type_params: list[str]) -> Variant:
        vname = self.eat("IDENT").value
        fields: list[Ty] = []
        field_names: list = []
        if self.accept("LPAREN"):
            if self.peek().kind != "RPAREN":
                self._parse_variant_field(type_params, fields, field_names)
                while self.accept("COMMA"):
                    self._parse_variant_field(type_params, fields, field_names)
            self.eat("RPAREN")
        return Variant(name=vname, fields=fields, field_names=field_names)

    def _parse_variant_field(self, type_params, fields, field_names) -> None:
        # v4.69: a field may be `Type` (unnamed) or `name: Type [where (p)]`
        # (named, refinement-capable). A named field is detected as an
        # IDENT followed by COLON — distinct from a bare type name, which
        # is an uppercase-leading IDENT NOT followed by colon, or `List<…>`.
        name = None
        if self.peek().kind == "IDENT" and self.peek(1).kind == "COLON":
            name = self.eat("IDENT").value
            self.eat("COLON")
            fields.append(self.parse_type(type_params, accept_refinement=True))
        else:
            fields.append(self.parse_type(type_params))
        field_names.append(name)

    def parse_params(self, accept_refinement: bool = False) -> list[tuple[str, Ty]]:
        params: list[tuple[str, Ty]] = []
        if self.peek().kind == "RPAREN":
            return params
        while True:
            name = self.eat("IDENT").value
            self.eat("COLON")
            ty = self.parse_type(accept_refinement=accept_refinement)
            params.append((name, ty))
            if not self.accept("COMMA"):
                break
        return params

    # ---- types ----
    def parse_type(
        self,
        type_params: list[str] | None = None,
        accept_refinement: bool = False,
    ) -> Ty:
        # In-scope type params come from both the explicit arg (used by
        # parse_variant) and the parser-wide stack (set up by parse_fn_decl).
        scoped = list(type_params) if type_params else []
        scoped.extend(self.current_type_params())
        base = self._parse_type_atom(scoped)
        # Optional refinement: `T where (predicate)`. Only allowed at top-level
        # type positions (fn param types, let annotations); enforced by callers
        # passing accept_refinement=True only in those positions.
        if accept_refinement and self.peek().kind == "where":
            self.eat("where")
            self.eat("LPAREN")
            pred = self.parse_expr()
            self.eat("RPAREN")
            return TyRefine(base=base, pred=pred)
        return base

    def _parse_type_atom(self, scoped: list[str]) -> Ty:
        # function type: (T1, T2) -> T   OR   parenthesised T   OR   tuple type (T1, T2)
        if self.accept("LPAREN"):
            params: list[Ty] = []
            if self.peek().kind != "RPAREN":
                params.append(self.parse_type(scoped))
                while self.accept("COMMA"):
                    params.append(self.parse_type(scoped))
            self.eat("RPAREN")
            if self.accept("ARROW"):
                ret = self.parse_type(scoped)
                effects = self._consume_effect_set(scoped=scoped)
                return TyFn(tuple(params), ret, effects)
            if len(params) == 1:
                return params[0]  # parenthesised single type
            if len(params) >= 2:
                return TyTuple(tuple(params))
            raise SyntaxError("() is not a valid type in v0.6 (use a 1-tuple work-around)")
        name = self.eat("IDENT").value
        # Primitive types.
        if name == "Int":    return TyInt()
        if name == "String": return TyString()
        if name == "Bool":   return TyBool()
        if name == "List":
            self.eat("LT")
            elem = self.parse_type(scoped)
            self.eat("GT")
            return TyList(elem)
        # A reference to a type parameter (e.g. T inside type Option<T>
        # or inside fn foo<T>(...): ...).
        if name in scoped:
            return TyVar(name)
        # Otherwise it's an applied algebraic data type.
        args: list[Ty] = []
        if self.accept("LT"):
            args.append(self.parse_type(scoped))
            while self.accept("COMMA"):
                args.append(self.parse_type(scoped))
            self.eat("GT")
        return TyADT(name=name, args=tuple(args))

    # ---- expressions (Pratt) ----
    def parse_expr(self, min_prec: int = 0) -> Node:
        left = self.parse_unary()
        while True:
            t = self.peek()
            prec = BIN_PREC.get(t.kind)
            if prec is None or prec < min_prec:
                break
            self.pos += 1
            next_min = prec if t.kind in RIGHT_ASSOC else prec + 1
            right = self.parse_expr(next_min)
            if t.kind == "PIPE":
                # x |> f  =>  f(x)  (and f may itself be a call expression)
                if isinstance(right, Call):
                    left = Call(fn=right.fn, args=[left] + right.args)
                else:
                    left = Call(fn=right, args=[left])
            else:
                left = BinOp(op=OP_NAME[t.kind], lhs=left, rhs=right)
                nxt = self.peek()
                if t.kind in COMPARISON_OPS and nxt.kind in COMPARISON_OPS:
                    raise SyntaxError(
                        f"chained comparison '{OP_NAME[t.kind]} ... {OP_NAME[nxt.kind]}' "
                        f"at line {nxt.line} needs parentheses — comparison operators "
                        f"don't associate; write e.g. (a {OP_NAME[t.kind]} b) {OP_NAME[nxt.kind]} c"
                    )
        return left

    def parse_unary(self) -> Node:
        # Unary minus is folded into INT literal at the lexer level.
        # v4.54: BANG (`!`) is unary logical NOT in expression context.
        # The same token starts effect rows (`!{IO}`) in type context;
        # parse_type handles that path separately, so seeing BANG here
        # is unambiguously the boolean operator.
        if self.peek().kind == "BANG":
            self.pos += 1
            inner = self.parse_unary()  # right-assoc so `!!x` works
            return UnaryNot(expr=inner)
        return self.parse_postfix()

    def parse_postfix(self) -> Node:
        e = self.parse_atom()
        while True:
            nxt = self.peek()
            if nxt.kind == "LPAREN":
                # An LPAREN that starts a new line at column 1 is a new
                # top-level expression, not a call continuation. Without
                # this, `let s = id("hello")\n(n, s)` silently parses as
                # `id("hello")(n, s)`. The column-1 restriction keeps
                # indented continuations (`f\n  (x)`) working as calls.
                prev = self.tokens[self.pos - 1] if self.pos > 0 else None
                if prev is not None and nxt.col == 1 and nxt.line > prev.line:
                    break
                self.eat("LPAREN")
                args: list[Node] = []
                if self.peek().kind != "RPAREN":
                    args.append(self.parse_expr())
                    while self.accept("COMMA"):
                        args.append(self.parse_expr())
                self.eat("RPAREN")
                e = Call(fn=e, args=args)
            elif self.peek().kind == "DOT":
                self.eat("DOT")
                field = self.eat("IDENT").value
                e = FieldAccess(record=e, field=field)
            else:
                break
        return e

    def parse_atom(self) -> Node:
        t = self.peek()
        if t.kind == "INT":
            self.pos += 1
            return IntLit(t.value)
        if t.kind == "STRING":
            self.pos += 1
            return StringLit(t.value)
        if t.kind == "true":
            self.pos += 1
            return BoolLit(True)
        if t.kind == "false":
            self.pos += 1
            return BoolLit(False)
        if t.kind == "LBRACK":
            self.eat("LBRACK")
            items: list[Node] = []
            if self.peek().kind != "RBRACK":
                items.append(self.parse_expr())
                while self.accept("COMMA"):
                    items.append(self.parse_expr())
            self.eat("RBRACK")
            return ListLit(items)
        if t.kind == "LPAREN":
            self.eat("LPAREN")
            e = self.parse_expr()
            if self.accept("COMMA"):
                items = [e, self.parse_expr()]
                while self.accept("COMMA"):
                    items.append(self.parse_expr())
                self.eat("RPAREN")
                return TupleLit(items=items)
            self.eat("RPAREN")
            return e
        if t.kind == "if":
            self.eat("if")
            cond = self.parse_expr()
            self.eat("then")
            then_b = self.parse_expr()
            self.eat("else")
            else_b = self.parse_expr()
            return If(cond, then_b, else_b)
        if t.kind == "let":
            return self.parse_let_in()
        if t.kind == "fn":
            return self.parse_lambda()
        if t.kind == "match":
            return self.parse_match()
        if t.kind == "IDENT":
            self.pos += 1
            # An uppercase-start ident followed by `{` is a record literal.
            # We disambiguate by capital-letter convention — lowercase never
            # starts a record literal, so `x { ... }` is always two tokens.
            if (t.value and t.value[0].isupper()
                and self.peek().kind == "LBRACE"):
                self.eat("LBRACE")
                fields: list[tuple[str, Node]] = []
                if self.peek().kind != "RBRACE":
                    fields.append(self._parse_record_field())
                    while self.accept("COMMA"):
                        fields.append(self._parse_record_field())
                self.eat("RBRACE")
                return RecordLit(name=t.value, fields=fields)
            return Ident(t.value)
        raise SyntaxError(f"unexpected token {t.kind} ({t.value!r}) at line {t.line}")

    def _parse_record_field(self) -> tuple[str, Node]:
        name = self.eat("IDENT").value
        self.eat("COLON")
        value = self.parse_expr()
        return (name, value)

    def parse_let_in(self) -> LetIn:
        self.eat("let")
        # v4.67: `let lin x = EXPR in BODY` marks x linear. `lin` is a
        # CONTEXTUAL keyword — only special when it's an IDENT "lin"
        # immediately followed by another IDENT (the binding name). So
        # `let lin = 5 in lin` (a variable literally named lin) still
        # works: there `lin` is followed by `=`, not an identifier.
        linear = False
        if (self.peek().kind == "IDENT" and self.peek().value == "lin"
                and self.peek(1).kind == "IDENT"):
            self.pos += 1   # consume `lin`
            linear = True
        # `let* PAT = EXPR in BODY` — Result-bind sugar (v2.4).
        if self.peek().kind == "STAR":
            self.eat("STAR")
            return self._parse_let_star_in()
        # `let? PAT = EXPR in BODY` — Option-bind sugar (v2.5).
        if self.peek().kind == "QMARK":
            self.eat("QMARK")
            return self._parse_let_qmark_in()
        # `let PAT = EXPR in BODY` where PAT is a tuple/list/ctor pattern (v2.7).
        # Identifier-only lets keep the traditional LetIn path so let-polymorphism
        # generalization still applies. Other patterns desugar to Match.
        if self.peek().kind in ("LPAREN", "LBRACK"):
            return self._parse_let_pattern_in()
        # Uppercase-leading IDENT followed by ASSIGN means the user wrote a
        # constructor pattern (e.g. `let Pair(a, b) = ...`). Desugar to Match.
        if (self.peek().kind == "IDENT"
            and self.peek().value
            and self.peek().value[0].isupper()):
            return self._parse_let_pattern_in()
        name = self.eat("IDENT").value
        ann: Ty | None = None
        if self.accept("COLON"):
            ann = self.parse_type(accept_refinement=True)
        self.eat("ASSIGN")
        value = self.parse_expr()
        self.eat("in")
        body = self.parse_expr()
        return LetIn(name=name, ann=ann, value=value, body=body, linear=linear)

    def _parse_let_pattern_in(self):
        """Parse `let PAT = EXPR in BODY` where PAT is not a bare identifier.

        Desugars to: match EXPR { PAT => BODY }
        Type-checker enforces exhaustiveness, so non-exhaustive patterns
        (like `let Some(x) = optional in ...`) get a compile-time warning
        from the same machinery that handles match.
        """
        pat = self.parse_pattern()
        self.eat("ASSIGN")
        value = self.parse_expr()
        self.eat("in")
        body = self.parse_expr()
        return Match(scrutinee=value, arms=[(pat, body)])

    def _let_star_counter(self) -> int:
        n = getattr(self, "_ls_counter", 0)
        self._ls_counter = n + 1
        return n

    def _parse_let_star_in(self):
        """Parse `let* PAT = EXPR in BODY` and desugar to a Match.

        The desugar pulls in `Ok`/`Err` constructors; the user must already
        be writing inside a function whose return type is `Result<_, _>` for
        the resulting expression to type-check.
        """
        pat = self.parse_pattern()
        self.eat("ASSIGN")
        value = self.parse_expr()
        self.eat("in")
        body = self.parse_expr()
        n = self._let_star_counter()
        err_name = f"__star_err_{n}"
        ok_name = f"__star_ok_{n}"
        err_pat = Pattern("ctor", value="Err",
                          args=[Pattern("ident", value=err_name)])
        err_body = Call(fn=Ident(name="Err"), args=[Ident(name=err_name)])
        ok_pat = Pattern("ctor", value="Ok",
                         args=[Pattern("ident", value=ok_name)])
        ok_body = Match(scrutinee=Ident(name=ok_name), arms=[(pat, body)])
        return Match(scrutinee=value, arms=[(err_pat, err_body), (ok_pat, ok_body)])

    def _parse_let_qmark_in(self):
        """Parse `let? PAT = EXPR in BODY` and desugar to a Match.

        Mirror of `let*` for Option. The enclosing context must have an
        Option<_> result type for the desugared `None` arm to type-check.
        """
        pat = self.parse_pattern()
        self.eat("ASSIGN")
        value = self.parse_expr()
        self.eat("in")
        body = self.parse_expr()
        n = self._let_star_counter()
        some_name = f"__qmark_some_{n}"
        # Arm 1: None => None  (None is a zero-arg ctor, used as a value)
        none_pat = Pattern("ctor", value="None", args=[])
        none_body = Ident(name="None")
        # Arm 2: Some(__qmark_some_N) => match __qmark_some_N { PAT => BODY }
        some_pat = Pattern("ctor", value="Some",
                           args=[Pattern("ident", value=some_name)])
        some_body = Match(scrutinee=Ident(name=some_name), arms=[(pat, body)])
        return Match(scrutinee=value, arms=[(none_pat, none_body), (some_pat, some_body)])

    def parse_lambda(self) -> Lambda:
        self.eat("fn")
        self.eat("LPAREN")
        # v4.47: accept_refinement=True so lambda params can carry
        # `where (pred)` clauses (e.g. fn(x: Int where (x > 0)) -> ...).
        # apply_fn already enforces TyRefine on params at call time, so
        # no separate runtime path is needed in the host.
        params = self.parse_params(accept_refinement=True)
        self.eat("RPAREN")
        self.eat("ARROW")
        body = self.parse_expr()
        # Lambda return type is inferred in v0.0.1 (annotated lambdas: v0.1)
        return Lambda(params=params, ret=TyVar("_"), body=body)

    def parse_match(self) -> Match:
        self.eat("match")
        scrut = self.parse_expr()
        self.eat("LBRACE")
        arms: list[tuple[Pattern, Node]] = []
        while self.peek().kind != "RBRACE":
            pat = self.parse_pattern()
            self.eat("FATARROW")
            body = self.parse_expr()
            arms.append((pat, body))
            self.accept("SEMI")  # optional separator
        self.eat("RBRACE")
        return Match(scrutinee=scrut, arms=arms)

    def parse_pattern(self) -> Pattern:
        t = self.peek()
        if t.kind == "IDENT" and t.value == "_":
            self.pos += 1
            return Pattern("wild")
        if t.kind == "IDENT":
            # Convention: uppercase-leading identifier = constructor; else binding.
            if t.value[0].isupper():
                self.pos += 1
                # Record pattern: Name { field1, field2, ... } — each entry
                # binds the field of that name. (v0.8: bindings only; no
                # renaming or `..` rest, both are post-v0.8.)
                if self.accept("LBRACE"):
                    rec_fields: list[str] = []
                    if self.peek().kind != "RBRACE":
                        rec_fields.append(self.eat("IDENT").value)
                        while self.accept("COMMA"):
                            rec_fields.append(self.eat("IDENT").value)
                    self.eat("RBRACE")
                    return Pattern("record", value=t.value, args=rec_fields)
                args: list[Pattern] | None = None
                if self.accept("LPAREN"):
                    args = []
                    if self.peek().kind != "RPAREN":
                        args.append(self.parse_pattern())
                        while self.accept("COMMA"):
                            args.append(self.parse_pattern())
                    self.eat("RPAREN")
                return Pattern("ctor", value=t.value, args=args)
            self.pos += 1
            return Pattern("ident", value=t.value)
        if t.kind == "INT":
            self.pos += 1
            return Pattern("int", value=t.value)
        if t.kind == "STRING":
            self.pos += 1
            return Pattern("string", value=t.value)
        if t.kind in ("true", "false"):
            self.pos += 1
            return Pattern("bool", value=(t.kind == "true"))
        if t.kind == "LBRACK":
            self.eat("LBRACK")
            if self.accept("RBRACK"):
                return Pattern("nil")
            heads = [self.parse_pattern()]
            # `[h1, .., hn]` is a fixed-length list (tail = nil); `[h1, .., hn, ...t]`
            # binds the rest to t. Both desugar to right-nested cons. Fixed-length
            # support matches prism, which accepts `[a, b]` — the reference used to
            # require the `...t` ellipsis and reject `[a, b]`.
            tail: Pattern = Pattern("nil")
            while self.peek().kind == "COMMA":
                self.eat("COMMA")
                if self.accept("ELLIPSIS"):
                    tail = self.parse_pattern()
                    break
                heads.append(self.parse_pattern())
            self.eat("RBRACK")
            # Build right-associative cons: heads = [h1, h2, h3], tail = t
            #   → cons(h1, cons(h2, cons(h3, t)))
            result = tail
            for h in reversed(heads):
                result = Pattern("cons", head=h, tail=result)
            return result
        if t.kind == "LPAREN":
            self.eat("LPAREN")
            items = [self.parse_pattern()]
            while self.accept("COMMA"):
                items.append(self.parse_pattern())
            self.eat("RPAREN")
            if len(items) == 1:
                return items[0]  # parenthesised single pattern
            return Pattern("tuple", args=items)
        raise SyntaxError(f"bad pattern starting at {t.kind}")


# =============================================================================
# Type checker
# =============================================================================

class TypeError_(Exception):
    pass


def builtin_types() -> dict[str, Ty]:
    T, U, A = TyVar("T"), TyVar("U"), TyVar("A")
    # Effect-row variable used by polymorphic higher-order builtins so they
    # adapt to whatever effects their callback brings.
    E = EffectRow(frozenset(), "E")
    # Data-first convention: the subject (list) is the first argument.
    # Note: TyADT("Option", ...) here is a structural reference; Option is
    # registered by the prelude before any user code runs.
    return {
        "print":          TyFn((TyString(),), TyString(),
                                EffectRow(frozenset({"IO"}))),
        "random_int":     TyFn((TyInt(), TyInt()), TyInt(),
                                EffectRow(frozenset({"Random"}))),
        # !{Inference}: marks a call into an external model (LLM, classifier,
        # etc.). Visible at every call site, just like IO/Random.
        "model_call":     TyFn((TyString(),), TyString(),
                                EffectRow(frozenset({"Inference"}))),
        "len":            TyFn((TyList(T),), TyInt()),
        "head":           TyFn((TyList(T),), TyADT("Option", (T,))),
        "tail":           TyFn((TyList(T),), TyADT("Option", (TyList(T),))),
        "reverse":        TyFn((TyList(T),), TyList(T)),
        # Effect-polymorphic: map's effects are exactly its callback's effects.
        # `map(xs, print)` ⇒ map's effects bind to {IO}.
        # `map(xs, double)` ⇒ map's effects bind to {} (pure).
        "map":            TyFn((TyList(T), TyFn((T,), U, E)), TyList(U), E),
        "filter":         TyFn((TyList(T), TyFn((T,), TyBool(), E)), TyList(T), E),
        "fold":           TyFn((TyList(T), A, TyFn((A, T), A, E)), A, E),
        "range":          TyFn((TyInt(), TyInt()), TyList(TyInt())),
        # Goldilocks field arithmetic on base-2^16 limb lists (fast path for the
        # ZK prover; same result as the Glass fmul/fadd/fsub, computed in one bignum op).
        "gold_mul":       TyFn((TyList(TyInt()), TyList(TyInt())), TyList(TyInt())),
        "gold_add":       TyFn((TyList(TyInt()), TyList(TyInt())), TyList(TyInt())),
        "gold_sub":       TyFn((TyList(TyInt()), TyList(TyInt())), TyList(TyInt())),
        "string_length":  TyFn((TyString(),), TyInt()),
        "substring":      TyFn((TyString(), TyInt(), TyInt()), TyString()),
        # Loud, both-sides abort: stderr message + nonzero exit (native q_error
        # mirrors this). Pure-divergent (no effect row, polymorphic return like
        # Haskell's `error :: String -> a`) so it composes anywhere — used by the
        # prove bridge to REFUSE to certify a circuit it cannot faithfully build,
        # instead of silently lowering to a proven 0.
        "error":          TyFn((TyString(),), A),
        # v4.40: ASCII case conversion. Strings outside A-Za-z pass
        # through unchanged. Non-ASCII bytes are left alone (no
        # Unicode normalisation) so host and Quartz agree.
        "string_to_upper": TyFn((TyString(),), TyString()),
        "string_to_lower": TyFn((TyString(),), TyString()),
        # v4.41: char_at returns the byte's value as Int (codepoint
        # for ASCII; raw byte for UTF-8). Matches Quartz semantics and
        # quartz_parser.glass / djb2 hash usage. Prism's user-defined
        # `fn char_at(s, i) : String = substring(s, i, i+1)` still
        # shadows this builtin inside prism's own source — prism's
        # internal lexer keeps using its String-returning char_at.
        "char_at": TyFn((TyString(), TyInt()), TyInt()),
        # v4.42: bitwise ops on Int. Semantics match C's int64_t:
        # results are masked to 64 bits and sign-extended. So
        # bit_shl(1, 63) is -9223372036854775808 (the smallest int64),
        # and djb2 overflow matches the compiled-Glass output. Without
        # the mask Python's unbounded ints would give different
        # numbers from Quartz.
        "bit_and": TyFn((TyInt(), TyInt()), TyInt()),
        "bit_or":  TyFn((TyInt(), TyInt()), TyInt()),
        "bit_xor": TyFn((TyInt(), TyInt()), TyInt()),
        "bit_not": TyFn((TyInt(),),          TyInt()),
        "bit_shl": TyFn((TyInt(), TyInt()), TyInt()),
        "bit_shr": TyFn((TyInt(), TyInt()), TyInt()),
        # v4.43: explicit int64 wrap. On host this applies the same
        # _to_int64 mask the bitwise ops use; on Quartz it's a no-op
        # (values are already int64_t natively). Gives users a knob
        # for algorithms that overflow `+`/`-`/`*` and need Quartz-
        # parity output through the host interpreter.
        "wrap_int64": TyFn((TyInt(),), TyInt()),
        "string_index_of": TyFn(
            (TyString(), TyString()),
            TyADT("Option", (TyInt(),)),
        ),
        "read_file":      TyFn(
            (TyString(),),
            TyADT("Result", (TyString(), TyString())),
            EffectRow(frozenset({"File"})),
        ),
        # v3.13 — write a String to disk. Result<Int, String> where Ok wraps
        # the byte count written and Err carries the OS error message.
        # Effect: !{File}, same as read_file.
        "write_file":     TyFn(
            (TyString(), TyString()),
            TyADT("Result", (TyInt(), TyString())),
            EffectRow(frozenset({"File"})),
        ),
        # v3.13 — invoke an external command. Takes (cmd, args) where args
        # is a List<String>. On success returns Ok((exit_code, stdout, stderr));
        # on failure (file-not-found, etc.) returns Err(message). The tuple
        # in Ok lets demos inspect all three outputs separately.
        # Effect: !{Process} — a new, distinct effect from File so the
        # type signature makes process-spawning visible at every call site.
        "run_command":    TyFn(
            (TyString(), TyList(TyString())),
            TyADT("Result",
                  (TyTuple((TyInt(), TyString(), TyString())), TyString())),
            EffectRow(frozenset({"Process"})),
        ),
        "int_to_string":  TyFn((TyInt(),), TyString()),
    }


def unify_effects(
    e1: EffectRow,
    e2: EffectRow,
    eff_subst: dict[str, EffectRow],
    rigid_eff: set[str],
) -> bool:
    """Unify two effect rows. Updates eff_subst in place.

    Simplifying restrictions for v0.7:
      - A "row var on one side, anything on the other" only binds when the
        var side has empty concrete. Mixed rows (concrete + var) require
        exact equality.
      - Rigid vars only unify with the same-named rigid var (parallel to
        rigid TyVar semantics).
    These cover map/filter/fold and most common cases; can be relaxed later."""
    e1 = resolve_effects(e1, eff_subst)
    e2 = resolve_effects(e2, eff_subst)
    if e1 == e2:
        return True
    # Pure-var on the left: bind it (if non-rigid).
    if e1.var is not None and not e1.concrete:
        if e1.var in rigid_eff:
            # Rigid: only equal to same row (handled above).
            return False
        eff_subst[e1.var] = e2
        return True
    if e2.var is not None and not e2.concrete:
        if e2.var in rigid_eff:
            return False
        eff_subst[e2.var] = e1
        return True
    # Mixed (concrete + var) rows: require structural equality.
    return False


def resolve_effects(
    e: EffectRow,
    eff_subst: dict[str, EffectRow],
) -> EffectRow:
    if e.var is None or e.var not in eff_subst:
        return e
    bound = resolve_effects(eff_subst[e.var], eff_subst)
    return EffectRow(e.concrete | bound.concrete, bound.var)


def instantiate_effects(
    e: EffectRow,
    eff_mapping: dict[str, str],
) -> EffectRow:
    if e.var is None or e.var not in eff_mapping:
        return e
    return EffectRow(e.concrete, eff_mapping[e.var])


def effect_row_subset(small: EffectRow, big: EffectRow) -> bool:
    """Is `small` a subset of `big`? Used for the body-effects-vs-declared
    check. small.concrete must be ⊆ big.concrete, and any row variable in
    small must equal big's row variable (or big must be the same rigid var)."""
    if not small.concrete.issubset(big.concrete):
        return False
    if small.var is None:
        return True
    return small.var == big.var


def extend_effects(acc: EffectRow, more: EffectRow) -> EffectRow:
    """Accumulate `more` into `acc` for effect propagation through calls.
    Concrete labels union; row variables are kept if compatible (same name
    or one side has no var). If two distinct row vars appear, the result
    keeps the existing one — callers detect mismatches via the body-subset
    check at fn-body end."""
    new_concrete = acc.concrete | more.concrete
    new_var = acc.var if acc.var is not None else more.var
    return EffectRow(new_concrete, new_var)


def unify(
    t1: Ty, t2: Ty,
    subst: dict[str, Ty],
    eff_subst: dict[str, EffectRow] | None = None,
    rigid_eff: set[str] | None = None,
) -> bool:
    """Unification with rigid-var handling. Refinements are transparent —
    stripped to their base before structural comparison. Static type system
    treats `Int where (x > 0)` and `Int` as equivalent; runtime enforces
    the predicate separately. eff_subst and rigid_eff carry effect-row
    substitutions and the set of currently-rigid effect var names."""
    if eff_subst is None: eff_subst = {}
    if rigid_eff is None: rigid_eff = set()
    t1 = base_of(resolve(t1, subst, eff_subst))
    t2 = base_of(resolve(t2, subst, eff_subst))

    # Same rigid var: OK without binding.
    if (isinstance(t1, TyVar) and isinstance(t2, TyVar)
        and t1.rigid and t2.rigid and t1.name == t2.name):
        return True

    # Rigid on the left: only a non-rigid TyVar on the right can unify with it.
    if isinstance(t1, TyVar) and t1.rigid:
        if isinstance(t2, TyVar) and not t2.rigid:
            subst[t2.name] = t1
            return True
        return False
    if isinstance(t2, TyVar) and t2.rigid:
        if isinstance(t1, TyVar) and not t1.rigid:
            subst[t1.name] = t2
            return True
        return False

    # Non-rigid TyVars bind freely.
    if isinstance(t1, TyVar):
        subst[t1.name] = t2
        return True
    if isinstance(t2, TyVar):
        subst[t2.name] = t1
        return True

    # Concrete vs concrete: structural.
    if type(t1) != type(t2):
        return False
    if isinstance(t1, TyList) and isinstance(t2, TyList):
        return unify(t1.elem, t2.elem, subst, eff_subst, rigid_eff)
    if isinstance(t1, TyFn) and isinstance(t2, TyFn):
        if len(t1.params) != len(t2.params):
            return False
        if not unify_effects(t1.effects, t2.effects, eff_subst, rigid_eff):
            return False
        for a, b in zip(t1.params, t2.params):
            if not unify(a, b, subst, eff_subst, rigid_eff): return False
        return unify(t1.ret, t2.ret, subst, eff_subst, rigid_eff)
    if isinstance(t1, TyADT) and isinstance(t2, TyADT):
        if t1.name != t2.name: return False
        if len(t1.args) != len(t2.args): return False
        for a, b in zip(t1.args, t2.args):
            if not unify(a, b, subst, eff_subst, rigid_eff): return False
        return True
    if isinstance(t1, TyTuple) and isinstance(t2, TyTuple):
        if len(t1.items) != len(t2.items): return False
        for a, b in zip(t1.items, t2.items):
            if not unify(a, b, subst, eff_subst, rigid_eff): return False
        return True
    return True  # both Int/String/Bool


def resolve(
    t: Ty,
    subst: dict[str, Ty],
    eff_subst: dict[str, EffectRow] | None = None,
) -> Ty:
    if eff_subst is None: eff_subst = {}
    if isinstance(t, TyVar) and t.name in subst:
        return resolve(subst[t.name], subst, eff_subst)
    if isinstance(t, TyList):
        return TyList(resolve(t.elem, subst, eff_subst))
    if isinstance(t, TyFn):
        return TyFn(
            tuple(resolve(p, subst, eff_subst) for p in t.params),
            resolve(t.ret, subst, eff_subst),
            resolve_effects(t.effects, eff_subst),
        )
    if isinstance(t, TyADT):
        return TyADT(t.name, tuple(resolve(a, subst, eff_subst) for a in t.args))
    if isinstance(t, TyTuple):
        return TyTuple(tuple(resolve(item, subst, eff_subst) for item in t.items))
    if isinstance(t, TyRefine):
        return TyRefine(resolve(t.base, subst, eff_subst), t.pred)
    return t


def equal_ty(t1: Ty, t2: Ty) -> bool:
    return base_of(resolve(t1, {})) == base_of(resolve(t2, {}))


# ---- Fresh type variables and polymorphic instantiation ----

_fresh_counter = 0
def fresh_tv() -> TyVar:
    global _fresh_counter
    _fresh_counter += 1
    return TyVar(f"_v{_fresh_counter}")


def fresh_eff_var() -> str:
    """Fresh effect-row variable name."""
    global _fresh_counter
    _fresh_counter += 1
    return f"_e{_fresh_counter}"


def collect_tyvars(t: Ty) -> set[str]:
    if isinstance(t, TyVar):
        return set() if t.rigid else {t.name}
    if isinstance(t, TyList): return collect_tyvars(t.elem)
    if isinstance(t, TyFn):
        s: set[str] = set()
        for p in t.params: s |= collect_tyvars(p)
        return s | collect_tyvars(t.ret)
    if isinstance(t, TyADT):
        s = set()
        for a in t.args: s |= collect_tyvars(a)
        return s
    if isinstance(t, TyTuple):
        s = set()
        for it in t.items: s |= collect_tyvars(it)
        return s
    if isinstance(t, TyRefine):
        return collect_tyvars(t.base)
    return set()


def collect_effect_vars(t: Ty, rigid_eff: set[str] | None = None) -> set[str]:
    """Collect non-rigid effect-row variable names appearing in t.
    Used by instantiate_fresh so each polymorphic identifier lookup gets
    fresh effect vars in addition to fresh type vars."""
    if rigid_eff is None: rigid_eff = set()
    if isinstance(t, TyFn):
        s: set[str] = set()
        for p in t.params: s |= collect_effect_vars(p, rigid_eff)
        s |= collect_effect_vars(t.ret, rigid_eff)
        if t.effects.var is not None and t.effects.var not in rigid_eff:
            s.add(t.effects.var)
        return s
    if isinstance(t, TyList):
        return collect_effect_vars(t.elem, rigid_eff)
    if isinstance(t, TyADT):
        s = set()
        for a in t.args: s |= collect_effect_vars(a, rigid_eff)
        return s
    if isinstance(t, TyTuple):
        s = set()
        for it in t.items: s |= collect_effect_vars(it, rigid_eff)
        return s
    if isinstance(t, TyRefine):
        return collect_effect_vars(t.base, rigid_eff)
    return set()


def instantiate(
    t: Ty,
    mapping: dict[str, Ty],
    eff_mapping: dict[str, str] | None = None,
) -> Ty:
    if eff_mapping is None: eff_mapping = {}
    if isinstance(t, TyVar):
        return mapping.get(t.name, t)
    if isinstance(t, TyList):
        return TyList(instantiate(t.elem, mapping, eff_mapping))
    if isinstance(t, TyFn):
        return TyFn(
            tuple(instantiate(p, mapping, eff_mapping) for p in t.params),
            instantiate(t.ret, mapping, eff_mapping),
            instantiate_effects(t.effects, eff_mapping),
        )
    if isinstance(t, TyADT):
        return TyADT(t.name, tuple(instantiate(a, mapping, eff_mapping) for a in t.args))
    if isinstance(t, TyTuple):
        return TyTuple(tuple(instantiate(item, mapping, eff_mapping) for item in t.items))
    if isinstance(t, TyRefine):
        # Predicates reference value-level names, not type vars — leave them.
        return TyRefine(instantiate(t.base, mapping, eff_mapping), t.pred)
    return t


# Alias: substitute is the same operation, just used in a different context
# (specialising ADT field types against scrutinee args, not refreshing fresh vars).
substitute = instantiate


def instantiate_fresh(t: Ty, rigid_eff: set[str] | None = None) -> Ty:
    """Replace each non-rigid TyVar and effect-row var in t with a fresh
    one — used at every Ident lookup so multiple uses of the same polymorphic
    identifier don't share variables."""
    if rigid_eff is None: rigid_eff = set()
    tvs = collect_tyvars(t)
    evs = collect_effect_vars(t, rigid_eff)
    if not tvs and not evs:
        return t
    mapping = {n: fresh_tv() for n in tvs}
    eff_mapping = {n: fresh_eff_var() for n in evs}
    return instantiate(t, mapping, eff_mapping)


class TypeChecker:
    def __init__(self):
        self.env: dict[str, Ty] = builtin_types()
        # adt_name -> (type_param_names, variants).
        self.adt_registry: dict[str, tuple[list[str], list[Variant]]] = {}
        # ctor_name -> (adt_name, field_types, param_names).
        self.ctor_registry: dict[str, tuple[str, list[Ty], list[str]]] = {}
        # record_name -> (type_param_names, [(field_name, field_type)]).
        # Records use the same TyADT representation as sums; the registry
        # distinguishes them at construction/access sites.
        self.record_registry: dict[
            str, tuple[list[str], list[tuple[str, Ty]]]
        ] = {}
        # Stack of rigid-substitution maps. Pushed on entering a polymorphic
        # fn body so any type annotation inside (lambda params, let-in anns)
        # gets the rigid version of the type params.
        self.rigid_stack: list[dict[str, Ty]] = []
        # Parallel stack for rigid effect-row vars: pushed when entering a
        # polymorphic fn body that declares an effect var like `<E>` and
        # uses it in `!{E}`. Effect vars are rigid in the body and become
        # bindable substitution targets at the call site.
        self.rigid_effect_stack: list[set[str]] = []
        # Effect accumulator. Initialised to pure; check_call extends it
        # when an effectful fn is invoked. check_fn_body verifies that the
        # accumulated row is a subset of the declared row.
        self.current_effects: EffectRow = PURE
        # Map from fn name -> FnDecl, populated during signature registration.
        # Used by static refinement discharge to recover param names from a
        # bare Ident call site.
        self.fn_decls: dict[str, FnDecl] = {}
        # Effect-substitution dict shared across a single body's checking
        # (so the same row var, bound at one call site, propagates to others).
        self.eff_subst: dict[str, EffectRow] = {}

    def current_rigid_eff(self) -> set[str]:
        merged: set[str] = set()
        for frame in self.rigid_effect_stack:
            merged |= frame
        return merged

    def current_rigid_map(self) -> dict[str, Ty]:
        merged: dict[str, Ty] = {}
        for frame in self.rigid_stack:
            merged.update(frame)
        return merged

    def rigidify(self, t: Ty) -> Ty:
        rm = self.current_rigid_map()
        return substitute(t, rm) if rm else t

    def check_refinement_pred(
        self, name: str, ty: Ty, env: dict[str, Ty],
    ) -> None:
        """If ty is a refinement, type-check its predicate as Bool with the
        binder name in scope. env must already contain name -> base type."""
        if not isinstance(ty, TyRefine):
            return
        pred_ty = self.infer(ty.pred, env)
        if not equal_ty(base_of(pred_ty), TyBool()):
            raise TypeError_(
                f"refinement predicate for {name!r} must return Bool, got {pred_ty}"
            )

    def check_program(self, decls: list[Node]) -> None:
        """Two-pass type checking:
        Pass 1 registers all type declarations and fn signatures so mutual
        recursion between top-level fns works. Pass 2 checks fn bodies and
        let initializers in source order."""
        for d in decls:
            if isinstance(d, TypeDecl):
                self.register_type(d)
            elif isinstance(d, RecordDecl):
                self.register_record(d)
            elif isinstance(d, FnDecl):
                self.register_fn_signature(d)
        for d in decls:
            if isinstance(d, FnDecl):
                self.check_fn_body(d)
            elif isinstance(d, LetDecl):
                self.check_decl(d)
            # TypeDecls and RecordDecls already handled in pass 1.

    def register_fn_signature(self, d: FnDecl) -> None:
        """Pass 1 of fn checking: validate signature types, register the
        fn name with its non-rigid type in env. Body is NOT checked yet."""
        for _, t in d.params:
            self.validate_type(t)
        self.validate_type(d.ret)
        # d.effects is already an EffectRow built by the parser.
        fn_ty = TyFn(tuple(p[1] for p in d.params), d.ret, d.effects)
        self.env[d.name] = fn_ty
        self.fn_decls[d.name] = d

    def check_fn_body(self, d: FnDecl) -> None:
        """Pass 2 of fn checking: check the body against the (already-registered)
        signature, with rigid type params and effect tracking.

        For effect polymorphism: any type param mentioned in the declared
        effect row (e.g. `E` in `: T !{E}`) is RIGID inside the body —
        it can only unify with itself. At each call site OUTSIDE the body,
        E is bound to whatever the actual callback's effects are."""
        declared_effects = d.effects
        rigid_map: dict[str, Ty] = {
            tp: TyVar(tp, rigid=True) for tp in d.type_params
        }
        rigid_params = [(name, substitute(t, rigid_map)) for name, t in d.params]
        rigid_ret = substitute(d.ret, rigid_map)
        rigid_fn_ty = TyFn(
            tuple(t for _, t in rigid_params), rigid_ret, declared_effects,
        )
        # local_env inherits the global env (which already has all fn signatures
        # from pass 1, enabling mutual recursion) but overrides this fn's name
        # with its rigid signature for self-recursive calls.
        local_env = {**self.env, d.name: rigid_fn_ty}
        for p, t in rigid_params:
            local_env[p] = t
        for p, t in rigid_params:
            self.check_refinement_pred(p, t, local_env)
        self.rigid_stack.append(rigid_map)
        # Rigid effect var: the var named in the declared row, if any.
        rigid_eff_frame: set[str] = set()
        if declared_effects.var is not None:
            rigid_eff_frame.add(declared_effects.var)
        self.rigid_effect_stack.append(rigid_eff_frame)
        saved_effects = self.current_effects
        saved_eff_subst = self.eff_subst
        self.current_effects = PURE
        self.eff_subst = {}
        try:
            body_ty = self.infer(d.body, local_env)
        finally:
            body_effects = resolve_effects(self.current_effects, self.eff_subst)
            self.current_effects = saved_effects
            self.eff_subst = saved_eff_subst
            self.rigid_stack.pop()
            self.rigid_effect_stack.pop()
        # Subset check on the resolved body row vs declared row.
        if not effect_row_subset(body_effects, declared_effects):
            extra: list[str] = []
            if not body_effects.concrete.issubset(declared_effects.concrete):
                extra.extend(sorted(body_effects.concrete - declared_effects.concrete))
            if body_effects.var is not None and body_effects.var != declared_effects.var:
                extra.append(body_effects.var)
            declared_str = (
                "{" + ", ".join(sorted(declared_effects.concrete) +
                                ([declared_effects.var] if declared_effects.var else []))
                + "}" if (declared_effects.concrete or declared_effects.var) else "{}"
            )
            raise TypeError_(
                f"fn {d.name} performs effect(s) {extra} not declared "
                f"in {declared_str}"
            )
        subst: dict[str, Ty] = {}
        if not unify(body_ty, rigid_ret, subst, self.eff_subst,
                     self.current_rigid_eff()):
            raise TypeError_(
                f"fn {d.name}: declared return {d.ret}, body is {body_ty}"
            )

    def check_decl(self, d: Node) -> None:
        """Single-decl checker — used by install_decl in REPL mode and by
        check_program's pass 2 for non-Fn decls. For FnDecl, performs both
        signature registration and body check (so REPL can process one fn
        at a time)."""
        if isinstance(d, TypeDecl):
            self.register_type(d)
        elif isinstance(d, RecordDecl):
            self.register_record(d)
        elif isinstance(d, LetDecl):
            if d.ann is not None:
                self.validate_type(d.ann)
            inferred = self.infer(d.value, self.env)
            if d.ann is not None:
                subst: dict[str, Ty] = {}
                if not unify(inferred, d.ann, subst):
                    raise TypeError_(
                        f"let {d.name}: declared {d.ann}, inferred {inferred}"
                    )
                self.env[d.name] = d.ann
                # Check predicate (binder now in scope).
                self.check_refinement_pred(d.name, d.ann, self.env)
            else:
                self.env[d.name] = inferred
        elif isinstance(d, FnDecl):
            # For single-decl mode (REPL): do both passes inline.
            self.register_fn_signature(d)
            self.check_fn_body(d)
        else:
            raise TypeError_(f"unknown decl {type(d).__name__}")

    def register_type(self, d: TypeDecl) -> None:
        if d.name in self.adt_registry or d.name in self.record_registry:
            raise TypeError_(f"type {d.name!r} declared twice")
        self.adt_registry[d.name] = (d.params, d.variants)
        # Each variant becomes either a value (zero-arg) or a function (n-arg)
        # in the term-level env. Param names appear inside field types as
        # TyVar(name); instantiate_fresh refreshes them at each use site.
        result_ty = TyADT(d.name, tuple(TyVar(p) for p in d.params))
        for v in d.variants:
            if v.name in self.ctor_registry:
                raise TypeError_(f"constructor {v.name!r} declared twice")
            self.ctor_registry[v.name] = (d.name, v.fields, d.params)
            if not v.fields:
                self.env[v.name] = result_ty
            else:
                self.env[v.name] = TyFn(tuple(v.fields), result_ty)

    def register_record(self, d: RecordDecl) -> None:
        if d.name in self.adt_registry or d.name in self.record_registry:
            raise TypeError_(f"type {d.name!r} declared twice")
        self.record_registry[d.name] = (d.params, d.fields)
        # Validate field types against the type-param scope. Field-type
        # validation deferred until all top-level types are registered
        # (which is fine — register_record is called in pass 1).

    def validate_type(self, t: Ty) -> None:
        """Check that any TyADT references a registered type with matching arity."""
        if isinstance(t, TyADT):
            if t.name in self.adt_registry:
                params, _ = self.adt_registry[t.name]
            elif t.name in self.record_registry:
                params, _ = self.record_registry[t.name]
            else:
                raise TypeError_(f"unknown type {t.name!r}")
            if len(t.args) != len(params):
                raise TypeError_(
                    f"type {t.name} expects {len(params)} arg(s), got {len(t.args)}"
                )
            for a in t.args:
                self.validate_type(a)
        elif isinstance(t, TyList):
            self.validate_type(t.elem)
        elif isinstance(t, TyFn):
            for p in t.params: self.validate_type(p)
            self.validate_type(t.ret)
        elif isinstance(t, TyTuple):
            for it in t.items: self.validate_type(it)
        elif isinstance(t, TyRefine):
            self.validate_type(t.base)
            # The predicate itself is type-checked separately (after the
            # binder name is in scope) so it sees the right env.

    def infer(self, e: Node, env: dict[str, Ty]) -> Ty:
        if isinstance(e, IntLit):    return TyInt()
        if isinstance(e, StringLit): return TyString()
        if isinstance(e, BoolLit):   return TyBool()
        if isinstance(e, Ident):
            if e.name not in env:
                hint = (" (names starting with an uppercase letter are treated as "
                        "constructors; variables and parameters must be lowercase)"
                        if e.name[:1].isupper() else "")
                raise TypeError_(f"unbound identifier {e.name!r}{hint}")
            # Polymorphic identifiers (builtins, constructors, generic fns)
            # get fresh TyVars AND fresh effect-row vars at each use so
            # multiple uses don't share variables.
            return instantiate_fresh(env[e.name], self.current_rigid_eff())
        if isinstance(e, ListLit):
            if not e.items:
                return TyList(fresh_tv())  # element type from context
            ts = [self.infer(it, env) for it in e.items]
            t0 = ts[0]
            subst: dict[str, Ty] = {}
            rigid_eff = self.current_rigid_eff()
            for t in ts[1:]:
                if (not unify(t0, t, subst, self.eff_subst, rigid_eff)
                    and not unify(t, t0, subst, self.eff_subst, rigid_eff)):
                    raise TypeError_(f"list elements differ: {t0} vs {t}")
            return TyList(resolve(t0, subst, self.eff_subst))
        if isinstance(e, TupleLit):
            return TyTuple(tuple(self.infer(it, env) for it in e.items))
        if isinstance(e, RecordLit):
            if e.name not in self.record_registry:
                if e.name in self.adt_registry:
                    raise TypeError_(
                        f"{e.name!r} is a sum type — use {e.name}(...) for "
                        f"constructor call, not {{...}} for record literal"
                    )
                raise TypeError_(f"unknown record type {e.name!r}")
            type_params, decl_fields = self.record_registry[e.name]
            decl_field_names = [n for n, _ in decl_fields]
            given_names = [n for n, _ in e.fields]
            # Field set must match exactly (no extras, no missing).
            missing = set(decl_field_names) - set(given_names)
            extra   = set(given_names) - set(decl_field_names)
            if missing:
                raise TypeError_(
                    f"record {e.name} missing field(s): {sorted(missing)}"
                )
            if extra:
                raise TypeError_(
                    f"record {e.name} has no field(s): {sorted(extra)}"
                )
            # Fresh type-param vars; unify each provided field value's type
            # against the declared field type (after substitution).
            mapping = {p: fresh_tv() for p in type_params}
            given_lookup = {n: v for n, v in e.fields}
            subst: dict[str, Ty] = {}
            rigid_eff = self.current_rigid_eff()
            for fname, fty in decl_fields:
                actual_t = self.infer(given_lookup[fname], env)
                want_t   = instantiate(fty, mapping)
                if not unify(want_t, actual_t, subst, self.eff_subst, rigid_eff):
                    raise TypeError_(
                        f"record {e.name} field {fname!r}: "
                        f"expected {resolve(want_t, subst, self.eff_subst)}, got {actual_t}"
                    )
            resolved_args = tuple(
                resolve(mapping[p], subst, self.eff_subst) for p in type_params
            )
            return TyADT(e.name, resolved_args)
        if isinstance(e, FieldAccess):
            rec_ty = self.infer(e.record, env)
            rec_ty = base_of(resolve(rec_ty, {}, self.eff_subst))
            if not isinstance(rec_ty, TyADT):
                raise TypeError_(f"field access on non-record value of type {rec_ty}")
            if rec_ty.name not in self.record_registry:
                raise TypeError_(
                    f"field access on {rec_ty.name}: not a record type "
                    f"(sum types use match for projection)"
                )
            type_params, decl_fields = self.record_registry[rec_ty.name]
            for fname, fty in decl_fields:
                if fname == e.field:
                    mapping = dict(zip(type_params, rec_ty.args))
                    return instantiate(fty, mapping)
            raise TypeError_(
                f"record {rec_ty.name} has no field {e.field!r} "
                f"(known: {[n for n, _ in decl_fields]})"
            )
        if isinstance(e, BinOp):
            return self.check_binop(e, env)
        if isinstance(e, UnaryNot):
            # v4.54: !expr requires Bool, produces Bool.
            inner_t = self.infer(e.expr, env)
            if not equal_ty(inner_t, TyBool()):
                raise TypeError_(f"!: expected Bool, got {inner_t}")
            return TyBool()
        if isinstance(e, Call):
            return self.check_call(e, env)
        if isinstance(e, If):
            ct = self.infer(e.cond, env)
            if not equal_ty(ct, TyBool()):
                raise TypeError_(f"if condition must be Bool, got {ct}")
            tt = self.infer(e.then_b, env)
            ft = self.infer(e.else_b, env)
            subst = {}
            if not (unify(tt, ft, subst) or unify(ft, tt, subst)):
                raise TypeError_(f"if branches differ: {tt} vs {ft}")
            return resolve(tt, subst)
        if isinstance(e, LetIn):
            vt = self.infer(e.value, env)
            ann = self.rigidify(e.ann) if e.ann is not None else None
            if ann is not None:
                subst = {}
                if not unify(vt, ann, subst):
                    raise TypeError_(f"let-in {e.name}: declared {ann}, inferred {vt}")
            new_env = {**env, e.name: ann or vt}
            if ann is not None:
                self.check_refinement_pred(e.name, ann, new_env)
            # v4.67: enforce linearity — a `let lin` binding must be used
            # exactly once along every path in the body.
            if getattr(e, "linear", False):
                n = linear_uses(e.body, e.name)
                if n == 0:
                    raise TypeError_(
                        f"linear variable {e.name!r} is never used — a linear "
                        f"resource must be consumed exactly once (no dropping)")
                if n > 1:
                    raise TypeError_(
                        f"linear variable {e.name!r} used {n} times — a linear "
                        f"resource must be consumed exactly once (no cloning)")
            return self.infer(e.body, new_env)
        if isinstance(e, Lambda):
            new_env = {**env}
            rigid_param_types: list[tuple[str, Ty]] = []
            for p, t in e.params:
                rt = self.rigidify(t)
                new_env[p] = rt
                rigid_param_types.append((p, rt))
            # The lambda's body effects become the lambda's effects.
            # Constructing the lambda doesn't cause them (calling it will).
            saved = self.current_effects
            self.current_effects = PURE
            try:
                body_t = self.infer(e.body, new_env)
            finally:
                lambda_effects = resolve_effects(self.current_effects, self.eff_subst)
                self.current_effects = saved
            return TyFn(
                tuple(t for _, t in rigid_param_types),
                body_t,
                lambda_effects,
            )
        if isinstance(e, Match):
            return self.check_match(e, env)
        raise TypeError_(f"cannot infer {type(e).__name__}")

    def check_binop(self, e: BinOp, env: dict[str, Ty]) -> Ty:
        lt = self.infer(e.lhs, env)
        rt = self.infer(e.rhs, env)
        if e.op in ("+", "-", "*", "/", "%"):
            if not (equal_ty(lt, TyInt()) and equal_ty(rt, TyInt())):
                raise TypeError_(f"{e.op}: expected Int, Int — got {lt}, {rt}")
            return TyInt()
        if e.op == "++":
            if equal_ty(lt, TyString()) and equal_ty(rt, TyString()):
                return TyString()
            if isinstance(lt, TyList) and equal_ty(lt, rt):
                return lt
            raise TypeError_(f"++: incompatible operands {lt}, {rt}")
        if e.op in ("<", ">", "<=", ">="):
            if not (equal_ty(lt, TyInt()) and equal_ty(rt, TyInt())):
                raise TypeError_(f"{e.op}: expected Int, Int — got {lt}, {rt}")
            return TyBool()
        if e.op in ("==", "!="):
            if not equal_ty(lt, rt):
                raise TypeError_(f"{e.op}: operands differ {lt} vs {rt}")
            return TyBool()
        if e.op in ("&&", "||"):
            # v4.51: both sides must be Bool; result is Bool. The
            # evaluator short-circuits, but the type system doesn't
            # care about evaluation order — it just enforces shape.
            if not (equal_ty(lt, TyBool()) and equal_ty(rt, TyBool())):
                raise TypeError_(
                    f"{e.op}: expected Bool, Bool — got {lt}, {rt}"
                )
            return TyBool()
        raise TypeError_(f"unknown op {e.op}")

    def check_call(self, e: Call, env: dict[str, Ty]) -> Ty:
        ft = self.infer(e.fn, env)
        if not isinstance(ft, TyFn):
            raise TypeError_(f"not a function: {ft}")
        if len(ft.params) != len(e.args):
            raise TypeError_(
                f"arity mismatch: expected {len(ft.params)}, got {len(e.args)}"
            )
        subst: dict[str, Ty] = {}
        rigid_eff = self.current_rigid_eff()
        # Static refinement discharge: for each refinement-typed param, try to
        # prove the predicate at compile time given a constant-foldable arg.
        # Records the set of arg indices that were statically discharged so
        # the evaluator can skip the runtime check.
        discharged: set[int] = set()
        # Try to recover param names from the AST if e.fn is a known Ident
        # pointing at a fn decl. Otherwise use positional default names.
        param_names = self._recover_param_names(e.fn, len(ft.params))
        for idx, (formal, actual_expr) in enumerate(zip(ft.params, e.args)):
            actual = self.infer(actual_expr, env)
            if not unify(formal, actual, subst, self.eff_subst, rigid_eff):
                expected = resolve(formal, subst, self.eff_subst)
                raise TypeError_(f"arg type mismatch: expected {expected}, got {actual}")
            # Static discharge attempt — only if the (resolved) formal has refinements.
            resolved_formal = resolve(formal, subst, self.eff_subst)
            if isinstance(resolved_formal, TyRefine):
                pname = param_names[idx] if idx < len(param_names) else f"_arg{idx}"
                status, detail = try_static_discharge(
                    resolved_formal, actual_expr, pname, actual_ty=actual,
                )
                if status == "fail":
                    raise TypeError_(
                        f"refinement violated at compile time: {detail}"
                    )
                if status == "ok":
                    discharged.add(idx)
        # Attach to the Call node so eval_expr can skip runtime checks
        # for these positions.
        if discharged:
            e.discharged_args = discharged
        call_effects = resolve_effects(ft.effects, self.eff_subst)
        self.current_effects = extend_effects(self.current_effects, call_effects)
        return resolve(ft.ret, subst, self.eff_subst)

    def _recover_param_names(self, fn_expr: Node, arity: int) -> list[str]:
        """Best-effort: if the call is a direct ident referencing a fn decl,
        return that fn's parameter names. Otherwise empty (fallback names used)."""
        if isinstance(fn_expr, Ident):
            decl = self.fn_decls.get(fn_expr.name)
            if decl is not None and len(decl.params) == arity:
                return [p[0] for p in decl.params]
        return []

    def check_match(self, e: Match, env: dict[str, Ty]) -> Ty:
        st = self.infer(e.scrutinee, env)
        # Pattern bindings may refine the scrutinee type (e.g. None binds the
        # type variable in Option<T>); use a per-match substitution.
        match_subst: dict[str, Ty] = {}
        arm_types: list[Ty] = []
        for pat, body in e.arms:
            bindings = self.pattern_bindings(pat, resolve(st, match_subst), match_subst)
            resolved_bindings = {k: resolve(v, match_subst) for k, v in bindings.items()}
            arm_types.append(self.infer(body, {**env, **resolved_bindings}))
        # All arms must agree on result type.
        t0 = arm_types[0]
        result_subst: dict[str, Ty] = {}
        for t in arm_types[1:]:
            if not (unify(t0, t, result_subst) or unify(t, t0, result_subst)):
                raise TypeError_(f"match arms differ: {t0} vs {t}")
        self.check_exhaustive([p for p, _ in e.arms], resolve(st, match_subst))
        return resolve(t0, result_subst)

    def pattern_bindings(
        self, p: Pattern, scrut_ty: Ty, subst: dict[str, Ty]
    ) -> dict[str, Ty]:
        if p.kind == "wild": return {}
        if p.kind == "ident": return {p.value: scrut_ty}
        if p.kind == "int":
            if not equal_ty(scrut_ty, TyInt()):
                raise TypeError_(f"int pattern against {scrut_ty}")
            return {}
        if p.kind == "string":
            if not equal_ty(scrut_ty, TyString()):
                raise TypeError_(f"string pattern against {scrut_ty}")
            return {}
        if p.kind == "bool":
            if not equal_ty(scrut_ty, TyBool()):
                raise TypeError_(f"bool pattern against {scrut_ty}")
            return {}
        if p.kind == "nil":
            if not isinstance(scrut_ty, TyList):
                raise TypeError_(f"[] pattern against {scrut_ty}")
            return {}
        if p.kind == "cons":
            if not isinstance(scrut_ty, TyList):
                raise TypeError_(f"cons pattern against {scrut_ty}")
            head_b = self.pattern_bindings(p.head, scrut_ty.elem, subst)
            tail_b = self.pattern_bindings(p.tail, scrut_ty, subst)
            return {**head_b, **tail_b}
        if p.kind == "tuple":
            scrut_b = base_of(scrut_ty)
            if not isinstance(scrut_b, TyTuple):
                raise TypeError_(
                    f"tuple pattern against {scrut_ty} — to destructure an ADT "
                    f"like Pair, use a constructor pattern, e.g. Pair(a, b), not a "
                    f"tuple pattern (a, b)")
            args = p.args or []
            if len(args) != len(scrut_b.items):
                raise TypeError_(
                    f"tuple pattern arity mismatch: pattern has {len(args)}, "
                    f"scrutinee has {len(scrut_b.items)}"
                )
            bindings: dict[str, Ty] = {}
            for sub_p, fld_ty in zip(args, scrut_b.items):
                bindings.update(self.pattern_bindings(sub_p, fld_ty, subst))
            return bindings
        if p.kind == "ctor":
            if p.value not in self.ctor_registry:
                raise TypeError_(f"unknown constructor {p.value!r}")
            adt_name, field_tys, param_names = self.ctor_registry[p.value]
            if not isinstance(scrut_ty, TyADT) or scrut_ty.name != adt_name:
                raise TypeError_(
                    f"constructor {p.value} is from {adt_name}, "
                    f"but scrutinee is {scrut_ty}"
                )
            args = p.args or []
            if len(args) != len(field_tys):
                raise TypeError_(
                    f"{p.value} expects {len(field_tys)} field(s), got {len(args)}"
                )
            # Bind type params to scrut args so field types specialise.
            mapping = dict(zip(param_names, scrut_ty.args))
            bindings: dict[str, Ty] = {}
            for sub_p, fld_ty in zip(args, field_tys):
                concrete_fld = substitute(fld_ty, mapping)
                bindings.update(self.pattern_bindings(sub_p, concrete_fld, subst))
            return bindings
        if p.kind == "record":
            if p.value not in self.record_registry:
                raise TypeError_(
                    f"record pattern uses {p.value!r} which isn't a record type"
                )
            if not isinstance(scrut_ty, TyADT) or scrut_ty.name != p.value:
                raise TypeError_(
                    f"record pattern {p.value} {{...}} but scrutinee is {scrut_ty}"
                )
            type_params, decl_fields = self.record_registry[p.value]
            decl_lookup = {n: t for n, t in decl_fields}
            mapping = dict(zip(type_params, scrut_ty.args))
            bindings = {}
            for fname in (p.args or []):
                if fname not in decl_lookup:
                    raise TypeError_(
                        f"record {p.value} has no field {fname!r}"
                    )
                bindings[fname] = instantiate(decl_lookup[fname], mapping)
            return bindings
        raise TypeError_(f"bad pattern {p}")

    def check_exhaustive(self, pats: list[Pattern], scrut_ty: Ty) -> None:
        # A wildcard or bare identifier alone is exhaustive.
        for p in pats:
            if p.kind in ("wild", "ident"):
                return
        scrut_ty = base_of(resolve(scrut_ty, {}))
        if isinstance(scrut_ty, TyTuple):
            # A tuple pattern destructures; one arm with a tuple pattern is
            # always exhaustive over the tuple type.
            for p in pats:
                if p.kind == "tuple":
                    return
            raise TypeError_(
                "non-exhaustive match on tuple: need a tuple pattern or wildcard"
            )
        if isinstance(scrut_ty, TyBool):
            seen = {p.value for p in pats if p.kind == "bool"}
            if seen >= {True, False}: return
            missing = {True, False} - seen
            raise TypeError_(f"non-exhaustive match: missing {missing}")
        if isinstance(scrut_ty, TyList):
            has_nil = any(p.kind == "nil" for p in pats)
            has_cons = any(p.kind == "cons" for p in pats)
            if has_nil and has_cons: return
            raise TypeError_(
                "non-exhaustive match on list: need both [] and [h, ...t]"
            )
        if isinstance(scrut_ty, TyADT):
            # Record destructure is exhaustive with one record pattern.
            if scrut_ty.name in self.record_registry:
                for p in pats:
                    if p.kind == "record":
                        return
                raise TypeError_(
                    f"non-exhaustive match on record {scrut_ty.name}: "
                    f"need a record pattern or wildcard"
                )
            _, variants = self.adt_registry[scrut_ty.name]
            seen = {p.value for p in pats if p.kind == "ctor"}
            all_ctors = {v.name for v in variants}
            if seen >= all_ctors: return
            missing = all_ctors - seen
            raise TypeError_(
                f"non-exhaustive match on {scrut_ty.name}: missing {sorted(missing)}"
            )
        if isinstance(scrut_ty, (TyInt, TyString)):
            raise TypeError_(
                f"non-exhaustive match on {scrut_ty}: needs a wildcard or identifier arm"
            )


# =============================================================================
# Values + Interpreter
# =============================================================================

class Value:
    __slots__ = ()

@dataclass(**_SLOTS)
class IntV(Value):
    v: int
    def __str__(self): return str(self.v)

@dataclass(**_SLOTS)
class StringV(Value):
    v: str
    def __str__(self): return self.v

@dataclass(**_SLOTS)
class BoolV(Value):
    v: bool
    def __str__(self): return "true" if self.v else "false"

@dataclass(**_SLOTS)
class ListV(Value):
    items: list[Value]
    def __str__(self):
        return "[" + ", ".join(str(x) for x in self.items) + "]"

@dataclass(**_SLOTS)
class TupleV(Value):
    items: list[Value]
    def __str__(self):
        return "(" + ", ".join(str(x) for x in self.items) + ")"

@dataclass(**_SLOTS)
class RecordV(Value):
    name: str
    fields: dict[str, Value]
    def __str__(self):
        body = ", ".join(f"{k}: {v}" for k, v in self.fields.items())
        return f"{self.name} {{ {body} }}"

@dataclass(**_SLOTS)
class FnV(Value):
    """A user-defined function value. params carries (name, declared_type)
    so the interpreter can run refinement checks at call boundaries.
    ret is the declared return type, carried so refinements on returns
    can be checked at every exit point (v1.3)."""
    params: list[tuple[str, Ty]]
    body: Node
    env: dict[str, Value]
    ret: Ty | None = None
    def __str__(self):
        names = ", ".join(p for p, _ in self.params)
        return f"<fn({names})>"

@dataclass(**_SLOTS)
class BuiltinV(Value):
    name: str
    fn: Callable[..., Value]
    def __str__(self): return f"<builtin {self.name}>"

@dataclass(**_SLOTS)
class ADTValue(Value):
    """A constructed value of an algebraic data type, e.g. Some(42), Ok("ok")."""
    ctor: str
    args: list[Value]
    def __str__(self):
        if not self.args:
            return self.ctor
        return f"{self.ctor}(" + ", ".join(str(a) for a in self.args) + ")"

@dataclass(**_SLOTS)
class CtorV(Value):
    """A constructor used as a function (Some, Ok). Zero-arg constructors are
    bound directly as ADTValue, not as CtorV."""
    name: str
    arity: int
    # v4.69: field types + binder names, so a refined field is checked
    # when the constructor is applied (see apply_fn's CtorV branch).
    fields: list = field(default_factory=list)
    field_names: list = field(default_factory=list)
    def __str__(self): return f"<ctor {self.name}/{self.arity}>"


def builtin_values() -> dict[str, Value]:
    import random as _random_module
    def b_print(s):
        print(s.v)
        return s
    def b_error(s):
        # Mirror native q_error: stderr + nonzero exit. A loud refusal, not a
        # silent proven-0 — the prove bridge calls this when it cannot lower a
        # construct faithfully (unresolved/over-deep call, parse failure).
        sys.stderr.write("glass error: " + s.v + "\n")
        sys.stderr.flush()
        sys.exit(1)
    def b_random_int(lo, hi):
        # Half-open [lo, hi). Real crypto would use a secure RNG and a
        # different effect label like CryptoRandom — see LANG.md.
        return IntV(_random_module.randrange(lo.v, hi.v))
    def b_len(xs): return IntV(len(xs.items))
    def b_head(xs):
        if not xs.items: return ADTValue("None", [])
        return ADTValue("Some", [xs.items[0]])
    def b_tail(xs):
        if not xs.items: return ADTValue("None", [])
        return ADTValue("Some", [ListV(xs.items[1:])])
    def b_reverse(xs):
        return ListV(list(reversed(xs.items)))
    def b_map(xs, f):
        return ListV([apply_fn(f, [x]) for x in xs.items])
    def b_filter(xs, f):
        return ListV([x for x in xs.items if apply_fn(f, [x]).v])
    def b_fold(xs, init, f):
        acc = init
        for x in xs.items:
            acc = apply_fn(f, [acc, x])
        return acc
    def b_range(a, b):
        return ListV([IntV(i) for i in range(a.v, b.v)])
    def b_string_length(s): return IntV(len(s.v))
    def b_string_to_upper(s):
        # v4.40: ASCII-only upper-case; bytes outside A-Za-z pass
        # through unchanged. Matches Quartz's pure-ASCII helper so
        # host and Quartz produce identical results for any input.
        return StringV("".join(
            chr(c - 32) if 0x61 <= (c := ord(ch)) <= 0x7a else ch
            for ch in s.v
        ))
    def b_string_to_lower(s):
        return StringV("".join(
            chr(c + 32) if 0x41 <= (c := ord(ch)) <= 0x5a else ch
            for ch in s.v
        ))
    def b_char_at(s, i):
        n = len(s.v)
        if i.v < 0:
            raise RuntimeError(f"char_at: negative index ({i.v})")
        if i.v >= n:
            raise RuntimeError(
                f"char_at: index {i.v} out of range for string of "
                f"length {n}"
            )
        return IntV(ord(s.v[i.v]))
    # v4.42: int64 wrap so Python's unbounded ints match C's int64_t.
    # Mask to 64 bits, then if the high bit is set interpret as
    # negative (two's complement). All bitwise builtins funnel through
    # this so djb2 overflow produces the same value the compiled
    # binary does.
    _MASK64 = (1 << 64) - 1
    def _to_int64(n: int) -> int:
        n &= _MASK64
        if n & (1 << 63):
            n -= 1 << 64
        return n
    def b_bit_and(a, b): return IntV(_to_int64(a.v & b.v))
    def b_bit_or(a, b):  return IntV(_to_int64(a.v | b.v))
    def b_bit_xor(a, b): return IntV(_to_int64(a.v ^ b.v))
    def b_bit_not(a):    return IntV(_to_int64(~a.v))
    def b_bit_shl(a, b): return IntV(_to_int64(a.v << b.v))
    # bit_shr is arithmetic right shift on signed int64. Python's >>
    # is already arithmetic on negative ints, so the result for any
    # in-range input matches C without an extra mask.
    def b_bit_shr(a, b): return IntV(a.v >> b.v)
    def b_wrap_int64(n): return IntV(_to_int64(n.v))
    def b_substring(s, start, end):
        # Clamp to string bounds; raise on inverted indices to keep semantics
        # honest. Negative indices are not Python-style — that's a footgun.
        a, b = start.v, end.v
        if a < 0 or b < 0:
            raise RuntimeError(f"substring: negative index ({a}, {b})")
        if a > b:
            raise RuntimeError(f"substring: start > end ({a} > {b})")
        n = len(s.v)
        a = min(a, n); b = min(b, n)
        return StringV(s.v[a:b])
    def b_string_index_of(s, needle):
        # Glass-level Option<Int>. Empty needle returns Some(0) like Python.
        i = s.v.find(needle.v)
        if i < 0:
            return ADTValue(ctor="None", args=[])
        return ADTValue(ctor="Some", args=[IntV(i)])
    def b_read_file(path):
        # !{File} effect. Returns Result<String, String> — Err on any I/O
        # failure, with the OS message. The point is the TYPE: every
        # file read is visible at every call site via !{File}.
        try:
            with open(path.v, "r") as f:
                return ADTValue(ctor="Ok", args=[StringV(f.read())])
        except (OSError, IOError) as e:
            return ADTValue(ctor="Err", args=[StringV(str(e))])
    def b_write_file(path, content):
        # !{File} effect. Returns Result<Int, String> — Ok wraps byte count.
        # v3.13 addition. Pairs with read_file to enable Glass-side build
        # pipelines (write generated C source to disk, then compile it).
        try:
            data = content.v
            with open(path.v, "w") as f:
                n = f.write(data)
            return ADTValue(ctor="Ok", args=[IntV(n if n is not None else len(data))])
        except (OSError, IOError) as e:
            return ADTValue(ctor="Err", args=[StringV(str(e))])
    def b_run_command(cmd, args):
        # !{Process} effect. Invokes the external program `cmd` with
        # arguments `args` (a List<String>). Returns Result with a
        # 3-tuple on success (exit_code, stdout, stderr). v3.13 addition.
        # This is what closes the loop on Stage 5: prism interprets
        # quartz_min, which produces C; write_file persists it;
        # run_command invokes cc, then the resulting binary.
        try:
            argv = [cmd.v]
            # args is a ListV of StringV values.
            for a in args.items:
                if not isinstance(a, StringV):
                    return ADTValue(
                        ctor="Err",
                        args=[StringV(f"run_command: arg list must be List<String>, got {type(a).__name__}")],
                    )
                argv.append(a.v)
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                # 30s ceiling — long enough for cc on small files,
                # short enough to avoid runaway children.
                timeout=30,
            )
            return ADTValue(
                ctor="Ok",
                args=[TupleV([
                    IntV(proc.returncode),
                    StringV(proc.stdout),
                    StringV(proc.stderr),
                ])],
            )
        except FileNotFoundError as e:
            return ADTValue(ctor="Err", args=[StringV(f"command not found: {cmd.v}")])
        except subprocess.TimeoutExpired:
            return ADTValue(ctor="Err", args=[StringV(f"timeout: {cmd.v}")])
        except (OSError, ValueError) as e:
            return ADTValue(ctor="Err", args=[StringV(str(e))])
    def b_itos(n): return StringV(str(n.v))
    def b_model_call(prompt):
        # Mock: a real backend would dispatch to an LLM, classifier, etc.
        # Here we just echo with a tag, so demos run without external state.
        # The point is the TYPE: !{Inference} makes every model call visible.
        return StringV(f"[model]: {prompt.v}")
    # --- Goldilocks field fast path (base-2^16 limb lists; p = 2^64 - 2^32 + 1) ---
    _GOLD_P = (1 << 64) - (1 << 32) + 1
    def _gold_to_int(xs):
        return sum((l.v & 0xFFFF) << (16 * i) for i, l in enumerate(xs.items))
    def _gold_to_limbs(r):
        r %= _GOLD_P
        out = []
        while r > 0:
            out.append(IntV(r & 0xFFFF))
            r >>= 16
        return ListV(out)
    def b_gold_mul(a, b): return _gold_to_limbs(_gold_to_int(a) * _gold_to_int(b))
    def b_gold_add(a, b): return _gold_to_limbs(_gold_to_int(a) + _gold_to_int(b))
    def b_gold_sub(a, b): return _gold_to_limbs(_gold_to_int(a) - _gold_to_int(b))
    return {
        "print":            BuiltinV("print", b_print),
        "error":            BuiltinV("error", b_error),
        "random_int":       BuiltinV("random_int", b_random_int),
        "model_call":       BuiltinV("model_call", b_model_call),
        "len":              BuiltinV("len", b_len),
        "head":             BuiltinV("head", b_head),
        "tail":             BuiltinV("tail", b_tail),
        "reverse":          BuiltinV("reverse", b_reverse),
        "map":              BuiltinV("map", b_map),
        "filter":           BuiltinV("filter", b_filter),
        "fold":             BuiltinV("fold", b_fold),
        "range":            BuiltinV("range", b_range),
        "gold_mul":         BuiltinV("gold_mul", b_gold_mul),
        "gold_add":         BuiltinV("gold_add", b_gold_add),
        "gold_sub":         BuiltinV("gold_sub", b_gold_sub),
        "string_length":    BuiltinV("string_length", b_string_length),
        "string_to_upper":  BuiltinV("string_to_upper", b_string_to_upper),
        "string_to_lower":  BuiltinV("string_to_lower", b_string_to_lower),
        "char_at":          BuiltinV("char_at", b_char_at),
        "bit_and":          BuiltinV("bit_and", b_bit_and),
        "bit_or":           BuiltinV("bit_or",  b_bit_or),
        "bit_xor":          BuiltinV("bit_xor", b_bit_xor),
        "bit_not":          BuiltinV("bit_not", b_bit_not),
        "bit_shl":          BuiltinV("bit_shl", b_bit_shl),
        "bit_shr":          BuiltinV("bit_shr", b_bit_shr),
        "wrap_int64":       BuiltinV("wrap_int64", b_wrap_int64),
        "substring":        BuiltinV("substring", b_substring),
        "string_index_of":  BuiltinV("string_index_of", b_string_index_of),
        "read_file":        BuiltinV("read_file", b_read_file),
        "write_file":       BuiltinV("write_file", b_write_file),
        "run_command":      BuiltinV("run_command", b_run_command),
        "int_to_string":    BuiltinV("int_to_string", b_itos),
    }


def apply_fn(
    f: Value,
    args: list[Value],
    skip_refinement_indices: set[int] | None = None,
) -> Value:
    """v4.28: trampoline-based tail-call elimination.

    The OUTER `while True` loop reapplies functions. After setting up the
    env for the current `f`, the INNER loop peels through tail-position
    `If` / `LetIn` / `Match` arms looking for a tail `Call`. If the tail
    is a Call to another FnV (and the current fn has no return-type
    refinement, since dropping its check would be unsound), we trampoline:
    replace `f`/`args`/`skip` and continue the outer loop with no Python
    stack growth. Result: arbitrarily-deep tail-recursive programs run in
    O(1) Python frames.

    Non-tail forms (BinOp, Ident, list, etc.) and Calls under a
    return-type refinement still go through `eval_expr` as before, so the
    refactor is semantically conservative — every existing test continues
    to pass.
    """
    # v1.7 perf: dispatch by type identity, not isinstance. FnV is by far
    # the hottest case so it goes first; BuiltinV and CtorV follow.
    while True:
        t = type(f)
        if t is BuiltinV:
            return f.fn(*args)
        if t is CtorV:
            if len(args) != f.arity:
                raise RuntimeError(
                    f"ctor {f.name} expects {f.arity} args, got {len(args)}"
                )
            # v4.69: enforce refinements on refined fields at construction.
            # Each field is bound by name as we go, so a later field's
            # refinement may reference EARLIER fields (cross-field, like
            # the cross-parameter refinements of v4.56) — e.g.
            # `Range(lo: Int, hi: Int where (hi > lo))`.
            field_env: dict = {}
            for i, fld_ty in enumerate(f.fields):
                binder = (f.field_names[i]
                          if i < len(f.field_names) and f.field_names[i]
                          else f"_field{i}")
                if type(fld_ty) is TyRefine:
                    check_refinement_runtime(
                        binder, fld_ty, args[i], {**field_env, binder: args[i]})
                field_env[binder] = args[i]
            return ADTValue(ctor=f.name, args=list(args))
        if t is not FnV:
            raise RuntimeError(f"not callable: {f}")
        if len(args) != len(f.params):
            raise RuntimeError(f"arity mismatch calling {f}")
        new_env = f.env.copy()
        # v4.29: inline `type(t_p) is TyRefine` at the call site so we
        # skip the function-call overhead when the param isn't refined.
        # Most params aren't refined; for prism running prism (millions
        # of fn applications), saving one Python call per param is real.
        if skip_refinement_indices is None:
            for (p, t_p), a in zip(f.params, args):
                new_env[p] = a
                if type(t_p) is TyRefine:
                    check_refinement_runtime(p, t_p, a, new_env)
        else:
            for idx, ((p, t_p), a) in enumerate(zip(f.params, args)):
                new_env[p] = a
                if type(t_p) is TyRefine and idx not in skip_refinement_indices:
                    check_refinement_runtime(p, t_p, a, new_env)
        f_ret = f.ret
        has_ret_ref = f_ret is not None and type(f_ret) is TyRefine
        body = f.body
        env = new_env
        # Inner loop: peel tail-position constructs. Stops at either a
        # trampolinable Call (sets new f/args and breaks to outer) or any
        # non-tail-recursive form (eval normally and return).
        tail_recursed = False
        while True:
            bt = type(body)
            if bt is If:
                cond = body.cond
                c = eval_binop(cond, env) if type(cond) is BinOp else eval_expr(cond, env)
                body = body.then_b if c.v else body.else_b
                continue
            if bt is LetIn:
                v = eval_expr(body.value, env)
                env = {**env, body.name: v}
                # v4.29: inline TyRefine check — skip the call when the
                # annotation has no refinement to enforce.
                ann = body.ann
                if ann is not None and type(ann) is TyRefine:
                    check_refinement_runtime(body.name, ann, v, env)
                body = body.body
                continue
            if bt is Match:
                scrut = eval_expr(body.scrutinee, env)
                matched = False
                for pat, arm_body in body.arms:
                    ok, bindings = pat_match(pat, scrut)
                    if ok:
                        env = {**env, **bindings}
                        body = arm_body
                        matched = True
                        break
                if not matched:
                    raise RuntimeError("non-exhaustive match")
                continue
            if bt is Call and not has_ret_ref:
                bfn = body.fn
                callee = env[bfn.name] if type(bfn) is Ident else eval_expr(bfn, env)
                call_args = []
                for a in body.args:
                    ta = type(a)
                    if   ta is Ident:  call_args.append(env[a.name])
                    elif ta is IntLit: call_args.append(IntV(a.value))
                    elif ta is BinOp:  call_args.append(eval_binop(a, env))
                    else:              call_args.append(eval_expr(a, env))
                skip = getattr(body, "discharged_args", None)
                if type(callee) is FnV:
                    # Trampoline: outer loop will set up the new fn's env.
                    f = callee
                    args = call_args
                    skip_refinement_indices = skip
                    tail_recursed = True
                    break
                # Non-FnV (builtin/ctor) tail call — apply directly. No
                # need to re-enter the outer loop because builtins and
                # ctors don't have a body to peel.
                return apply_fn(callee, call_args, skip)
            # Non-tail-recursive form (BinOp, Ident, Lambda, list, ...)
            # or a Call under a return-type refinement we can't safely
            # drop. Evaluate normally, then check the return refinement.
            result = eval_expr(body, env)
            if has_ret_ref:
                env["result"] = result
                check_refinement_runtime("result", f_ret, result, env)
            return result
        # Inner loop broke with tail_recursed = True → restart outer.
        if tail_recursed:
            continue


def _ast_equal(a: Node, b: Node) -> bool:
    """Structural equality of two predicate ASTs. Recognises the subset of
    expressions that try_const_eval handles: literals, Ident, BinOp, If.
    Anything else falls through to False, which is conservative (no
    discharge) rather than unsound."""
    if type(a) is not type(b):
        return False
    if isinstance(a, IntLit):    return a.value == b.value
    if isinstance(a, BoolLit):   return a.value == b.value
    if isinstance(a, StringLit): return a.value == b.value
    if isinstance(a, Ident):     return a.name == b.name
    if isinstance(a, BinOp):
        return a.op == b.op and _ast_equal(a.lhs, b.lhs) and _ast_equal(a.rhs, b.rhs)
    if isinstance(a, UnaryNot):
        return _ast_equal(a.expr, b.expr)
    if isinstance(a, If):
        return (_ast_equal(a.cond, b.cond) and
                _ast_equal(a.then_b, b.then_b) and
                _ast_equal(a.else_b, b.else_b))
    return False


def _alpha_rename(e: Node, old: str, new: str) -> Node:
    """Return a copy of e with every Ident(old) renamed to Ident(new)."""
    if isinstance(e, Ident):
        return Ident(new) if e.name == old else e
    if isinstance(e, BinOp):
        return BinOp(op=e.op,
                     lhs=_alpha_rename(e.lhs, old, new),
                     rhs=_alpha_rename(e.rhs, old, new))
    if isinstance(e, UnaryNot):
        return UnaryNot(expr=_alpha_rename(e.expr, old, new))
    if isinstance(e, If):
        return If(cond=_alpha_rename(e.cond, old, new),
                  then_b=_alpha_rename(e.then_b, old, new),
                  else_b=_alpha_rename(e.else_b, old, new))
    return e  # IntLit / BoolLit / StringLit / anything else — no binders inside


def predicate_alpha_equiv(p1: Node, n1: str, p2: Node, n2: str) -> bool:
    """True iff p1 (with binder n1) and p2 (with binder n2) are structurally
    identical after renaming both binders to the same fresh name."""
    fresh = "__alpha_fresh__"
    return _ast_equal(_alpha_rename(p1, n1, fresh), _alpha_rename(p2, n2, fresh))


def _extract_comparison(pred: Node, binder: str) -> tuple[str, int] | None:
    """If pred is a comparison of `binder` against an integer constant,
    return (op, k) where the comparison is `binder op k` (variable on left).
    Returns None if pred isn't a recognised simple comparison.

    Recognises both `binder OP const` and `const OP binder` (flipping the
    operator when the binder is on the right)."""
    if not isinstance(pred, BinOp):
        return None
    if pred.op not in ("<", ">", "<=", ">=", "==", "!="):
        return None
    # Try lhs = binder, rhs = const-foldable
    if isinstance(pred.lhs, Ident) and pred.lhs.name == binder:
        rhs_val = try_const_eval(pred.rhs)
        if isinstance(rhs_val, IntV):
            return (pred.op, rhs_val.v)
    # Try lhs = const, rhs = binder (flip operator)
    if isinstance(pred.rhs, Ident) and pred.rhs.name == binder:
        lhs_val = try_const_eval(pred.lhs)
        if isinstance(lhs_val, IntV):
            flip = {"<": ">", ">": "<", "<=": ">=", ">=": "<=",
                    "==": "==", "!=": "!="}
            return (flip[pred.op], lhs_val.v)
    return None


def _comparison_implies(op1: str, k1: int, op2: str, k2: int) -> bool:
    """Does (n op1 k1) imply (n op2 k2)?

    Both refer to the same variable n; constants are on the right. Uses
    set-inclusion semantics over integer arithmetic:

      > k      = [k+1, ∞)
      >= k     = [k,   ∞)
      < k      = (-∞,  k-1]
      <= k     = (-∞,  k  ]
      == k     = {k}
      != k     = Z \\ {k}

    Returns True iff the first set is a subset of the second."""

    def satisfies(op: str, k: int, v: int) -> bool:
        if op == "<":  return v < k
        if op == ">":  return v > k
        if op == "<=": return v <= k
        if op == ">=": return v >= k
        if op == "==": return v == k
        if op == "!=": return v != k
        return False

    # n == k1: singleton set. Check whether k1 itself satisfies op2/k2.
    if op1 == "==":
        return satisfies(op2, k2, k1)

    # n == k2 would require S1 to be {k2}; only possible if op1 was ==
    # (already handled above).
    if op2 == "==":
        return False

    # n != k1: domain is Z \ {k1}. Almost no useful implications other
    # than the same predicate (which alpha-equiv would have caught).
    if op1 == "!=":
        return op2 == "!=" and k1 == k2

    # Conclusion is "n != k2": S1 must exclude k2.
    if op2 == "!=":
        if op1 == ">":  return k2 <= k1   # (k1, ∞) excludes k2 iff k2 <= k1
        if op1 == ">=": return k2 <  k1
        if op1 == "<":  return k2 >= k1
        if op1 == "<=": return k2 >  k1
        return False

    # Both ops are in {<, >, <=, >=}. Convert to canonical bounds.
    # For >, >= : set has a lower bound only (extends to +∞).
    # For <, <= : set has an upper bound only (extends to -∞).
    if op1 in (">", ">=") and op2 in (">", ">="):
        low1 = k1 + 1 if op1 == ">" else k1
        low2 = k2 + 1 if op2 == ">" else k2
        return low1 >= low2
    if op1 in ("<", "<=") and op2 in ("<", "<="):
        high1 = k1 - 1 if op1 == "<" else k1
        high2 = k2 - 1 if op2 == "<" else k2
        return high1 <= high2
    # Mixed direction (one bounded below, one bounded above): the first
    # set is unbounded in the direction the second set restricts, so the
    # subset relation can't hold (for nonempty integer types).
    return False


def predicate_implies(p1: Node, n1: str, p2: Node, n2: str) -> bool:
    """Does (p1 with binder n1) imply (p2 with binder n2)?

    Currently handles the case where both predicates are simple
    comparisons of their binder against an integer constant. Anything
    more complex (compound predicates, non-integer comparisons, calls)
    falls through to False — the sound conservative default."""
    c1 = _extract_comparison(p1, n1)
    c2 = _extract_comparison(p2, n2)
    if c1 is None or c2 is None:
        return False
    return _comparison_implies(c1[0], c1[1], c2[0], c2[1])


def try_const_eval(e: Node, env: dict[str, Value] | None = None) -> Value | None:
    """Best-effort constant evaluator. Returns a Value if `e` is purely
    constant (or constant given the optional env), None otherwise.

    Supports integer literals, bool literals, string literals, arithmetic
    BinOp on integers, comparison BinOp returning bool, and If with a
    constant condition. Identifiers resolve only if their binding is in
    env (used for chains like let-in over constants).

    This is intentionally simple — it covers the cases where the user
    writes a literal or a small constant expression at a call site, which
    is the common pattern that motivates static refinement discharge.
    Anything else returns None (fall back to runtime check)."""
    env = env or {}
    if isinstance(e, IntLit):    return IntV(e.value)
    if isinstance(e, BoolLit):   return BoolV(e.value)
    if isinstance(e, StringLit): return StringV(e.value)
    if isinstance(e, Ident):
        return env.get(e.name)
    if isinstance(e, BinOp):
        l = try_const_eval(e.lhs, env)
        r = try_const_eval(e.rhs, env)
        if l is None or r is None:
            return None
        op = e.op
        if isinstance(l, IntV) and isinstance(r, IntV):
            if op == "+":  return IntV(l.v + r.v)
            if op == "-":  return IntV(l.v - r.v)
            if op == "*":  return IntV(l.v * r.v)
            if op == "/" and r.v != 0:  return IntV(l.v // r.v)
            if op == "%" and r.v != 0:  return IntV(l.v % r.v)
            if op == "<":  return BoolV(l.v <  r.v)
            if op == ">":  return BoolV(l.v >  r.v)
            if op == "<=": return BoolV(l.v <= r.v)
            if op == ">=": return BoolV(l.v >= r.v)
            if op == "==": return BoolV(l.v == r.v)
            if op == "!=": return BoolV(l.v != r.v)
        if isinstance(l, BoolV) and isinstance(r, BoolV):
            if op == "==": return BoolV(l.v == r.v)
            if op == "!=": return BoolV(l.v != r.v)
        if isinstance(l, StringV) and isinstance(r, StringV):
            if op == "==": return BoolV(l.v == r.v)
            if op == "!=": return BoolV(l.v != r.v)
            if op == "++": return StringV(l.v + r.v)
        return None
    if isinstance(e, UnaryNot):
        # v4.54: const-fold logical NOT for static discharge.
        v = try_const_eval(e.expr, env)
        if isinstance(v, BoolV):
            return BoolV(not v.v)
        return None
    if isinstance(e, If):
        c = try_const_eval(e.cond, env)
        if isinstance(c, BoolV):
            return try_const_eval(e.then_b if c.v else e.else_b, env)
        return None
    return None


# Static discharge tally — populated by try_static_discharge so we can
# print a summary at the end of a run (or use it for diagnostics).
_discharge_stats: dict[str, int] = {"ok": 0, "fail": 0, "unknown": 0}


def try_static_discharge(
    ty: Ty,
    actual_expr: Node,
    bind_name: str,
    actual_ty: Ty | None = None,
) -> tuple[str, str]:
    """Attempt to discharge a refinement at compile time.

    Returns one of:
        ('ok',      detail)  — refinement provably satisfied; skip runtime check.
        ('fail',    detail)  — refinement provably violated; raise compile error.
        ('unknown', '')      — can't determine statically; runtime check stays.

    Two strategies tried, in order:

    1. CONSTANT-FOLD DISCHARGE. If the actual_expr is constant-foldable to
       a value V, substitute V into the predicate and try to fold it. If
       it folds to True, ok. To False, fail. Otherwise unknown.

    2. SUBSUMPTION DISCHARGE. If the actual_ty (the inferred type of the
       actual expression) itself carries a refinement whose predicate is
       alpha-equivalent to the formal refinement's predicate, ok.
       This is what enables refinement composition through call chains:
       `fn abs(n: Int) : Int where (result >= 0) = ...`
       feeding into
       `fn sqrt_floor(n: Int where (n >= 0)) : Int = ...`
       discharges at compile time because `result >= 0` and `n >= 0` are
       the same predicate up to binder rename.
    """
    # Strategy 1: constant-fold discharge.
    actual_value = try_const_eval(actual_expr)
    if actual_value is not None:
        detail = ""
        chain = ty
        while isinstance(chain, TyRefine):
            pred_value = try_const_eval(chain.pred, {bind_name: actual_value})
            if pred_value is None or not isinstance(pred_value, BoolV):
                # Fall through to strategy 2.
                actual_value = None
                break
            if not pred_value.v:
                _discharge_stats["fail"] += 1
                return ("fail", f"{bind_name} = {actual_value} fails predicate ({pp_expr(chain.pred)})")
            detail = f"{bind_name} = {actual_value} satisfies ({pp_expr(chain.pred)})"
            chain = chain.base
        else:
            # Loop completed without break: all layers discharged.
            _discharge_stats["ok"] += 1
            return ("ok", detail)
    # Strategy 2: subsumption discharge against actual_ty's refinement chain.
    if actual_ty is not None:
        # Collect all (binder, pred) pairs from the actual type's refinement
        # chain. The binder for a return-type refinement is "result" (the
        # convention used by apply_fn). For nested chains we can't recover
        # the binder name in full generality, but in practice every
        # refinement we propagate from a call's return uses "result".
        actual_preds: list[tuple[str, Node]] = []
        at = actual_ty
        while isinstance(at, TyRefine):
            actual_preds.append(("result", at.pred))
            at = at.base
        # For each formal refinement layer, check if any actual predicate
        # subsumes it. Subsumption proven by alpha-equivalence OR by
        # comparison-implication (v1.4). If every formal layer is matched,
        # discharge.
        all_matched = True
        chain = ty
        while isinstance(chain, TyRefine):
            matched = False
            for (an, ap) in actual_preds:
                if predicate_alpha_equiv(chain.pred, bind_name, ap, an):
                    matched = True
                    break
                if predicate_implies(ap, an, chain.pred, bind_name):
                    matched = True
                    break
            if not matched:
                all_matched = False
                break
            chain = chain.base
        if all_matched and isinstance(ty, TyRefine):
            _discharge_stats["ok"] += 1
            return ("ok", f"refinement subsumed via return-type")
    _discharge_stats["unknown"] += 1
    return ("unknown", "")


def check_refinement_runtime(
    bind_name: str,
    ty: Ty,
    value: Value,
    env: dict[str, Value],
) -> None:
    """If ty (or its base chain) is a refinement, evaluate the predicate
    with bind_name -> value in env. Raise on violation.

    v1.7 perf: type(ty) is TyRefine bypasses isinstance, and the most
    common case (non-refined type) returns immediately."""
    while type(ty) is TyRefine:
        # bind_name must already be in env (caller's responsibility).
        result = eval_expr(ty.pred, env)
        if not (type(result) is BoolV and result.v):
            raise RuntimeError(
                f"refinement violated: {bind_name} = {value} fails "
                f"predicate ({pp_expr(ty.pred)})"
            )
        ty = ty.base


def eval_expr(e: Node, env: dict[str, Value]) -> Value:
    # v1.7 perf: dispatch with `type(e) is X` rather than `isinstance`. AST
    # nodes aren't subclassed, so identity comparison is equivalent and
    # ~3x faster than the isinstance call. Branches are ordered by
    # observed frequency on prism.glass: Ident, Call, BinOp, If are the
    # hot path.
    t = type(e)
    if t is Ident:
        if e.name not in env:
            raise RuntimeError(f"unbound at runtime: {e.name}")
        return env[e.name]
    if t is Call:
        fn_node = e.fn
        f = env[fn_node.name] if type(fn_node) is Ident else eval_expr(fn_node, env)
        # Inline the leaf arg cases (Ident / IntLit / BinOp) — same skip-a-call
        # win as in eval_binop, for the very hot fn-application path.
        args = []
        for a in e.args:
            ta = type(a)
            if   ta is Ident:  args.append(env[a.name])
            elif ta is IntLit: args.append(IntV(a.value))
            elif ta is BinOp:  args.append(eval_binop(a, env))
            else:              args.append(eval_expr(a, env))
        # If the type checker statically discharged any refinement at this
        # call site, pass that to apply_fn so the runtime check is skipped.
        skip = getattr(e, "discharged_args", None)
        return apply_fn(f, args, skip_refinement_indices=skip)
    if t is BinOp:
        return eval_binop(e, env)
    if t is UnaryNot:
        # v4.54: evaluate inner, flip the Bool. Typechecker has
        # already ensured inner is Bool so we trust it.
        v = eval_expr(e.expr, env)
        return BoolV(not v.v)
    if t is If:
        cond = e.cond
        c = eval_binop(cond, env) if type(cond) is BinOp else eval_expr(cond, env)
        return eval_expr(e.then_b if c.v else e.else_b, env)
    if t is IntLit:    return IntV(e.value)
    if t is StringLit: return StringV(e.value)
    if t is BoolLit:   return BoolV(e.value)
    if t is LetIn:
        v = eval_expr(e.value, env)
        new_env = {**env, e.name: v}
        # v4.29: same inline TyRefine guard as in apply_fn's trampoline.
        ann = e.ann
        if ann is not None and type(ann) is TyRefine:
            check_refinement_runtime(e.name, ann, v, new_env)
        return eval_expr(e.body, new_env)
    if t is Match:
        scrut = eval_expr(e.scrutinee, env)
        for pat, body in e.arms:
            ok, bindings = pat_match(pat, scrut)
            if ok:
                return eval_expr(body, {**env, **bindings})
        raise RuntimeError("non-exhaustive match")
    if t is Lambda:
        return FnV(params=list(e.params), body=e.body, env=env, ret=e.ret)
    if t is ListLit:
        return ListV([eval_expr(it, env) for it in e.items])
    if t is TupleLit:
        return TupleV([eval_expr(it, env) for it in e.items])
    if t is RecordLit:
        return RecordV(
            name=e.name,
            fields={fname: eval_expr(fval, env) for fname, fval in e.fields},
        )
    if t is FieldAccess:
        rec = eval_expr(e.record, env)
        if not isinstance(rec, RecordV):
            raise RuntimeError(f"field access on non-record value: {rec}")
        if e.field not in rec.fields:
            raise RuntimeError(f"record {rec.name} has no field {e.field!r}")
        return rec.fields[e.field]
    raise RuntimeError(f"cannot eval {t.__name__}")


def eval_binop(e: BinOp, env: dict[str, Value]) -> Value:
    op = e.op
    # v4.51: short-circuit boolean combinators. Evaluate lhs first;
    # if its value already determines the outcome, skip rhs entirely.
    # Glass is pure, so the OBSERVABLE result is the same either way,
    # but short-circuit is the user-expected semantics and avoids
    # wasted work (e.g. `n != 0 && big_value / n > 0`).
    if op == "&&":
        lv = eval_expr(e.lhs, env)
        if not lv.v:
            return BoolV(False)
        return eval_expr(e.rhs, env)
    if op == "||":
        lv = eval_expr(e.lhs, env)
        if lv.v:
            return BoolV(True)
        return eval_expr(e.rhs, env)
    # Inline the leaf operand cases (Ident / IntLit / nested BinOp) to skip an
    # eval_expr dispatch+call each — binop operands are overwhelmingly these in
    # arithmetic-heavy code. Other forms fall back to eval_expr. Semantics are
    # identical (a well-typed program never hits an unbound Ident here).
    lhs = e.lhs; tl = type(lhs)
    if   tl is Ident:  lv = env[lhs.name]
    elif tl is BinOp:  lv = eval_binop(lhs, env)
    elif tl is IntLit: lv = IntV(lhs.value)
    else:              lv = eval_expr(lhs, env)
    rhs = e.rhs; tr = type(rhs)
    if   tr is Ident:  rv = env[rhs.name]
    elif tr is BinOp:  rv = eval_binop(rhs, env)
    elif tr is IntLit: rv = IntV(rhs.value)
    else:              rv = eval_expr(rhs, env)
    if op == "+":  return IntV(lv.v + rv.v)
    if op == "-":  return IntV(lv.v - rv.v)
    if op == "*":  return IntV(lv.v * rv.v)
    if op == "/":  return IntV(lv.v // rv.v)
    # v4.53: modulo. Uses Python's `%` which is floor-modulo (result
    # has sign of divisor); Quartz emits C's `%` which is truncated
    # (result has sign of dividend). The two agree for non-negative
    # operands — the common case — and diverge only when the dividend
    # is negative. Same divergence story as `/` (host uses `//` floor,
    # Quartz uses C `/` truncate). Documented under the v4.43 overflow
    # parity discussion; calling out here for completeness.
    if op == "%":  return IntV(lv.v % rv.v)
    if op == "++":
        if type(lv) is StringV: return StringV(lv.v + rv.v)
        if type(lv) is ListV:   return ListV(lv.items + rv.items)
    if op == "<":  return BoolV(lv.v < rv.v)
    if op == ">":  return BoolV(lv.v > rv.v)
    if op == "<=": return BoolV(lv.v <= rv.v)
    if op == ">=": return BoolV(lv.v >= rv.v)
    if op == "==": return BoolV(_eq(lv, rv))
    if op == "!=": return BoolV(not _eq(lv, rv))
    raise RuntimeError(f"unknown op {op}")


def _eq(a: Value, b: Value) -> bool:
    # v1.7 perf: type identity comparison
    ta = type(a)
    tb = type(b)
    if ta is not tb: return False
    if ta is IntV or ta is StringV or ta is BoolV:
        return a.v == b.v
    if ta is ListV:
        if len(a.items) != len(b.items): return False
        return all(_eq(x, y) for x, y in zip(a.items, b.items))
    if ta is ADTValue:
        if a.ctor != b.ctor: return False
        if len(a.args) != len(b.args): return False
        return all(_eq(x, y) for x, y in zip(a.args, b.args))
    if ta is TupleV:
        if len(a.items) != len(b.items): return False
        return all(_eq(x, y) for x, y in zip(a.items, b.items))
    if ta is RecordV:
        if a.name != b.name: return False
        if set(a.fields.keys()) != set(b.fields.keys()): return False
        return all(_eq(a.fields[k], b.fields[k]) for k in a.fields)
    return False


def pat_match(p: Pattern, v: Value) -> tuple[bool, dict[str, Value]]:
    # v1.7 perf: type(v) is X is ~3x faster than isinstance(v, X) and
    # the dispatch fires millions of times during prism.glass execution.
    k = p.kind
    if k == "wild": return True, {}
    if k == "ident": return True, {p.value: v}
    if k == "ctor":
        if type(v) is not ADTValue or v.ctor != p.value:
            return False, {}
        args = p.args or []
        if len(args) != len(v.args):
            return False, {}
        bindings: dict[str, Value] = {}
        for sub_p, sub_v in zip(args, v.args):
            ok, b = pat_match(sub_p, sub_v)
            if not ok: return False, {}
            bindings.update(b)
        return True, bindings
    if k == "cons":
        if type(v) is not ListV or len(v.items) < 1:
            return False, {}
        h_ok, h_b = pat_match(p.head, v.items[0])
        if not h_ok: return False, {}
        t_ok, t_b = pat_match(p.tail, ListV(v.items[1:]))
        if not t_ok: return False, {}
        h_b.update(t_b)
        return True, h_b
    if k == "nil":
        return (type(v) is ListV and len(v.items) == 0), {}
    if k == "int":    return (type(v) is IntV and v.v == p.value), {}
    if k == "string": return (type(v) is StringV and v.v == p.value), {}
    if k == "bool":   return (type(v) is BoolV and v.v == p.value), {}
    if k == "tuple":
        args = p.args or []
        if type(v) is not TupleV or len(v.items) != len(args):
            return False, {}
        bindings = {}
        for sub_p, sub_v in zip(args, v.items):
            ok, b = pat_match(sub_p, sub_v)
            if not ok: return False, {}
            bindings.update(b)
        return True, bindings
    if k == "record":
        if type(v) is not RecordV or v.name != p.value:
            return False, {}
        field_names: list[str] = p.args or []
        bindings = {}
        for fname in field_names:
            if fname not in v.fields:
                return False, {}
            bindings[fname] = v.fields[fname]
        return True, bindings
    return False, {}


# =============================================================================
# Driver
# =============================================================================

PRELUDE = """
type Option<T> =
  | None
  | Some(T)

type Result<T, E> =
  | Ok(T)
  | Err(E)

type Pair<A, B> =
  | Pair(A, B)

# Generic helpers. These exist because nested error-handling code is the
# single biggest legibility cost in Glass; bind flattens four-deep matches
# into linear pipelines.

fn map_option<A, B, Eff>(o: Option<A>, f: (A) -> B !{Eff}) : Option<B> !{Eff} =
  match o {
    None    => None;
    Some(x) => Some(f(x))
  }

fn bind_option<A, B, Eff>(o: Option<A>, k: (A) -> Option<B> !{Eff}) : Option<B> !{Eff} =
  match o {
    None    => None;
    Some(x) => k(x)
  }

fn map_result<A, B, Err, Eff>(r: Result<A, Err>, f: (A) -> B !{Eff}) : Result<B, Err> !{Eff} =
  match r {
    Err(e) => Err(e);
    Ok(x)  => Ok(f(x))
  }

fn bind_result<A, B, Err, Eff>(r: Result<A, Err>, k: (A) -> Result<B, Err> !{Eff}) : Result<B, Err> !{Eff} =
  match r {
    Err(e) => Err(e);
    Ok(x)  => k(x)
  }

fn fst<A, B>(p: Pair<A, B>) : A =
  match p {
    Pair(a, _) => a
  }

fn snd<A, B>(p: Pair<A, B>) : B =
  match p {
    Pair(_, b) => b
  }

# String helpers built on the new v0.8 builtins.
fn string_contains(s: String, needle: String) : Bool =
  match string_index_of(s, needle) {
    None    => false;
    Some(_) => true
  }
"""


def install_decl(
    d: Node,
    checker: TypeChecker,
    env: dict[str, Value],
    verbose: bool = False,
    is_repl: bool = False,
) -> None:
    """Single-decl install: type-check d and install its runtime effect.
    Used by the REPL (which sees one decl at a time, no mutual recursion).
    For batched programs use install_program for proper two-pass semantics."""
    checker.check_decl(d)
    if isinstance(d, TypeDecl):
        for v in d.variants:
            if not v.fields:
                env[v.name] = ADTValue(ctor=v.name, args=[])
            else:
                env[v.name] = CtorV(name=v.name, arity=len(v.fields), fields=v.fields, field_names=v.field_names)
        if verbose:
            print(f"  type {d.name}: " +
                  " | ".join(v.name + (f"({len(v.fields)})" if v.fields else "")
                             for v in d.variants))
    elif isinstance(d, RecordDecl):
        # Records don't need a runtime constructor — RecordLit builds them
        # directly. Only the type registry needs the info.
        if verbose:
            fs = ", ".join(f"{n}: {t}" for n, t in d.fields)
            print(f"  record {d.name} {{ {fs} }}")
    elif isinstance(d, LetDecl):
        env[d.name] = eval_expr(d.value, env)
        if d.ann is not None:
            check_refinement_runtime(d.name, d.ann, env[d.name], env)
        if verbose:
            if d.name != "_":
                print(f"  {d.name} : {checker.env[d.name]} = {env[d.name]}")
            elif is_repl:
                print(f"  : {checker.env['_']} = {env[d.name]}")
    elif isinstance(d, FnDecl):
        fv = FnV(params=list(d.params), body=d.body, env=env, ret=d.ret)
        env[d.name] = fv
        fv.env = env
        if verbose:
            print(f"  {d.name} : {checker.env[d.name]}")


def install_program(
    decls: list[Node],
    checker: TypeChecker,
    env: dict[str, Value],
    verbose: bool = False,
) -> None:
    """Two-pass install for a batch of declarations.

    Pass 1 registers types (in the checker AND value env) and fn signatures
    (in the checker) and fn values (in env). After pass 1, all top-level
    fn names are bound BOTH statically and at runtime, so mutual recursion
    works in either direction.

    Pass 2 checks fn bodies and runs let initializers in source order."""
    # Pass 1: register everything that could be forward-referenced.
    for d in decls:
        if isinstance(d, TypeDecl):
            checker.register_type(d)
            for v in d.variants:
                if not v.fields:
                    env[v.name] = ADTValue(ctor=v.name, args=[])
                else:
                    env[v.name] = CtorV(name=v.name, arity=len(v.fields), fields=v.fields, field_names=v.field_names)
        elif isinstance(d, RecordDecl):
            checker.register_record(d)
            # No runtime binding — record values are built via RecordLit.
        elif isinstance(d, FnDecl):
            checker.register_fn_signature(d)
            fv = FnV(params=list(d.params), body=d.body, env=env, ret=d.ret)
            env[d.name] = fv
            fv.env = env  # closure references shared env dict
    # Pass 2: check fn bodies and run let decls in source order.
    for d in decls:
        if isinstance(d, TypeDecl):
            if verbose:
                print(f"  type {d.name}: " +
                      " | ".join(v.name + (f"({len(v.fields)})" if v.fields else "")
                                 for v in d.variants))
        elif isinstance(d, RecordDecl):
            if verbose:
                fs = ", ".join(f"{n}: {t}" for n, t in d.fields)
                print(f"  record {d.name} {{ {fs} }}")
        elif isinstance(d, FnDecl):
            checker.check_fn_body(d)
            if verbose:
                print(f"  {d.name} : {checker.env[d.name]}")
        elif isinstance(d, LetDecl):
            checker.check_decl(d)
            env[d.name] = eval_expr(d.value, env)
            if d.ann is not None:
                check_refinement_runtime(d.name, d.ann, env[d.name], env)
            if verbose:
                if d.name != "_":
                    print(f"  {d.name} : {checker.env[d.name]} = {env[d.name]}")


def make_runtime() -> tuple[TypeChecker, dict[str, Value]]:
    """Build a checker + value env pre-loaded with the prelude."""
    checker = TypeChecker()
    env = builtin_values()
    install_program(
        Parser(tokenize(PRELUDE)).parse_program(),
        checker, env, verbose=False,
    )
    return checker, env


def expand_imports(
    decls: list[Node], base_dir: str, seen: set[str] | None = None
) -> list[Node]:
    """v4.70: replace each `import "file"` with the imported file's
    DEFINITIONS (TypeDecl / RecordDecl / FnDecl), recursively. A file's
    top-level `let`s and final expression are skipped, so importing a
    file never runs its demos. Paths resolve relative to the importing
    file's directory (then CWD). A `seen` set dedupes and breaks cycles
    — a diamond import installs each library exactly once."""
    seen = seen if seen is not None else set()
    out: list[Node] = []
    for d in decls:
        if not isinstance(d, Import):
            out.append(d)
            continue
        cand = os.path.join(base_dir, d.path)
        path = cand if os.path.exists(cand) else d.path
        real = os.path.realpath(path)
        if real in seen:
            continue   # already imported (diamond / cycle) — install once
        seen.add(real)
        try:
            src = open(path).read()
        except OSError as ex:
            raise RuntimeError(f"import: cannot read {d.path!r}: {ex}")
        imported = Parser(tokenize(src)).parse_program()
        # Recurse first (the imported file may import others), then keep
        # only its definitions — not its `let`s or trailing expression.
        expanded = expand_imports(imported, os.path.dirname(real), seen)
        for sub in expanded:
            if isinstance(sub, (TypeDecl, RecordDecl, FnDecl)):
                out.append(sub)
    return out


def run_source(src: str, verbose: bool = False, base_dir: str = ".") -> None:
    checker, env = make_runtime()
    decls = Parser(tokenize(src)).parse_program()
    decls = expand_imports(decls, base_dir)
    install_program(decls, checker, env, verbose=verbose)


def _is_incomplete_input_error(ex: Exception) -> bool:
    """Heuristic: is this parse error one that more input would fix?
    Used by the REPL to decide whether to keep reading or surface the
    error. Errors about unexpected END or expected-but-missing tokens
    typically mean the user hasn't finished typing."""
    msg = str(ex)
    incomplete_markers = (
        "unexpected END",
        "unexpected end of input",
        "unexpected token EOF",
        "expected RBRACE",
        "expected RBRACKET",
        "expected RPAREN",
        "expected then",
        "expected else",
        "expected in",
        "expected =>",
        "expected IDENT",
    )
    return any(m in msg for m in incomplete_markers)


def _repl_help() -> str:
    return """\
Commands:
  :help              Show this message.
  :quit  / :q        Exit the REPL (or press Ctrl-D).
  :reset             Clear all definitions and start fresh.
  :type EXPR         Show the type of EXPR without evaluating.
  :env               List currently bound names.
  :load PATH         Read a .glass file and install its declarations.

Anything else is parsed as Glass: an expression, a let, a fn, or a type.
Multi-line input is supported — keep typing while the prompt shows '...'.
"""


def repl() -> None:
    """Interactive Glass REPL with multi-line input, commands, persistent
    environment, and (if available) readline history + editing.

    Reads input until the parser accepts; if the parser fails with an
    'incomplete input' error (looking for `then`, `RBRACE`, etc.), the
    REPL keeps reading. Top-level identifiers stay in scope across
    iterations."""
    # Try to enable readline for history + line editing.
    try:
        import readline  # noqa: F401  (just importing enables it on POSIX)
        import atexit
        import os
        histfile = os.path.expanduser("~/.glass_history")
        try:
            readline.read_history_file(histfile)
        except (OSError, FileNotFoundError):
            pass
        atexit.register(lambda: _save_history(histfile))
    except ImportError:
        pass

    print("Glass v5.33 — interactive REPL")
    print("Type :help for commands, :quit to exit.")
    print()

    checker, env = make_runtime()
    # Snapshot the initial env so :env can show only user-added names.
    initial_names = set(checker.env.keys())
    buffer: list[str] = []

    while True:
        prompt = "glass> " if not buffer else "    ... "
        try:
            line = input(prompt)
        except EOFError:
            print()
            return
        except KeyboardInterrupt:
            print("\n  (interrupted)")
            buffer.clear()
            continue

        # ----- handle :commands when no buffer is pending -----
        if not buffer:
            stripped = line.strip()
            if stripped in (":quit", ":q"):
                return
            if stripped == ":help":
                print(_repl_help())
                continue
            if stripped == ":reset":
                checker, env = make_runtime()
                initial_names = set(checker.env.keys())
                print("  (environment reset)")
                continue
            if stripped == ":env":
                user_names = sorted(
                    n for n in checker.env
                    if n not in initial_names and not n.startswith("_")
                )
                if user_names:
                    for n in user_names:
                        print(f"  {n} : {checker.env[n]}")
                else:
                    print("  (no user-defined bindings)")
                continue
            if stripped.startswith(":type "):
                expr_src = stripped[6:].strip()
                try:
                    tokens = tokenize(expr_src)
                    p = Parser(tokens)
                    node = p.parse_expr()
                    ty = checker.infer(node, checker.env)
                    print(f"  {expr_src} : {ty}")
                except Exception as ex:
                    print(f"  ! {type(ex).__name__}: {ex}")
                continue
            if stripped.startswith(":load "):
                path = stripped[6:].strip()
                try:
                    with open(path) as fh:
                        src = fh.read()
                    decls = Parser(tokenize(src)).parse_program()
                    install_program(decls, checker, env, verbose=True)
                except Exception as ex:
                    print(f"  ! {type(ex).__name__}: {ex}")
                continue
            if stripped.startswith(":"):
                print(f"  unknown command: {stripped}.  Try :help.")
                continue

        # ----- accumulate input and try to parse -----
        buffer.append(line)
        src = "\n".join(buffer)
        if not src.strip():
            buffer.clear()
            continue

        try:
            tokens = tokenize(src)
            decls = Parser(tokens).parse_program()
        except (SyntaxError, TypeError_, RuntimeError) as ex:
            if _is_incomplete_input_error(ex):
                # Keep accumulating; the user is mid-input.
                continue
            print(f"  ! {type(ex).__name__}: {ex}")
            buffer.clear()
            continue

        # Parsed cleanly — try to type-check + install each decl.
        buffer.clear()
        try:
            for d in decls:
                install_decl(d, checker, env, verbose=True, is_repl=True)
        except (SyntaxError, TypeError_, RuntimeError) as ex:
            print(f"  ! {type(ex).__name__}: {ex}")


def _save_history(path: str) -> None:
    try:
        import readline
        readline.write_history_file(path)
    except Exception:
        pass


def main() -> None:
    """Console entry point. After `pip install glass-lang`, this is what
    the `glass` command invokes. With no args it starts the REPL; with a
    filename it runs that file."""
    if len(sys.argv) == 1:
        repl()
    elif sys.argv[1] in ("--version", "-V"):
        print("Glass 5.49.0")
    elif sys.argv[1] == "prove":
        # `glass prove <file.glass> [name=value ...]` — compile the file's `main`
        # expression into a circuit and emit a succinct, zero-knowledge proof of
        # its result. Free variables named on the command line are PRIVATE inputs
        # (they stay in the witness). The prove pipeline itself is Glass: this
        # assembles a driver over examples/prove/prove_source_adt_zk.glass.
        # --goldilocks: prove over the production Goldilocks field (p = 2^64-2^32+1)
        # instead of toy Baby Bear (2^31). Covers the arithmetic/comparison subset
        # (+,-,*,let,calls,==,if) with multiple private inputs; the bignum field makes
        # it heavier on the interpreter. The default keeps Baby Bear for the full ADT
        # feature set. See docs/soundness.md.
        args = [a for a in sys.argv[2:] if a not in ("--goldilocks", "--baby-bear", "--zk", "--fast")]
        # Default is now Goldilocks (2^64, ADTs) — off the toy 2^31 Baby Bear field.
        # `--baby-bear` opts back into the educational small-field prover.
        goldilocks = "--baby-bear" not in sys.argv[2:]
        # Goldilocks verifier selection:
        #   default : SOUND — prove_b3 + the independent witness-free verify_b3.
        #   --zk    : SOUND + zero-knowledge (randomized-trace hiding); heavy.
        #   --fast  : the old self-check (gprove_m/prove_stark) — NOT a soundness proof,
        #             kept for quick iteration only.
        zk_mode = "--zk" in sys.argv[2:]
        fast_mode = "--fast" in sys.argv[2:]
        if len(args) < 1:
            print("usage: glass prove [--baby-bear] [--zk | --fast] <file.glass> [name=value ...]")
            return
        upath = args[0]
        inputs = []
        for arg in args[1:]:
            if "=" in arg:
                k, v = arg.split("=", 1)
                inputs.append((k.strip(), int(v.strip())))
        with open(upath) as f:
            usrc = f.read()
        here = os.path.dirname(os.path.abspath(__file__))
        bridge_dir = os.path.join(here, "examples", "prove")
        esc = usrc.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        inp_glass = "[" + ", ".join('Pair("%s", %d)' % (k, v) for k, v in inputs) + "]"
        bridge_file = "prove_source_goldilocks_zk.glass" if goldilocks else "prove_source_adt_zk.glass"
        with open(os.path.join(bridge_dir, bridge_file)) as f:
            bridge = f.read()
        cut = bridge.find("# --- demo")
        machinery = bridge[:cut] if cut > 0 else bridge
        if goldilocks:
            if fast_mode:
                _prove_call = "gprove_m(_usrc, _inp, _r, 11111)"
                _prove_label = "ACCEPT  (self-check over the witness — NOT a soundness proof; drop --fast for verify_b3)"
            elif zk_mode:
                _prove_call = "gprove_zk(_usrc, _inp, _r, 11111, 256)"
                _prove_label = "ACCEPT  (SOUND + zero-knowledge — independent verify_b3 + randomized-trace hiding)"
            else:
                _prove_call = "gprove_sound(_usrc, _inp, _r)"
                _prove_label = "ACCEPT  (SOUND — independent witness-free verify_b3; not zero-knowledge)"
            driver = machinery + (
                '\nlet _usrc : String = "%s"\n'
                'let _inp : List<Pair<String, Int>> = %s\n'
                'let _rv : List<List<Int>> = gref_m_checked(_usrc, _inp)\n'
                'let _r : List<Int> = vh(_rv)\n'
                'let _ : String = print("result:  " ++ bn_dec(_r) ++ "  (over Goldilocks, p = 2^64-2^32+1)")\n'
                'let _ : String = print("proof:   " ++ (if %s then "%s" else "REJECT"))\n'
                '"glass prove --goldilocks"\n'
            ) % (esc, inp_glass, _prove_call, _prove_label)
        else:
            driver = machinery + (
                '\nlet bbw : Int = find_nonres_b(2)\n'
                'let bbv : F2 = find_v(0, bbw)\n'
                'let _usrc : String = "%s"\n'
                'let _inp : List<Pair<String, Int>> = %s\n'
                'let _r : Int = ref_result(_usrc, _inp)\n'
                'let _ : String = print("result:  " ++ int_to_string(_r))\n'
                'let _ : String = print("proof:   " ++ (if prove(_usrc, _inp, _r, 11111, bbv, bbw) then "ACCEPT  (succinct, zero-knowledge)" else "REJECT"))\n'
                '"glass prove"\n'
            ) % (esc, inp_glass)
        field = "Goldilocks (2^64)" if goldilocks else "Baby Bear (2^31)"
        print("Glass prove — %s  [field: %s]" % (upath, field))
        if inputs:
            names = ", ".join(k for k, _ in inputs)
            print("private inputs: %s  (kept in the witness; the proof reveals only the result)" % names)
        print("")
        if goldilocks:
            # Goldilocks is bignum-heavy — run natively (the interpreter is ~hours).
            # run_native.sh builds native_glassc once, then compiles + runs the driver.
            _tmp = "/tmp/glass_prove_driver.glass"
            with open(_tmp, "w") as _f:
                _f.write(driver)
            _proc = subprocess.run(["bash", os.path.join(here, "examples", "selfhost", "run_native.sh"), _tmp],
                           check=False, env={**os.environ, "PYTHON": sys.executable})
            if _proc.returncode != 0:
                # The native prover refused (e.g. the bridge's loud `error` on a
                # parse/unroll failure) — propagate a nonzero exit and do NOT print
                # the success footer that would imply a proof was produced.
                sys.exit(_proc.returncode)
        else:
            run_source(driver, verbose=False, base_dir=bridge_dir)
        print("")
        if goldilocks:
            if fast_mode:
                print("(F_{p^2} FRI STARK; --fast = self-check over the witness, NOT a soundness proof.)")
            elif zk_mode:
                print("(F_{p^2} FRI STARK; SOUND + zero-knowledge via the independent verify_b3. Research-grade, UNAUDITED.)")
            else:
                print("(F_{p^2} FRI STARK; SOUND via the independent witness-free verify_b3 (per-row gates + PLONK wiring). Research-grade, UNAUDITED; --zk adds hiding.)")
        else:
            print("(blinded F_{p^4} FRI STARK over the gate circuit; `glass prove` proves AND verifies.)")
    else:
        # -q/--quiet: run a file printing only its output (no type-signature
        # echoes) — handy for diffing against the self-hosted compiler.
        quiet = sys.argv[1] in ("-q", "--quiet")
        path = sys.argv[2] if quiet else sys.argv[1]
        with open(path) as f:
            src = f.read()
        # v4.70: resolve `import` paths relative to the source file's dir.
        run_source(src, verbose=not quiet,
                   base_dir=os.path.dirname(os.path.abspath(path)))


if __name__ == "__main__":
    main()
