#!/usr/bin/env python3
"""Deterministic claim checker for AI-written lifecycle emails.

Run it on every AI-written draft BEFORE a human reviews it. It reads
claim-rules.toml and emails.json (docs/data-contracts.md, "claim-rules.toml and
emails.json") and reports every blocker and warning, quoting the offending text
and saying what to write instead.

Check families: prohibited, pattern, fact_rule, cta, greeting, product_name,
required; in template mode also unknown_placeholder, literal_name_in_template,
literal_value_in_template and cross_user_name.

Python 3.11+, standard library only. Nothing is sent over the network.
"""

import argparse
import difflib
import json
import math
import re
from pathlib import Path

# --- BEGIN shared:common (generated from scripts/shared/common.py; do not edit here) ---
import csv as _csv
import json as _json
import math as _math
import sys as _sys
from datetime import date as _date, datetime as _datetime, timezone as _timezone
from pathlib import Path as _Path

TRUE_VALUES = {"1", "true", "yes", "y", "t"}
FALSE_VALUES = {"0", "false", "no", "n", "f"}


class InputError(Exception):
    """Malformed input. The message names the file, row and column."""


def parse_bool(value, where=""):
    """Return True/False, or None for blank. Raise InputError for anything else."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value in (0, 1):
            return bool(value)
        raise InputError(f"{where}: expected a boolean (1/0, true/false), got {value!r}")
    text = str(value).strip().lower()
    if text == "":
        return None
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    raise InputError(f"{where}: expected a boolean (1/0, true/false), got {value!r}")


def parse_time(value, where=""):
    """Parse ISO 8601. Naive values and dates are UTC. Return None for blank."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        if len(text) == 10:
            d = _date.fromisoformat(text)
            return _datetime(d.year, d.month, d.day, tzinfo=_timezone.utc)
        if text.endswith("Z") or text.endswith("z"):
            text = text[:-1] + "+00:00"
        dt = _datetime.fromisoformat(text)
    except ValueError:
        raise InputError(f"{where}: expected an ISO 8601 timestamp, got {value!r}") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_timezone.utc)
    return dt.astimezone(_timezone.utc)


def parse_number(value, where=""):
    """Return float, or None for blank."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        raise InputError(f"{where}: expected a number, got {value!r}") from None


def read_csv(path, required=()):
    """Read a CSV into a list of dicts (values stripped). Each row gets '_where' = 'file:line'."""
    p = _Path(path)
    if not p.exists():
        raise InputError(f"{path}: file not found")
    with p.open(newline="", encoding="utf-8-sig") as fh:
        reader = _csv.DictReader(fh)
        header = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in required if c not in header]
        if missing:
            raise InputError(f"{path}: missing required column(s): {', '.join(missing)} "
                             f"(found: {', '.join(header) or 'no header'})")
        rows = []
        for i, raw in enumerate(reader, start=2):
            row = {(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
            row["_where"] = f"{p.name}:{i}"
            rows.append(row)
    return rows


def load_toml(path):
    import tomllib
    p = _Path(path)
    if not p.exists():
        raise InputError(f"{path}: file not found")
    try:
        with p.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise InputError(f"{path}: invalid TOML: {exc}") from None


def _json_safe(obj):
    if isinstance(obj, float):
        return obj if _math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (_datetime, _date)):
        return obj.isoformat()
    return obj


def write_outputs(out_dir, report_md, result, quiet=False):
    """Write report.md and result.json to out_dir and echo the report to stdout."""
    out = _Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(report_md.rstrip() + "\n", encoding="utf-8")
    (out / "result.json").write_text(_json.dumps(_json_safe(result), indent=2, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
    if not quiet:
        print(report_md.rstrip())


def pct(x, digits=1):
    """Format a proportion as a percentage string; '—' for missing."""
    if x is None or (isinstance(x, float) and not _math.isfinite(x)):
        return "—"
    return f"{100 * x:.{digits}f}%"


def pp(x, digits=1):
    """Format a difference of proportions in percentage points."""
    if x is None or (isinstance(x, float) and not _math.isfinite(x)):
        return "—"
    return f"{100 * x:+.{digits}f}pp"


def run_main(main):
    """Call main(); turn InputError into exit code 2 with a clean message."""
    try:
        code = main()
    except InputError as exc:
        print(f"error: {exc}", file=_sys.stderr)
        _sys.exit(2)
    _sys.exit(code or 0)
# --- END shared:common ---

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


SCHEMA_VERSION = 1
LEVELS = ("blocker", "warning")
REMINDER = "This check catches known mistakes. A human still approves every email before it is sent."
DEFAULT_NAME_FIELD = "first_name"
DEFAULT_FALLBACK = "Hi there,"
GENERIC_GREETING_WORDS = {"there", "all", "everyone", "friend", "friends"}

# One-for-one replacements, so match positions in the normalised text are valid in the original.
_PUNCT = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2033": '"',
    "\u00a0": " ", "\u2007": " ", "\u2009": " ", "\u202f": " ",
})

_GREETING = re.compile(
    r"^\s*(?P<word>hi|hello|hey|hiya|howdy|dear|greetings|good\s+(?:morning|afternoon|evening))(?!\w)"
    r"[ \t]*,?[ \t]*"
    r"(?P<name>[^\s,!.?:;]+(?:[ \t]+[^\s,!.?:;]+){0,2})?"
    r"[ \t]*(?:[,!.?:;\n]|$)",
    re.IGNORECASE,
)
_DOUBLE = re.compile(r"\{\{(.*?)\}\}", re.S)
_TAG = re.compile(r"\{%.*?%\}", re.S)
_SINGLE = re.compile(r"(?<!\{)\{[ \t]*([A-Za-z_][A-Za-z0-9_.]*)[ \t]*\}(?!\})")
_PLAIN_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _norm(text):
    return text.translate(_PUNCT)


def _collapse(text):
    return " ".join(str(text).split())


def _is_blank(value):
    return value is None or (isinstance(value, str) and value.strip() == "")


def _quote(text, limit=120):
    text = _collapse(text)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return f'"{text}"'


def _ph(name):
    return "{{ " + name + " }}"


def _fmt_num(x):
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def _fmt_fact(value):
    if _is_blank(value):
        return "blank"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return _fmt_num(value)
    return f'"{value}"'


def _numeric(value):
    """A fact value as a number, or None (blank, boolean or not a number)."""
    if isinstance(value, bool) or _is_blank(value):
        return None
    try:
        x = float(value) if isinstance(value, (int, float)) else float(str(value).strip())
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def phrase_regex(phrase, where, case_sensitive=False):
    """Match a phrase on word boundaries, tolerant of any run of whitespace between words."""
    words = _norm(str(phrase)).split()
    if not words:
        raise InputError(f"{where}: empty phrase")
    body = r"\s+".join(re.escape(w) for w in words)
    lead = r"(?<!\w)" if re.match(r"\w", words[0]) else ""
    tail = r"(?!\w)" if re.search(r"\w$", words[-1]) else ""
    return re.compile(lead + body + tail, 0 if case_sensitive else re.IGNORECASE)


def _token_regex(token):
    m = re.fullmatch(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", token)
    if m:
        return re.compile(r"\{\{\s*" + re.escape(m.group(1)) + r"\s*\}\}")
    return re.compile(re.escape(token))


def _issue(family, level, field, text, message):
    return {"family": family, "level": level, "message": message, "field": field, "text": text}


def _severity(issues):
    if any(i["level"] == "blocker" for i in issues):
        return "BLOCKED"
    return "WARNINGS" if issues else "CLEAN"


# ---------------------------------------------------------------------------
# claim-rules.toml
# ---------------------------------------------------------------------------

class Rules:
    """A validated claim-rules.toml."""

    def __init__(self):
        self.product_name = ""
        self.forbidden_names = []          # [(name, regex)]
        self.ctas = []                     # [{key, label, url, label_rx}]
        self.prohibited = []               # [{phrase, regex, level, reason}]
        self.patterns = []                 # [{source, regex, level, reason}]
        self.fact_rules = []               # [{when, predicate, fields, forbid, level, reason}]
        self.name_field = DEFAULT_NAME_FIELD
        self.fallback = DEFAULT_FALLBACK
        self.generic_names = set(GENERIC_GREETING_WORDS)
        self.footer_required = False
        self.unsubscribe_token = ""
        self.unsubscribe_rx = None
        self.allowed_placeholders = None   # None = [template] not configured


def _table(data, key, fname):
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise InputError(f"{fname}: [{key}] must be a table")
    return value


def _array_of_tables(data, key, fname):
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise InputError(f"{fname}: [[{key}]] must be an array of tables")
    return value


def _rule_str(value, where, required=False):
    if value is None:
        if required:
            raise InputError(f"{where} is required")
        return ""
    if not isinstance(value, str):
        raise InputError(f"{where} must be a string, got {value!r}")
    if required and not value.strip():
        raise InputError(f"{where} must not be empty")
    return value


def _rule_str_list(value, where, required=False):
    if value is None:
        if required:
            raise InputError(f"{where} is required")
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise InputError(f"{where} must be a list of strings")
    if any(not v.strip() for v in value):
        raise InputError(f"{where} contains an empty string")
    if required and not value:
        raise InputError(f"{where} must list at least one entry")
    return value


def _rule_level(entry, where):
    level = entry.get("level", "blocker")
    if not isinstance(level, str) or level.strip().lower() not in LEVELS:
        raise InputError(f'{where}: level must be "blocker" or "warning", got {level!r}')
    return level.strip().lower()


def _rule_where(fname, table, index, reason):
    return f"{fname}: [[{table}]] #{index}" + (f' ("{reason}")' if reason else "")


def load_rules(path):
    data = load_toml(path)
    fname = Path(path).name
    rules = Rules()

    product = _table(data, "product", fname)
    rules.product_name = _rule_str(product.get("name"), f"{fname}: [product].name").strip()
    where = f"{fname}: [product].forbidden_names"
    for name in _rule_str_list(product.get("forbidden_names"), where):
        rules.forbidden_names.append((name.strip(), phrase_regex(name, where)))

    for i, entry in enumerate(_array_of_tables(data, "cta", fname), start=1):
        where = f"{fname}: [[cta]] #{i}"
        label = _rule_str(entry.get("label"), f"{where} label", required=True).strip()
        url = _rule_str(entry.get("url"), f"{where} url", required=True).strip()
        key = _rule_str(entry.get("key"), f"{where} key").strip() or label
        rules.ctas.append({"key": key, "label": label, "url": url, "label_rx": phrase_regex(label, where)})

    for i, entry in enumerate(_array_of_tables(data, "prohibited", fname), start=1):
        reason = _rule_str(entry.get("reason"), f"{fname}: [[prohibited]] #{i} reason").strip()
        where = _rule_where(fname, "prohibited", i, reason)
        level = _rule_level(entry, where)
        for phrase in _rule_str_list(entry.get("phrases"), f"{where} phrases", required=True):
            rules.prohibited.append({"phrase": phrase, "regex": phrase_regex(phrase, where),
                                     "level": level, "reason": reason})

    for i, entry in enumerate(_array_of_tables(data, "patterns", fname), start=1):
        reason = _rule_str(entry.get("reason"), f"{fname}: [[patterns]] #{i} reason").strip()
        where = _rule_where(fname, "patterns", i, reason)
        source = _rule_str(entry.get("regex"), f"{where} regex", required=True)
        level = _rule_level(entry, where)
        try:
            rx = re.compile(source, re.IGNORECASE)
        except re.error as exc:
            raise InputError(f"{where}: invalid regex {source!r}: {exc}") from None
        rules.patterns.append({"source": source, "regex": rx, "level": level, "reason": reason})

    for i, entry in enumerate(_array_of_tables(data, "fact_rules", fname), start=1):
        reason = _rule_str(entry.get("reason"), f"{fname}: [[fact_rules]] #{i} reason").strip()
        where = _rule_where(fname, "fact_rules", i, reason)
        when = _rule_str(entry.get("when"), f"{where} when", required=True)
        try:
            predicate, fields = compile_condition(when)
        except ConditionError as exc:
            raise InputError(f"{where}: invalid condition: {exc}") from None
        forbid = [(p, phrase_regex(p, where))
                  for p in _rule_str_list(entry.get("forbid"), f"{where} forbid", required=True)]
        rules.fact_rules.append({"when": when.strip(), "predicate": predicate, "fields": sorted(fields),
                                 "forbid": forbid, "level": _rule_level(entry, where), "reason": reason})

    greeting = _table(data, "greeting", fname)
    rules.name_field = (_rule_str(greeting.get("verified_name_field"),
                                  f"{fname}: [greeting].verified_name_field").strip() or DEFAULT_NAME_FIELD)
    rules.fallback = _rule_str(greeting.get("fallback", DEFAULT_FALLBACK), f"{fname}: [greeting].fallback").strip()
    m = _GREETING.match(_norm(rules.fallback)) if rules.fallback else None
    if m and m.group("name"):
        rules.generic_names.add(_collapse(m.group("name")).casefold())

    required = _table(data, "required", fname)
    footer = required.get("footer", False)
    if not isinstance(footer, bool):
        raise InputError(f"{fname}: [required].footer must be true or false, got {footer!r}")
    rules.footer_required = footer
    rules.unsubscribe_token = _rule_str(required.get("unsubscribe_token"),
                                        f"{fname}: [required].unsubscribe_token").strip()
    rules.unsubscribe_rx = _token_regex(rules.unsubscribe_token) if rules.unsubscribe_token else None

    if "template" in data:
        template = _table(data, "template", fname)
        where = f"{fname}: [template].allowed_placeholders"
        names = _rule_str_list(template.get("allowed_placeholders"), where)
        for name in names:
            if not _PLAIN_NAME.fullmatch(name.strip()):
                raise InputError(f"{where}: {name!r} is not a plain placeholder name (write first_name, not {_ph('first_name')})")
        rules.allowed_placeholders = {n.strip() for n in names}
    return rules


# ---------------------------------------------------------------------------
# emails.json
# ---------------------------------------------------------------------------

def _json_text(value, where):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise InputError(f"{where}: expected text, got {type(value).__name__} {value!r}")
    return value


def _parse_email(email, where):
    """Return the ordered list of (field, text) for customer-facing text, plus the CTA URL."""
    if not isinstance(email, dict):
        raise InputError(f'{where}: "email" must be an object')
    fields = [(k, _json_text(email.get(k), f"{where}.{k}")) for k in ("subject", "preheader", "headline", "intro")]
    body = email.get("body")
    if body is None:
        body = []
    elif isinstance(body, str):
        body = [body]
    elif not isinstance(body, list):
        raise InputError(f"{where}.body: expected a list of paragraphs")
    fields += [(f"body[{i}]", _json_text(p, f"{where}.body[{i}]")) for i, p in enumerate(body)]
    fields.append(("cta_label", _json_text(email.get("cta_label"), f"{where}.cta_label")))
    fields.append(("footer", _json_text(email.get("footer"), f"{where}.footer")))
    return fields, _json_text(email.get("cta_url"), f"{where}.cta_url")


def _parse_items(raw_items, fname, key, default_state=""):
    items, seen = [], set()
    for i, raw in enumerate(raw_items):
        where = f"{fname}: {key}[{i}]"
        if not isinstance(raw, dict):
            raise InputError(f"{where}: expected an object")
        item_id = raw.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            raise InputError(f'{where}: needs a non-empty string "id"')
        if item_id in seen:
            raise InputError(f"{where}: duplicate id {item_id!r}")
        seen.add(item_id)
        facts = raw.get("facts") or {}
        if not isinstance(facts, dict):
            raise InputError(f'{where} ({item_id}): "facts" must be an object')
        state = _json_text(raw.get("state"), f"{where}.state") or default_state
        fields, cta_url = _parse_email(raw.get("email"), f"{where} ({item_id}).email")
        items.append({"id": item_id, "state": state, "facts": facts, "fields": fields, "cta_url": cta_url})
    return items


def load_emails(path):
    p = Path(path)
    if not p.exists():
        raise InputError(f"{path}: file not found")
    fname = p.name
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError:
        raise InputError(f"{fname}: not UTF-8 text") from None
    except json.JSONDecodeError as exc:
        raise InputError(f"{fname}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from None
    if not isinstance(data, dict):
        raise InputError(f"{fname}: the top level must be a JSON object")
    if "template" in data or "renders" in data:
        tpl = data.get("template")
        if not isinstance(tpl, dict):
            raise InputError(f'{fname}: "template" must be an object with an "email" object')
        state = _json_text(tpl.get("state"), f"{fname}: template.state")
        fields, cta_url = _parse_email(tpl.get("email"), f"{fname}: template.email")
        renders = data.get("renders")
        if not isinstance(renders, list):
            raise InputError(f'{fname}: "renders" must be a list')
        return {"mode": "template", "file": fname,
                "template": {"state": state, "fields": fields, "cta_url": cta_url},
                "items": _parse_items(renders, fname, "renders", default_state=state)}
    if "emails" in data:
        if not isinstance(data["emails"], list):
            raise InputError(f'{fname}: "emails" must be a list')
        return {"mode": "emails", "file": fname, "items": _parse_items(data["emails"], fname, "emails")}
    raise InputError(f'{fname}: expected {{"emails": [...]}} or {{"template": {{...}}, "renders": [...]}}')


def _field(item, name):
    return next((text for label, text in item["fields"] if label == name), "")


# ---------------------------------------------------------------------------
# Per-email checks
# ---------------------------------------------------------------------------

def _reason(reason):
    return f" ({reason})" if reason else ""


def check_prohibited(rules, norm):
    issues = []
    for rule in rules.prohibited:
        for label, text, ntext in norm:
            m = rule["regex"].search(ntext)
            if not m:
                continue
            found = text[m.start():m.end()]
            if rule["level"] == "blocker":
                kind, fix = "prohibited", "Remove it; make only claims the approved product memory supports."
            else:
                kind, fix = "discouraged", "Prefer calmer wording; it can stay only if the reviewer accepts it explicitly."
            issues.append(_issue("prohibited", rule["level"], label, found,
                                 f"{label}: {_quote(found)} is a {kind} phrase{_reason(rule['reason'])}. {fix}"))
    return issues


def check_patterns(rules, norm):
    issues = []
    for rule in rules.patterns:
        for label, text, ntext in norm:
            seen = set()
            for m in rule["regex"].finditer(ntext):
                found = text[m.start():m.end()]
                if not found or found.casefold() in seen:
                    continue
                seen.add(found.casefold())
                issues.append(_issue(
                    "pattern", rule["level"], label, found,
                    f"{label}: {_quote(found)} matches a banned pattern{_reason(rule['reason'])}. "
                    "Rewrite the sentence without this detail (describe what the person did, not an exact figure)."))
    return issues


def _mask_cta_labels(rules, ntext):
    """Blank out approved CTA labels: a call to action is an ask, not a claim about the reader."""
    for cta in rules.ctas:
        ntext = cta["label_rx"].sub(lambda m: "\x00" * len(m.group(0)), ntext)
    return ntext


def check_fact_rules(rules, norm, facts):
    issues = []
    masked = [(label, text, _mask_cta_labels(rules, ntext)) for label, text, ntext in norm]
    for rule in rules.fact_rules:
        fired = rule["predicate"](facts)
        missing = [f for f in rule["fields"] if _is_blank(facts.get(f))]
        if not fired and not missing:
            continue
        shown = ", ".join(f"{f} = {_fmt_fact(facts.get(f))}" for f in rule["fields"])
        for phrase, rx in rule["forbid"]:
            for label, text, mtext in masked:
                m = rx.search(mtext)
                if not m:
                    continue
                found = text[m.start():m.end()]
                if fired:
                    issues.append(_issue(
                        "fact_rule", rule["level"], label, found,
                        f"{label}: {_quote(found)} contradicts this user's facts{_reason(rule['reason'])}: "
                        f"{shown} (rule: {rule['when']}). Remove it, or say only what the facts support."))
                else:
                    issues.append(_issue(
                        "fact_rule", "warning", label, found,
                        f"{label}: {_quote(found)} cannot be checked{_reason(rule['reason'])}: "
                        f"{', '.join(missing)} is blank or missing (rule: {rule['when']}). "
                        "Add the fact before review, or remove the claim."))
    return issues


def _closest_cta(ctas, label, url):
    def score(c):
        return (difflib.SequenceMatcher(None, label.casefold(), c["label"].casefold()).ratio()
                + difflib.SequenceMatcher(None, url, c["url"]).ratio())
    return max(ctas, key=score)


def check_cta(rules, item):
    if not rules.ctas:
        return []
    label = _field(item, "cta_label").strip()
    url = item["cta_url"].strip()
    if any(c["label"] == label and c["url"] == url for c in rules.ctas):
        return []
    best = _closest_cta(rules.ctas, label, url)
    closest = f' Closest allowlisted CTA: {best["key"]} ({_quote(best["label"])} → {best["url"]}).'
    shown = f'{_quote(label) if label else "(no label)"} → {url or "(no URL)"}'
    same_label = [c for c in rules.ctas if label and c["label"] == label]
    same_url = [c for c in rules.ctas if url and c["url"] == url]
    if not label and not url:
        msg = "cta: this email has no CTA. Use exactly one CTA from the allowlist, label and URL as written."
    elif same_label:
        urls = " or ".join(c["url"] for c in same_label)
        msg = (f"cta: the label {_quote(label)} is approved only with {urls}, but this email links to "
               f"{url or '(no URL)'}. Use the approved URL for this label.")
    elif same_url:
        labels = " or ".join(_quote(c["label"]) for c in same_url)
        msg = (f"cta: {shown} is not an approved pair; that URL is approved with the label {labels}. "
               "Use the approved label exactly as written.")
    else:
        msg = f"cta: {shown} is not in the CTA allowlist. Use an approved CTA exactly as written."
    issue = _issue("cta", "blocker", "cta", f"{label} → {url}", msg + closest)
    issue["closest"] = best["key"]
    return [issue]


def check_greeting(rules, item):
    intro = _field(item, "intro")
    nintro = _norm(intro)
    name = item["facts"].get(rules.name_field)
    field = rules.name_field
    fallback = rules.fallback
    m = _GREETING.match(nintro)
    greeted = _collapse(m.group("name") or "") if m else ""
    shown = intro[m.start("word"):m.end()].strip() if m else intro.strip()
    if _is_blank(name):
        if fallback and _collapse(nintro).casefold().startswith(_collapse(_norm(fallback)).casefold()):
            return []
        if greeted and greeted.casefold() not in rules.generic_names:
            fix = f"start the intro with {_quote(fallback)}" if fallback else "greet without a name"
            msg = (f"intro: {_quote(shown)} greets {_quote(greeted)}, but {field} is blank. Never guess a name "
                   f"from an email address or username: {fix}.")
        elif fallback:
            what = _quote(shown) if intro.strip() else "the intro is empty; it"
            msg = f"intro: {what} must start with {_quote(fallback)} because {field} is blank."
        else:
            return []
        return [_issue("greeting", "blocker", "intro", shown, msg)]
    verified = _collapse(name)
    if greeted and greeted.casefold() not in rules.generic_names and greeted.casefold() != verified.casefold():
        word = _collapse(m.group("word"))
        alt = f" or {_quote(fallback)}" if fallback else ""
        msg = (f"intro: {_quote(shown)} greets {_quote(greeted)}, but the verified {field} is {_quote(verified)}. "
               f"Use {_quote(word + ' ' + verified + ',')}{alt}.")
        return [_issue("greeting", "blocker", "intro", shown, msg)]
    return []


def check_product_names(rules, norm):
    issues = []
    product = _quote(rules.product_name) if rules.product_name else "its customer-facing name"
    for name, rx in rules.forbidden_names:
        for label, text, ntext in norm:
            m = rx.search(ntext)
            if m:
                found = text[m.start():m.end()]
                issues.append(_issue("product_name", "blocker", label, found,
                                     f"{label}: {_quote(found)} is an internal or plan name. "
                                     f"Customer copy must call the product {product}."))
    return issues


def check_required(rules, item):
    issues = []
    footer = _field(item, "footer")
    if rules.footer_required and not footer.strip():
        issues.append(_issue("required", "blocker", "footer", "",
                             "footer: the footer is empty. Add the standard footer (why they get this email, "
                             "and the unsubscribe link)."))
    if rules.unsubscribe_rx is not None:
        texts = [t for label, t in item["fields"] if label == "footer" or label.startswith("body[")]
        if not any(rules.unsubscribe_rx.search(t) for t in texts):
            issues.append(_issue("required", "blocker", "footer", rules.unsubscribe_token,
                                 f"footer: the unsubscribe token {_quote(rules.unsubscribe_token)} is missing from "
                                 "the footer and body. Add it to the footer, exactly as written."))
    return issues


def scan_placeholders(text):
    """Return [(kind, token, name)]. kind: name, syntax, single, stray."""
    out = []
    for m in _DOUBLE.finditer(text):
        inner = m.group(1).strip()
        if _PLAIN_NAME.fullmatch(inner):
            out.append(("name", m.group(0), inner))
        else:
            out.append(("syntax", m.group(0), ""))
    for m in _TAG.finditer(text):
        out.append(("syntax", m.group(0), ""))
    rest = _TAG.sub(" ", _DOUBLE.sub(" ", text))
    for m in _SINGLE.finditer(rest):
        out.append(("single", m.group(0), m.group(1)))
    for stray in ("{{", "}}"):
        if stray in rest:
            out.append(("stray", stray, ""))
    return out


def placeholder_issues(rules, fields, prefix, rendered):
    """unknown_placeholder issues for a template (rendered=False) or a rendered email (rendered=True)."""
    allowed = rules.allowed_placeholders
    ok_names = set(allowed or ())
    tok = _PLAIN_NAME.fullmatch(rules.unsubscribe_token.strip("{} ")) if rules.unsubscribe_token else None
    if tok:
        ok_names.add(tok.group(0))
    allowed_text = ", ".join(sorted(allowed)) if allowed else ""
    issues, used = [], set()
    for label, text in fields:
        where = f"{prefix}{label}"
        for kind, token, name in scan_placeholders(text):
            if kind == "name":
                used.add(name)
                if name in ok_names or (rendered and allowed is None):
                    continue
                if rendered:
                    msg = (f"{where}: {_quote(token)} is not an allowed placeholder and would reach the reader "
                           "unrendered. Fill it in or remove it.")
                elif allowed is None:
                    msg = (f"{where}: {_quote(token)} cannot be used: claim-rules.toml has no "
                           "[template].allowed_placeholders, so no placeholder is allowed. List the safe ones there.")
                else:
                    msg = (f"{where}: {_quote(token)} is not an allowed placeholder. Remove it, or use one of: "
                           f"{allowed_text}.")
            elif kind == "single":
                note = "" if name in ok_names else f" ({name} is not an allowed placeholder either.)"
                msg = (f"{where}: {_quote(token)} is a malformed placeholder (single braces), so the renderer "
                       f"would print it as-is. Write it as {_quote(_ph(name))}.{note}")
            elif kind == "syntax":
                msg = (f"{where}: {_quote(token)} uses template syntax this check does not allow (filters, "
                       f"expressions or tags crash or mis-render). Use a plain placeholder such as "
                       f"{_quote(_ph('first_name'))}.")
            else:
                msg = (f"{where}: an unmatched {_quote(token)} is a malformed placeholder. Write placeholders as "
                       f"{_quote(_ph('name'))}.")
            issues.append(_issue("unknown_placeholder", "blocker", where, token, msg))
    return issues, used


def check_email(rules, item):
    norm = [(label, text, _norm(text)) for label, text in item["fields"]]
    issues = []
    issues += check_prohibited(rules, norm)
    issues += check_patterns(rules, norm)
    issues += check_fact_rules(rules, norm, item["facts"])
    issues += check_cta(rules, item)
    issues += check_greeting(rules, item)
    issues += check_product_names(rules, norm)
    issues += check_required(rules, item)
    issues += placeholder_issues(rules, item["fields"] + [("cta_url", item["cta_url"])], "", rendered=True)[0]
    return issues


# ---------------------------------------------------------------------------
# Group template checks
# ---------------------------------------------------------------------------

def _without_placeholders(text):
    text = _DOUBLE.sub(" ", text)
    text = _TAG.sub(" ", text)
    return _norm(_SINGLE.sub(" ", text))


def _first_name(rules, item):
    value = item["facts"].get(rules.name_field)
    return "" if _is_blank(value) else _collapse(value)


def check_template(rules, template, renders):
    """Template-level issues (field prefixed 'template.') and the placeholders it uses."""
    all_fields = template["fields"] + [("cta_url", template["cta_url"])]
    issues, used = placeholder_issues(rules, all_fields, "template.", rendered=False)
    stripped = [(label, _without_placeholders(text)) for label, text in template["fields"]]

    names = {}
    for r in renders:
        n = _first_name(rules, r)
        if n:
            names.setdefault(n, []).append(r["id"])
    for name, ids in names.items():
        rx = phrase_regex(name, f"{rules.name_field} of {ids[0]}", case_sensitive=True)
        for label, text in stripped:
            m = rx.search(text)
            if m:
                issues.append(_issue(
                    "literal_name_in_template", "blocker", f"template.{label}", m.group(0),
                    f"template.{label}: {_quote(m.group(0))} is the verified {rules.name_field} of "
                    f"{'a recipient' if len(ids) == 1 else str(len(ids)) + ' recipients'} in this group. "
                    "A group template must not hard-code a name: use "
                    f"{_quote(_ph(rules.name_field))} or remove it."))

    values = {}
    for r in renders:
        for key, raw in r["facts"].items():
            x = _numeric(raw)
            if x is not None:
                values.setdefault(key, set()).add(x)
    hits = {}
    for key in sorted(values):
        if len(values[key]) < 2:
            continue
        for x in sorted(values[key]):
            if x < 2:
                continue
            s = _fmt_num(x)
            rx = re.compile(r"(?<![\w.])" + re.escape(s) + r"(?!\w|[.,]\d)")
            for label, text in stripped:
                if rx.search(text):
                    hits.setdefault((label, s), []).append(key)
    for (label, s), keys in hits.items():
        varies = "; ".join(f"{k} is {', '.join(_fmt_num(v) for v in sorted(values[k]))}" for k in keys)
        usable = [k for k in keys if k in (rules.allowed_placeholders or ())]
        fix = (f"Use {_quote(_ph(usable[0]))} instead." if usable
               else "Remove the number, or add a safe placeholder for it to [template].allowed_placeholders.")
        issues.append(_issue(
            "literal_value_in_template", "blocker", f"template.{label}", s,
            f"template.{label}: {_quote(s)} is hard-coded, but it varies across renders ({varies}). {fix}"))
    return issues, used


def check_cross_user_names(rules, item, renders):
    own = _first_name(rules, item).casefold()
    others = {}
    for r in renders:
        n = _first_name(rules, r)
        if r is not item and n and n.casefold() != own:
            others.setdefault(n, []).append(r["id"])
    issues = []
    for name, ids in others.items():
        rx = phrase_regex(name, f"{rules.name_field} of {ids[0]}", case_sensitive=True)
        for label, text in item["fields"]:
            ntext = _norm(text)
            m = rx.search(ntext)
            if m:
                found = text[m.start():m.end()]
                issues.append(_issue(
                    "cross_user_name", "blocker", label, found,
                    f"{label}: {_quote(found)} is another recipient's {rules.name_field}. "
                    "Remove it: an email may name only its own recipient."))
    return issues


# ---------------------------------------------------------------------------
# Run, report, CLI
# ---------------------------------------------------------------------------

def run_checks(rules, data):
    items = data["items"]
    template_issues, used = [], set()
    if data["mode"] == "template":
        template_issues, used = check_template(rules, data["template"], items)
    results = {}
    for item in items:
        issues = check_email(rules, item)
        if data["mode"] == "template":
            issues += check_cross_user_names(rules, item, items)
            issues += [dict(i, from_template=True) for i in template_issues]
        sev = _severity(issues)
        results[item["id"]] = {
            "state": item["state"],
            "passed": sev != "BLOCKED",
            "severity": sev,
            "blockers": sum(i["level"] == "blocker" for i in issues),
            "warnings": sum(i["level"] == "warning" for i in issues),
            "issues": issues,
        }
    sevs = [r["severity"] for r in results.values()]
    all_issues = [i for r in results.values() for i in r["issues"]]
    summary = {
        "emails": len(results),
        "blockers": sevs.count("BLOCKED"),
        "warnings": sevs.count("WARNINGS"),
        "clean": sevs.count("CLEAN"),
        "blocker_issues": sum(i["level"] == "blocker" for i in all_issues),
        "warning_issues": sum(i["level"] == "warning" for i in all_issues),
    }
    result = {"schema_version": SCHEMA_VERSION, "tool": "claim_check.py", "mode": data["mode"],
              "summary": summary, "results": results}
    any_blocker = summary["blockers"] > 0
    if data["mode"] == "template":
        tsev = _severity(template_issues)
        families = {i["family"] for i in template_issues + all_issues if i["level"] == "blocker"}
        allowed = rules.allowed_placeholders
        result["template"] = {
            "state": data["template"]["state"],
            "passed": tsev != "BLOCKED",
            "severity": tsev,
            "issues": template_issues,
            "placeholders_used": sorted(used),
            "allowed_placeholders": sorted(allowed) if allowed is not None else [],
            "renders": len(items),
            "group_passed": tsev != "BLOCKED" and not any_blocker,
            "group_blocker_families": sorted(families),
        }
        summary["template_blocked"] = tsev == "BLOCKED"
        any_blocker = any_blocker or tsev == "BLOCKED"
    result["passed"] = not any_blocker
    return result


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ") or "—"


def _issue_line(issue):
    level = "Blocker" if issue["level"] == "blocker" else "Warning"
    return f"- **{level}** `{issue['family']}`: {issue['message']}"


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def build_report(result, rules_file, emails_file):
    s = result["summary"]
    template = result.get("template")
    lines = ["# Claim check" + (": group template" if template else ""), ""]
    if template:
        lines.append(f"`{rules_file}` applied to `{emails_file}`: one group template"
                     f"{' for state ' + template['state'] if template['state'] else ''} and "
                     f"{_plural(template['renders'], 'render')}.")
    else:
        lines.append(f"`{rules_file}` applied to `{emails_file}`.")
    lines += ["", f"**{_plural(s['emails'], 'email')}: {s['clean']} clean, {s['warnings']} with warnings, "
                  f"{s['blockers']} blocked**", ""]
    if template:
        if template["passed"]:
            lines.append("**Template: CLEAN.**")
        else:
            lines.append(f"**Template: BLOCKED** ({_plural(len(template['issues']), 'issue')}). No email from this "
                         "template can be approved until the template is fixed.")
        lines.append("")
    if not result["passed"]:
        lines += ["Fix every blocker and run the check again. A warning can stay only if the reviewer accepts it "
                  "explicitly.", ""]
    elif s["warnings"]:
        lines += ["No blockers. Each warning needs the reviewer's explicit OK.", ""]

    if template:
        lines += ["## Template", ""]
        lines += [_issue_line(i) for i in template["issues"]] or ["No template issues."]
        allowed = ", ".join(template["allowed_placeholders"]) or "none configured"
        lines += ["", f"Placeholders used: {', '.join(template['placeholders_used']) or 'none'}. "
                      f"Allowed: {allowed}.", "", "## Emails", ""]

    lines += ["| Email | State | Result | Issues |", "|---|---|---|---|"]
    for email_id, r in result["results"].items():
        n = len(r["issues"])
        inherited = sum(1 for i in r["issues"] if i.get("from_template"))
        count = f"{n} ({inherited} from template)" if inherited else str(n)
        lines.append(f"| {_cell(email_id)} | {_cell(r['state'])} | {r['severity']} | {count} |")

    flagged = [(k, r) for k, r in result["results"].items() if r["severity"] != "CLEAN"]
    if flagged:
        lines += ["", "## Details"]
        for email_id, r in flagged:
            lines += ["", f"### {email_id}: {r['severity']}", ""]
            own = [i for i in r["issues"] if not i.get("from_template")]
            inherited = len(r["issues"]) - len(own)
            lines += [_issue_line(i) for i in own]
            if inherited:
                lines.append(f"- {'Also blocked' if own else 'Blocked'} by the "
                             f"{_plural(inherited, 'template issue')} listed under Template.")
    lines += ["", "---", "", REMINDER]
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="claim_check.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Check AI-written lifecycle emails for known mistakes before a human reviews them.\n\n"
            "It flags prohibited phrases, banned patterns (such as exact usage metrics), claims\n"
            "that the user's own facts contradict, CTAs outside the allowlist, guessed or wrong\n"
            "greetings, internal product names, and a missing footer or unsubscribe link. For a\n"
            "group template it also flags unknown or malformed placeholders, names and counts\n"
            "hard-coded into the template, and one user's name leaking into another user's email.\n\n"
            "Every issue is a blocker or a warning. An email with any blocker is BLOCKED; one with\n"
            "only warnings is WARNINGS; one with nothing is CLEAN. A human still approves every\n"
            "email: this check only catches the mistakes it knows about."),
        epilog=(
            "exit codes:\n"
            "  0  no blockers (every email is clean or has warnings only)\n"
            "  1  at least one blocker was found (unless --no-fail)\n"
            "  2  an input is malformed: bad TOML or JSON, an invalid regex or condition;\n"
            "     the message names the file and the rule\n\n"
            "sections left out of claim-rules.toml are not checked, with two exceptions:\n"
            "[greeting] defaults to verified_name_field = \"first_name\" and fallback = \"Hi there,\";\n"
            "without [template], a group template may not use any placeholder.\n\n"
            "example:\n"
            "  python3 claim_check.py --rules claim-rules.toml --emails emails.json --out out/"),
    )
    parser.add_argument(
        "--rules", required=True, metavar="claim-rules.toml",
        help="The rules file (TOML): banned phrases and patterns, rules tying phrases to the user's facts, "
             "the approved CTAs, the greeting rule, the required footer parts and the allowed placeholders.")
    parser.add_argument(
        "--emails", required=True, metavar="emails.json",
        help='The emails to check (JSON). Either {"emails": [...]}, one rendered email per user with that '
             'user\'s facts, or {"template": {...}, "renders": [...]}, one group template plus the emails '
             "rendered from it.")
    parser.add_argument(
        "--no-fail", action="store_true",
        help="Exit with code 0 even when blockers are found. The report still lists every blocker. Use it "
             "when you want the report without failing a pipeline.")
    parser.add_argument(
        "--out", required=True, metavar="DIR",
        help="Folder for the results: report.md (for people) and result.json (for tools). It is created if "
             "missing. The report is also printed.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    rules = load_rules(args.rules)
    data = load_emails(args.emails)
    result = run_checks(rules, data)
    report = build_report(result, Path(args.rules).name, data["file"])
    write_outputs(args.out, report, result)
    return 1 if (not result["passed"] and not args.no_fail) else 0


if __name__ == "__main__":
    run_main(main)
