"""
Glass v1.0 — reference implementation.

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
import re

sys.setrecursionlimit(20000)


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
    "type", "where",
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
    ("BAR",      r"\|"),
    ("CONCAT",   r"\+\+"),
    ("ELLIPSIS", r"\.\.\."),
    ("DOT",      r"\."),
    ("LE",       r"<="),
    ("GE",       r">="),
    ("EQ",       r"=="),
    ("NEQ",      r"!="),
    ("BANG",     r"!"),
    ("LT",       r"<"),
    ("GT",       r">"),
    ("ASSIGN",   r"="),
    ("PLUS",     r"\+"),
    ("MINUS",    r"-"),
    ("STAR",     r"\*"),
    ("SLASH",    r"/"),
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


def pp_expr(e: "Node") -> str:
    """Compact pretty-printer for AST expressions. Used by TyRefine.__str__
    for diagnostics — keep it terse, not round-trippable."""
    if isinstance(e, IntLit):    return str(e.value)
    if isinstance(e, StringLit): return repr(e.value)
    if isinstance(e, BoolLit):   return "true" if e.value else "false"
    if isinstance(e, Ident):     return e.name
    if isinstance(e, BinOp):     return f"{pp_expr(e.lhs)} {e.op} {pp_expr(e.rhs)}"
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
    "EQ": 2, "NEQ": 2, "LT": 2, "GT": 2, "LE": 2, "GE": 2,
    "CONCAT": 3,
    "PLUS":   4, "MINUS": 4,
    "STAR":   5, "SLASH": 5,
}
RIGHT_ASSOC = {"CONCAT"}
OP_NAME = {
    "PLUS": "+", "MINUS": "-", "STAR": "*", "SLASH": "/",
    "EQ": "==", "NEQ": "!=", "LT": "<", "GT": ">", "LE": "<=", "GE": ">=",
    "CONCAT": "++", "PIPE": "|>",
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
            ret = self.parse_type()
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
        if self.accept("LPAREN"):
            if self.peek().kind != "RPAREN":
                fields.append(self.parse_type(type_params))
                while self.accept("COMMA"):
                    fields.append(self.parse_type(type_params))
            self.eat("RPAREN")
        return Variant(name=vname, fields=fields)

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
        return left

    def parse_unary(self) -> Node:
        # Unary minus is folded into INT literal at the lexer level.
        return self.parse_postfix()

    def parse_postfix(self) -> Node:
        e = self.parse_atom()
        while True:
            if self.peek().kind == "LPAREN":
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
        name = self.eat("IDENT").value
        ann: Ty | None = None
        if self.accept("COLON"):
            ann = self.parse_type(accept_refinement=True)
        self.eat("ASSIGN")
        value = self.parse_expr()
        self.eat("in")
        body = self.parse_expr()
        return LetIn(name=name, ann=ann, value=value, body=body)

    def parse_lambda(self) -> Lambda:
        self.eat("fn")
        self.eat("LPAREN")
        params = self.parse_params()
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
            # Multi-head support: [h1, h2, h3, ...t] is sugar for nested cons.
            # Each comma separates either another head or the ellipsis.
            tail: Pattern
            while True:
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
        "string_length":  TyFn((TyString(),), TyInt()),
        "substring":      TyFn((TyString(), TyInt(), TyInt()), TyString()),
        "string_index_of": TyFn(
            (TyString(), TyString()),
            TyADT("Option", (TyInt(),)),
        ),
        "read_file":      TyFn(
            (TyString(),),
            TyADT("Result", (TyString(), TyString())),
            EffectRow(frozenset({"File"})),
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
                raise TypeError_(f"unbound identifier {e.name!r}")
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
        if e.op in ("+", "-", "*", "/"):
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
        for formal, actual_expr in zip(ft.params, e.args):
            actual = self.infer(actual_expr, env)
            if not unify(formal, actual, subst, self.eff_subst, rigid_eff):
                expected = resolve(formal, subst, self.eff_subst)
                raise TypeError_(f"arg type mismatch: expected {expected}, got {actual}")
        # Calling this fn causes its (post-substitution) effects to be added
        # to the surrounding scope's effect row. Effect-row variables in
        # ft.effects may have been bound during arg unification — resolve
        # before extending.
        call_effects = resolve_effects(ft.effects, self.eff_subst)
        self.current_effects = extend_effects(self.current_effects, call_effects)
        return resolve(ft.ret, subst, self.eff_subst)

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
                raise TypeError_(f"tuple pattern against {scrut_ty}")
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
    pass

@dataclass
class IntV(Value):
    v: int
    def __str__(self): return str(self.v)

@dataclass
class StringV(Value):
    v: str
    def __str__(self): return self.v

@dataclass
class BoolV(Value):
    v: bool
    def __str__(self): return "true" if self.v else "false"

@dataclass
class ListV(Value):
    items: list[Value]
    def __str__(self):
        return "[" + ", ".join(str(x) for x in self.items) + "]"

@dataclass
class TupleV(Value):
    items: list[Value]
    def __str__(self):
        return "(" + ", ".join(str(x) for x in self.items) + ")"

@dataclass
class RecordV(Value):
    name: str
    fields: dict[str, Value]
    def __str__(self):
        body = ", ".join(f"{k}: {v}" for k, v in self.fields.items())
        return f"{self.name} {{ {body} }}"

@dataclass
class FnV(Value):
    """A user-defined function value. params carries (name, declared_type)
    so the interpreter can run refinement checks at call boundaries."""
    params: list[tuple[str, Ty]]
    body: Node
    env: dict[str, Value]
    def __str__(self):
        names = ", ".join(p for p, _ in self.params)
        return f"<fn({names})>"

@dataclass
class BuiltinV(Value):
    name: str
    fn: Callable[..., Value]
    def __str__(self): return f"<builtin {self.name}>"

@dataclass
class ADTValue(Value):
    """A constructed value of an algebraic data type, e.g. Some(42), Ok("ok")."""
    ctor: str
    args: list[Value]
    def __str__(self):
        if not self.args:
            return self.ctor
        return f"{self.ctor}(" + ", ".join(str(a) for a in self.args) + ")"

@dataclass
class CtorV(Value):
    """A constructor used as a function (Some, Ok). Zero-arg constructors are
    bound directly as ADTValue, not as CtorV."""
    name: str
    arity: int
    def __str__(self): return f"<ctor {self.name}/{self.arity}>"


def builtin_values() -> dict[str, Value]:
    import random as _random_module
    def b_print(s):
        print(s.v)
        return s
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
    def b_itos(n): return StringV(str(n.v))
    def b_model_call(prompt):
        # Mock: a real backend would dispatch to an LLM, classifier, etc.
        # Here we just echo with a tag, so demos run without external state.
        # The point is the TYPE: !{Inference} makes every model call visible.
        return StringV(f"[model]: {prompt.v}")
    return {
        "print":            BuiltinV("print", b_print),
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
        "string_length":    BuiltinV("string_length", b_string_length),
        "substring":        BuiltinV("substring", b_substring),
        "string_index_of":  BuiltinV("string_index_of", b_string_index_of),
        "read_file":        BuiltinV("read_file", b_read_file),
        "int_to_string":    BuiltinV("int_to_string", b_itos),
    }


def apply_fn(f: Value, args: list[Value]) -> Value:
    if isinstance(f, BuiltinV):
        return f.fn(*args)
    if isinstance(f, FnV):
        if len(args) != len(f.params):
            raise RuntimeError(f"arity mismatch calling {f}")
        new_env = {**f.env}
        for (p, t), a in zip(f.params, args):
            new_env[p] = a
            # Refinement check: predicate evaluates with all already-bound
            # params in scope, including earlier params (so a refinement on
            # `b` can reference `a`).
            check_refinement_runtime(p, t, a, new_env)
        return eval_expr(f.body, new_env)
    if isinstance(f, CtorV):
        if len(args) != f.arity:
            raise RuntimeError(f"ctor {f.name} expects {f.arity} args, got {len(args)}")
        return ADTValue(ctor=f.name, args=list(args))
    raise RuntimeError(f"not callable: {f}")


def check_refinement_runtime(
    bind_name: str,
    ty: Ty,
    value: Value,
    env: dict[str, Value],
) -> None:
    """If ty (or its base chain) is a refinement, evaluate the predicate
    with bind_name -> value in env. Raise on violation."""
    while isinstance(ty, TyRefine):
        # bind_name must already be in env (caller's responsibility).
        result = eval_expr(ty.pred, env)
        if not (isinstance(result, BoolV) and result.v):
            raise RuntimeError(
                f"refinement violated: {bind_name} = {value} fails "
                f"predicate ({pp_expr(ty.pred)})"
            )
        ty = ty.base


def eval_expr(e: Node, env: dict[str, Value]) -> Value:
    if isinstance(e, IntLit):    return IntV(e.value)
    if isinstance(e, StringLit): return StringV(e.value)
    if isinstance(e, BoolLit):   return BoolV(e.value)
    if isinstance(e, ListLit):
        return ListV([eval_expr(it, env) for it in e.items])
    if isinstance(e, TupleLit):
        return TupleV([eval_expr(it, env) for it in e.items])
    if isinstance(e, RecordLit):
        return RecordV(
            name=e.name,
            fields={fname: eval_expr(fval, env) for fname, fval in e.fields},
        )
    if isinstance(e, FieldAccess):
        rec = eval_expr(e.record, env)
        if not isinstance(rec, RecordV):
            raise RuntimeError(f"field access on non-record value: {rec}")
        if e.field not in rec.fields:
            raise RuntimeError(f"record {rec.name} has no field {e.field!r}")
        return rec.fields[e.field]
    if isinstance(e, Ident):
        if e.name not in env:
            raise RuntimeError(f"unbound at runtime: {e.name}")
        return env[e.name]
    if isinstance(e, BinOp):
        return eval_binop(e, env)
    if isinstance(e, Call):
        f = eval_expr(e.fn, env)
        args = [eval_expr(a, env) for a in e.args]
        return apply_fn(f, args)
    if isinstance(e, If):
        c = eval_expr(e.cond, env)
        return eval_expr(e.then_b if c.v else e.else_b, env)
    if isinstance(e, LetIn):
        v = eval_expr(e.value, env)
        new_env = {**env, e.name: v}
        if e.ann is not None:
            check_refinement_runtime(e.name, e.ann, v, new_env)
        return eval_expr(e.body, new_env)
    if isinstance(e, Lambda):
        return FnV(params=list(e.params), body=e.body, env=env)
    if isinstance(e, Match):
        scrut = eval_expr(e.scrutinee, env)
        for pat, body in e.arms:
            ok, bindings = pat_match(pat, scrut)
            if ok:
                return eval_expr(body, {**env, **bindings})
        raise RuntimeError("non-exhaustive match")
    raise RuntimeError(f"cannot eval {type(e).__name__}")


def eval_binop(e: BinOp, env: dict[str, Value]) -> Value:
    lv = eval_expr(e.lhs, env)
    rv = eval_expr(e.rhs, env)
    op = e.op
    if op == "+":  return IntV(lv.v + rv.v)
    if op == "-":  return IntV(lv.v - rv.v)
    if op == "*":  return IntV(lv.v * rv.v)
    if op == "/":  return IntV(lv.v // rv.v)
    if op == "++":
        if isinstance(lv, StringV): return StringV(lv.v + rv.v)
        if isinstance(lv, ListV):   return ListV(lv.items + rv.items)
    if op == "<":  return BoolV(lv.v < rv.v)
    if op == ">":  return BoolV(lv.v > rv.v)
    if op == "<=": return BoolV(lv.v <= rv.v)
    if op == ">=": return BoolV(lv.v >= rv.v)
    if op == "==": return BoolV(_eq(lv, rv))
    if op == "!=": return BoolV(not _eq(lv, rv))
    raise RuntimeError(f"unknown op {op}")


def _eq(a: Value, b: Value) -> bool:
    if isinstance(a, (IntV, StringV, BoolV)) and isinstance(b, (IntV, StringV, BoolV)):
        return a.v == b.v
    if isinstance(a, ListV) and isinstance(b, ListV):
        if len(a.items) != len(b.items): return False
        return all(_eq(x, y) for x, y in zip(a.items, b.items))
    if isinstance(a, ADTValue) and isinstance(b, ADTValue):
        if a.ctor != b.ctor: return False
        if len(a.args) != len(b.args): return False
        return all(_eq(x, y) for x, y in zip(a.args, b.args))
    if isinstance(a, TupleV) and isinstance(b, TupleV):
        if len(a.items) != len(b.items): return False
        return all(_eq(x, y) for x, y in zip(a.items, b.items))
    if isinstance(a, RecordV) and isinstance(b, RecordV):
        if a.name != b.name: return False
        if set(a.fields.keys()) != set(b.fields.keys()): return False
        return all(_eq(a.fields[k], b.fields[k]) for k in a.fields)
    return False


def pat_match(p: Pattern, v: Value) -> tuple[bool, dict[str, Value]]:
    if p.kind == "wild": return True, {}
    if p.kind == "ident": return True, {p.value: v}
    if p.kind == "int":   return (isinstance(v, IntV) and v.v == p.value), {}
    if p.kind == "string":return (isinstance(v, StringV) and v.v == p.value), {}
    if p.kind == "bool":  return (isinstance(v, BoolV) and v.v == p.value), {}
    if p.kind == "nil":
        return (isinstance(v, ListV) and len(v.items) == 0), {}
    if p.kind == "cons":
        if not (isinstance(v, ListV) and len(v.items) >= 1):
            return False, {}
        h_ok, h_b = pat_match(p.head, v.items[0])
        if not h_ok: return False, {}
        t_ok, t_b = pat_match(p.tail, ListV(v.items[1:]))
        if not t_ok: return False, {}
        return True, {**h_b, **t_b}
    if p.kind == "ctor":
        if not (isinstance(v, ADTValue) and v.ctor == p.value):
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
    if p.kind == "tuple":
        if not (isinstance(v, TupleV) and len(v.items) == len(p.args or [])):
            return False, {}
        args = p.args or []
        bindings = {}
        for sub_p, sub_v in zip(args, v.items):
            ok, b = pat_match(sub_p, sub_v)
            if not ok: return False, {}
            bindings.update(b)
        return True, bindings
    if p.kind == "record":
        if not (isinstance(v, RecordV) and v.name == p.value):
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
                env[v.name] = CtorV(name=v.name, arity=len(v.fields))
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
        fv = FnV(params=list(d.params), body=d.body, env=env)
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
                    env[v.name] = CtorV(name=v.name, arity=len(v.fields))
        elif isinstance(d, RecordDecl):
            checker.register_record(d)
            # No runtime binding — record values are built via RecordLit.
        elif isinstance(d, FnDecl):
            checker.register_fn_signature(d)
            fv = FnV(params=list(d.params), body=d.body, env=env)
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


def run_source(src: str, verbose: bool = False) -> None:
    checker, env = make_runtime()
    decls = Parser(tokenize(src)).parse_program()
    install_program(decls, checker, env, verbose=verbose)


def repl() -> None:
    print("Glass v1.0 — REPL.  Ctrl-D to exit.")
    checker, env = make_runtime()
    while True:
        try:
            line = input("glass> ").strip()
        except EOFError:
            print()
            return
        if not line: continue
        try:
            tokens = tokenize(line)
            decls = Parser(tokens).parse_program()
            for d in decls:
                install_decl(d, checker, env, verbose=True, is_repl=True)
        except (SyntaxError, TypeError_, RuntimeError) as ex:
            print(f"  ! {type(ex).__name__}: {ex}")


def main() -> None:
    """Console entry point. After `pip install glass-lang`, this is what
    the `glass` command invokes. With no args it starts the REPL; with a
    filename it runs that file."""
    if len(sys.argv) == 1:
        repl()
    else:
        with open(sys.argv[1]) as f:
            src = f.read()
        run_source(src, verbose=True)


if __name__ == "__main__":
    main()
