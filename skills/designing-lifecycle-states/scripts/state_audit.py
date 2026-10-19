#!/usr/bin/env python3
"""Audit a lifecycle state model (states.toml) against real per-user facts.

Part of the designing-lifecycle-states skill. The script sorts every user into exactly
one bucket (UNOBSERVABLE, then exclusions, then states in order, then the fallback),
measures the outcome in each bucket, and reports the mistakes that make lifecycle
programs send a lot and move nothing: unreachable states, duplicate asks, success
states that still send, asks for someone who does not read the email, and distinctions
that do not separate the outcome.

Standard library only. Formats are defined in docs/data-contracts.md.

Example:
    python3 state_audit.py --states states.toml --facts facts.csv \\
        --outcome converted --out state-audit/
"""

import argparse
import csv
import difflib
import re
from collections import Counter
from itertools import combinations
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

# --- BEGIN shared:stats (generated from scripts/shared/stats.py; do not edit here) ---
import math as _smath
from statistics import NormalDist as _NormalDist

Z95 = 1.959963984540054


def z_for(confidence=0.95):
    """Two-sided critical value, e.g. 1.96 for 0.95."""
    return _NormalDist().inv_cdf(1 - (1 - confidence) / 2)


def wilson(k, n, z=Z95):
    """Wilson score interval for k successes out of n. (nan, nan) when n == 0."""
    if n <= 0:
        return (_smath.nan, _smath.nan)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * _smath.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - half) / denom, (centre + half) / denom)


def newcombe_diff(k1, n1, k2, n2, z=Z95):
    """Difference p1 - p2 with Newcombe's hybrid score interval (method 10).
    Returns (diff, lo, hi); all nan if either group is empty."""
    if n1 <= 0 or n2 <= 0:
        return (_smath.nan, _smath.nan, _smath.nan)
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    d = p1 - p2
    lo = d - _smath.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + _smath.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (d, lo, hi)


def two_prop_p(k1, n1, k2, n2):
    """Two-sided pooled z-test p-value for p1 == p2. 1.0 when undefined."""
    if n1 <= 0 or n2 <= 0:
        return 1.0
    pool = (k1 + k2) / (n1 + n2)
    se = _smath.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = (k1 / n1 - k2 / n2) / se
    return _smath.erfc(abs(z) / _smath.sqrt(2))


def _log_hypergeom(a, row1, col1, n):
    lg = _smath.lgamma
    return (lg(row1 + 1) + lg(n - row1 + 1) + lg(col1 + 1) + lg(n - col1 + 1)
            - lg(n + 1) - lg(a + 1) - lg(row1 - a + 1) - lg(col1 - a + 1) - lg(n - row1 - col1 + a + 1))


def fisher_exact(a, b, c, d):
    """Two-sided Fisher exact p-value for the 2x2 table [[a, b], [c, d]]."""
    row1, col1, n = a + b, a + c, a + b + c + d
    if n == 0:
        return 1.0
    lo, hi = max(0, row1 + col1 - n), min(row1, col1)
    log_obs = _log_hypergeom(a, row1, col1, n)
    total = 0.0
    for x in range(lo, hi + 1):
        lp = _log_hypergeom(x, row1, col1, n)
        if lp <= log_obs + 1e-7:
            total += _smath.exp(lp)
    return min(1.0, total)


def holm(pvalues):
    """Holm step-down adjusted p-values, in the original order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def chi2_1df_p(x):
    """Upper-tail p-value of a chi-square statistic with 1 degree of freedom."""
    if x <= 0:
        return 1.0
    return _smath.erfc(_smath.sqrt(x / 2))


def srm_p(n_treatment, n_control, allocation_treatment):
    """Sample-ratio-mismatch p-value (chi-square goodness of fit, 1 df)."""
    n = n_treatment + n_control
    if n == 0:
        return 1.0
    e_t, e_c = n * allocation_treatment, n * (1 - allocation_treatment)
    x = (n_treatment - e_t) ** 2 / e_t + (n_control - e_c) ** 2 / e_c
    return chi2_1df_p(x)


def sample_size_per_arm(p1, p2, alpha=0.05, power=0.8, allocation_treatment=0.5):
    """Users needed in the control arm (p1) and treatment arm (p2) to detect p2 - p1,
    two-sided, normal approximation. Returns (n_control, n_treatment)."""
    if p1 == p2:
        return (_smath.inf, _smath.inf)
    k = allocation_treatment / (1 - allocation_treatment)      # n_t = k * n_c
    za = _NormalDist().inv_cdf(1 - alpha / 2)
    zb = _NormalDist().inv_cdf(power)
    pbar = (p1 + k * p2) / (1 + k)
    num = (za * _smath.sqrt(pbar * (1 - pbar) * (1 + 1 / k))
           + zb * _smath.sqrt(p1 * (1 - p1) + p2 * (1 - p2) / k)) ** 2
    n_c = _smath.ceil(num / (p2 - p1) ** 2)
    return (n_c, _smath.ceil(k * n_c))
# --- END shared:stats ---

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
UNOBSERVABLE = "UNOBSERVABLE"
DEFAULT_FALLBACK = "UNCLASSIFIED"
ALPHA = 0.05

FINDING_ORDER = [
    "unknown_field", "unobservable_rows", "unreachable_state", "success_state_sends",
    "no_success_state", "duplicate_ask", "sending_state_without_ask", "actor_mismatch",
    "indistinguishable_pair", "small_state",
]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _blank(value):
    return value is None or (isinstance(value, str) and value.strip() == "")


def _text(value, where, default=""):
    if value is None:
        return default
    if not isinstance(value, str):
        raise InputError(f"{where}: expected text, got {value!r}")
    return value.strip()


def _flag(value, where):
    """A TOML boolean (or 1/0, yes/no text). Returns (value, was_set)."""
    if value is None:
        return False, False
    parsed = parse_bool(value, where)
    if parsed is None:
        return False, False
    return parsed, True


def _compile(fname, key, name, when):
    where = f"{fname}:{key}.when"
    if not isinstance(when, str) or not when.strip():
        raise InputError(f"{where}: {name!r} needs a non-empty `when` rule")
    try:
        fn, fields = compile_condition(when)
    except ConditionError as exc:
        raise InputError(f"{where}: bad rule for {name!r}: {when!r}: {exc}") from None
    return fn, sorted(fields)


def load_model(path):
    """Read and validate states.toml. Every rule is compiled here."""
    data = load_toml(path)
    fname = Path(path).name

    model = data.get("model", {})
    if not isinstance(model, dict):
        raise InputError(f"{fname}:model: expected a [model] table")
    email_actor = _text(model.get("email_actor"), f"{fname}:model.email_actor") or None

    unobs = data.get("unobservable")
    required = []
    if unobs is not None:
        if not isinstance(unobs, dict):
            raise InputError(f"{fname}:unobservable: expected an [unobservable] table")
        rf = unobs.get("required_fields", [])
        if not isinstance(rf, list) or not all(isinstance(x, str) and x.strip() for x in rf):
            raise InputError(f"{fname}:unobservable.required_fields: expected a list of column names")
        required = [x.strip() for x in rf]

    names = {UNOBSERVABLE: "[unobservable]"} if unobs is not None else {}

    def claim(name, key):
        if name in names:
            raise InputError(f"{fname}:{key}.name: {name!r} is already used by {names[name]}")
        names[name] = key

    exclusions = []
    raw = data.get("exclusions", [])
    if not isinstance(raw, list):
        raise InputError(f"{fname}:exclusions: expected [[exclusions]] tables")
    for i, ex in enumerate(raw, start=1):
        key = f"exclusions[{i}]"
        if not isinstance(ex, dict):
            raise InputError(f"{fname}:{key}: expected a table")
        name = _text(ex.get("name"), f"{fname}:{key}.name")
        if not name:
            raise InputError(f"{fname}:{key}.name: every exclusion needs a name")
        claim(name, key)
        fn, fields = _compile(fname, key, name, ex.get("when"))
        reason = _text(ex.get("reason"), f"{fname}:{key}.reason") or name
        exclusions.append({"name": name, "when": ex["when"].strip(), "fn": fn, "fields": fields,
                           "reason": reason})

    states = []
    raw = data.get("states", [])
    if not isinstance(raw, list) or not raw:
        raise InputError(f"{fname}:states: expected at least one [[states]] table")
    for i, st in enumerate(raw, start=1):
        key = f"states[{i}]"
        if not isinstance(st, dict):
            raise InputError(f"{fname}:{key}: expected a table")
        name = _text(st.get("name"), f"{fname}:{key}.name")
        if not name:
            raise InputError(f"{fname}:{key}.name: every state needs a name")
        claim(name, key)
        fn, fields = _compile(fname, key, name, st.get("when"))
        send, send_set = _flag(st.get("send"), f"{fname}:{key}.send")
        success, _ = _flag(st.get("success"), f"{fname}:{key}.success")
        states.append({
            "name": name, "when": st["when"].strip(), "fn": fn, "fields": fields,
            "send": send, "send_set": send_set, "success": success,
            "ask": _text(st.get("ask"), f"{fname}:{key}.ask"),
            "actor": _text(st.get("actor"), f"{fname}:{key}.actor") or None,
        })

    fb = data.get("fallback", {})
    if not isinstance(fb, dict):
        raise InputError(f"{fname}:fallback: expected a [fallback] table")
    fb_name = _text(fb.get("name"), f"{fname}:fallback.name") or DEFAULT_FALLBACK
    claim(fb_name, "fallback")
    fb_send, _ = _flag(fb.get("send"), f"{fname}:fallback.send")

    return {
        "file": fname,
        "name": _text(model.get("name"), f"{fname}:model.name") or Path(path).stem,
        "email_actor": email_actor,
        "decision_window_days": model.get("decision_window_days"),
        "unobservable": unobs is not None,
        "required_fields": required,
        "exclusions": exclusions,
        "states": states,
        "fallback": {"name": fb_name, "send": fb_send},
    }


def read_header(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        first = next(csv.reader(fh), [])
    return [h.strip() for h in first]


def load_facts(path, outcome):
    """Read facts.csv. Returns (header, rows); each row gets '_outcome' (True/False/None)."""
    rows = read_csv(path, required=("user_id", outcome))
    header = read_header(path)
    seen = {}
    for row in rows:
        where = row["_where"]
        uid = row.get("user_id") or ""
        if uid == "":
            raise InputError(f"{where}: column 'user_id' is blank")
        if uid in seen:
            raise InputError(f"{where}: column 'user_id' repeats the user on {seen[uid]} "
                             f"(facts.csv must have one row per user)")
        seen[uid] = where
        row["_outcome"] = parse_bool(row.get(outcome), f"{where}: column {outcome!r}")
    return header, rows


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def classify(model, row):
    """Return (bucket, reason) for one user. Order: UNOBSERVABLE, exclusions, states, fallback."""
    missing = [f for f in model["required_fields"] if _blank(row.get(f))]
    if missing:
        return UNOBSERVABLE, "missing:" + "|".join(missing)
    for ex in model["exclusions"]:
        if ex["fn"](row):
            return ex["name"], ex["reason"]
    for st in model["states"]:
        if st["fn"](row):
            return st["name"], st["name"]
    return model["fallback"]["name"], "no_state_matched"


def _normalise_ask(text):
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _null_tested(field, rules):
    pat = re.compile(rf"(?<![\w.]){re.escape(field)}\s*(==|!=)\s*null\b")
    return any(pat.search(r) for r in rules)


def _ci(k, n):
    if n <= 0:
        return None
    lo, hi = wilson(k, n)
    return [lo, hi]


def _join(names):
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _counts(counter):
    return ", ".join(f"{k} {v:,}" for k, v in counter.most_common())


def analyse(model, header, rows, outcome, min_users, facts_name="facts.csv"):
    """Bucket every user and build the full result dict (also used to render the report)."""
    header_set = set(header)
    assigned = [classify(model, row) for row in rows]
    states = model["states"]
    state_by_name = {s["name"]: s for s in states}

    # Buckets, in evaluation order.
    order = []
    if model["unobservable"]:
        order.append((UNOBSERVABLE, "unobservable"))
    order += [(e["name"], "exclusion") for e in model["exclusions"]]
    order += [(s["name"], "state") for s in states]
    order.append((model["fallback"]["name"], "fallback"))
    stats_by = {name: {"users": 0, "measured": 0, "positives": 0} for name, _ in order}
    for row, (bucket, _) in zip(rows, assigned):
        b = stats_by[bucket]
        b["users"] += 1
        if row["_outcome"] is not None:
            b["measured"] += 1
            b["positives"] += 1 if row["_outcome"] else 0
    total = len(rows)
    buckets = {}
    for name, kind in order:
        b = stats_by[name]
        st = state_by_name.get(name)
        buckets[name] = {
            "kind": kind,
            "users": b["users"],
            "share": b["users"] / total if total else None,
            "measured": b["measured"],
            "unmeasured": b["users"] - b["measured"],
            "positives": b["positives"],
            "outcome_rate": b["positives"] / b["measured"] if b["measured"] else None,
            "ci": _ci(b["positives"], b["measured"]),
            "send": bool(st["send"]) if st else (model["fallback"]["send"] if kind == "fallback" else False),
            "success": bool(st["success"]) if st else False,
        }

    findings = []

    def add(fid, names, message, fix, **extra):
        findings.append({"id": fid, "states": list(names), "message": message, "fix": fix, **extra})

    # --- unknown_field -------------------------------------------------------
    users_of_field = {}
    for f in model["required_fields"]:
        users_of_field.setdefault(f, []).append(UNOBSERVABLE)
    for item in model["exclusions"] + states:
        for f in item["fields"]:
            users_of_field.setdefault(f, []).append(item["name"])
    unknown = sorted(f for f in users_of_field if f not in header_set)
    columns = [h for h in header if h != "user_id"]
    for f in unknown:
        guess = difflib.get_close_matches(f, columns, n=1)
        hint = f" The closest column is `{guess[0]}`." if guess else ""
        add("unknown_field", users_of_field[f],
            f"The rules read `{f}`, but {facts_name} has no `{f}` column. It counts as blank (null) "
            f"for every user, so any comparison with it is false. Used by: {_join(users_of_field[f])}.",
            f"Add `{f}` to {facts_name}, or correct the field name in the rule.{hint}",
            field=f)

    # --- blanks in the fields the rules read ---------------------------------
    rule_texts = [x["when"] for x in model["exclusions"] + states]
    blank_fields = []
    silent_fields = []
    for f in sorted(users_of_field):
        if f in unknown:
            handling = "column missing: blank for everyone"
            n_blank = total
        else:
            n_blank = sum(1 for r in rows if _blank(r.get(f)))
            if f in model["required_fields"]:
                handling = "sent to UNOBSERVABLE"
            elif _null_tested(f, rule_texts):
                handling = "a rule tests it for null explicitly"
            elif n_blank:
                handling = "**not caught**: the rules treat it as null and still place the user"
                silent_fields.append(f)
            else:
                handling = "none now; a blank would be treated as null, not caught"
        blank_fields.append({"field": f, "blank_users": n_blank, "handling": handling})

    # --- unobservable_rows ---------------------------------------------------
    unobs_b = buckets.get(UNOBSERVABLE)
    if unobs_b and unobs_b["users"]:
        miss = Counter()
        for row, (bucket, _) in zip(rows, assigned):
            if bucket == UNOBSERVABLE:
                for f in model["required_fields"]:
                    if _blank(row.get(f)):
                        miss[f] += 1
        rate = (f" Their {outcome} rate is {pct(unobs_b['outcome_rate'])} "
                f"({unobs_b['measured']:,} measured).") if unobs_b["measured"] else ""
        add("unobservable_rows", [UNOBSERVABLE],
            f"{unobs_b['users']:,} users ({pct(unobs_b['share'])}) are missing a required fact "
            f"({_counts(miss)}). They sit in UNOBSERVABLE, outside the model.{rate}",
            f"Fix tracking for {_join(sorted(miss))} and alert on this count. Keep these users out "
            f"of the model; never fold them into a lapsed or at-risk state.",
            users=unobs_b["users"], missing_by_field=dict(miss))
    if silent_fields:
        landed = Counter()
        n_users = 0
        model_buckets = {s["name"] for s in states} | {model["fallback"]["name"]}
        for row, (bucket, _) in zip(rows, assigned):
            if bucket in model_buckets and any(_blank(row.get(f)) for f in silent_fields):
                landed[bucket] += 1
                n_users += 1
        if n_users:
            missing_section = "" if model["unobservable"] else " The model has no [unobservable] section."
            per_field = ", ".join(f"{b['field']} {b['blank_users']:,}" for b in blank_fields
                                  if b["field"] in silent_fields)
            add("unobservable_rows", list(landed),
                f"{n_users:,} users have a blank in a field the rules read ({per_field}) but were "
                f"sorted into states anyway: {_counts(landed)}. Blank means unknown, not zero, so these "
                f"users were placed on missing data.{missing_section}",
                f"Add {_join(f'`{f}`' for f in silent_fields)} to [unobservable].required_fields so these "
                f"users land in UNOBSERVABLE, then fix tracking.",
                users=n_users, landed_in=dict(landed))

    # --- rule overlaps (who else would have taken these users) ---------------
    overlaps = []
    for i, st in enumerate(states):
        later = states[i + 1:]
        if not later or not buckets[st["name"]]["users"]:
            continue
        also = Counter()
        for row, (bucket, _) in zip(rows, assigned):
            if bucket == st["name"]:
                for other in later:
                    if other["fn"](row):
                        also[other["name"]] += 1
        if also:
            overlaps.append({"state": st["name"], "users": buckets[st["name"]]["users"],
                             "also_fit": {k: also[k] for k in [o["name"] for o in later] if also[k]}})

    # --- unreachable_state ---------------------------------------------------
    state_names = [s["name"] for s in states]
    for st in states:
        if buckets[st["name"]]["users"]:
            continue
        captors = Counter(bucket for row, (bucket, _) in zip(rows, assigned) if st["fn"](row))
        fits = sum(captors.values())
        rule = f"`{st['when']}`"
        if not fits:
            why = ""
            bad = [f for f in st["fields"] if f in unknown]
            if bad:
                why = f" Its rule reads {_join(f'`{f}`' for f in bad)}, which is not a column in {facts_name}."
            add("unreachable_state", [st["name"]],
                f"{st['name']} never matches: no user in {facts_name} fits its rule {rule}.{why}",
                f"Check {st['name']}'s fields and thresholds against the data, or delete the state.",
                fits_rule=0, captured_by={})
            continue
        parts = [f"{name} ({n:,})" for name, n in captors.most_common()]
        lead = "every user who fits it" if fits > 1 else "the one user who fits it"
        message = (f"{st['name']} never matches: {lead} ({fits:,}) was already captured by "
                   f"{_join(parts)}.")
        state_captors = [n for n, _ in captors.most_common() if n in state_by_name]
        if state_captors:
            fix = (f"Move {st['name']} above {_join(state_captors)}, or narrow "
                   f"{'that rule' if len(state_captors) == 1 else 'those rules'}. Check prerequisites "
                   f"(setup not done) before risk states (inactive). Typesy's AT_RISK check ran before "
                   f"its no-child check and told families with no child to \"restart your child's lessons\".")
        else:
            fix = (f"Everyone who fits {st['name']} is excluded or unobservable. Delete {st['name']}, "
                   f"or fix the exclusion if it is too broad.")
        overlap = {o["state"]: o["also_fit"] for o in overlaps}
        for captor in state_captors:
            others = {k: v for k, v in overlap.get(captor, {}).items() if k != st["name"]}
            if others:
                message += (f" {captor} also takes users who fit later states ("
                            f"{', '.join(f'{k} {v:,}' for k, v in others.items())}); check that its premise "
                            f"and ask are true for them.")
        add("unreachable_state", [st["name"]], message, fix, fits_rule=fits, captured_by=dict(captors))

    # --- success_state_sends / no_success_state ------------------------------
    in_model = sum(buckets[n]["users"] for n in state_names) + buckets[model["fallback"]["name"]]["users"]
    for st in states:
        if st["success"] and st["send"]:
            b = buckets[st["name"]]
            share = pct(b["users"] / in_model) if in_model else "—"
            add("success_state_sends", [st["name"]],
                f"{st['name']} is a success state (the leading indicator is reached) but it still sends. "
                f"{b['users']:,} users ({share} of users in the model) sit here. In Typesy Homeschool, 73% "
                f"of sends went to households already past the key action.",
                f"Set send = false on {st['name']}. Success ends the activation sequence; spend the "
                f"budget on states that have not reached the indicator yet.")
    if not any(st["success"] for st in states):
        add("no_success_state", [],
            "No state has success = true. Nothing marks the leading indicator as reached, so nothing "
            "tells the sequence to stop.",
            "Add a state for users who reached the leading indicator, with success = true and "
            "send = false, right after the exclusions.")

    # --- duplicate_ask -------------------------------------------------------
    groups = {}
    for st in states:
        if st["send"] and st["ask"]:
            groups.setdefault(_normalise_ask(st["ask"]), []).append(st)
    for norm, group in groups.items():
        if len(group) < 2 or not norm:
            continue
        names = [s["name"] for s in group]
        asks = sorted({s["ask"] for s in group})
        shown = " / ".join(f'"{a}"' for a in asks)
        add("duplicate_ask", names,
            f"{_join(names)} all make the same ask: {shown}. One ask per state: the same ask means "
            f"one state." if len(names) > 2 else
            f"{_join(names)} both make the same ask: {shown}. One ask per state: the same ask means "
            f"one state.",
            f"Merge {_join(names)} into one state and keep the difference as a fact for the copy, "
            f"or give each a different single action the reader can take.")

    # --- sending_state_without_ask / actor_mismatch --------------------------
    sending = [st for st in states if st["send"]]
    for st in sending:
        if not st["ask"]:
            add("sending_state_without_ask", [st["name"]],
                f"{st['name']} sends but has no ask, so its email cannot say what the reader should do.",
                f"Give {st['name']} one concrete action the reader can take today, or set send = false.")
    actor = model["email_actor"]
    if sending and not actor:
        add("actor_mismatch", [st["name"] for st in sending],
            "[model].email_actor is not set, so nobody has checked that each ask is for the person "
            "who reads the email.",
            "Set [model].email_actor to the person who reads the email (for example \"learner\" or "
            "\"parent\"), then make every sending state's actor match it.")
    elif actor:
        for st in sending:
            if st["actor"] is None:
                add("actor_mismatch", [st["name"]],
                    f"{st['name']} sends but does not say who must perform its ask, so the audit cannot "
                    f"check that the reader ({actor}) can do it.",
                    f"Set actor = \"{actor}\" on {st['name']} if the reader performs the ask; otherwise "
                    f"rewrite the ask as something the {actor} can do.")
            elif st["actor"].lower() != actor.lower():
                ask = f" (\"{st['ask']}\")" if st["ask"] else ""
                add("actor_mismatch", [st["name"]],
                    f"{st['name']} asks the {st['actor']} to act{ask}, but the email goes to the "
                    f"{actor}. Email can only ask the reader to act.",
                    f"Rewrite {st['name']}'s ask as something the {actor} can do (Typesy: \"add a child\", "
                    f"not \"hatch the next pet\"), or move this ask out of email.")

    # --- pairwise separation -------------------------------------------------
    tested = [n for n in state_names if buckets[n]["measured"] >= min_users]
    skipped = [n for n in state_names if buckets[n]["measured"] < min_users]
    pairs = list(combinations(tested, 2))
    raw_p = []
    for a, b in pairs:
        ka, na = buckets[a]["positives"], buckets[a]["measured"]
        kb, nb = buckets[b]["positives"], buckets[b]["measured"]
        raw_p.append(fisher_exact(ka, na - ka, kb, nb - kb))
    adj = holm(raw_p) if raw_p else []
    pairwise = []
    for (a, b), p, ph in zip(pairs, raw_p, adj):
        ka, na = buckets[a]["positives"], buckets[a]["measured"]
        kb, nb = buckets[b]["positives"], buckets[b]["measured"]
        d, lo, hi = newcombe_diff(ka, na, kb, nb)
        pairwise.append({
            "states": [a, b], "n": [na, nb], "rates": [ka / na, kb / nb],
            "diff": d, "diff_ci": [lo, hi], "p": p, "p_holm": ph,
            "distinguishable": ph < ALPHA,
            "adjacent": tested.index(b) == tested.index(a) + 1,
        })
    for pr in pairwise:
        if pr["distinguishable"]:
            continue
        a, b = pr["states"]
        same = ""
        if a in state_by_name and b in state_by_name and state_by_name[a]["ask"] and \
                _normalise_ask(state_by_name[a]["ask"]) == _normalise_ask(state_by_name[b]["ask"]):
            same = " They also make the same ask."
        add("indistinguishable_pair", [a, b],
            f"{a} ({pct(pr['rates'][0])} of {pr['n'][0]:,}) and {b} ({pct(pr['rates'][1])} of "
            f"{pr['n'][1]:,}) do not differ on {outcome}: difference {pp(pr['diff'])} (95% CI "
            f"{pp(pr['diff_ci'][0])} to {pp(pr['diff_ci'][1])}), Holm-adjusted p = {pr['p_holm']:.3g}."
            f"{same} In Typesy, pet depth (2.2pp, p = 0.676) did not earn a state; the add-child cliff "
            f"(42.7pp) did.",
            f"Consider merging {a} and {b}: this distinction does not earn a state. Keep the split only "
            f"if they need different asks, and say why before the test.",
            p=pr["p"], p_holm=pr["p_holm"])

    # --- small_state ---------------------------------------------------------
    for st in states:
        n = buckets[st["name"]]["users"]
        if 0 < n < min_users:
            add("small_state", [st["name"]],
                f"{st['name']} has only {n:,} users (fewer than {min_users}). Its {outcome} rate is "
                f"too noisy to act on.",
                f"Merge {st['name']} into a neighbouring state, or collect more data before giving it "
                f"its own message.", users=n)

    findings.sort(key=lambda f: FINDING_ORDER.index(f["id"]))

    # --- budget exposure -----------------------------------------------------
    cats = {"send_not_success": 0, "send_success": 0, "success_no_send": 0, "no_send_other": 0,
            "fallback": buckets[model["fallback"]["name"]]["users"]}
    for st in states:
        n = buckets[st["name"]]["users"]
        key = ("send_success" if st["success"] else "send_not_success") if st["send"] else \
              ("success_no_send" if st["success"] else "no_send_other")
        cats[key] += n
    fb_send = model["fallback"]["send"]
    sending_users = cats["send_not_success"] + cats["send_success"] + (cats["fallback"] if fb_send else 0)
    success_users = cats["send_success"] + cats["success_no_send"]
    no_send_users = cats["success_no_send"] + cats["no_send_other"] + (0 if fb_send else cats["fallback"])

    def share(n):
        return n / in_model if in_model else None

    budget = {
        "denominator": in_model,
        "excluded_or_unobservable": total - in_model,
        "sending_users": sending_users, "sending_share": share(sending_users),
        "success_users": success_users, "success_share": share(success_users),
        "no_send_users": no_send_users, "no_send_share": share(no_send_users),
        "sending_and_success_users": cats["send_success"],
        "sending_and_success_share": share(cats["send_success"]),
        "share_of_sending_users_already_successful":
            cats["send_success"] / sending_users if sending_users else None,
        "fallback_users": cats["fallback"],
        "categories": cats,
    }

    n_measured = sum(1 for r in rows if r["_outcome"] is not None)
    result = {
        "schema_version": SCHEMA_VERSION,
        "tool": "state_audit",
        "inputs": {
            "states_file": model["file"], "facts_file": facts_name, "outcome": outcome,
            "min_users": min_users, "users": total, "measured": n_measured,
            "unmeasured": total - n_measured, "columns": header,
        },
        "model": {
            "name": model["name"], "email_actor": model["email_actor"],
            "decision_window_days": model["decision_window_days"],
            "unobservable_required_fields": model["required_fields"] if model["unobservable"] else None,
            "exclusions": [{"name": e["name"], "when": e["when"], "reason": e["reason"]}
                           for e in model["exclusions"]],
            "states": [{"name": s["name"], "when": s["when"], "send": s["send"],
                        "send_set": s["send_set"], "success": s["success"], "ask": s["ask"],
                        "actor": s["actor"]} for s in states],
            "fallback": model["fallback"]["name"],
        },
        "bucket_order": [name for name, _ in order],
        "buckets": buckets,
        "blank_fields": blank_fields,
        "overlaps": overlaps,
        "pairwise": pairwise,
        "pairwise_skipped": skipped,
        "budget_exposure": budget,
        "findings": findings,
        "finding_counts": dict(Counter(f["id"] for f in findings)),
    }
    return result, assigned


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _ci_text(ci):
    if not ci:
        return "—"
    return f"{pct(ci[0])} – {pct(ci[1])}"


def render_report(r):
    inp, model, buckets = r["inputs"], r["model"], r["buckets"]
    out = []
    w = out.append
    w(f"# State model audit: {model['name']}")
    w("")
    w(f"- **Model:** `{inp['states_file']}`. **Facts:** `{inp['facts_file']}`, {inp['users']:,} users.")
    w(f"- **Outcome:** `{inp['outcome']}`. {inp['measured']:,} users have it measured; "
      f"{inp['unmeasured']:,} are blank (not measured yet). Blanks are reported, never counted as 0.")
    w(f"- **Who reads the email:** {model['email_actor'] or 'not set'}.")
    counts = r["finding_counts"]
    if counts:
        summary = ", ".join(f"`{fid}` {counts[fid]}" for fid in FINDING_ORDER if fid in counts)
        w(f"- **{len(r['findings'])} finding(s):** {summary}. Each one has a fix in section 3.")
    else:
        w("- **No findings.** The model passes every check in this audit.")
    be = r["budget_exposure"]
    if be["denominator"]:
        w(f"- **Budget exposure:** {pct(be['sending_share'])} of users in the model sit in sending states; "
          f"{pct(be['success_share'])} have already reached a success state"
          + (f", and {pct(be['sending_and_success_share'])} are in a success state that still sends."
             if be["sending_and_success_users"] else "."))
    w("")

    # 1. Model summary
    w("## 1. The model")
    w("")
    w("Users are checked top to bottom; the first match wins.")
    w("")
    w("| # | Bucket | Kind | Sends? | Success? | Ask | Actor | Rule |")
    w("|---|---|---|---|---|---|---|---|")
    i = 0
    if model["unobservable_required_fields"] is not None:
        i += 1
        req = ", ".join(model["unobservable_required_fields"]) or "(none listed)"
        w(f"| {i} | {UNOBSERVABLE} | unobservable | no | no | — | — | {_cell('any blank in: ' + req)} |")
    for e in model["exclusions"]:
        i += 1
        w(f"| {i} | {e['name']} | exclusion (`{e['reason']}`) | no | no | — | — | `{_cell(e['when'])}` |")
    for s in model["states"]:
        i += 1
        send = ("yes" if s["send"] else "no") + ("" if s["send_set"] else " (not set)")
        ask = f"\"{_cell(s['ask'])}\"" if s["ask"] else "—"
        w(f"| {i} | {s['name']} | state | {send} | {'**yes**' if s['success'] else 'no'} | {ask} | "
          f"{s['actor'] or '—'} | `{_cell(s['when'])}` |")
    i += 1
    w(f"| {i} | {model['fallback']} | fallback | {'yes' if buckets[model['fallback']]['send'] else 'no'} "
      f"| no | — | — | nothing above matched |")
    w("")

    # 2. Distribution
    w(f"## 2. Where users land, and how they convert ({inp['outcome']})")
    w("")
    w("| Bucket | Users | Share | Measured | Blank | Positive | Rate | 95% CI |")
    w("|---|---:|---:|---:|---:|---:|---:|---|")
    for name in r["bucket_order"]:
        b = buckets[name]
        w(f"| {name} | {b['users']:,} | {pct(b['share'])} | {b['measured']:,} | {b['unmeasured']:,} | "
          f"{b['positives']:,} | {pct(b['outcome_rate'])} | {_ci_text(b['ci'])} |")
    w("")
    w("Rates use measured users only. A blank outcome is unknown, not a negative.")
    w("")
    if r["blank_fields"]:
        w("**Blanks in the fields the rules read**")
        w("")
        w("| Field | Blank users | How the model handles a blank |")
        w("|---|---:|---|")
        for b in r["blank_fields"]:
            w(f"| `{b['field']}` | {b['blank_users']:,} | {b['handling']} |")
        w("")
    if r["overlaps"]:
        w("**Rule overlaps.** Users each state took who also fit a later state's rule. Nesting is fine "
          "when the earlier state is the more specific one. It is a bug when a risk state takes users "
          "who have not done the setup step yet.")
        w("")
        w("| State | Users | Also fit (later states) |")
        w("|---|---:|---|")
        for o in r["overlaps"]:
            also = ", ".join(f"{k} {v:,}" for k, v in o["also_fit"].items())
            w(f"| {o['state']} | {o['users']:,} | {also} |")
        w("")

    # 3. Findings
    w("## 3. Findings and what to fix")
    w("")
    if not r["findings"]:
        w("No findings. Keep this audit in CI and re-run it whenever a rule changes.")
        w("")
    for n, f in enumerate(r["findings"], start=1):
        label = f" ({', '.join(f['states'])})" if f["states"] else ""
        w(f"**{n}. `{f['id']}`{label}.** {f['message']}")
        w("")
        w(f"   *What to fix:* {f['fix']}")
        w("")

    # 4. Pairwise
    w(f"## 4. Does each distinction earn its place? (pairwise {inp['outcome']} rates)")
    w("")
    w(f"Two-sided Fisher exact test on every pair of states with at least {inp['min_users']} measured "
      f"users, Holm-adjusted across {len(r['pairwise'])} pair(s). A pair with Holm p ≥ 0.05 does not "
      f"separate the outcome.")
    w("")
    shown = [p for p in r["pairwise"] if not p["distinguishable"] or p["adjacent"]]
    if shown:
        w("| Pair | Rate A | Rate B | Difference (95% CI) | Fisher p | Holm p | Verdict |")
        w("|---|---:|---:|---|---:|---:|---|")
        for p in shown:
            verdict = "separates" if p["distinguishable"] else "**does not separate: consider merging**"
            w(f"| {p['states'][0]} vs {p['states'][1]} | {pct(p['rates'][0])} (n={p['n'][0]:,}) | "
              f"{pct(p['rates'][1])} (n={p['n'][1]:,}) | {pp(p['diff'])} ({pp(p['diff_ci'][0])} to "
              f"{pp(p['diff_ci'][1])}) | {p['p']:.3g} | {p['p_holm']:.3g} | {verdict} |")
        w("")
        hidden = len(r["pairwise"]) - len(shown)
        if hidden:
            w(f"Shown: pairs that do not separate, plus neighbouring states. {hidden} other pair(s) "
              f"separate; all pairs are in result.json.")
            w("")
    else:
        w("No pair could be tested.")
        w("")
    if r["pairwise_skipped"]:
        w(f"Not tested (fewer than {inp['min_users']} measured users): {', '.join(r['pairwise_skipped'])}.")
        w("")

    # 5. Budget exposure
    w("## 5. Budget exposure")
    w("")
    if not be["denominator"]:
        w("No users are in the model (everyone is excluded or unobservable).")
    else:
        w(f"Of {be['denominator']:,} users in the model ({be['excluded_or_unobservable']:,} excluded or "
          f"unobservable users are left out):")
        w("")
        cats = be["categories"]
        d = be["denominator"]
        w("| Where they sit | Users | Share |")
        w("|---|---:|---:|")
        w(f"| Sending states, not yet successful (where email can help) | {cats['send_not_success']:,} | "
          f"{pct(cats['send_not_success'] / d)} |")
        w(f"| Success states that still send (wasted budget) | {cats['send_success']:,} | "
          f"{pct(cats['send_success'] / d)} |")
        w(f"| Success states, no send (correct) | {cats['success_no_send']:,} | "
          f"{pct(cats['success_no_send'] / d)} |")
        w(f"| Other no-send states | {cats['no_send_other']:,} | {pct(cats['no_send_other'] / d)} |")
        w(f"| Fallback ({model['fallback']}) | {cats['fallback']:,} | {pct(cats['fallback'] / d)} |")
        w("")
        w(f"- In sending states: {be['sending_users']:,} ({pct(be['sending_share'])}).")
        w(f"- In success states: {be['success_users']:,} ({pct(be['success_share'])}).")
        w(f"- In no-send states: {be['no_send_users']:,} ({pct(be['no_send_share'])}).")
        if be["sending_and_success_users"]:
            w(f"- {pct(be['share_of_sending_users_already_successful'])} of the users who would get email "
              f"have already reached the indicator. What to fix: make the success state no-send; that "
              f"moves this share of the budget to users who can still move.")
        if cats["fallback"] / d > 0.05:
            w(f"- The fallback holds {pct(cats['fallback'] / d)} of users. What to fix: a fallback should "
              f"be near-empty; add a state for the situation these users are in.")
        w("")
        w("These are user counts at the decision point, not send counts. Use `audit_sends.py` "
          "(designing-state-journeys) to see where real sends went.")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _positive_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def build_parser():
    p = argparse.ArgumentParser(
        prog="state_audit.py",
        description="Audit a lifecycle state model against per-user facts. Every user is placed in "
                    "exactly one bucket (UNOBSERVABLE, then exclusions, then states in order, then the "
                    "fallback). The report shows where users land, how each bucket converts, and what "
                    "to fix: unreachable states, duplicate asks, success states that still send, asks "
                    "for someone who does not read the email, and states that do not separate the outcome.",
        epilog="Exit codes: 0 = the audit ran (findings do not change the exit code); 2 = malformed "
               "input (the message names the file and row, or the state and rule). Formats: "
               "docs/data-contracts.md.",
    )
    p.add_argument("--states", required=True, metavar="FILE",
                   help="The state model to audit (states.toml): [model], optional [unobservable], "
                        "[[exclusions]], [[states]] in priority order, and [fallback].")
    p.add_argument("--facts", required=True, metavar="FILE",
                   help="facts.csv: one row per user with a user_id column, the fact columns the rules "
                        "read, and the outcome column.")
    p.add_argument("--outcome", required=True, metavar="COLUMN",
                   help="Name of the outcome column in facts.csv (1/0; blank = not measured yet). "
                        "Example: converted.")
    p.add_argument("--min-users", type=_positive_int, default=30, metavar="N",
                   help="Smallest state worth acting on (default 30). States with fewer users are "
                        "flagged small_state, and states with fewer measured users are left out of the "
                        "pairwise tests.")
    p.add_argument("--emit-user-file", action="store_true",
                   help="Also write users.csv (user_id, bucket, reason) to --out. It contains user IDs, "
                        "so keep it internal. The report never contains IDs.")
    p.add_argument("--out", required=True, metavar="DIR",
                   help="Folder for report.md and result.json (created if missing). The report is also "
                        "printed to stdout.")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    model = load_model(args.states)
    header, rows = load_facts(args.facts, args.outcome)
    result, assigned = analyse(model, header, rows, args.outcome, args.min_users,
                               facts_name=Path(args.facts).name)
    write_outputs(args.out, render_report(result), result)
    if args.emit_user_file:
        path = Path(args.out) / "users.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow(["user_id", "bucket", "reason"])
            for row, (bucket, reason) in zip(rows, assigned):
                writer.writerow([row["user_id"], bucket, reason])
    return 0


if __name__ == "__main__":
    run_main(main)
