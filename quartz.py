"""Quartz: native C compiler back-end for Glass (v3.0 first prototype).

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

def c_type_for_ty(ty):
    if isinstance(ty, glass.TyInt):    return "int64_t"
    if isinstance(ty, glass.TyBool):   return "bool"
    if isinstance(ty, glass.TyString): return "const char*"
    if isinstance(ty, glass.TyADT):    return "q_value_t*"
    if isinstance(ty, glass.TyVar):
        # Type variables erase to int64_t. The boxed q_value_t storage
        # for ADT/record fields is int64_t-wide; primitive fields fit
        # directly and pointer fields fit via intptr_t. The caller knows
        # the concrete type (from the host's inferrer) and can cast at
        # use sites.
        return "int64_t"
    raise NotImplementedError(
        f"Quartz v3.0 does not support type: {type(ty).__name__}"
    )


def c_print_for_ty(ty, atom):
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
}


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
    """Return `ty` with TyVar names rebound per `subst`."""
    if isinstance(ty, glass.TyVar):
        return subst.get(ty.name, ty)
    if isinstance(ty, glass.TyADT):
        return glass.TyADT(
            ty.name,
            tuple(_substitute_ty(a, subst) for a in ty.args),
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
                 record_env: dict | None = None):
        self.stmts: list[str] = []
        self.type_env: dict[str, glass.Ty] = {}
        # Map fn name → (param_tys, ret_ty). Shared across all Codegens in
        # a program so each fn body can type-check calls to other fns.
        self.fn_signatures: dict = fn_signatures if fn_signatures is not None else {}
        # Map ctor name → (parent_type_name, [field_tys]).
        self.ctor_env: dict = ctor_env if ctor_env is not None else {}
        # Map ctor name → global int tag.
        self.ctor_tags: dict = ctor_tags if ctor_tags is not None else {}
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
            if e.op in ("+", "-", "*", "/"):
                return glass.TyInt()
            if e.op == "++":
                return glass.TyString()
            raise NotImplementedError(f"Quartz v3.0 op: {e.op}")
        if isinstance(e, glass.If):
            return self.type_of(e.then_b)
        if isinstance(e, glass.LetIn):
            saved = self.type_env.get(e.name)
            self.type_env[e.name] = self.type_of(e.value)
            t = self.type_of(e.body)
            if saved is None:
                self.type_env.pop(e.name, None)
            else:
                self.type_env[e.name] = saved
            return t
        if isinstance(e, glass.Call):
            # Three cases: top-level fn, constructor, neither.
            if not isinstance(e.fn, glass.Ident):
                raise NotImplementedError(
                    f"Quartz v3.1 only supports calls to named functions or constructors; "
                    f"got callee {type(e.fn).__name__}"
                )
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
                parent_name, _ = self.ctor_env[e.fn.name]
                return glass.TyADT(parent_name, ())
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
            _, field_tys = self.ctor_env[ctor_name]
            sub_pats = pat.args if pat.args is not None else []
            if len(sub_pats) != len(field_tys):
                raise ValueError(
                    f"Quartz: constructor {ctor_name} expects "
                    f"{len(field_tys)} fields, got {len(sub_pats)}"
                )
            for sub, field_ty in zip(sub_pats, field_tys):
                if sub.kind == "ident":
                    bindings.append((sub.value, field_ty))
                elif sub.kind == "wild":
                    pass
                else:
                    raise NotImplementedError(
                        f"Quartz v3.2: nested pattern {sub.kind!r} inside "
                        f"constructor; only `wild` and `ident` are allowed "
                        f"as sub-patterns"
                    )
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
        raise NotImplementedError(
            f"Quartz v3.2: top-level pattern {pat.kind!r} not supported "
            f"(only `wild`, `ident`, `ctor`, `record` are; lists/tuples "
            f"deferred to v3.x)"
        )

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
                # String concatenation. Calls the runtime helper which
                # heap-allocates a fresh result. The helper is emitted at
                # the top of every Quartz-compiled program; the C linker
                # strips it as dead code if unused.
                return f"quartz_str_concat({l}, {r})"
            op = BIN_OP_C.get(e.op)
            if op is None:
                raise NotImplementedError(f"Quartz v3.0 op: {e.op}")
            return f"({l} {op} {r})"
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
            val_ty = self.type_of(e.value)
            val_atom = self.emit_expr(e.value)
            c_ty = c_type_for_ty(val_ty)
            self.stmts.append(f"{c_ty} {mangle(e.name)} = {val_atom};")
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
            # Evaluate args left-to-right; emit a C function call expression.
            if not isinstance(e.fn, glass.Ident):
                raise NotImplementedError(
                    f"Quartz only supports calls to named functions or constructors; "
                    f"got callee {type(e.fn).__name__}"
                )
            name = e.fn.name
            # Constructor application?
            if name in self.ctor_env:
                tag = self.ctor_tags[name]
                arg_atoms = [self.emit_expr(a) for a in e.args]
                if not arg_atoms:
                    return f"q_ctor_alloc({tag}, 0)"
                # Each field gets cast to int64_t so we can pass via va_args.
                # Pointers (q_value_t*, const char*) fit in int64_t on the
                # platforms quartz targets; bool zero-extends; int64_t is
                # itself.
                casted = ", ".join(f"(int64_t)(intptr_t){a}" for a in arg_atoms)
                return f"q_ctor_alloc({tag}, {len(arg_atoms)}, {casted})"
            # Top-level fn call (possibly generic).
            if name not in self.fn_signatures:
                raise NameError(
                    f"Quartz: unknown function or constructor in call: {name}"
                )
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
            # Emit args; cast to int64_t when the formal slot contains a
            # TyVar. The intptr_t bridge is universal — works for ints,
            # bools, and pointers (q_value_t*, const char*).
            arg_atoms = []
            for arg, formal in zip(e.args, param_tys):
                atom = self.emit_expr(arg)
                if _contains_tyvar(formal):
                    atom = f"(int64_t)(intptr_t)({atom})"
                arg_atoms.append(atom)
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

    def _emit_match(self, m: "glass.Match") -> str:
        """Emit a Match as an if/else chain over the scrutinee's tag,
        storing the chosen arm's value in a fresh result variable."""
        scrut_ty = self.type_of(m.scrutinee)
        if not isinstance(scrut_ty, glass.TyADT):
            raise NotImplementedError(
                f"Quartz v3.2: `match` is supported only over ADT scrutinees; "
                f"got {scrut_ty}"
            )
        scrut_atom = self.emit_expr(m.scrutinee)
        scrut_var = self.fresh()
        self.stmts.append(f"q_value_t* {scrut_var} = {scrut_atom};")
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
        the scrutinee. Variable-binding patterns (wild, ident) always match,
        so emit `true`. Ctor patterns test the tag."""
        if pat.kind == "wild" or pat.kind == "ident":
            return "true"
        if pat.kind == "ctor":
            ctor_name = pat.value
            if ctor_name not in self.ctor_tags:
                raise NameError(
                    f"Quartz: unknown constructor in pattern: {ctor_name}"
                )
            tag = self.ctor_tags[ctor_name]
            return f"{scrut_var}->tag == {tag}"
        if pat.kind == "record":
            # Records have a single tag (the record's name). The pattern
            # always matches; the binding step is what does the work.
            rec_name = pat.value
            if rec_name not in self.ctor_tags:
                raise NameError(
                    f"Quartz: unknown record in pattern: {rec_name}"
                )
            tag = self.ctor_tags[rec_name]
            return f"{scrut_var}->tag == {tag}"
        raise NotImplementedError(
            f"Quartz v3.2: pattern kind {pat.kind!r} not supported"
        )

    def _emit_pattern_bindings(self, pat, scrut_var: str) -> list:
        """Emit C bindings for pattern variables. Returns the (name, ty)
        pairs introduced (mirrors _collect_pattern_bindings)."""
        bindings: list[tuple[str, glass.Ty]] = []
        scrut_ty_or_none = None  # filled in for ident patterns
        if pat.kind == "wild":
            return bindings
        if pat.kind == "ident":
            # Top-level ident pattern binds the whole scrutinee. The type
            # must come from somewhere — we don't have it inline, so look
            # it up via the parent type_of context. For v3.2 simplicity,
            # ident at top of arm is only used when scrutinee is ADT, and
            # bindings get TyADT type.
            # We don't actually use ident-at-top in our v3.2 demos; require
            # ctor pattern for ADT match.
            raise NotImplementedError(
                "Quartz v3.2: bare identifier patterns at top of match arm "
                "are not supported; use a constructor pattern or `_`"
            )
        if pat.kind == "ctor":
            ctor_name = pat.value
            _, field_tys = self.ctor_env[ctor_name]
            sub_pats = pat.args if pat.args is not None else []
            for i, (sub, ft) in enumerate(zip(sub_pats, field_tys)):
                if sub.kind == "ident":
                    name = sub.value
                    c_ty = c_type_for_ty(ft)
                    # Cast through intptr_t to silence "cast to pointer from
                    # different size" warnings when ft is a pointer type.
                    self.stmts.append(
                        f"    {c_ty} {mangle(name)} = "
                        f"({c_ty})(intptr_t){scrut_var}->fields[{i}];"
                    )
                    bindings.append((name, ft))
                # wild: nothing to bind
        if pat.kind == "record":
            rec_name = pat.value
            fields = self.record_env[rec_name]
            field_ty_map = {fn: (i, ft) for i, (fn, ft) in enumerate(fields)}
            field_names = pat.args if pat.args is not None else []
            for fn in field_names:
                idx, ft = field_ty_map[fn]
                c_ty = c_type_for_ty(ft)
                self.stmts.append(
                    f"    {c_ty} {mangle(fn)} = "
                    f"({c_ty})(intptr_t){scrut_var}->fields[{idx}];"
                )
                bindings.append((fn, ft))
        return bindings


# === Top-level program compilation ======================================

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
    next_tag = 0

    # If the host's checker is available, seed the env/tag maps from its
    # registries first. This pulls in prelude types (Option, Result, Pair)
    # and any ADT/record that came from PRELUDE plus our own decls.
    if checker is not None:
        for name, (params, variants) in checker.adt_registry.items():
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
            for v in d.variants:
                ctor_env[v.name] = (d.name, list(v.fields))
                ctor_tags[v.name] = next_tag
                next_tag += 1
        for d in record_decls:
            record_env[d.name] = list(d.fields)
            ctor_tags[d.name] = next_tag
            next_tag += 1

    # Validate FnDecls — v3.4.x restrictions: no effectful functions.
    # Generic functions (`fn id<T>(...)` with type_params) are supported
    # via type erasure: type-variable params and returns lower to int64_t
    # in C; call sites cast args going in and results coming out.
    for d in fn_decls:
        if d.effects != glass.PURE:
            raise NotImplementedError(
                f"Quartz v3.4 does not support effectful functions; "
                f"`fn {d.name}(...) !{{...}}` is deferred to v3.x"
            )

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

    # Pass 2: emit each fn body as a C function definition.
    fn_definitions: list[str] = []
    for d in fn_decls:
        cg = Codegen(fn_signatures=fn_signatures,
                     ctor_env=ctor_env, ctor_tags=ctor_tags,
                     record_env=record_env)
        # Seed type_env with the params.
        for n, t in d.params:
            cg.type_env[n] = t
        body_atom = cg.emit_expr(d.body)
        body_stmts = list(cg.stmts)
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
                 record_env=record_env)
    *bindings, final = let_decls

    for d in bindings:
        val_ty = cg.type_of(d.value)
        val_atom = cg.emit_expr(d.value)
        c_ty = c_type_for_ty(val_ty)
        cg.stmts.append(f"{c_ty} {mangle(d.name)} = {val_atom};")
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

    # Type-check by walking with the existing checker. If anything fails,
    # codegen below will also fail — but checking here gives better errors.
    # We keep the post-check checker so codegen can consult inferred types
    # for polymorphic final expressions.
    checker, env = glass.make_runtime()
    try:
        glass.install_program(decls, checker, env, verbose=False)
    except (glass.TypeError_, SyntaxError) as ex:
        raise RuntimeError(f"type/parse error: {ex}")

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
        result = subprocess.run(
            [cc, c_file, "-o", output_binary, "-O2"],
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
        description="Quartz: compile Glass to native binary (v3.0)"
    )
    p.add_argument("source", help=".glass source file")
    p.add_argument("-o", "--output", default="a.out", help="output binary")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="print generated C source")
    p.add_argument("--cc", default="cc", help="C compiler to invoke")
    args = p.parse_args()

    try:
        build(args.source, args.output, cc=args.cc, verbose=args.verbose)
    except Exception as ex:
        print(f"glass-build: {ex}", file=sys.stderr)
        raise SystemExit(1)
    print(f"compiled: {args.output}")


if __name__ == "__main__":
    cli()
