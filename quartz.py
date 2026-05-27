"""Quartz: native C compiler back-end for Glass (v5.21).

Takes a parsed + typed Glass program and emits C source. Invokes the
system C compiler to produce a native binary that, when run, prints
the program's final value.

v3.0 SCOPE — explicitly limited per docs/quartz.md:
  - Int, Bool, String literals
  - Arithmetic (+, -, *, /), comparisons (<, >, <=, >=, ==, !=)
  - if-then-else as expression
  - let-in
  - top-level let bindings (let x = 5\\nlet y = 10\\nx + y)
  - print to stdout of the final value

v3.0 explicitly does NOT support:
  - Functions (fn decls or lambdas)
  - ADTs, records, generics, refinements, effects, match
  - List or tuple values
  - Multiple .glass files

Subsequent v3.x releases extend coverage. The path is documented in
docs/quartz.md.
"""

import os
import subprocess
import sys
import tempfile

import glass


# === Helpers ============================================================

def strip_refine(ty):
    # v4.49: refinements are runtime checks, not part of the C-level
    # representation. Recursively peel TyRefine layers so the rest of
    # the codegen sees only the base type. Mirrors host parity —
    # apply_fn also strips refinements before unifying.
    while isinstance(ty, glass.TyRefine):
        ty = ty.base
    return ty


def c_type_for_ty(ty):
    # v4.49: see strip_refine — refinements vanish at the C-type level
    # but are enforced separately via emitted predicate checks.
    ty = strip_refine(ty)
    if isinstance(ty, glass.TyInt):    return "int64_t"
    if isinstance(ty, glass.TyBool):   return "bool"
    if isinstance(ty, glass.TyString): return "const char*"
    if isinstance(ty, glass.TyADT):    return "q_value_t*"
    # v4.30: tuples reuse the q_value_t boxed-pointer representation.
    # A tuple `(a, b, c)` becomes a q_value_t with TUPLE_TAG and the
    # element values stored in `fields`. Tuple destructuring in match
    # codegen reads fields by index. Same lowering shape as ADTs;
    # tuples just have no ctor name.
    if isinstance(ty, glass.TyTuple): return "q_value_t*"
    # v4.31: lists also reuse q_value_t. The representation is a cons
    # chain — Nil is `q_ctor_alloc(0, 0)` (num_fields == 0), Cons(h, t)
    # is `q_ctor_alloc(0, 2, h, t)` (num_fields == 2; fields[0]=head,
    # fields[1]=tail). The tag value is irrelevant; matching dispatches
    # on num_fields. Lists are distinguished from other q_value_t
    # values by the type system, not at runtime.
    if isinstance(ty, glass.TyList): return "q_value_t*"
    # v4.44: closures (Lambda values) reuse q_value_t. fields[0]
    # holds the lifted-fn pointer cast to int64_t; remaining fields
    # hold captured values (zero in v4.44 — captures land in v4.45).
    # Tag value is irrelevant; the type system distinguishes closures
    # from other q_value_t values.
    if isinstance(ty, glass.TyFn): return "q_value_t*"
    if isinstance(ty, glass.TyVar):
        # Type variables erase to int64_t. The boxed q_value_t storage
        # for ADT/record fields is int64_t-wide; primitive fields fit
        # directly and pointer fields fit via intptr_t. The caller knows
        # the concrete type (from the host's inferrer) and can cast at
        # use sites.
        return "int64_t"
    raise NotImplementedError(
        f"Quartz does not yet support type: {type(ty).__name__}"
    )


def c_print_for_ty(ty, atom):
    # v4.49: same as c_type_for_ty — the print-shape is governed by
    # the base type, not the refinement (refinements are runtime
    # checks, not type-level distinctions).
    ty = strip_refine(ty)
    if isinstance(ty, glass.TyInt):
        return f'printf("%lld\\n", (long long){atom});'
    if isinstance(ty, glass.TyBool):
        return f'printf("%s\\n", {atom} ? "true" : "false");'
    if isinstance(ty, glass.TyString):
        return f'printf("%s\\n", {atom});'
    if isinstance(ty, glass.TyADT):
        raise NotImplementedError(
            f"Quartz v3.2 cannot print ADT values directly; "
            f"`match` on them and print the result"
        )
    raise NotImplementedError(
        f"Quartz v3.0 cannot print type: {type(ty).__name__}"
    )


BIN_OP_C = {
    "+":  "+",
    "-":  "-",
    "*":  "*",
    "/":  "/",
    "<":  "<",
    ">":  ">",
    "<=": "<=",
    ">=": ">=",
    "==": "==",
    "!=": "!=",
    # v4.51: boolean combinators land. C's && and || are short-circuiting
    # so the semantics match host eval_binop directly.
    "&&": "&&",
    "||": "||",
    # v4.53: modulo. C's `%` is truncated (sign of dividend); host uses
    # Python's floor `%` (sign of divisor). They agree for non-negative
    # operands — the canonical parity-check case — and diverge only when
    # the dividend is negative. Same trade-off as `/` already accepts.
    "%": "%",
}


# Quartz builtins. Maps a Glass-level fn name → tuple of
# (param_tys, ret_ty, emit_fn). The emit_fn takes the list of arg
# atoms AND the Codegen instance, returning the C atom for the call.
# Codegen access lets Option-returning builtins look up Some/None
# tags at emit time.
#
# Type signatures match what `glass.builtin_types()` already
# declares, so the host type-checker accepts these calls naturally
# and Quartz just has to recognize them when it sees the AST.
#
# v4.38 added string_length, substring, int_to_string.
# v4.39 adds len, head, tail, reverse, string_index_of and
# refactored emit_fn to take the Codegen so list / Option builtins
# can resolve ctor tags.
# v4.71 (Phase A2): effectful builtins. The effect is type-level only
# (erased at codegen, v4.71/A1); these just emit the C that performs it.
def _emit_print(args, cg):
    # print : (String) -> String !{IO}. Puts the line, returns the arg.
    return f"quartz_print({args[0]})"


def _emit_read_file(args, cg):
    # read_file : (String) -> Result<String, String> !{File}.
    ok_tag = cg.ctor_tags["Ok"]
    err_tag = cg.ctor_tags["Err"]
    return f"quartz_read_file({args[0]}, {ok_tag}, {err_tag})"


def _emit_write_file(args, cg):
    # write_file : (String, String) -> Result<Int, String> !{File}.
    ok_tag = cg.ctor_tags["Ok"]
    err_tag = cg.ctor_tags["Err"]
    return f"quartz_write_file({args[0]}, {args[1]}, {ok_tag}, {err_tag})"


def _emit_run_command(args, cg):
    # run_command : (String, List<String>)
    #   -> Result<(Int, String, String), String> !{Process}.
    # Ok wraps a tuple (exit_code, stdout, stderr). The tuple is a
    # tag-0 q_value (quartz's tuple convention).
    ok_tag = cg.ctor_tags["Ok"]
    err_tag = cg.ctor_tags["Err"]
    return f"quartz_run_command({args[0]}, {args[1]}, {ok_tag}, {err_tag})"


def _emit_string_length(args, cg):
    return f"((int64_t)strlen({args[0]}))"


def _emit_substring(args, cg):
    return f"quartz_substring({args[0]}, {args[1]}, {args[2]})"


def _emit_int_to_string(args, cg):
    return f"quartz_int_to_string({args[0]})"


def _emit_len(args, cg):
    return f"quartz_list_len({args[0]})"


def _emit_reverse(args, cg):
    return f"quartz_list_reverse({args[0]})"


def _emit_head(args, cg):
    none_tag = cg.ctor_tags["None"]
    some_tag = cg.ctor_tags["Some"]
    return f"quartz_list_head({args[0]}, {none_tag}, {some_tag})"


def _emit_tail(args, cg):
    none_tag = cg.ctor_tags["None"]
    some_tag = cg.ctor_tags["Some"]
    return f"quartz_list_tail({args[0]}, {none_tag}, {some_tag})"


def _emit_string_index_of(args, cg):
    none_tag = cg.ctor_tags["None"]
    some_tag = cg.ctor_tags["Some"]
    return (
        f"quartz_string_index_of({args[0]}, {args[1]}, "
        f"{none_tag}, {some_tag})"
    )


def _emit_string_to_upper(args, cg):
    return f"quartz_string_to_upper({args[0]})"


def _emit_string_to_lower(args, cg):
    return f"quartz_string_to_lower({args[0]})"


def _emit_char_at(args, cg):
    return f"quartz_char_at({args[0]}, {args[1]})"


def _emit_range(args, cg):
    return f"quartz_range({args[0]}, {args[1]})"


# v4.42: bitwise ops inline directly as C operators on int64_t.
# No runtime helpers — the C compiler emits one or two instructions.
def _emit_bit_and(args, cg): return f"({args[0]} & {args[1]})"
def _emit_bit_or(args, cg):  return f"({args[0]} | {args[1]})"
def _emit_bit_xor(args, cg): return f"({args[0]} ^ {args[1]})"
def _emit_bit_not(args, cg): return f"(~{args[0]})"
def _emit_bit_shl(args, cg): return f"({args[0]} << {args[1]})"
def _emit_bit_shr(args, cg): return f"({args[0]} >> {args[1]})"


# v4.43: wrap_int64 is a no-op in Quartz — int64_t is the native
# representation of every Int. The cast through int64_t is defensive
# (formally a no-op the compiler removes) and makes the intent
# explicit in the generated C source.
def _emit_wrap_int64(args, cg):
    return f"((int64_t){args[0]})"


# v4.46: map/filter/fold dispatch through closure values (q_value_t*
# with fn pointer at fields[0]). The runtime helpers each cast the
# fn pointer to the appropriate signature for the closure's arity
# (unary for map/filter, binary for fold).
def _emit_map(args, cg):
    return f"quartz_map({args[0]}, {args[1]})"


def _emit_filter(args, cg):
    return f"quartz_filter({args[0]}, {args[1]})"


def _emit_fold(args, cg):
    return f"quartz_fold({args[0]}, {args[1]}, {args[2]})"


# Lazy import dance: glass.TyInt() etc. are typed objects, so we
# build the dict inside a function called once at module load.
def _build_quartz_builtins():
    T = glass.TyVar("T")
    # v4.46: extra TyVars for the higher-order list builtins.
    U = glass.TyVar("U")
    A = glass.TyVar("A")
    return {
        # v4.71 (Phase A2): effectful builtins — print and read_file.
        # Effects are erased at codegen; these emit the C that performs
        # the IO/File side effect.
        "print": (
            (glass.TyString(),), glass.TyString(), _emit_print,
        ),
        "read_file": (
            (glass.TyString(),),
            glass.TyADT("Result", (glass.TyString(), glass.TyString())),
            _emit_read_file,
        ),
        # v4.74 (Phase B): file write + process spawn, needed so quartz.py
        # can compile glassc.glass's driver (it writes the .c file and shells
        # out to cc). Effects (File/Process) are erased at codegen.
        "write_file": (
            (glass.TyString(), glass.TyString()),
            glass.TyADT("Result", (glass.TyInt(), glass.TyString())),
            _emit_write_file,
        ),
        "run_command": (
            (glass.TyString(), glass.TyList(glass.TyString())),
            glass.TyADT("Result", (
                glass.TyTuple((glass.TyInt(), glass.TyString(), glass.TyString())),
                glass.TyString())),
            _emit_run_command,
        ),
        "string_length": (
            (glass.TyString(),), glass.TyInt(), _emit_string_length,
        ),
        "substring": (
            (glass.TyString(), glass.TyInt(), glass.TyInt()),
            glass.TyString(), _emit_substring,
        ),
        "int_to_string": (
            (glass.TyInt(),), glass.TyString(), _emit_int_to_string,
        ),
        # v4.39 batch.
        "len": (
            (glass.TyList(T),), glass.TyInt(), _emit_len,
        ),
        "reverse": (
            (glass.TyList(T),), glass.TyList(T), _emit_reverse,
        ),
        "head": (
            (glass.TyList(T),), glass.TyADT("Option", (T,)),
            _emit_head,
        ),
        "tail": (
            (glass.TyList(T),), glass.TyADT("Option", (glass.TyList(T),)),
            _emit_tail,
        ),
        "string_index_of": (
            (glass.TyString(), glass.TyString()),
            glass.TyADT("Option", (glass.TyInt(),)),
            _emit_string_index_of,
        ),
        # v4.40 batch — ASCII case conversion.
        "string_to_upper": (
            (glass.TyString(),), glass.TyString(), _emit_string_to_upper,
        ),
        "string_to_lower": (
            (glass.TyString(),), glass.TyString(), _emit_string_to_lower,
        ),
        # v4.41 — returns the byte at index i as Int. Matches host's
        # codepoint semantics and quartz_parser.glass's existing use
        # (e.g. djb2 hash, ASCII lexer dispatch).
        "char_at": (
            (glass.TyString(), glass.TyInt()), glass.TyInt(),
            _emit_char_at,
        ),
        # v4.43 — host has `range(lo, hi) : (Int, Int) -> List<Int>`
        # since v0.x. Half-open: range(0, 5) is [0, 1, 2, 3, 4].
        # Empty result when lo >= hi.
        "range": (
            (glass.TyInt(), glass.TyInt()),
            glass.TyList(glass.TyInt()), _emit_range,
        ),
        # v4.42 batch — bitwise ops. Inline as C operators on int64_t.
        "bit_and": (
            (glass.TyInt(), glass.TyInt()), glass.TyInt(), _emit_bit_and,
        ),
        "bit_or": (
            (glass.TyInt(), glass.TyInt()), glass.TyInt(), _emit_bit_or,
        ),
        "bit_xor": (
            (glass.TyInt(), glass.TyInt()), glass.TyInt(), _emit_bit_xor,
        ),
        "bit_not": (
            (glass.TyInt(),), glass.TyInt(), _emit_bit_not,
        ),
        "bit_shl": (
            (glass.TyInt(), glass.TyInt()), glass.TyInt(), _emit_bit_shl,
        ),
        "bit_shr": (
            (glass.TyInt(), glass.TyInt()), glass.TyInt(), _emit_bit_shr,
        ),
        # v4.43: explicit int64 wrap. No-op in Quartz; on host it
        # applies _to_int64 so users can opt into wrap semantics for
        # overflow-sensitive algorithms.
        "wrap_int64": (
            (glass.TyInt(),), glass.TyInt(), _emit_wrap_int64,
        ),
        # v4.46 batch — higher-order list builtins. Host already
        # declares these in builtin_types(); Quartz adds the runtime
        # helpers. T, U, A are fresh TyVars matching the host signatures.
        "map": (
            (glass.TyList(T), glass.TyFn((T,), U, glass.PURE)),
            glass.TyList(U), _emit_map,
        ),
        "filter": (
            (glass.TyList(T),
             glass.TyFn((T,), glass.TyBool(), glass.PURE)),
            glass.TyList(T), _emit_filter,
        ),
        # fold combine fn is binary: (A, T) -> A.
        "fold": (
            (glass.TyList(T), A,
             glass.TyFn((A, T), A, glass.PURE)),
            A, _emit_fold,
        ),
    }


QUARTZ_BUILTINS = _build_quartz_builtins()


# C reserved words + common globals that would collide if Glass code
# uses them as identifier names. `double`, `int`, `if`, etc. all need
# mangling. The prefix `g_` is short and unambiguous in generated code.
C_RESERVED = {
    # C89/90 keywords
    "auto", "break", "case", "char", "const", "continue", "default",
    "do", "double", "else", "enum", "extern", "float", "for", "goto",
    "if", "int", "long", "register", "return", "short", "signed",
    "sizeof", "static", "struct", "switch", "typedef", "union",
    "unsigned", "void", "volatile", "while",
    # C99 additions
    "inline", "restrict", "_Bool", "_Complex", "_Imaginary",
    # C11 additions
    "_Alignas", "_Alignof", "_Atomic", "_Generic", "_Noreturn",
    "_Static_assert", "_Thread_local",
    # stdbool.h
    "true", "false", "bool",
    # stdint.h types
    "int8_t", "int16_t", "int32_t", "int64_t",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t",
    # Quartz-generated names we want to keep unique
    "main", "printf", "stdin", "stdout", "stderr", "NULL", "_result",
}


def mangle(name: str) -> str:
    """Map a Glass identifier to a C-safe identifier. Glass names that
    collide with C reserved words or quartz-generated names get a `g_`
    prefix; everything else passes through unchanged."""
    if name in C_RESERVED or name.startswith("_t") or name.startswith("g_"):
        return f"g_{name}"
    return name


# v4.55: compile a refinement predicate to a C boolean expression.
#
# History: v4.49 supported only `binder OP int_literal`; v4.51 added
# `&&` / `||`, v4.53 added the `binder % K OP M` parity special-case,
# v4.54 added unary `!`. Each was a hand-enumerated shape in a growing
# match cascade. v4.55 replaces the shape-matcher with a proper
# recursive expression compiler: the predicate is just an
# arithmetic / comparison / boolean tree over the binder and integer
# literals, so we compile it the same way the rest of codegen compiles
# expressions — recurse, transcribe each operator to its C equivalent.
#
# This widens the envelope to ANY combination of those pieces:
#   (n + 1) > 0          ((n + 1LL) > 0LL)
#   n * n >= 1           ((n * n) >= 1LL)
#   n % 2 == 0 && n > 0  (((n % 2LL) == 0LL) && (n > 0LL))
#
# The envelope stays SAFE by what it refuses: the only identifiers
# allowed are the binder itself plus any names in `allowed_names` —
# the set of OTHER variables known to be in C scope at the guard site.
# v4.56 passes the full parameter set for function refinements, so a
# later param's predicate can reference an earlier one
# (`clamp(lo, hi where (hi > lo))`): at the guard site, all params are
# C function parameters, hence in scope. A reference to any name NOT
# in that set is refused (it would compile to an undefined C
# identifier — an opaque cc failure instead of a clean Glass error).
# Function calls, string ops, field access still raise the envelope
# error. Glass's rule holds: compile exactly what the guard can prove.
_PRED_ARITH_OPS = {"+", "-", "*", "/", "%"}
_PRED_CMP_OPS = {"<", ">", "<=", ">=", "==", "!="}


def _compile_refinement_pred(binder: str, pred, allowed_names=None) -> str:
    allowed = allowed_names if allowed_names is not None else set()
    # Integer literal leaf — suffixed LL to match the int64_t binder.
    if isinstance(pred, glass.IntLit):
        return f"{pred.value}LL"
    # The binder, or any other in-scope name (v4.56), is accepted.
    if isinstance(pred, glass.Ident):
        if pred.name == binder or pred.name in allowed:
            return mangle(pred.name)
        raise NotImplementedError(
            "Quartz refinement predicates may reference the bound name "
            f"`{binder}`, other parameters in scope, and integer "
            f"literals; got out-of-scope identifier `{pred.name}` in: "
            f"{glass.pp_expr(pred)}"
        )
    # Unary NOT recurses on its operand.
    if isinstance(pred, glass.UnaryNot):
        return f"(!{_compile_refinement_pred(binder, pred.expr, allowed)})"
    # Any binary operator we know how to transcribe: arithmetic,
    # comparison, or boolean. All map 1:1 to C; we recurse on both
    # sides so nested expressions (e.g. `(n + 1) * 2 > 0`) compile.
    if isinstance(pred, glass.BinOp) and pred.op in (
        _PRED_ARITH_OPS | _PRED_CMP_OPS | {"&&", "||"}
    ):
        l_c = _compile_refinement_pred(binder, pred.lhs, allowed)
        r_c = _compile_refinement_pred(binder, pred.rhs, allowed)
        return f"({l_c} {pred.op} {r_c})"
    raise NotImplementedError(
        "Quartz refinement predicates support arithmetic "
        "(+, -, *, /, %), comparison (<, >, <=, >=, ==, !=), boolean "
        "(&&, ||, !) over the bound name, in-scope parameters, and "
        f"integer literals; got: {glass.pp_expr(pred)}"
    )


# v4.49: emit a runtime guard for one refined value. Walks every
# TyRefine layer (refinements can stack: `Int where (n > 0) where (n < 100)`)
# and emits one `if (!cond) { ...exit(1); }` per layer. The reported
# binder name matches the host's runtime-check phrasing so error
# strings agree across both implementations.
def _emit_refinement_check(
    binder: str, ty: "glass.Ty", indent: str = "    ", allowed_names=None
) -> list[str]:
    out: list[str] = []
    cur = ty
    while isinstance(cur, glass.TyRefine):
        cond_c = _compile_refinement_pred(binder, cur.pred, allowed_names)
        pred_repr = glass.pp_expr(cur.pred).replace('"', '\\"')
        msg = (
            f"refinement violated: {binder} fails predicate ({pred_repr})"
        )
        # %lld formatter only applies to integer binders; v4.49 scope is
        # exactly that shape, so emitting it unconditionally is safe.
        out.append(
            f'{indent}if (!{cond_c}) {{ '
            f'fprintf(stderr, "%s\\n", "{msg}"); exit(1); }}'
        )
        cur = cur.base
    return out


# === Generic-function support (type erasure) ============================
#
# Glass generic functions like `fn id<T>(x: T) : T = x` compile to a
# single C function where every TyVar param/return slot uses int64_t.
# At call sites, args of pointer type are cast to int64_t via intptr_t;
# results are cast back to the inferred concrete type via the same
# bridge. Within the body, a TyVar-typed value flows through int64_t-
# compatible operations only — the host's type checker has already
# rejected any program that would do otherwise.

def _contains_tyvar(ty) -> bool:
    """True if `ty` contains a TyVar anywhere in its structure."""
    if isinstance(ty, glass.TyVar):
        return True
    if isinstance(ty, glass.TyADT):
        return any(_contains_tyvar(a) for a in ty.args)
    return False


def _substitute_ty(ty, subst: dict):
    """Return `ty` with TyVar names rebound per `subst`.

    v4.37: extended to recurse through TyList and TyTuple so generic
    container types (`List<T>`, `Tuple<T, U>`) inside variant fields
    or fn signatures get their inner TyVars substituted too. Previous
    versions only walked TyADT; List/Tuple were leaves.
    """
    if isinstance(ty, glass.TyVar):
        return subst.get(ty.name, ty)
    if isinstance(ty, glass.TyADT):
        return glass.TyADT(
            ty.name,
            tuple(_substitute_ty(a, subst) for a in ty.args),
        )
    if isinstance(ty, glass.TyList):
        return glass.TyList(_substitute_ty(ty.elem, subst))
    if isinstance(ty, glass.TyTuple):
        return glass.TyTuple(
            tuple(_substitute_ty(it, subst) for it in ty.items)
        )
    return ty


def _unify_into_subst(formal, actual, subst: dict) -> None:
    """Walk formal (which may contain TyVars) and actual (concrete) in
    parallel, binding TyVars in `subst`. No-op on shape mismatch — the
    host checker has already verified the program."""
    if isinstance(formal, glass.TyVar):
        if formal.name not in subst:
            subst[formal.name] = actual
        return
    if isinstance(formal, glass.TyADT) and isinstance(actual, glass.TyADT):
        for f_arg, a_arg in zip(formal.args, actual.args):
            _unify_into_subst(f_arg, a_arg, subst)


def c_string_literal(s):
    """Escape a Glass string for embedding in C source as a string literal."""
    escaped = (s.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\t", "\\t"))
    return f'"{escaped}"'


# === Codegen ============================================================

class Codegen:
    """Walks Glass AST, emits C statements + atom expressions.

    Each emit_expr returns a C "atom" string (variable name or literal)
    representing the value. Side effect: appends C statements to
    self.stmts that prepare the value.
    """

    def __init__(self, fn_signatures: dict | None = None,
                 ctor_env: dict | None = None,
                 ctor_tags: dict | None = None,
                 record_env: dict | None = None,
                 adt_params: dict | None = None,
                 lifted_lambdas: list | None = None,
                 lambda_counter: list | None = None):
        self.stmts: list[str] = []
        self.type_env: dict[str, glass.Ty] = {}
        # v4.44: lambda-lifting state. SHARED across all Codegen
        # instances in a program — fn bodies, main(), and recursive
        # lifts all push into the same list so compile_program can
        # emit them as top-level static C fns. The counter is a
        # 1-element list (used as a mutable box) so increments
        # propagate across Codegen instances.
        self.lifted_lambdas: list = (
            lifted_lambdas if lifted_lambdas is not None else []
        )
        self.lambda_counter: list = (
            lambda_counter if lambda_counter is not None else [0]
        )
        # Map fn name → (param_tys, ret_ty). Shared across all Codegens in
        # a program so each fn body can type-check calls to other fns.
        self.fn_signatures: dict = fn_signatures if fn_signatures is not None else {}
        # Map ctor name → (parent_type_name, [field_tys]).
        self.ctor_env: dict = ctor_env if ctor_env is not None else {}
        # Map ctor name → global int tag.
        self.ctor_tags: dict = ctor_tags if ctor_tags is not None else {}
        # v4.37: map ADT name → list of type-parameter names (in
        # declaration order). Used by structural-eq codegen to
        # substitute the TyADT's type args into variant field types
        # when comparing values of a generic sum type.
        self.adt_params: dict = adt_params if adt_params is not None else {}
        # Map record name → [(field_name, field_ty), ...] in declaration
        # order. Records reuse the q_value_t representation: each record
        # gets a tag (stored in ctor_tags under the record's name) and its
        # fields populate fields[] in declaration order.
        self.record_env: dict = record_env if record_env is not None else {}
        self.counter = 0

    def fresh(self) -> str:
        self.counter += 1
        return f"_t{self.counter}"

    def type_of(self, e) -> glass.Ty:
        """Light-weight type inference — Quartz v3.0 supports only three
        primitives, so we can compute the type by walking the AST without
        the full inferrer."""
        if isinstance(e, glass.IntLit):    return glass.TyInt()
        if isinstance(e, glass.BoolLit):   return glass.TyBool()
        if isinstance(e, glass.StringLit): return glass.TyString()
        if isinstance(e, glass.Ident):
            # 0-arg constructor used as bare expression (e.g. `Red`, `None`).
            if e.name in self.ctor_env and not self.ctor_env[e.name][1]:
                return glass.TyADT(self.ctor_env[e.name][0], ())
            t = self.type_env.get(e.name)
            if t is None:
                raise NameError(f"Quartz: unbound identifier: {e.name}")
            return t
        if isinstance(e, glass.BinOp):
            if e.op in ("<", ">", "<=", ">=", "==", "!="):
                return glass.TyBool()
            if e.op in ("&&", "||"):
                return glass.TyBool()
            if e.op in ("+", "-", "*", "/", "%"):
                return glass.TyInt()
            if e.op == "++":
                # v4.32: ++ is polymorphic over String and List. Look at
                # the lhs type to decide which.
                lt = self.type_of(e.lhs)
                if isinstance(lt, glass.TyList):
                    return lt
                return glass.TyString()
            raise NotImplementedError(f"Quartz v3.0 op: {e.op}")
        if isinstance(e, glass.UnaryNot):
            return glass.TyBool()
        if isinstance(e, glass.If):
            return self.type_of(e.then_b)
        if isinstance(e, glass.LetIn):
            saved = self.type_env.get(e.name)
            # v4.37: prefer the user's annotation when present — it
            # carries the resolved type args for generic ADTs (e.g.,
            # `let x : Option<Int> = None`), which Quartz's lightweight
            # type_of can't infer from a bare `None`.
            self.type_env[e.name] = (
                e.ann if e.ann is not None else self.type_of(e.value)
            )
            t = self.type_of(e.body)
            if saved is None:
                self.type_env.pop(e.name, None)
            else:
                self.type_env[e.name] = saved
            return t
        if isinstance(e, glass.Call):
            # v4.44: extended to indirect calls. If the callee isn't a
            # known Ident, evaluate its type and project to ret_ty.
            if not isinstance(e.fn, glass.Ident):
                callee_ty = self.type_of(e.fn)
                if not isinstance(callee_ty, glass.TyFn):
                    raise NotImplementedError(
                        f"Quartz: indirect call requires a TyFn callee; "
                        f"got {type(callee_ty).__name__}"
                    )
                return callee_ty.ret
            # v4.38: builtins (string_length, substring, int_to_string).
            # v4.72: a USER fn of the same name SHADOWS the builtin — in
            # the host, a top-level `fn char_at(...) : String` overwrites
            # the builtin in the env (prism does exactly this — its
            # char_at returns a 1-char String, not the builtin's Int
            # codepoint). So we skip the builtin branch when the name is
            # a user fn, and fall through to fn_signatures below.
            if e.fn.name in QUARTZ_BUILTINS and e.fn.name not in self.fn_signatures:
                params, ret_ty, _emit = QUARTZ_BUILTINS[e.fn.name]
                # v4.39: for builtins with TyVar params/returns (list
                # ops, head/tail), substitute the TyVar against the
                # actual arg type so the caller sees a concrete ret.
                # This mirrors the generic-fn-call inference at line ~285.
                if any(_contains_tyvar(t) for t in params) or _contains_tyvar(ret_ty):
                    arg_tys = [self.type_of(a) for a in e.args]
                    subst: dict = {}
                    for formal, actual in zip(params, arg_tys):
                        _unify_into_subst(formal, actual, subst)
                    return _substitute_ty(ret_ty, subst)
                return ret_ty
            sig = self.fn_signatures.get(e.fn.name)
            if sig is not None:
                param_tys, ret_ty = sig
                # Generic fn? If any formal contains a TyVar, instantiate.
                if (any(_contains_tyvar(t) for t in param_tys)
                        or _contains_tyvar(ret_ty)):
                    arg_tys = [self.type_of(a) for a in e.args]
                    subst: dict = {}
                    for formal, actual in zip(param_tys, arg_tys):
                        _unify_into_subst(formal, actual, subst)
                    return _substitute_ty(ret_ty, subst)
                return ret_ty
            if e.fn.name in self.ctor_env:
                # v4.37: infer the TyADT's type args from the ctor's
                # argument types. For a generic ADT like `Option<T>`
                # with `Some(T)`, calling `Some(42)` unifies T against
                # TyInt and produces TyADT("Option", (TyInt,)). Mirrors
                # the generic-fn-call path above. Zero-arg ctors of
                # generic ADTs (e.g. `None`) leave the args at TyVar —
                # context (let annotation, fn signature) usually fills
                # in the right type at the use site.
                parent_name, field_tys = self.ctor_env[e.fn.name]
                params = self.adt_params.get(parent_name, [])
                if not params:
                    return glass.TyADT(parent_name, ())
                subst: dict = {}
                arg_tys = [self.type_of(a) for a in e.args]
                for formal, actual in zip(field_tys, arg_tys):
                    _unify_into_subst(formal, actual, subst)
                resolved = tuple(
                    subst.get(p, glass.TyVar(p)) for p in params
                )
                return glass.TyADT(parent_name, resolved)
            # v4.44: let-bound closure? Same shape as a literal lambda
            # at the call site — type_env carries a TyFn, and we
            # project to its ret.
            callee_ty = self.type_env.get(e.fn.name)
            if callee_ty is not None and isinstance(callee_ty, glass.TyFn):
                return callee_ty.ret
            raise NameError(
                f"Quartz: unknown function or constructor in call: {e.fn.name}"
            )
        if isinstance(e, glass.Match):
            if not e.arms:
                raise ValueError("Quartz: match with no arms")
            # All arms have the same type — peek the first body.
            # Bind pattern variables (without emitting C) so the body
            # type-checks; restore after.
            scrut_ty = self.type_of(e.scrutinee)
            first_pat, first_body = e.arms[0]
            bindings = self._collect_pattern_bindings(first_pat, scrut_ty)
            saved = {n: self.type_env.get(n) for n, _ in bindings}
            for n, t in bindings:
                self.type_env[n] = t
            body_ty = self.type_of(first_body)
            for n, _ in bindings:
                if saved[n] is None:
                    self.type_env.pop(n, None)
                else:
                    self.type_env[n] = saved[n]
            return body_ty
        if isinstance(e, glass.RecordLit):
            return glass.TyADT(e.name, ())
        if isinstance(e, glass.TupleLit):
            # v4.30: tuple type follows from its element types.
            return glass.TyTuple(tuple(self.type_of(it) for it in e.items))
        if isinstance(e, glass.ListLit):
            # v4.31: list type is List<elem_ty>. Empty list defaults to
            # List<Int> as a placeholder — the actual element type is
            # irrelevant at runtime (no fields to extract) and Quartz's
            # downstream cast sites use the consumer's expected type.
            if not e.items:
                return glass.TyList(glass.TyInt())
            elem_ty = self.type_of(e.items[0])
            return glass.TyList(elem_ty)
        if isinstance(e, glass.Lambda):
            # v4.44: Lambda type is TyFn(param_tys, body_ty, pure).
            # v4.46: multi-param lambdas now supported. The body type
            # is computed under all param bindings.
            param_tys = tuple(p_ty for _, p_ty in e.params)
            saved = {
                p_name: self.type_env.get(p_name)
                for p_name, _ in e.params
            }
            for p_name, p_ty in e.params:
                self.type_env[p_name] = p_ty
            body_ty = self.type_of(e.body)
            for p_name, _ in e.params:
                if saved[p_name] is None:
                    self.type_env.pop(p_name, None)
                else:
                    self.type_env[p_name] = saved[p_name]
            return glass.TyFn(param_tys, body_ty, glass.PURE)
        if isinstance(e, glass.FieldAccess):
            rec_ty = self.type_of(e.record)
            if not isinstance(rec_ty, glass.TyADT):
                raise TypeError(
                    f"Quartz: field access requires a record value; got {rec_ty}"
                )
            if rec_ty.name not in self.record_env:
                raise NameError(
                    f"Quartz: '{rec_ty.name}' is not a record type"
                )
            fields = self.record_env[rec_ty.name]
            for fname, fty in fields:
                if fname == e.field:
                    return fty
            raise NameError(
                f"Quartz: record '{rec_ty.name}' has no field '{e.field}'"
            )
        raise NotImplementedError(
            f"Quartz v3.0 cannot type: {type(e).__name__}"
        )

    def _collect_pattern_bindings(self, pat, scrut_ty):
        """Return a list of (var_name, ty) introduced by matching `pat`
        against a scrutinee of type `scrut_ty`. No C emitted — this is
        a pure traversal used by type_of(Match)."""
        bindings: list[tuple[str, glass.Ty]] = []
        if pat.kind == "wild":
            return bindings
        if pat.kind == "ident":
            bindings.append((pat.value, scrut_ty))
            return bindings
        if pat.kind == "ctor":
            ctor_name = pat.value
            if ctor_name not in self.ctor_env:
                raise NameError(
                    f"Quartz: unknown constructor in pattern: {ctor_name}"
                )
            parent, field_tys = self.ctor_env[ctor_name]
            # v4.71: specialise generic field types with the scrutinee's
            # type args (mirrors the codegen path), so nested patterns
            # see concrete field types.
            if isinstance(scrut_ty, glass.TyADT):
                params = self.adt_params.get(parent, [])
                if params and len(params) == len(scrut_ty.args):
                    subst = dict(zip(params, scrut_ty.args))
                    field_tys = [_substitute_ty(ft, subst) for ft in field_tys]
            sub_pats = pat.args if pat.args is not None else []
            if len(sub_pats) != len(field_tys):
                raise ValueError(
                    f"Quartz: constructor {ctor_name} expects "
                    f"{len(field_tys)} fields, got {len(sub_pats)}"
                )
            # v4.71: recurse into sub-patterns (nested ctor/tuple/cons
            # now allowed, matching the recursive codegen binder).
            for sub, field_ty in zip(sub_pats, field_tys):
                bindings.extend(self._collect_pattern_bindings(sub, field_ty))
            return bindings
        if pat.kind == "record":
            rec_name = pat.value
            if rec_name not in self.record_env:
                raise NameError(
                    f"Quartz: unknown record in pattern: {rec_name}"
                )
            fields = self.record_env[rec_name]
            # `args` is a list[str] of field names the user wants to bind.
            field_names = pat.args if pat.args is not None else []
            field_ty_map = {fn: ft for fn, ft in fields}
            for fn in field_names:
                if fn not in field_ty_map:
                    raise NameError(
                        f"Quartz: record '{rec_name}' has no field '{fn}'"
                    )
                bindings.append((fn, field_ty_map[fn]))
            return bindings
        if pat.kind == "tuple":
            # v4.30: tuple destructuring. The scrutinee type must be a
            # TyTuple of the same arity, and each sub-pattern binds the
            # corresponding element type.
            if not isinstance(scrut_ty, glass.TyTuple):
                raise TypeError(
                    f"Quartz: tuple pattern against non-tuple type {scrut_ty}"
                )
            sub_pats = pat.args if pat.args is not None else []
            if len(sub_pats) != len(scrut_ty.items):
                raise TypeError(
                    f"Quartz: tuple pattern arity {len(sub_pats)} doesn't "
                    f"match scrutinee arity {len(scrut_ty.items)}"
                )
            for sub_p, fld_ty in zip(sub_pats, scrut_ty.items):
                bindings.extend(self._collect_pattern_bindings(sub_p, fld_ty))
            return bindings
        if pat.kind == "nil":
            # v4.31: nil binds nothing.
            if not isinstance(scrut_ty, glass.TyList):
                raise TypeError(
                    f"Quartz: nil pattern against non-list type {scrut_ty}"
                )
            return bindings
        if pat.kind == "cons":
            # v4.31: cons binds the head as elem_ty and the tail as List<elem_ty>.
            if not isinstance(scrut_ty, glass.TyList):
                raise TypeError(
                    f"Quartz: cons pattern against non-list type {scrut_ty}"
                )
            elem_ty = scrut_ty.elem
            if pat.head is not None:
                bindings.extend(
                    self._collect_pattern_bindings(pat.head, elem_ty)
                )
            if pat.tail is not None:
                bindings.extend(
                    self._collect_pattern_bindings(
                        pat.tail, glass.TyList(elem_ty)
                    )
                )
            return bindings
        if pat.kind in ("int", "bool", "string"):
            # v4.71: literal patterns match by value and bind nothing.
            return bindings
        raise NotImplementedError(
            f"Quartz: top-level pattern {pat.kind!r} not supported "
            f"(supported: `wild`, `ident`, `ctor`, `record`, `tuple`, "
            f"`nil`, `cons`, `int`, `bool`, `string`)"
        )

    def _bridge_args(self, args_exprs, param_tys):
        """v4.43: shared cast-bridge for call sites whose args' C type
        may differ from each formal's. Pattern-bound values are erased
        to int64_t at binding time; their C type rarely matches a
        formal of e.g. q_value_t* or const char*. The intptr_t cast
        bridges either direction.

        Previously open-coded at three call sites (v4.22 generic fn
        calls, v4.32 list ++ args — implicitly relied on q_value_t*
        matching, v4.39 builtin calls). v4.43 factors them all to
        this helper.

        Returns the list of bridged C atoms ready to drop into a call.
        """
        atoms = []
        for arg, formal in zip(args_exprs, param_tys):
            atom = self.emit_expr(arg)
            formal_c = c_type_for_ty(formal)
            if formal_c == "int64_t":
                atom = f"(int64_t)(intptr_t)({atom})"
            elif formal_c in ("q_value_t*", "const char*"):
                atom = f"({formal_c})(intptr_t)({atom})"
            # bool: C auto-converts; no explicit cast needed.
            atoms.append(atom)
        return atoms

    def _pattern_names(self, pat) -> set:
        """v4.45: collect names bound by a Pattern. Used by free-var
        analysis to extend `bound` across match arms.
        """
        if pat.kind == "wild":
            return set()
        if pat.kind == "ident":
            return {pat.value}
        if pat.kind in ("ctor", "tuple"):
            s = set()
            for sub in (pat.args or []):
                s |= self._pattern_names(sub)
            return s
        if pat.kind == "cons":
            s = set()
            if pat.head is not None:
                s |= self._pattern_names(pat.head)
            if pat.tail is not None:
                s |= self._pattern_names(pat.tail)
            return s
        if pat.kind == "record":
            # Record patterns bind field names directly.
            return set(pat.args or [])
        # int/bool/string/nil literal patterns bind nothing.
        return set()

    def _free_vars(self, node, bound: set) -> set:
        """v4.45: identifiers referenced in `node` that aren't in
        `bound` and aren't globals (top-level fns, ctors, builtins).
        Used by _lift_lambda to figure out which outer-scope names a
        lambda captures.

        Walks every AST node shape that can contain or shadow
        identifiers (Ident, BinOp, If, LetIn, Lambda, Call, Match,
        TupleLit, ListLit, RecordLit, FieldAccess). Literal nodes
        and pattern atoms have no free vars.
        """
        if isinstance(node, (glass.IntLit, glass.BoolLit, glass.StringLit)):
            return set()
        if isinstance(node, glass.Ident):
            name = node.name
            if name in bound:
                return set()
            # Globals — never captured. Top-level fns and ctors are
            # available everywhere; builtins are dispatched without an
            # env lookup. Filtering them keeps the capture list small.
            if name in self.fn_signatures:
                return set()
            if name in self.ctor_env:
                return set()
            if name in QUARTZ_BUILTINS:
                return set()
            return {name}
        if isinstance(node, glass.BinOp):
            return (self._free_vars(node.lhs, bound)
                    | self._free_vars(node.rhs, bound))
        if isinstance(node, glass.If):
            return (self._free_vars(node.cond, bound)
                    | self._free_vars(node.then_b, bound)
                    | self._free_vars(node.else_b, bound))
        if isinstance(node, glass.LetIn):
            return (self._free_vars(node.value, bound)
                    | self._free_vars(node.body, bound | {node.name}))
        if isinstance(node, glass.Lambda):
            new_bound = bound | {p_name for p_name, _ in node.params}
            return self._free_vars(node.body, new_bound)
        if isinstance(node, glass.Call):
            s = self._free_vars(node.fn, bound)
            for a in node.args:
                s |= self._free_vars(a, bound)
            return s
        if isinstance(node, glass.Match):
            s = self._free_vars(node.scrutinee, bound)
            for pat, arm_body in node.arms:
                s |= self._free_vars(
                    arm_body, bound | self._pattern_names(pat)
                )
            return s
        if isinstance(node, (glass.TupleLit, glass.ListLit)):
            s = set()
            for it in node.items:
                s |= self._free_vars(it, bound)
            return s
        if isinstance(node, glass.RecordLit):
            s = set()
            for _fname, fval in node.fields:
                s |= self._free_vars(fval, bound)
            return s
        if isinstance(node, glass.FieldAccess):
            return self._free_vars(node.record, bound)
        # Defensive fallback for unknown node shapes.
        return set()

    def _lift_lambda(self, lambda_node):
        """v4.44/4.45: convert a Lambda AST node into a generated
        static C function and add it to the shared lifted_lambdas
        list. Returns (fn_name, captures) where captures is the list
        of outer-scope names this lambda closes over. The caller uses
        captures to populate __env->fields[1..] at construction.

        The fn signature is uniform:

            int64_t __lambda_N(q_value_t* __env, int64_t __arg)

        Caller and callee both cast through intptr_t at the call site,
        so this single shape covers every lambda regardless of its
        actual param/return types.

        v4.45: captures land via free-variable analysis. The lifted
        fn unpacks them from __env->fields[1..] at the top of the
        body and binds them as local C vars matching their original
        Glass types.
        """
        # Fresh name from the shared counter (a 1-elt list to share
        # mutability across Codegen instances).
        n = self.lambda_counter[0]
        self.lambda_counter[0] = n + 1
        fn_name = f"__lambda_{n}"
        # v4.46: multi-param lambdas allowed. The lifted fn takes
        # `n` int64_t args after `__env`; indirect calls pass them
        # with matching arity via a dynamic fn-pointer cast.
        params = list(lambda_node.params)
        param_names = {p_name for p_name, _ in params}
        # v4.45: free-variable analysis — what does the body reference
        # from the enclosing scope? Sorted for deterministic ordering;
        # the unpack order in the lifted fn matches the field order at
        # the construction site.
        captures = sorted(self._free_vars(lambda_node.body, param_names))
        # Stash the outer Codegen state so we can emit the body into
        # a fresh stmts buffer; we don't want body statements
        # contaminating the caller's stmt list.
        saved_stmts = self.stmts
        saved_env = dict(self.type_env)
        # Look up each capture's type from the outer scope. If a
        # capture isn't in type_env (e.g., a recursive let-rec where
        # the name is bound but its type isn't tracked yet), fall
        # through to int64_t as a defensive default.
        capture_tys: dict[str, glass.Ty] = {}
        for cap_name in captures:
            cap_ty = saved_env.get(cap_name)
            if cap_ty is None:
                # Best-effort default — TyInt is the safe fallback
                # because int64_t is the erasure for any value
                # passed through the intptr_t bridge.
                cap_ty = glass.TyInt()
            capture_tys[cap_name] = cap_ty
        # Build lifted fn body in a fresh stmts buffer. Type env has
        # all params + captures so the body's emit_expr sees them as
        # ordinary locals.
        self.stmts = []
        for p_name, p_ty in params:
            self.type_env[p_name] = p_ty
        for cap_name in captures:
            self.type_env[cap_name] = capture_tys[cap_name]
        body_atom = self.emit_expr(lambda_node.body)
        body_stmts = list(self.stmts)
        # Restore.
        self.stmts = saved_stmts
        self.type_env = saved_env
        # Build the lifted fn signature: __env then one int64_t per param.
        sig_params = (
            ["q_value_t* __env"]
            + [f"int64_t __arg{i}" for i in range(len(params))]
        )
        sig = ", ".join(sig_params)
        # Capture unpacks at the top of the body.
        capture_lines: list[str] = []
        for i, cap_name in enumerate(captures):
            cap_ty = capture_tys[cap_name]
            cap_c = c_type_for_ty(cap_ty)
            capture_lines.append(
                f"    {cap_c} {mangle(cap_name)} = "
                f"({cap_c})(intptr_t)__env->fields[{i + 1}];"
            )
        capture_block = (
            "\n".join(capture_lines) + "\n" if capture_lines else ""
        )
        # When there are no captures, mark __env as unused so the
        # compiler doesn't warn.
        env_use = (
            "    (void)__env;\n" if not captures else ""
        )
        # Param bindings: each __arg<i> cast to its param's C type.
        # v4.50: emit a refinement guard immediately after each param
        # binding when the param's declared type is TyRefine. Mirrors
        # the top-level fn-decl path in compile_program — the guard
        # fires on every lambda application, including from inside
        # map / filter / fold, so refined lambda params get enforced
        # whatever the indirect call chain looks like.
        param_lines: list[str] = []
        for i, (p_name, p_ty) in enumerate(params):
            p_c = c_type_for_ty(p_ty)
            param_lines.append(
                f"    {p_c} {mangle(p_name)} = "
                f"({p_c})(intptr_t)__arg{i};"
            )
            if isinstance(p_ty, glass.TyRefine):
                param_lines.extend(_emit_refinement_check(p_name, p_ty))
        param_block = "\n".join(param_lines) + "\n"
        body_indented = "\n    ".join(body_stmts)
        body_block = (
            f"    {body_indented}\n    " if body_stmts else "    "
        )
        fn_def = (
            f"static int64_t {fn_name}({sig}) {{\n"
            f"{env_use}"
            f"{capture_block}"
            f"{param_block}"
            f"{body_block}"
            f"return (int64_t)(intptr_t)({body_atom});\n"
            f"}}"
        )
        self.lifted_lambdas.append(fn_def)
        return fn_name, captures

    def _emit_named_fn_call(self, e, name: str) -> str:
        """v4.44 extraction: emit a call to a top-level fn declared in
        fn_signatures. Previously inlined in emit_expr's Call branch.
        """
        param_tys, ret_ty = self.fn_signatures[name]
        is_generic = (any(_contains_tyvar(t) for t in param_tys)
                      or _contains_tyvar(ret_ty))
        if not is_generic:
            arg_atoms = [self.emit_expr(a) for a in e.args]
            return f"{mangle(name)}({', '.join(arg_atoms)})"
        # Generic call. Determine substitution from concrete arg types
        # so we can cast the result back to its instantiation type.
        arg_tys = [self.type_of(a) for a in e.args]
        subst: dict = {}
        for formal, actual in zip(param_tys, arg_tys):
            _unify_into_subst(formal, actual, subst)
        # v4.43: cast-bridge factored into _bridge_args.
        arg_atoms = self._bridge_args(e.args, param_tys)
        call_str = f"{mangle(name)}({', '.join(arg_atoms)})"
        # Cast the result back if the return slot was a TyVar that
        # resolved to something with a different C representation.
        if _contains_tyvar(ret_ty):
            concrete = _substitute_ty(ret_ty, subst)
            if not _contains_tyvar(concrete):
                c_ty = c_type_for_ty(concrete)
                if c_ty != "int64_t":
                    call_str = f"({c_ty})(intptr_t)({call_str})"
        return call_str

    def _emit_indirect_call(self, e) -> str:
        """v4.44/4.46: call a closure value through fields[0]. Used
        when the callee isn't a known Ident (e.g., a Lambda
        expression) or when an Ident resolves to a let-bound TyFn
        value.

        The closure value is a q_value_t* whose fields[0] holds a
        function pointer with the uniform shape
        `int64_t (*)(q_value_t*, int64_t, ..., int64_t)` — one
        int64_t per Glass param plus the env pointer up front. We
        bind the callee to a fresh var first so its expression is
        evaluated exactly once, then build the fn-pointer cast at
        the matching arity.

        v4.46: extended to multi-arg calls. Arity comes from
        `len(e.args)`. The host type-checker has already verified
        the call's arity matches the closure's TyFn.
        """
        # Evaluate callee + args in source order; stash callee in a
        # fresh var to avoid double-eval.
        callee_atom = self.emit_expr(e.fn)
        closure_var = self.fresh()
        self.stmts.append(f"q_value_t* {closure_var} = {callee_atom};")
        arg_atoms = [self.emit_expr(a) for a in e.args]
        # Build the fn-pointer cast signature based on arity.
        n = len(arg_atoms)
        fn_ptr_sig = ", ".join(["q_value_t*"] + ["int64_t"] * n)
        args_passed = ", ".join(
            [closure_var]
            + [f"(int64_t)(intptr_t)({a})" for a in arg_atoms]
        )
        call_expr = (
            f"((int64_t (*)({fn_ptr_sig}))(intptr_t)"
            f"{closure_var}->fields[0])({args_passed})"
        )
        # The lifted fn returns int64_t; cast back to the call's
        # expected C type when it's a pointer/bool type.
        ret_ty = self.type_of(e)
        ret_c = c_type_for_ty(ret_ty)
        if ret_c == "int64_t":
            return call_expr
        return f"({ret_c})(intptr_t)({call_expr})"

    def emit_expr(self, e) -> str:
        """Emit statements for e and return a C atom for its value."""
        if isinstance(e, glass.IntLit):
            return str(e.value)
        if isinstance(e, glass.BoolLit):
            return "true" if e.value else "false"
        if isinstance(e, glass.StringLit):
            return c_string_literal(e.value)
        if isinstance(e, glass.Ident):
            # 0-arg constructor used as a bare expression — allocate it.
            if e.name in self.ctor_env and not self.ctor_env[e.name][1]:
                tag = self.ctor_tags[e.name]
                return f"q_ctor_alloc({tag}, 0)"
            if e.name not in self.type_env:
                raise NameError(f"Quartz: unbound identifier: {e.name}")
            return mangle(e.name)
        if isinstance(e, glass.BinOp):
            l = self.emit_expr(e.lhs)
            r = self.emit_expr(e.rhs)
            if e.op == "++":
                # v4.32: ++ is polymorphic. Inspect the lhs type to
                # pick string-concat vs list-concat. Pre-v4.32 always
                # emitted quartz_str_concat, which silently miscompiled
                # list-concat programs (the list pointers were read as
                # null-terminated chars → garbage).
                lt = self.type_of(e.lhs)
                if isinstance(lt, glass.TyList):
                    return f"quartz_list_concat({l}, {r})"
                # String concatenation. Calls the runtime helper which
                # heap-allocates a fresh result. The helper is emitted at
                # the top of every Quartz-compiled program; the C linker
                # strips it as dead code if unused.
                return f"quartz_str_concat({l}, {r})"
            if e.op == "==" or e.op == "!=":
                # v4.33: == / != on Strings now does content comparison
                # via quartz_str_eq, matching Glass semantics. Pre-v4.33
                # used plain C `==` on `const char*` — pointer compare —
                # which happened to work for equal string literals (C
                # compilers dedupe them) but failed for any string that
                # came from `++` or other allocation.
                #
                # v4.34: structural equality now extends to List<P> and
                # Tuple<P, ...> when every P is a primitive (Int/Bool/
                # String). The codegen emits a loop (lists) or a
                # sequence of typed compares (tuples) as statements and
                # returns a fresh result var. Non-primitive elements
                # (nested lists, lists of tuples, ADTs, etc.) still
                # error loudly — recursive codegen is deferred.
                lt = self.type_of(e.lhs)
                base_atom = self._emit_eq_atom(l, r, lt)
                return base_atom if e.op == "==" else f"(!{base_atom})"
            op = BIN_OP_C.get(e.op)
            if op is None:
                raise NotImplementedError(f"Quartz v3.0 op: {e.op}")
            return f"({l} {op} {r})"
        if isinstance(e, glass.UnaryNot):
            # v4.54: logical NOT. C's `!` maps 1:1 to Glass's `!`;
            # the typechecker has already ensured the operand is Bool
            # so no cast is needed.
            inner = self.emit_expr(e.expr)
            return f"(!{inner})"
        if isinstance(e, glass.If):
            cond = self.emit_expr(e.cond)
            t_ty = self.type_of(e.then_b)
            c_ty = c_type_for_ty(t_ty)
            var = self.fresh()
            self.stmts.append(f"{c_ty} {var};")
            self.stmts.append(f"if ({cond}) {{")
            then_atom = self.emit_expr(e.then_b)
            self.stmts.append(f"  {var} = {then_atom};")
            self.stmts.append(f"}} else {{")
            else_atom = self.emit_expr(e.else_b)
            self.stmts.append(f"  {var} = {else_atom};")
            self.stmts.append("}")
            return var
        if isinstance(e, glass.LetIn):
            # v4.50: a refined `let x : T where (pred) = ... in ...`
            # ann carries the TyRefine. Prefer the annotation for the
            # declared C type so the variable is exactly what the user
            # wrote (matches the LetDecl path in pass 3).
            val_ty = e.ann if e.ann is not None else self.type_of(e.value)
            val_atom = self.emit_expr(e.value)
            c_ty = c_type_for_ty(val_ty)
            # v4.71: `_` is a throwaway binding — never referenced, and
            # repeated `let _ = ...` would collide as C variables. Emit
            # the value for its side effects and discard it, don't bind.
            if e.name == "_":
                self.stmts.append(f"(void)({val_atom});")
            else:
                self.stmts.append(f"{c_ty} {mangle(e.name)} = {val_atom};")
            if isinstance(e.ann, glass.TyRefine):
                self.stmts.extend(_emit_refinement_check(e.name, e.ann))
            saved = self.type_env.get(e.name)
            self.type_env[e.name] = val_ty
            body_atom = self.emit_expr(e.body)
            # Glass's let-in scopes the binding, but C function-scoped
            # variables persist. For v3.0 we don't worry about shadowing —
            # the parser already prevents most issues, and identifier names
            # collide loudly via C if they do.
            if saved is None:
                self.type_env.pop(e.name, None)
            else:
                self.type_env[e.name] = saved
            return body_atom
        if isinstance(e, glass.Call):
            # v3.1: top-level fn calls. v3.2: also constructor application.
            # v4.44: indirect calls through a closure value (Lambda or
            # any let-bound TyFn).
            #
            # Try Ident-based dispatch first (named fn / ctor / builtin).
            # If the callee isn't an Ident, or the Ident doesn't name a
            # known callable, fall through to the indirect-call path
            # which evaluates the callee as a q_value_t* closure and
            # dispatches through fields[0].
            if isinstance(e.fn, glass.Ident):
                name = e.fn.name
                # v4.72: a user fn of the same name SHADOWS the builtin
                # (the host overwrites the builtin in its env when a
                # top-level `fn` is declared — prism's `char_at` returns
                # a String, not the builtin's Int). Skip the builtin
                # branch for names that are user fns; they're handled by
                # the fn_signatures dispatch below.
                if name in QUARTZ_BUILTINS and name not in self.fn_signatures:
                    param_tys, _ret_ty, emit_fn = QUARTZ_BUILTINS[name]
                    arg_atoms = self._bridge_args(e.args, param_tys)
                    return emit_fn(arg_atoms, self)
                # Constructor application?
                if name in self.ctor_env:
                    tag = self.ctor_tags[name]
                    arg_atoms = [self.emit_expr(a) for a in e.args]
                    if not arg_atoms:
                        return f"q_ctor_alloc({tag}, 0)"
                    casted = ", ".join(
                        f"(int64_t)(intptr_t){a}" for a in arg_atoms
                    )
                    return (
                        f"q_ctor_alloc({tag}, {len(arg_atoms)}, {casted})"
                    )
                # Top-level fn call?
                if name in self.fn_signatures:
                    return self._emit_named_fn_call(e, name)
                # Otherwise fall through to indirect call below.
            return self._emit_indirect_call(e)
        if isinstance(e, glass.Match):
            return self._emit_match(e)
        if isinstance(e, glass.RecordLit):
            if e.name not in self.record_env:
                raise NameError(f"Quartz: unknown record type: {e.name}")
            fields = self.record_env[e.name]  # declaration order
            # Reorder user-provided field values to match declaration order.
            user_map = {fn: fv for fn, fv in e.fields}
            for fn, _ in fields:
                if fn not in user_map:
                    raise ValueError(
                        f"Quartz: record '{e.name}' missing field '{fn}'"
                    )
            ordered_atoms = [self.emit_expr(user_map[fn]) for fn, _ in fields]
            tag = self.ctor_tags[e.name]
            casted = ", ".join(f"(int64_t)(intptr_t){a}" for a in ordered_atoms)
            return f"q_ctor_alloc({tag}, {len(ordered_atoms)}, {casted})"
        if isinstance(e, glass.TupleLit):
            # v4.30: a tuple `(a, b, c)` lowers to the same boxed
            # q_value_t* representation as ADTs. We don't tag-dispatch on
            # tuples (the type system already knows the shape), so the
            # tag value itself is irrelevant — we use 0. Destructuring
            # in match codegen reads `fields[i]` directly without
            # checking the tag.
            element_atoms = [self.emit_expr(it) for it in e.items]
            casted = ", ".join(
                f"(int64_t)(intptr_t){a}" for a in element_atoms
            )
            return f"q_ctor_alloc(0, {len(element_atoms)}, {casted})"
        if isinstance(e, glass.ListLit):
            # v4.31: lower [a, b, c] to a nested cons chain.
            #   []         => q_ctor_alloc(0, 0)
            #   [a, ...t]  => q_ctor_alloc(0, 2, a, t)
            # Build right-to-left so each cons cell references the
            # already-built tail.
            chain = "q_ctor_alloc(0, 0)"
            for it in reversed(e.items):
                head_atom = self.emit_expr(it)
                chain = (
                    f"q_ctor_alloc(0, 2, "
                    f"(int64_t)(intptr_t){head_atom}, "
                    f"(int64_t)(intptr_t){chain})"
                )
            return chain
        if isinstance(e, glass.Lambda):
            # v4.44/4.45: lambda-lifting + capture marshalling. Lift the
            # body to a generated static fn; the returned captures list
            # names the outer-scope vars to pack into fields[1..]. Each
            # capture's atom is the mangled local name (it's in scope
            # at the construction site by definition of being a free
            # variable of the lambda's body).
            fn_name, captures = self._lift_lambda(e)
            field_atoms = [f"(int64_t)(intptr_t){fn_name}"]
            for cap_name in captures:
                field_atoms.append(
                    f"(int64_t)(intptr_t){mangle(cap_name)}"
                )
            n_fields = 1 + len(captures)
            # Tag value is irrelevant; closures aren't tag-dispatched.
            return (
                f"q_ctor_alloc(0, {n_fields}, "
                + ", ".join(field_atoms)
                + ")"
            )
        if isinstance(e, glass.FieldAccess):
            rec_atom = self.emit_expr(e.record)
            rec_ty = self.type_of(e.record)
            if not isinstance(rec_ty, glass.TyADT):
                raise TypeError(
                    f"Quartz: field access requires a record value; got {rec_ty}"
                )
            fields = self.record_env[rec_ty.name]
            field_ty = None
            field_idx = None
            for i, (fn, ft) in enumerate(fields):
                if fn == e.field:
                    field_idx, field_ty = i, ft
                    break
            if field_idx is None:
                raise NameError(
                    f"Quartz: record '{rec_ty.name}' has no field '{e.field}'"
                )
            c_ty = c_type_for_ty(field_ty)
            # Wrap rec_atom in parens so chained field access (a.b.c) groups
            # correctly under C's precedence rules (`->` binds tighter than
            # cast). Without the parens, `(T*)(intptr_t)a->fields[i]->fields[j]`
            # parses as `(T*)(intptr_t)((a->fields[i])->fields[j])` — the
            # cast doesn't bind to a->fields[i] before the second ->.
            return f"({c_ty})(intptr_t)({rec_atom})->fields[{field_idx}]"
        raise NotImplementedError(
            f"Quartz v3.0 cannot compile: {type(e).__name__}"
        )

    def _emit_eq_atom(self, l: str, r: str, ty) -> str:
        """v4.34: emit a C atom (variable or simple expression) whose
        value is true iff l and r are structurally equal at Glass-level
        type `ty`. For boxed-but-shallow types (List of primitives,
        Tuple of primitives), this appends a loop or a per-field
        compare chain to self.stmts and returns a fresh `bool` var
        name. For primitives, returns an inline expression. Anything
        deeper (nested lists, ADTs, records) raises with the same
        message v4.33 introduced.
        """
        # Primitives — inline expression, no statements emitted.
        if isinstance(ty, (glass.TyInt, glass.TyBool)):
            return f"({l} == {r})"
        if isinstance(ty, glass.TyString):
            return f"quartz_str_eq({l}, {r})"
        # List<P> for any P that _emit_eq_atom itself supports.
        # v4.35: recursion enabled — elements that are themselves
        # List/Tuple/primitive route through the appropriate arm; ADTs
        # still raise inside the recursive call so the loud error
        # surfaces with the type that triggered it.
        if isinstance(ty, glass.TyList):
            elem_ty = ty.elem
            a_var = self.fresh()
            b_var = self.fresh()
            eq_var = self.fresh()
            self.stmts.append(f"q_value_t* {a_var} = {l};")
            self.stmts.append(f"q_value_t* {b_var} = {r};")
            self.stmts.append(f"bool {eq_var} = true;")
            self.stmts.append(
                f"while ({a_var}->num_fields > 0 && "
                f"{b_var}->num_fields > 0) {{"
            )
            # Extract head from each side at the element's C type, then
            # recurse to build the per-element compare. For primitive
            # elements the recursion bottoms out in one line.
            c_ty = c_type_for_ty(elem_ty)
            head_a = f"({c_ty})(intptr_t){a_var}->fields[0]"
            head_b = f"({c_ty})(intptr_t){b_var}->fields[0]"
            elem_eq = self._emit_eq_atom(head_a, head_b, elem_ty)
            self.stmts.append(
                f"    if (!({elem_eq})) {{ {eq_var} = false; break; }}"
            )
            self.stmts.append(
                f"    {a_var} = "
                f"(q_value_t*)(intptr_t){a_var}->fields[1];"
            )
            self.stmts.append(
                f"    {b_var} = "
                f"(q_value_t*)(intptr_t){b_var}->fields[1];"
            )
            self.stmts.append("}")
            # Both lists must have ended at the same time.
            self.stmts.append(
                f"if ({eq_var}) {eq_var} = "
                f"({a_var}->num_fields == 0 && {b_var}->num_fields == 0);"
            )
            return eq_var
        # Tuple<P, ...> for any P that _emit_eq_atom supports. Like
        # the list case above, the per-field recursive call routes into
        # the right arm. ADT-typed fields propagate the loud error.
        if isinstance(ty, glass.TyTuple):
            a_var = self.fresh()
            b_var = self.fresh()
            eq_var = self.fresh()
            self.stmts.append(f"q_value_t* {a_var} = {l};")
            self.stmts.append(f"q_value_t* {b_var} = {r};")
            self.stmts.append(f"bool {eq_var} = true;")
            for i, elem_ty in enumerate(ty.items):
                c_ty = c_type_for_ty(elem_ty)
                a_field = f"({c_ty})(intptr_t){a_var}->fields[{i}]"
                b_field = f"({c_ty})(intptr_t){b_var}->fields[{i}]"
                elem_eq = self._emit_eq_atom(a_field, b_field, elem_ty)
                self.stmts.append(
                    f"if ({eq_var}) {eq_var} = ({elem_eq});"
                )
            return eq_var
        # v4.36: structural equality for TyADT covers records and
        # concrete sum types. Generic sum types (those with TyVar fields
        # in any variant) still error loudly — the substitution of the
        # TyADT's type args into the variant's field types is queued.
        if isinstance(ty, glass.TyADT):
            name = ty.name
            # Records: single tag, fields known concretely from
            # record_env. Field-by-field compare in declaration order.
            if name in self.record_env:
                fields = self.record_env[name]  # list of (fname, fty)
                a_var = self.fresh()
                b_var = self.fresh()
                eq_var = self.fresh()
                self.stmts.append(f"q_value_t* {a_var} = {l};")
                self.stmts.append(f"q_value_t* {b_var} = {r};")
                self.stmts.append(f"bool {eq_var} = true;")
                for i, (_fname, fty) in enumerate(fields):
                    c_ty = c_type_for_ty(fty)
                    a_field = f"({c_ty})(intptr_t){a_var}->fields[{i}]"
                    b_field = f"({c_ty})(intptr_t){b_var}->fields[{i}]"
                    elem_eq = self._emit_eq_atom(a_field, b_field, fty)
                    self.stmts.append(
                        f"if ({eq_var}) {eq_var} = ({elem_eq});"
                    )
                return eq_var
            # Sum types: enumerate variants from ctor_env, check tags
            # match, then per-variant field compare. v4.37: if the ADT
            # is generic (has type parameters), substitute the TyADT's
            # type args into the variant field types before emitting
            # the per-field compare. The substitution uses adt_params
            # for the param-name list and _substitute_ty for the walk.
            variants = [
                (cname, field_tys)
                for cname, (parent, field_tys) in self.ctor_env.items()
                if parent == name
            ]
            if not variants:
                raise NotImplementedError(
                    f"Quartz: structural equality on unknown TyADT "
                    f"{name!r}. Run through the host interpreter."
                )
            params = self.adt_params.get(name, [])
            if params:
                if len(params) != len(ty.args):
                    raise NotImplementedError(
                        f"Quartz: structural equality on {name!r}: "
                        f"type-arg count {len(ty.args)} doesn't match "
                        f"declared params {params}."
                    )
                subst = dict(zip(params, ty.args))
                variants = [
                    (cname, [_substitute_ty(ft, subst) for ft in ftys])
                    for cname, ftys in variants
                ]
                # After substitution any remaining TyVar means the type
                # is still abstract (e.g., comparing inside the body of
                # a generic fn that doesn't know its T yet). Defer.
                if any(_contains_tyvar(ft)
                       for _, ftys in variants for ft in ftys):
                    raise NotImplementedError(
                        f"Quartz: structural equality on {name!r} with "
                        f"unresolved TyVar fields after substitution. "
                        f"This usually means `==` is used inside a "
                        f"generic fn before T is concretized. Run "
                        f"through the host interpreter."
                    )
            a_var = self.fresh()
            b_var = self.fresh()
            eq_var = self.fresh()
            self.stmts.append(f"q_value_t* {a_var} = {l};")
            self.stmts.append(f"q_value_t* {b_var} = {r};")
            self.stmts.append(
                f"bool {eq_var} = ({a_var}->tag == {b_var}->tag);"
            )
            # Per-variant field compare. We need an outer `if ({eq_var})`
            # so that the variant-specific compares only fire when the
            # tags agreed. Inside, dispatch on the matching tag.
            self.stmts.append(f"if ({eq_var}) {{")
            for idx, (cname, ftys) in enumerate(variants):
                tag = self.ctor_tags[cname]
                keyword = "if" if idx == 0 else "else if"
                self.stmts.append(
                    f"    {keyword} ({a_var}->tag == {tag}) {{"
                )
                for i, fty in enumerate(ftys):
                    c_ty = c_type_for_ty(fty)
                    a_field = f"({c_ty})(intptr_t){a_var}->fields[{i}]"
                    b_field = f"({c_ty})(intptr_t){b_var}->fields[{i}]"
                    elem_eq = self._emit_eq_atom(a_field, b_field, fty)
                    self.stmts.append(
                        f"        if ({eq_var}) {eq_var} = ({elem_eq});"
                    )
                self.stmts.append("    }")
            # Safety: if the runtime tag matches NO known variant, the
            # type-checker should have prevented it but emit a defensive
            # fallthrough.
            self.stmts.append("    else {")
            self.stmts.append(f"        {eq_var} = false;")
            self.stmts.append("    }")
            self.stmts.append("}")
            return eq_var
        # Unknown type — error rather than silent miscompile.
        raise NotImplementedError(
            f"Quartz: structural equality on {type(ty).__name__} "
            f"is not yet supported."
        )

    def _emit_match(self, m: "glass.Match") -> str:
        """Emit a Match as an if/else chain over the scrutinee's tag,
        storing the chosen arm's value in a fresh result variable.
        v4.30: also accepts TyTuple scrutinees — tuple patterns always
        match (no tag dispatch), so the if/else chain collapses to a
        single arm but the binding code still fires."""
        scrut_ty = self.type_of(m.scrutinee)
        # v4.71: scalar scrutinees (Int/Bool/String) support literal
        # patterns (`match n { 0 => …; _ => … }`, char dispatch in the
        # lexer, etc.). They're stored in a scalar C var, not a
        # q_value_t*, and _pattern_test compares by value.
        scalar_scrut = isinstance(
            scrut_ty, (glass.TyInt, glass.TyBool, glass.TyString))
        if not (scalar_scrut
                or isinstance(scrut_ty, glass.TyADT)
                or isinstance(scrut_ty, glass.TyTuple)
                or isinstance(scrut_ty, glass.TyList)):
            raise NotImplementedError(
                f"Quartz: `match` is supported over ADT, tuple, list, and "
                f"scalar (Int/Bool/String) scrutinees; got {scrut_ty}"
            )
        scrut_atom = self.emit_expr(m.scrutinee)
        scrut_var = self.fresh()
        scrut_c = c_type_for_ty(scrut_ty) if scalar_scrut else "q_value_t*"
        self.stmts.append(f"{scrut_c} {scrut_var} = {scrut_atom};")
        # v4.30: stash scrut_ty so _emit_pattern_bindings can read element
        # types when the pattern is a tuple. v4.31: same stash is used by
        # cons patterns to determine the head element's C type. Set
        # unconditionally — non-tuple/non-list patterns ignore it.
        self._tuple_scrut_ty = scrut_ty
        # Compute the result type from any arm's body.
        result_ty = self.type_of(m)
        result_c = c_type_for_ty(result_ty)
        result_var = self.fresh()
        self.stmts.append(f"{result_c} {result_var};")
        # Emit each arm.
        for i, (pat, body) in enumerate(m.arms):
            cond = self._pattern_test(pat, scrut_var)
            keyword = "if" if i == 0 else "else if"
            self.stmts.append(f"{keyword} ({cond}) {{")
            bindings = self._emit_pattern_bindings(pat, scrut_var)
            # Track types for nested type_of calls inside the body.
            saved = {n: self.type_env.get(n) for n, _ in bindings}
            for n, t in bindings:
                self.type_env[n] = t
            body_atom = self.emit_expr(body)
            self.stmts.append(f"    {result_var} = {body_atom};")
            self.stmts.append("}")
            # Restore the type_env after the arm.
            for n, _ in bindings:
                if saved[n] is None:
                    self.type_env.pop(n, None)
                else:
                    self.type_env[n] = saved[n]
        # Fallback for non-exhaustive runtime hits — type-checker should
        # prevent this but we emit a safety net.
        self.stmts.append("else {")
        self.stmts.append(
            '    fprintf(stderr, "quartz: non-exhaustive match\\n"); '
            'exit(1);'
        )
        self.stmts.append("}")
        return result_var

    def _pattern_test(self, pat, scrut_var: str) -> str:
        """Return a C boolean expression that's true iff the pattern matches
        the value `scrut_var` (a C expression). Variable-binding patterns
        (wild, ident) always match, so emit `true`. Compound patterns
        (ctor/tuple/cons) RECURSE into their sub-patterns and AND the
        discriminating tests together — so `(TEnd, _)` tests that field 0
        is the TEnd ctor, not just that the scrutinee is some tuple. Without
        this, a tuple arm whose first element is a ctor would match every
        tuple (v4.73 fix: prism's tokenizer dispatches on `(TEnd, _)` etc.)."""
        k = pat.kind
        if k in ("wild", "ident"):
            return "true"
        if k == "int":
            return f"(({scrut_var}) == {pat.value}LL)"
        if k == "bool":
            return f"(({scrut_var}) == {'true' if pat.value else 'false'})"
        if k == "string":
            return (f"quartz_str_eq((const char*)(intptr_t)({scrut_var}), "
                    f"{c_string_literal(pat.value)})")
        # Compound patterns: cast to q_value_t* and test tag/shape + subs.
        holder = f"((q_value_t*)(intptr_t)({scrut_var}))"
        if k == "nil":
            return f"{holder}->num_fields == 0"
        if k == "record":
            rec_name = pat.value
            if rec_name not in self.ctor_tags:
                raise NameError(f"Quartz: unknown record in pattern: {rec_name}")
            # Record fields are idents (always match); only the tag matters.
            return f"{holder}->tag == {self.ctor_tags[rec_name]}"
        if k == "ctor":
            ctor_name = pat.value
            if ctor_name not in self.ctor_tags:
                raise NameError(
                    f"Quartz: unknown constructor in pattern: {ctor_name}")
            test = f"{holder}->tag == {self.ctor_tags[ctor_name]}"
            for i, sub in enumerate(pat.args or []):
                sub_t = self._pattern_test(sub, f"{holder}->fields[{i}]")
                if sub_t != "true":
                    test = f"({test} && {sub_t})"
            return test
        if k == "tuple":
            tests = []
            for i, sub in enumerate(pat.args or []):
                sub_t = self._pattern_test(sub, f"{holder}->fields[{i}]")
                if sub_t != "true":
                    tests.append(sub_t)
            return "(" + " && ".join(tests) + ")" if tests else "true"
        if k == "cons":
            test = f"{holder}->num_fields > 0"
            if pat.head is not None:
                ht = self._pattern_test(pat.head, f"{holder}->fields[0]")
                if ht != "true":
                    test = f"({test} && {ht})"
            if pat.tail is not None:
                tt = self._pattern_test(pat.tail, f"{holder}->fields[1]")
                if tt != "true":
                    test = f"({test} && {tt})"
            return test
        raise NotImplementedError(
            f"Quartz: pattern kind {pat.kind!r} not supported"
        )

    def _emit_pattern_bindings(self, pat, scrut_var: str) -> list:
        """Emit C bindings for a match arm's pattern. Delegates to the
        recursive _bind_pattern with the scrutinee's value + type."""
        bindings: list[tuple[str, glass.Ty]] = []
        self._bind_pattern(pat, scrut_var, self._tuple_scrut_ty, bindings)
        return bindings

    def _bind_pattern(self, pat, val_expr: str, val_ty, bindings: list) -> None:
        """v4.71: recursively emit C bindings for `pat` against the value
        `val_expr` (a C expression) of Glass type `val_ty`. Nested
        ctor/tuple/cons sub-patterns are handled by materializing the
        value into a temp and recursing on field accessors — so e.g.
        `[Pair(pat, body), ...rest]` binds `pat` and `body` from inside
        the cons head. Appends (name, ty) pairs to `bindings`."""
        k = pat.kind
        if k in ("wild", "int", "bool", "string", "nil"):
            return
        if k == "ident":
            c_ty = c_type_for_ty(val_ty)
            self.stmts.append(
                f"    {c_ty} {mangle(pat.value)} = "
                f"({c_ty})(intptr_t)({val_expr});"
            )
            bindings.append((pat.value, val_ty))
            return
        # Compound patterns need field access — materialize into a temp.
        holder = self.fresh()
        self.stmts.append(
            f"    q_value_t* {holder} = (q_value_t*)(intptr_t)({val_expr});"
        )
        if k == "ctor":
            parent, field_tys = self.ctor_env[pat.value]
            # Specialise generic field types with the value's type args
            # (Result<String,String> → Ok's field is String, not `A`).
            if isinstance(val_ty, glass.TyADT):
                params = self.adt_params.get(parent, [])
                if params and len(params) == len(val_ty.args):
                    subst = dict(zip(params, val_ty.args))
                    field_tys = [_substitute_ty(ft, subst) for ft in field_tys]
            for i, (sub, ft) in enumerate(
                zip(pat.args or [], field_tys)
            ):
                self._bind_pattern(sub, f"{holder}->fields[{i}]", ft, bindings)
            return
        if k == "record":
            fields = self.record_env[pat.value]
            idx_map = {fn: (i, ft) for i, (fn, ft) in enumerate(fields)}
            for fn in (pat.args or []):
                i, ft = idx_map[fn]
                c_ty = c_type_for_ty(ft)
                self.stmts.append(
                    f"    {c_ty} {mangle(fn)} = "
                    f"({c_ty})(intptr_t){holder}->fields[{i}];"
                )
                bindings.append((fn, ft))
            return
        if k == "tuple":
            items = val_ty.items if isinstance(val_ty, glass.TyTuple) else []
            for i, (sub, ft) in enumerate(zip(pat.args or [], items)):
                self._bind_pattern(sub, f"{holder}->fields[{i}]", ft, bindings)
            return
        if k == "cons":
            elem_ty = (val_ty.elem if isinstance(val_ty, glass.TyList)
                       else glass.TyVar("_"))
            if pat.head is not None:
                self._bind_pattern(
                    pat.head, f"{holder}->fields[0]", elem_ty, bindings)
            if pat.tail is not None:
                self._bind_pattern(
                    pat.tail, f"{holder}->fields[1]",
                    glass.TyList(elem_ty), bindings)
            return
        raise NotImplementedError(
            f"Quartz: pattern kind {pat.kind!r} not supported in binding"
        )


# === Top-level program compilation ======================================

def _collect_idents(node, acc=None) -> set:
    """v4.71: collect every identifier name referenced anywhere under
    `node` (a Node, or a list/tuple of them). Used to decide which
    prelude functions a program actually reaches. Generic recursive
    walk over dataclass fields — a `Call(fn=Ident("f"), ...)` surfaces
    "f"; Ty/Pattern leaves don't reference functions so they're ignored."""
    acc = acc if acc is not None else set()
    if isinstance(node, glass.Ident):
        acc.add(node.name)
    elif isinstance(node, glass.Node):
        for v in vars(node).values():
            _collect_idents(v, acc)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _collect_idents(v, acc)
    return acc


def compile_program(decls: list, checker=None) -> str:
    """Convert a parsed Glass program (list of decls) to C source.

    A program is a sequence of top-level decls. v3.4 supports:
      - LetDecl (top-level let bindings; top-level expressions are
        wrapped in LetDecl("_", ...) by the parser)
      - FnDecl (top-level functions; concrete-type, pure, no closures)
      - TypeDecl (ADTs, including generic)
      - RecordDecl (records, including generic)

    The LAST LetDecl is the "result" — its value is printed by the
    generated binary. FnDecls compile to C functions emitted above
    main(); LetDecls become C variable declarations inside main().

    If `checker` is provided (a glass.TypeChecker that has finished
    install_program), Quartz uses its registries to populate prelude
    ADT/record names and consults checker.env for the final expression's
    inferred concrete type — important when the apparent type is a
    polymorphic Option<T> but the actual instantiation is Option<Int>.
    """
    if not decls:
        raise ValueError("Quartz: empty program")

    # Separate FnDecls, LetDecls, TypeDecls, RecordDecls.
    fn_decls: list = []
    let_decls: list = []
    type_decls: list = []
    record_decls: list = []
    for d in decls:
        if isinstance(d, glass.FnDecl):
            fn_decls.append(d)
        elif isinstance(d, glass.LetDecl):
            let_decls.append(d)
        elif isinstance(d, glass.TypeDecl):
            type_decls.append(d)
        elif isinstance(d, glass.RecordDecl):
            record_decls.append(d)
        else:
            raise NotImplementedError(
                f"Quartz v3.3 does not support top-level {type(d).__name__}; "
                f"see docs/quartz.md for the v3.x roadmap"
            )

    # v4.71: dedupe FnDecls by name, keeping the LAST — matching the
    # host, where pass-1 installation lets a later `fn f` overwrite an
    # earlier one (prism.glass defines `empty_sub` twice). Without this
    # Quartz emits two C functions of the same name → redefinition.
    _fn_by_name: dict = {}
    for d in fn_decls:
        _fn_by_name[d.name] = d
    fn_decls = list(_fn_by_name.values())

    # Generic ADTs and records are supported in v3.4 via the boxed
    # q_value_t* representation: type parameters mean nothing at the C
    # level — every field is an int64_t slot that holds whatever value
    # was constructed in. Type-checking already happened in glass.py
    # before we got here, so Quartz can trust that the program is sound.

    # Build the ctor env + tag map. Tags are globally unique ints so the
    # generated C can compare with a single integer compare.
    ctor_env: dict = {}
    ctor_tags: dict = {}
    record_env: dict = {}
    # v4.37: type-parameter list per ADT name. Populated alongside ctor
    # registration so structural equality can substitute the TyADT's
    # type args into variant field types.
    adt_params: dict = {}
    next_tag = 0

    # If the host's checker is available, seed the env/tag maps from its
    # registries first. This pulls in prelude types (Option, Result, Pair)
    # and any ADT/record that came from PRELUDE plus our own decls.
    if checker is not None:
        for name, (params, variants) in checker.adt_registry.items():
            adt_params[name] = list(params)
            for v in variants:
                ctor_env[v.name] = (name, list(v.fields))
                ctor_tags[v.name] = next_tag
                next_tag += 1
        for name, (params, fields) in checker.record_registry.items():
            record_env[name] = list(fields)
            ctor_tags[name] = next_tag
            next_tag += 1
    else:
        # Fallback path — only register what's in `decls`. This branch
        # exists for tests that bypass install_program; production code
        # via `build()` always supplies a checker.
        for d in type_decls:
            adt_params[d.name] = list(d.params)
            for v in d.variants:
                ctor_env[v.name] = (d.name, list(v.fields))
                ctor_tags[v.name] = next_tag
                next_tag += 1
        for d in record_decls:
            record_env[d.name] = list(d.fields)
            ctor_tags[d.name] = next_tag
            next_tag += 1

    # v4.71 (Phase A1 of the migration): effects are erased at codegen.
    # An effect row (`!{IO, File}`) is a TYPE-LEVEL annotation — the
    # type checker uses it to track and constrain side effects, but it
    # carries no runtime representation. The generated C just performs
    # the effect (calls printf, fopen, popen, …) via the effectful
    # builtins. So an effectful fn lowers exactly like a pure one; we no
    # longer reject it. This unblocks compiling prism.glass, whose whole
    # pipeline runs under `!{IO, File}`.
    #
    # Generic functions (`fn id<T>(...)` with type_params) lower via type
    # erasure: type-variable params/returns become int64_t in C; call
    # sites cast args going in and results coming out.

    if not let_decls:
        raise ValueError(
            "Quartz: program has no value expression to print"
        )

    # Build the shared fn signature map. Both the fn-body codegens and
    # the main() codegen consult this for Call type lookup.
    fn_signatures = {
        d.name: ([t for _, t in d.params], d.ret)
        for d in fn_decls
    }

    # Pass 1: emit forward declarations for every fn. This lets fns
    # call each other (and themselves) regardless of source order.
    forward_decls: list[str] = []
    for d in fn_decls:
        ret_c = c_type_for_ty(d.ret)
        params_c = ", ".join(
            f"{c_type_for_ty(t)} {mangle(n)}" for n, t in d.params
        )
        forward_decls.append(f"{ret_c} {mangle(d.name)}({params_c});")

    # v4.44: lambda-lifting state shared across all Codegen instances.
    # Each Lambda encountered (in fn bodies or main()) appends to this
    # list; the counter (a 1-elt list as a mutable box) names them
    # uniquely.
    lifted_lambdas: list[str] = []
    lambda_counter: list[int] = [0]
    # Pass 2: emit each fn body as a C function definition.
    fn_definitions: list[str] = []
    for d in fn_decls:
        cg = Codegen(fn_signatures=fn_signatures,
                     ctor_env=ctor_env, ctor_tags=ctor_tags,
                     record_env=record_env, adt_params=adt_params,
                     lifted_lambdas=lifted_lambdas,
                     lambda_counter=lambda_counter)
        # Seed type_env with the params.
        for n, t in d.params:
            cg.type_env[n] = t
        # v4.49: emit refinement guards for any refined param BEFORE
        # the body runs. The host's apply_fn does the same on entry,
        # so the C-level fn matches host semantics. Guards live in
        # body_stmts ahead of the user code so they short-circuit
        # any subsequent computation if a precondition is violated.
        #
        # v4.56: a param's predicate may reference EARLIER params
        # (`clamp(lo, hi where (hi > lo))`). We pass exactly the set of
        # earlier param names to each guard — matching prism's
        # accumulating-env semantics (a later param sees earlier ones,
        # never a forward reference, even though all params are in C
        # scope here). This keeps host / prism / Quartz agreeing on the
        # same set of accepted programs.
        param_guards: list[str] = []
        seen_param_names: set = set()
        for n, t in d.params:
            if isinstance(t, glass.TyRefine):
                param_guards.extend(
                    _emit_refinement_check(n, t, allowed_names=seen_param_names)
                )
            seen_param_names.add(n)
        body_atom = cg.emit_expr(d.body)
        body_stmts = param_guards + list(cg.stmts)
        # v4.49: enforce a refined return type before returning.
        # The check binds the body's result to the binder `result`
        # (the same name host uses, see check_refinement_runtime call
        # with "result"). We materialize the result into a local so
        # the check expression can reference it.
        # v4.56: the return predicate sees ALL params (they're all in
        # scope when the body has finished), so pass the full set.
        if isinstance(d.ret, glass.TyRefine):
            all_param_names = {n for n, _ in d.params}
            ret_ty_base_c = c_type_for_ty(d.ret)
            body_stmts.append(f"{ret_ty_base_c} result = {body_atom};")
            body_stmts.extend(
                _emit_refinement_check(
                    "result", d.ret, allowed_names=all_param_names)
            )
            body_stmts.append("return result;")
        else:
            body_stmts.append(f"return {body_atom};")
        ret_c = c_type_for_ty(d.ret)
        params_c = ", ".join(
            f"{c_type_for_ty(t)} {mangle(n)}" for n, t in d.params
        )
        body_indented = "\n    ".join(body_stmts)
        fn_definitions.append(
            f"{ret_c} {mangle(d.name)}({params_c}) {{\n    {body_indented}\n}}"
        )

    # Pass 3: emit main() — top-level let decls, then print the result.
    cg = Codegen(fn_signatures=fn_signatures,
                 ctor_env=ctor_env, ctor_tags=ctor_tags,
                 record_env=record_env, adt_params=adt_params,
                 lifted_lambdas=lifted_lambdas,
                 lambda_counter=lambda_counter)
    *bindings, final = let_decls

    for d in bindings:
        # v4.37: prefer the let's type annotation when present so
        # generic-ADT type args (e.g., `let a : Option<Int> = None`)
        # propagate to subsequent uses of `a`.
        val_ty = d.ann if d.ann is not None else cg.type_of(d.value)
        val_atom = cg.emit_expr(d.value)
        c_ty = c_type_for_ty(val_ty)
        # v4.71: throwaway `_` binding — emit for side effects, don't
        # declare a C var (repeated `let _ = ...` would collide).
        if d.name == "_":
            cg.stmts.append(f"(void)({val_atom});")
        else:
            cg.stmts.append(f"{c_ty} {mangle(d.name)} = {val_atom};")
        # v4.50: enforce a refined annotation on the binding. The
        # guard runs against the just-bound name (which matches the
        # binder used in the predicate), mirroring host's
        # check_refinement_runtime call at let installation time.
        if isinstance(d.ann, glass.TyRefine):
            cg.stmts.extend(_emit_refinement_check(d.name, d.ann))
        cg.type_env[d.name] = val_ty

    final_ty = cg.type_of(final.value)
    # If Quartz's lightweight type_of returns a TyVar (e.g. the user's
    # final expression involved generic destructuring like `match Some(42)
    # { Some(n) => n; ... }` where `n`'s declared type is `T`), consult
    # the host checker for the concrete instantiation. The checker has
    # already verified the program; we just need its inference result.
    if isinstance(final_ty, glass.TyVar) and checker is not None:
        resolved = checker.env.get(final.name)
        if resolved is not None:
            # Walk past a Scheme wrapper if there is one.
            if hasattr(resolved, "body"):
                resolved = resolved.body
            final_ty = resolved
    final_atom = cg.emit_expr(final.value)
    final_c_ty = c_type_for_ty(final_ty)
    # v4.73: an explicit `let _ : T = <stmt>` final decl is a discard
    # statement (run for effects), not a REPL result — emit it for its
    # side effects without re-printing its value. A bare top-level
    # expression wraps to `let _` with ann=None and IS auto-printed (the
    # REPL convenience the test suite relies on). This distinction stops
    # prism's final `let _ : String = ... print(...) ...` double-printing.
    if final.name == "_" and final.ann is not None:
        cg.stmts.append(f"(void)({final_atom});")
    else:
        cg.stmts.append(f"{final_c_ty} _result = {final_atom};")
        cg.stmts.append(c_print_for_ty(final_ty, "_result"))

    main_body = "\n    ".join(cg.stmts)

    # Assemble.
    sections = [
        "/* Generated by Quartz v3.5 — Glass native compiler */",
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "#include <stdarg.h>",
        "#include <stdint.h>",
        "#include <string.h>",
        "#include <stdbool.h>",
        "#include <unistd.h>",
        "",
        "/* Quartz runtime — algebraic values, string concat. */",
        "typedef struct q_value {",
        "    int tag;",
        "    int num_fields;",
        "    int64_t fields[];",
        "} q_value_t;",
        "",
        "static q_value_t* q_ctor_alloc(int tag, int num_fields, ...) {",
        "    q_value_t* v = (q_value_t*)malloc(",
        "        sizeof(q_value_t) + (size_t)num_fields * sizeof(int64_t));",
        "    if (!v) { fprintf(stderr, \"quartz: out of memory\\n\"); exit(1); }",
        "    v->tag = tag;",
        "    v->num_fields = num_fields;",
        "    va_list args;",
        "    va_start(args, num_fields);",
        "    for (int i = 0; i < num_fields; i++) {",
        "        v->fields[i] = va_arg(args, int64_t);",
        "    }",
        "    va_end(args);",
        "    return v;",
        "}",
        "",
        "static const char* quartz_str_concat(const char* a, const char* b) {",
        "    size_t la = strlen(a), lb = strlen(b);",
        "    char* r = (char*)malloc(la + lb + 1);",
        "    if (!r) { fprintf(stderr, \"quartz: out of memory\\n\"); exit(1); }",
        "    memcpy(r, a, la);",
        "    memcpy(r + la, b, lb);",
        "    r[la + lb] = '\\0';",
        "    return r;",
        "}",
        "",
        # v4.33: structural string equality. Pre-v4.33 Quartz emitted
        # plain C `==` on `const char*`, which was pointer comparison —
        # equal for compile-time-deduplicated literals but wrong for
        # heap-allocated strings (e.g. concat results). strcmp is the
        # standard fix.
        "static bool quartz_str_eq(const char* a, const char* b) {",
        "    return strcmp(a, b) == 0;",
        "}",
        "",
        # v4.38: substring(s, start, end). end is exclusive. Matches
        # the host's semantics: raises on negative indices or
        # start > end; clamps each index to the string's length.
        "static const char* quartz_substring("
        "const char* s, int64_t start, int64_t end) {",
        "    if (start < 0 || end < 0) {",
        "        fprintf(stderr, \"quartz: substring: negative index "
        "(%lld, %lld)\\n\", (long long)start, (long long)end);",
        "        exit(1);",
        "    }",
        "    if (start > end) {",
        "        fprintf(stderr, \"quartz: substring: start > end "
        "(%lld > %lld)\\n\", (long long)start, (long long)end);",
        "        exit(1);",
        "    }",
        "    size_t n = strlen(s);",
        "    size_t a = (size_t)start; if (a > n) a = n;",
        "    size_t b = (size_t)end;   if (b > n) b = n;",
        "    size_t len = b - a;",
        "    char* r = (char*)malloc(len + 1);",
        "    if (!r) { fprintf(stderr, \"quartz: out of memory\\n\"); "
        "exit(1); }",
        "    memcpy(r, s + a, len);",
        "    r[len] = '\\0';",
        "    return r;",
        "}",
        "",
        # v4.38: int_to_string(n). 20 digits fits any int64 + sign +
        # null terminator, but 32 leaves room.
        "static const char* quartz_int_to_string(int64_t n) {",
        "    char* r = (char*)malloc(32);",
        "    if (!r) { fprintf(stderr, \"quartz: out of memory\\n\"); "
        "exit(1); }",
        "    snprintf(r, 32, \"%lld\", (long long)n);",
        "    return r;",
        "}",
        "",
        "/* v4.71 (Phase A2): effectful builtins. print returns its arg. */",
        "static const char* quartz_print(const char* s) {",
        "    printf(\"%s\\n\", s);",
        "    return s;",
        "}",
        "",
        "/* read_file: whole file -> Result<String,String> (Ok/Err). */",
        "static q_value_t* quartz_read_file(const char* path, int ok_tag, "
        "int err_tag) {",
        "    FILE* f = fopen(path, \"rb\");",
        "    if (!f) return q_ctor_alloc(err_tag, 1, "
        "(int64_t)(intptr_t)\"read error: cannot open file\");",
        "    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);",
        "    if (sz < 0) { fclose(f); return q_ctor_alloc(err_tag, 1, "
        "(int64_t)(intptr_t)\"read error: cannot size file\"); }",
        "    char* buf = (char*)malloc((size_t)sz + 1);",
        "    if (!buf) { fclose(f); fprintf(stderr, \"quartz: out of "
        "memory\\n\"); exit(1); }",
        "    size_t got = fread(buf, 1, (size_t)sz, f);",
        "    buf[got] = '\\0';",
        "    fclose(f);",
        "    return q_ctor_alloc(ok_tag, 1, (int64_t)(intptr_t)buf);",
        "}",
        "",
        # v4.74: write_file — whole content -> Result<Int,String> (Ok bytes).
        "static q_value_t* quartz_write_file(const char* path, "
        "const char* content, int ok_tag, int err_tag) {",
        "    FILE* f = fopen(path, \"wb\");",
        "    if (!f) return q_ctor_alloc(err_tag, 1, "
        "(int64_t)(intptr_t)\"write error: cannot open file\");",
        "    size_t len = strlen(content);",
        "    size_t wrote = fwrite(content, 1, len, f);",
        "    fclose(f);",
        "    return q_ctor_alloc(ok_tag, 1, (int64_t)wrote);",
        "}",
        "",
        # v4.74: run_command — spawn a process, capture exit/stdout/stderr.
        # Builds "cmd arg1 arg2 ... > out 2> err", runs via system(), reads
        # the temp files back. Ok wraps a tag-0 tuple (exit, stdout, stderr).
        # Mirrors glass.py's run_command (separate stdout/stderr + code).
        "static char* quartz__slurp(const char* path) {",
        "    FILE* f = fopen(path, \"rb\");",
        "    if (!f) { char* e = (char*)malloc(1); e[0] = 0; return e; }",
        "    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);",
        "    if (sz < 0) sz = 0;",
        "    char* buf = (char*)malloc((size_t)sz + 1);",
        "    size_t got = fread(buf, 1, (size_t)sz, f);",
        "    buf[got] = 0; fclose(f); return buf;",
        "}",
        "static q_value_t* quartz_run_command(const char* cmd, "
        "q_value_t* args, int ok_tag, int err_tag) {",
        "    char line[16384]; size_t pos = 0;",
        "    pos += (size_t)snprintf(line + pos, sizeof(line) - pos, "
        "\"%s\", cmd);",
        "    q_value_t* a = args;",
        "    while (a->num_fields > 0) {",
        "        const char* arg = (const char*)(intptr_t)a->fields[0];",
        "        pos += (size_t)snprintf(line + pos, sizeof(line) - pos, "
        "\" %s\", arg);",
        "        a = (q_value_t*)(intptr_t)a->fields[1];",
        "    }",
        "    char outp[64], errp[64];",
        "    snprintf(outp, sizeof(outp), \"/tmp/qrc_out_%d\", (int)getpid());",
        "    snprintf(errp, sizeof(errp), \"/tmp/qrc_err_%d\", (int)getpid());",
        "    snprintf(line + pos, sizeof(line) - pos, \" > %s 2> %s\", outp, errp);",
        "    int rc = system(line);",
        "    int code = (rc == -1) ? -1 : ((rc >> 8) & 0xFF);",
        "    char* out = quartz__slurp(outp);",
        "    char* err = quartz__slurp(errp);",
        "    unlink(outp); unlink(errp);",
        "    q_value_t* tup = q_ctor_alloc(0, 3, (int64_t)code, "
        "(int64_t)(intptr_t)out, (int64_t)(intptr_t)err);",
        "    return q_ctor_alloc(ok_tag, 1, (int64_t)(intptr_t)tup);",
        "}",
        "",
        # v4.39: list length. Walks the cons chain counting cells.
        "static int64_t quartz_list_len(q_value_t* xs) {",
        "    int64_t n = 0;",
        "    while (xs->num_fields > 0) {",
        "        n++;",
        "        xs = (q_value_t*)(intptr_t)xs->fields[1];",
        "    }",
        "    return n;",
        "}",
        "",
        # v4.39: list reverse. Builds a new chain right-to-left.
        "static q_value_t* quartz_list_reverse(q_value_t* xs) {",
        "    q_value_t* result = q_ctor_alloc(0, 0);",
        "    while (xs->num_fields > 0) {",
        "        q_value_t* cell = (q_value_t*)malloc(",
        "            sizeof(q_value_t) + 2 * sizeof(int64_t));",
        "        if (!cell) { fprintf(stderr, "
        "\"quartz: out of memory\\n\"); exit(1); }",
        "        cell->tag = 0;",
        "        cell->num_fields = 2;",
        "        cell->fields[0] = xs->fields[0];",
        "        cell->fields[1] = (int64_t)(intptr_t)result;",
        "        result = cell;",
        "        xs = (q_value_t*)(intptr_t)xs->fields[1];",
        "    }",
        "    return result;",
        "}",
        "",
        # v4.39: head — Option<T>. Empty list → None, otherwise Some(h).
        # The Some/None tags are passed by the caller (Quartz codegen
        # resolves them from ctor_tags) so the helper doesn't need to
        # hard-code prelude tag values.
        "static q_value_t* quartz_list_head(",
        "    q_value_t* xs, long none_tag, long some_tag) {",
        "    if (xs->num_fields == 0) return q_ctor_alloc(none_tag, 0);",
        "    return q_ctor_alloc(some_tag, 1, xs->fields[0]);",
        "}",
        "",
        # v4.39: tail — Option<List<T>>. Empty list → None, otherwise
        # Some(rest).
        "static q_value_t* quartz_list_tail(",
        "    q_value_t* xs, long none_tag, long some_tag) {",
        "    if (xs->num_fields == 0) return q_ctor_alloc(none_tag, 0);",
        "    q_value_t* rest = (q_value_t*)(intptr_t)xs->fields[1];",
        "    return q_ctor_alloc(some_tag, 1, "
        "(int64_t)(intptr_t)rest);",
        "}",
        "",
        # v4.39: string_index_of — Option<Int>. Returns the byte offset
        # of the first occurrence of `n` in `h`, or None if not found.
        # Empty needle matches at position 0 (matches strstr's
        # convention and the host's b_string_index_of).
        "static q_value_t* quartz_string_index_of(",
        "    const char* h, const char* n, long none_tag, "
        "long some_tag) {",
        "    const char* p = strstr(h, n);",
        "    if (p == NULL) return q_ctor_alloc(none_tag, 0);",
        "    return q_ctor_alloc(some_tag, 1, (int64_t)(p - h));",
        "}",
        "",
        # v4.40: ASCII case conversion. Explicit char arithmetic (not
        # locale-dependent toupper/tolower) so the conversion is
        # predictable on any input. Bytes outside A-Z / a-z pass
        # through unchanged. Matches host's b_string_to_upper /
        # b_string_to_lower exactly.
        "static const char* quartz_string_to_upper(const char* s) {",
        "    size_t n = strlen(s);",
        "    char* r = (char*)malloc(n + 1);",
        "    if (!r) { fprintf(stderr, "
        "\"quartz: out of memory\\n\"); exit(1); }",
        "    for (size_t i = 0; i < n; i++) {",
        "        unsigned char c = (unsigned char)s[i];",
        "        r[i] = (c >= 'a' && c <= 'z') "
        "? (char)(c - 'a' + 'A') : (char)c;",
        "    }",
        "    r[n] = '\\0';",
        "    return r;",
        "}",
        "",
        "static const char* quartz_string_to_lower(const char* s) {",
        "    size_t n = strlen(s);",
        "    char* r = (char*)malloc(n + 1);",
        "    if (!r) { fprintf(stderr, "
        "\"quartz: out of memory\\n\"); exit(1); }",
        "    for (size_t i = 0; i < n; i++) {",
        "        unsigned char c = (unsigned char)s[i];",
        "        r[i] = (c >= 'A' && c <= 'Z') "
        "? (char)(c - 'A' + 'a') : (char)c;",
        "    }",
        "    r[n] = '\\0';",
        "    return r;",
        "}",
        "",
        # v4.43: range(lo, hi). Builds a cons chain right-to-left so
        # the head is `lo`. Half-open: hi is exclusive. Returns the
        # empty list if lo >= hi.
        "static q_value_t* quartz_range(int64_t lo, int64_t hi) {",
        "    q_value_t* result = q_ctor_alloc(0, 0);",
        "    for (int64_t i = hi - 1; i >= lo; i--) {",
        "        q_value_t* cell = (q_value_t*)malloc(",
        "            sizeof(q_value_t) + 2 * sizeof(int64_t));",
        "        if (!cell) { fprintf(stderr, "
        "\"quartz: out of memory\\n\"); exit(1); }",
        "        cell->tag = 0;",
        "        cell->num_fields = 2;",
        "        cell->fields[0] = i;",
        "        cell->fields[1] = (int64_t)(intptr_t)result;",
        "        result = cell;",
        "    }",
        "    return result;",
        "}",
        "",
        # v4.46: higher-order list builtins. Each walks the list and
        # dispatches through the closure's fn pointer at fields[0].
        # Casts the pointer to the appropriate arity-specific
        # signature (unary for map/filter, binary for fold).
        "static q_value_t* quartz_map(q_value_t* xs, "
        "q_value_t* closure) {",
        "    int64_t (*fn)(q_value_t*, int64_t) =",
        "        (int64_t (*)(q_value_t*, int64_t))(intptr_t)"
        "closure->fields[0];",
        "    /* Count length so we can build right-to-left without "
        "extra walks. */",
        "    int64_t n = 0;",
        "    q_value_t* p = xs;",
        "    while (p->num_fields > 0) {",
        "        n++;",
        "        p = (q_value_t*)(intptr_t)p->fields[1];",
        "    }",
        "    int64_t* mapped = "
        "(int64_t*)malloc((size_t)n * sizeof(int64_t));",
        "    if (n > 0 && !mapped) { fprintf(stderr, "
        "\"quartz: out of memory\\n\"); exit(1); }",
        "    p = xs;",
        "    for (int64_t i = 0; i < n; i++) {",
        "        mapped[i] = fn(closure, p->fields[0]);",
        "        p = (q_value_t*)(intptr_t)p->fields[1];",
        "    }",
        "    q_value_t* result = q_ctor_alloc(0, 0);",
        "    for (int64_t i = n - 1; i >= 0; i--) {",
        "        q_value_t* cell = (q_value_t*)malloc(",
        "            sizeof(q_value_t) + 2 * sizeof(int64_t));",
        "        if (!cell) { fprintf(stderr, \"quartz: out of "
        "memory\\n\"); exit(1); }",
        "        cell->tag = 0;",
        "        cell->num_fields = 2;",
        "        cell->fields[0] = mapped[i];",
        "        cell->fields[1] = (int64_t)(intptr_t)result;",
        "        result = cell;",
        "    }",
        "    free(mapped);",
        "    return result;",
        "}",
        "",
        "static q_value_t* quartz_filter(q_value_t* xs, "
        "q_value_t* closure) {",
        "    int64_t (*fn)(q_value_t*, int64_t) =",
        "        (int64_t (*)(q_value_t*, int64_t))(intptr_t)"
        "closure->fields[0];",
        "    /* Count length once, then collect kept elements into a "
        "scratch array, then build the result chain right-to-left. */",
        "    int64_t n = 0;",
        "    q_value_t* p = xs;",
        "    while (p->num_fields > 0) {",
        "        n++;",
        "        p = (q_value_t*)(intptr_t)p->fields[1];",
        "    }",
        "    int64_t* kept = "
        "(int64_t*)malloc((size_t)n * sizeof(int64_t));",
        "    if (n > 0 && !kept) { fprintf(stderr, "
        "\"quartz: out of memory\\n\"); exit(1); }",
        "    int64_t k = 0;",
        "    p = xs;",
        "    for (int64_t i = 0; i < n; i++) {",
        "        int64_t elem = p->fields[0];",
        "        if (fn(closure, elem)) kept[k++] = elem;",
        "        p = (q_value_t*)(intptr_t)p->fields[1];",
        "    }",
        "    q_value_t* result = q_ctor_alloc(0, 0);",
        "    for (int64_t i = k - 1; i >= 0; i--) {",
        "        q_value_t* cell = (q_value_t*)malloc(",
        "            sizeof(q_value_t) + 2 * sizeof(int64_t));",
        "        if (!cell) { fprintf(stderr, \"quartz: out of "
        "memory\\n\"); exit(1); }",
        "        cell->tag = 0;",
        "        cell->num_fields = 2;",
        "        cell->fields[0] = kept[i];",
        "        cell->fields[1] = (int64_t)(intptr_t)result;",
        "        result = cell;",
        "    }",
        "    free(kept);",
        "    return result;",
        "}",
        "",
        # fold's combine takes (acc, elem) — binary closure. The fn
        # pointer cast uses the matching signature.
        "static int64_t quartz_fold(q_value_t* xs, int64_t init, "
        "q_value_t* closure) {",
        "    int64_t (*fn)(q_value_t*, int64_t, int64_t) =",
        "        (int64_t (*)(q_value_t*, int64_t, int64_t))"
        "(intptr_t)closure->fields[0];",
        "    int64_t acc = init;",
        "    q_value_t* p = xs;",
        "    while (p->num_fields > 0) {",
        "        acc = fn(closure, acc, p->fields[0]);",
        "        p = (q_value_t*)(intptr_t)p->fields[1];",
        "    }",
        "    return acc;",
        "}",
        "",
        # v4.41: char_at — return the byte at index i as int64_t.
        # Negative or OOB indices fail loudly with the same shape of
        # error the host raises (so a program tested through the host
        # interpreter gives identical error semantics when run as a
        # compiled binary).
        "static int64_t quartz_char_at(const char* s, int64_t i) {",
        "    if (i < 0) {",
        "        fprintf(stderr, \"quartz: char_at: negative index "
        "(%lld)\\n\", (long long)i);",
        "        exit(1);",
        "    }",
        "    size_t n = strlen(s);",
        "    if ((size_t)i >= n) {",
        "        fprintf(stderr, \"quartz: char_at: index %lld out "
        "of range for string of length %zu\\n\", "
        "(long long)i, n);",
        "        exit(1);",
        "    }",
        "    return (int64_t)(unsigned char)s[i];",
        "}",
        "",
        # v4.32: list concatenation. Walks the first list (each cell is",
        # a q_value_t with num_fields == 2: fields[0]=head, fields[1]=tail;",
        # nil has num_fields == 0), collecting heads into a temporary",
        # array, then builds a fresh cons chain whose final tail is the",
        # second list. Immutable: neither input is mutated.",
        "static q_value_t* quartz_list_concat(q_value_t* a, q_value_t* b) {",
        "    /* Walk `a` once to count its length. */",
        "    q_value_t* p = a;",
        "    size_t n = 0;",
        "    while (p->num_fields > 0) {",
        "        n++;",
        "        p = (q_value_t*)(intptr_t)p->fields[1];",
        "    }",
        "    /* Collect heads into a small stack array (n is bounded by",
        "       the source list's length, which the type-checker bounds",
        "       statically). */",
        "    int64_t* heads = (int64_t*)malloc(n * sizeof(int64_t));",
        "    if (n > 0 && !heads) {",
        "        fprintf(stderr, \"quartz: out of memory\\n\"); exit(1);",
        "    }",
        "    p = a;",
        "    for (size_t i = 0; i < n; i++) {",
        "        heads[i] = p->fields[0];",
        "        p = (q_value_t*)(intptr_t)p->fields[1];",
        "    }",
        "    /* Build the result right-to-left, starting from `b`. */",
        "    q_value_t* result = b;",
        "    for (size_t i = n; i > 0; i--) {",
        "        q_value_t* cell = (q_value_t*)malloc(",
        "            sizeof(q_value_t) + 2 * sizeof(int64_t));",
        "        if (!cell) { fprintf(stderr, \"quartz: out of memory\\n\"); exit(1); }",
        "        cell->tag = 0;",
        "        cell->num_fields = 2;",
        "        cell->fields[0] = heads[i - 1];",
        "        cell->fields[1] = (int64_t)(intptr_t)result;",
        "        result = cell;",
        "    }",
        "    free(heads);",
        "    return result;",
        "}",
        "",
    ]
    # Emit constructor tag comments — humans reading the C will want to
    # know which integer corresponds to which variant.
    if ctor_tags:
        sections.append("/* Constructor / record tags */")
        for name, tag in sorted(ctor_tags.items(), key=lambda kv: kv[1]):
            if name in ctor_env:
                parent, fields = ctor_env[name]
                arity = len(fields)
                label = f"{parent}::{name}"
            else:
                # Record
                fields = record_env[name]
                arity = len(fields)
                label = f"{name} (record)"
            arity_str = ""
            if arity:
                arity_str = f" ({arity} field" + ("s" if arity != 1 else "") + ")"
            sections.append(f"/*   {tag}: {label}{arity_str} */")
        sections.append("")
    if forward_decls:
        sections.append("/* Forward declarations */")
        sections.extend(forward_decls)
        sections.append("")
    if lifted_lambdas:
        # v4.44: lambda-lifted static fns. Emitted before fn
        # definitions so they're in scope when user fns construct
        # closures of them.
        sections.append("/* Lifted lambdas (v4.44) */")
        sections.extend(lifted_lambdas)
        sections.append("")
    if fn_definitions:
        sections.append("/* Function definitions */")
        sections.extend(fn_definitions)
        sections.append("")
    sections.append("int main(void) {")
    sections.append(f"    {main_body}")
    sections.append("    return 0;")
    sections.append("}")
    return "\n".join(sections) + "\n"


# === Build pipeline =====================================================

def build(source_file: str, output_binary: str,
          cc: str = "cc", verbose: bool = False) -> None:
    """Parse, compile to C, invoke cc, produce binary."""
    src = open(source_file).read()

    # Parse using the existing glass.py front-end.
    decls = glass.Parser(glass.tokenize(src)).parse_program()

    # v4.74 (Phase A3/B): expand `import "file"` into the imported file's
    # definitions before checking/codegen, mirroring glass.py's run_source.
    # Lets multi-file programs (e.g. glassc.glass importing prism.glass) be
    # compiled. Paths resolve relative to the source file's directory.
    decls = glass.expand_imports(
        decls, os.path.dirname(os.path.abspath(source_file)))

    # Type-check by walking with the existing checker. If anything fails,
    # codegen below will also fail — but checking here gives better errors.
    # We keep the post-check checker so codegen can consult inferred types
    # for polymorphic final expressions.
    checker, env = glass.make_runtime()
    try:
        glass.install_program(decls, checker, env, verbose=False)
    except (glass.TypeError_, SyntaxError) as ex:
        raise RuntimeError(f"type/parse error: {ex}")

    # v4.71 (Phase A2): emit the PRELUDE's functions the program USES.
    # The checker already registered prelude TYPES (Option/Result/Pair),
    # but prelude FUNCTIONS (string_contains, bind_result, fst/snd, …)
    # have no C definition unless we compile them. We include only the
    # ones reachable from the program (transitively) — that keeps simple
    # programs from dragging in higher-order prelude fns they never call,
    # and shrinks the emitted C. User redefinitions win (no clash).
    prelude_decls = glass.Parser(glass.tokenize(glass.PRELUDE)).parse_program()
    user_fn_names = {d.name for d in decls if isinstance(d, glass.FnDecl)}
    prelude_fn_map = {
        d.name: d for d in prelude_decls
        if isinstance(d, glass.FnDecl) and d.name not in user_fn_names
    }
    used = _collect_idents(decls)
    included: dict = {}
    worklist = [n for n in used if n in prelude_fn_map]
    while worklist:
        n = worklist.pop()
        if n in included:
            continue
        fd = prelude_fn_map[n]
        included[n] = fd
        for m in _collect_idents([fd]):     # transitive: prelude→prelude
            if m in prelude_fn_map and m not in included:
                worklist.append(m)
    decls = list(included.values()) + decls

    # Compile to C.
    c_source = compile_program(decls, checker=checker)
    if verbose:
        print("=== Generated C ===")
        print(c_source)
        print("=== End ===")

    # Write C to temp file, invoke cc.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".c", delete=False
    ) as f:
        f.write(c_source)
        c_file = f.name

    try:
        # v4.71: Quartz's value model stores every value in an
        # int64_t-wide slot and casts pointers through intptr_t — so
        # int64_t<->pointer interconversions are intentional and
        # value-preserving on a 64-bit target. Modern clang flags them
        # as errors by default; -Wno-int-conversion tells it these are
        # deliberate (the same rationale as the intptr_t casts). This is
        # what lets large erasure-heavy programs (prism) link.
        result = subprocess.run(
            [cc, c_file, "-o", output_binary, "-O2", "-Wno-int-conversion",
             "-fbracket-depth=100000"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"cc failed (exit {result.returncode}):\n{result.stderr}"
            )
    finally:
        os.unlink(c_file)


# === CLI ================================================================

def cli() -> None:
    import argparse
    p = argparse.ArgumentParser(
        prog="glass-build",
        description="Quartz: compile Glass to native binary"
    )
    p.add_argument("source", help=".glass source file")
    p.add_argument("-o", "--output", default="a.out", help="output binary")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="print generated C source")
    p.add_argument("--cc", default="cc", help="C compiler to invoke")
    args = p.parse_args()

    # v4.74: large self-host inputs (glassc.glass = prism + backend, ~7k
    # lines) recurse deep through the parser/checker/codegen; the default
    # CPython limit (1000) overflows. Raise it for the whole compile.
    sys.setrecursionlimit(100000)

    try:
        build(args.source, args.output, cc=args.cc, verbose=args.verbose)
    except Exception as ex:
        print(f"glass-build: {ex}", file=sys.stderr)
        raise SystemExit(1)
    print(f"compiled: {args.output}")


if __name__ == "__main__":
    cli()
