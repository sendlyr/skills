"""Canonical shared block: the small, safe condition language.

Grammar (see docs/data-contracts.md, "Condition language"):

    expr       := and_expr ("or" and_expr)*
    and_expr   := atom ("and" atom)*
    atom       := "(" expr ")" | comparison
    comparison := FIELD OP VALUE
    OP         := == | != | > | >= | < | <=
    VALUE      := number | "double-quoted string" | true | false | null

No arithmetic, no function calls, no eval. A blank or absent field is null; any
comparison with a null value is false except ``== null`` / ``!= null``.
"""

# --- BEGIN shared:conditions (generated from scripts/shared/conditions.py; do not edit here) ---
import re as _re

_TOKEN = _re.compile(
    r'\s*(?:(?P<lp>\()|(?P<rp>\))|(?P<op>==|!=|>=|<=|>|<)|(?P<str>"(?:[^"\\]|\\.)*")'
    r'|(?P<num>-?\d+(?:\.\d+)?)|(?P<word>[A-Za-z_][A-Za-z0-9_.]*))'
)
_KEYWORDS = {"and", "or", "true", "false", "null"}
_TRUTHY = {"1", "true", "yes", "y", "t"}
_FALSY = {"0", "false", "no", "n", "f"}


class ConditionError(ValueError):
    """A rule could not be parsed."""


def _tokenize(text):
    pos, out = 0, []
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise ConditionError(f"cannot parse condition {text!r} near position {pos}: {text[pos:pos + 12]!r}")
        kind = m.lastgroup
        value = m.group(kind)
        out.append((kind, value))
        pos = m.end()
    return out


def _as_number(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        low = s.lower()
        if low in _TRUTHY:
            return 1.0
        if low in _FALSY:
            return 0.0
        return None


def _as_bool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s == "":
        return None
    if s in _TRUTHY:
        return True
    if s in _FALSY:
        return False
    return None


def _is_null(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


def _compare(field, op, lit_kind, lit):
    def check(row):
        raw = row.get(field)
        if lit_kind == "null":
            return _is_null(raw) if op == "==" else not _is_null(raw)
        if _is_null(raw):
            return False
        if lit_kind == "num":
            x = _as_number(raw)
            if x is None:
                return False
            y = lit
        elif lit_kind == "bool":
            x = _as_bool(raw)
            if x is None:
                return False
            y = lit
        else:
            x = str(raw).strip() if not isinstance(raw, bool) else ("true" if raw else "false")
            y = lit
        if op == "==":
            return x == y
        if op == "!=":
            return x != y
        if op == ">":
            return x > y
        if op == ">=":
            return x >= y
        if op == "<":
            return x < y
        return x <= y
    return check


class _Parser:
    def __init__(self, text):
        self.text = text
        self.toks = _tokenize(text)
        self.i = 0
        self.fields = set()

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def fail(self, msg):
        raise ConditionError(f"{msg} in condition {self.text!r}")

    def parse(self):
        if not self.toks:
            self.fail("empty condition")
        fn = self.expr()
        if self.i != len(self.toks):
            self.fail(f"unexpected {self.peek()[1]!r}")
        return fn

    def expr(self):
        parts = [self.and_expr()]
        while self.peek() == ("word", "or"):
            self.take()
            parts.append(self.and_expr())
        if len(parts) == 1:
            return parts[0]
        return lambda row, ps=tuple(parts): any(p(row) for p in ps)

    def and_expr(self):
        parts = [self.atom()]
        while self.peek() == ("word", "and"):
            self.take()
            parts.append(self.atom())
        if len(parts) == 1:
            return parts[0]
        return lambda row, ps=tuple(parts): all(p(row) for p in ps)

    def atom(self):
        kind, value = self.peek()
        if kind == "lp":
            self.take()
            fn = self.expr()
            if self.take()[0] != "rp":
                self.fail("missing ')'")
            return fn
        if kind != "word" or value in _KEYWORDS:
            self.fail(f"expected a field name, got {value!r}")
        field = self.take()[1]
        self.fields.add(field)
        kind, op = self.take()
        if kind != "op":
            self.fail(f"expected a comparison after {field!r}")
        kind, raw = self.take()
        if kind == "num":
            return _compare(field, op, "num", float(raw))
        if kind == "str":
            if op not in ("==", "!="):
                self.fail(f"strings only support == and != ({field} {op} {raw})")
            return _compare(field, op, "str", raw[1:-1].replace('\\"', '"').replace("\\\\", "\\"))
        if kind == "word" and raw in ("true", "false"):
            if op not in ("==", "!="):
                self.fail(f"booleans only support == and != ({field} {op} {raw})")
            return _compare(field, op, "bool", raw == "true")
        if kind == "word" and raw == "null":
            if op not in ("==", "!="):
                self.fail(f"null only supports == and != ({field} {op} null)")
            return _compare(field, op, "null", None)
        self.fail(f"expected a value after {field} {op}")


def compile_condition(text):
    """Compile a rule into (predicate, referenced_fields). Raises ConditionError."""
    parser = _Parser(str(text))
    fn = parser.parse()
    return fn, frozenset(parser.fields)
# --- END shared:conditions ---
