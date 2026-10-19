#!/usr/bin/env python3
"""Write a decision-grade readout for a sealed holdout experiment. It can say "no".

Part of the writing-decision-readouts skill. The readout checks the integrity gates
first (assignment, delivery, measurement, maturity). Only when every gate passes does it
classify the intent-to-treat difference against the pre-registered minimum worthwhile
effect: SUPPORTED_AT_TARGET, HARMFUL, FALSIFIED_AS_WORTHWHILE or INCONCLUSIVE. Otherwise
the verdict is INVALID_ASSIGNMENT, INVALID_DELIVERY, INVALID_MEASUREMENT or NOT_READY,
and the arm difference is hidden from the report.

Standard library only. Formats are defined in docs/data-contracts.md.

Example:
    python3 readout.py --prereg prereg.toml --assignments assignments.csv \\
        --outcomes outcomes.csv --sends sends.csv --as-of 2026-07-15 --out readout/
"""

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
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

SCHEMA_VERSION = 1
ARMS = ("treatment", "control")
SEND_STATUSES = ("sent", "delivered", "suppressed", "blocked", "failed", "not_needed")
REACHED = {"sent", "delivered"}                 # the message reached the user
FIRST_CONTACT = {"sent", "delivered", "not_needed"}   # counts for timely treatment reach
VALID_VERDICTS = ("SUPPORTED_AT_TARGET", "HARMFUL", "FALSIFIED_AS_WORTHWHILE", "INCONCLUSIVE")
GATE_FAMILY = {"srm": "assignment", "treatment_reach": "delivery", "control_contacted": "delivery",
               "prereg_hash": "measurement", "missing_outcomes": "measurement", "maturity": "maturity"}
GATE_ORDER = ("srm", "treatment_reach", "control_contacted", "prereg_hash", "missing_outcomes", "maturity")

ITT_STATEMENT = ("This readout compares arms as randomised (intent-to-treat). It never compares contacted "
                 "against uncontacted users, because being contacted is not random.")
HIDDEN_REASON = ("hidden until the cohort is valid and mature, to prevent stopping early or changing the "
                 "question after seeing the answer")
CANNOT_REVISE = "These outcome numbers cannot revise the product hypothesis."
MECHANISM_LABEL = "This tells you whether the behaviour moved, not whether the outcome did."
STRATA_LABEL = "Pre-registered strata only; diagnostic, never a basis for choosing a winner after the fact."
P_VALUE_LABEL = "for reference; the decision uses the interval against the pre-registered effect"

ALLOWED_ACTIONS = {
    "SUPPORTED_AT_TARGET": (["adopt", "repeat", "revise", "stop"],
                            "Adopt the policy, replicate it, or test the next bottleneck. Adoption is a "
                            "business decision, not automatic optimisation."),
    "HARMFUL": (["revise", "stop"],
                "Stop, or revise with a changed mechanism. The same statement cannot be re-run as "
                "\"revised\" with new prose."),
    "FALSIFIED_AS_WORTHWHILE": (["revise", "stop"],
                                "Stop, or revise with a changed mechanism. The same statement cannot be "
                                "re-run as \"revised\" with new prose."),
    "INCONCLUSIVE": (["repeat", "revise", "stop"],
                     "The hypothesis stays unresolved. Repeat with more users, register a new "
                     "hypothesis, or stop. It is never relabelled a success or a failure."),
    "INVALID_ASSIGNMENT": (["repeat", "stop"],
                           "Repair and repeat the same hypothesis (it was never tested), or stop."),
    "INVALID_DELIVERY": (["repeat", "stop"],
                         "Repair and repeat the same hypothesis (it was never tested), or stop."),
    "INVALID_MEASUREMENT": (["repeat", "stop"],
                            "Repair and repeat the same hypothesis (it was never tested), or stop."),
    "NOT_READY": ([], "No decision yet. Wait for the pre-registered analysis date and run the readout again."),
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _finite(x):
    return x is not None and not (isinstance(x, float) and not math.isfinite(x))


def fmt_p(p):
    if not _finite(p):
        return "—"
    if p < 0.0001:
        return "< 0.0001"
    return f"{p:.4f}"


def fmt_ci(ci):
    if not ci or not _finite(ci[0]) or not _finite(ci[1]):
        return "—"
    return f"[{pct(ci[0])}, {pct(ci[1])}]"


def fmt_pp_ci(ci):
    if not ci or not _finite(ci[0]) or not _finite(ci[1]):
        return "—"
    return f"[{pp(ci[0])}, {pp(ci[1])}]"


def fmt_relative(x):
    return "—" if not _finite(x) else f"{100 * x:+.1f}%"


def fmt_day(dt):
    return dt.date().isoformat() if dt else "—"


def fmt_time(dt):
    return dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "—"


def fmt_hours(h):
    return "—" if h is None else f"{h:.1f} hours"


def conf_label(confidence):
    return f"{confidence * 100:g}%"


def percentile(values, q):
    if not values:
        return None
    v = sorted(values)
    pos = (len(v) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def toml_time(value, where):
    """A TOML date, datetime or ISO string as an aware UTC datetime; None if absent or blank."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str):
        return parse_time(value, where)
    raise InputError(f"{where}: expected a date such as 2026-05-11, got {value!r}")


# ---------------------------------------------------------------------------
# Pre-registration
# ---------------------------------------------------------------------------

def validate_prereg(data, name):
    """Check a parsed prereg.toml. Return (errors, warnings, plan). Same rules as holdout.py seal."""
    errors, warnings = [], []
    plan = {}

    def get(section, key):
        sec = data.get(section)
        return sec.get(key) if isinstance(sec, dict) else None

    def text(section, key, why, required=True):
        v = get(section, key)
        if v is None or (isinstance(v, str) and not v.strip()):
            if required:
                errors.append(f"{name}:{section}.{key}: missing or blank. {why}")
            return None
        if not isinstance(v, str):
            errors.append(f"{name}:{section}.{key}: expected text, got {v!r}.")
            return None
        return v.strip()

    def number(section, key, ok, rule, why, required=True):
        v = get(section, key)
        if v is None:
            if required:
                errors.append(f"{name}:{section}.{key}: missing. {why}")
            return None
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            errors.append(f"{name}:{section}.{key}: expected a number, got {v!r}. {why}")
            return None
        if not ok(v):
            errors.append(f"{name}:{section}.{key}: must be {rule}, got {v!r}. {why}")
            return None
        return float(v)

    def when(section, key, why):
        v = get(section, key)
        if v is None or (isinstance(v, str) and not v.strip()):
            errors.append(f"{name}:{section}.{key}: missing. {why}")
            return None
        try:
            return toml_time(v, f"{name}:{section}.{key}")
        except InputError as exc:
            errors.append(str(exc))
            return None

    plan["name"] = text("experiment", "name", "Every readout and lock names the experiment.")
    plan["hypothesis"] = text("experiment", "hypothesis", "A plan without a written hypothesis has nothing to test.")
    plan["mechanism_text"] = text("experiment", "mechanism", "", required=False)
    plan["unit"] = text("experiment", "unit", "", required=False) or "user"
    plan["salt"] = text("experiment", "salt", "", required=False)
    plan["cohort_start"] = when("experiment", "cohort_start",
                                "The cohort window fixes who is in the experiment before any result is seen.")
    plan["cohort_end"] = when("experiment", "cohort_end",
                              "The cohort window fixes who is in the experiment before any result is seen.")
    plan["analysis_not_before"] = when("experiment", "analysis_not_before",
                                       "Without a fixed analysis date a readout could stop early when the "
                                       "numbers look good.")
    plan["allocation"] = number("experiment", "allocation_treatment", lambda v: 0 < v < 1, "between 0 and 1",
                                "The sample-ratio check needs the sealed allocation.")
    plan["metric"] = text("primary", "metric", "The primary outcome must be named before launch.")
    plan["delta"] = number("primary", "minimum_worthwhile_effect", lambda v: 0 < v < 1,
                           "greater than 0 and below 1 (0.02 means 2 percentage points)",
                           "A pre-registration without a minimum worthwhile effect cannot be falsified.")
    direction = get("primary", "direction")
    if direction is None:
        errors.append(f"{name}:primary.direction: missing. The verdict needs to know which way is better "
                      "(\"increase\" or \"decrease\").")
    elif direction not in ("increase", "decrease"):
        errors.append(f"{name}:primary.direction: must be \"increase\" or \"decrease\", got {direction!r}.")
        direction = None
    plan["direction"] = direction
    plan["baseline"] = number("primary", "baseline_rate", lambda v: 0 < v < 1, "between 0 and 1",
                              "", required=False)
    if plan["baseline"] is None and get("primary", "baseline_rate") is None:
        warnings.append(f"{name}:primary.baseline_rate: not set. Pre-launch power cannot be shown.")
    plan["confidence"] = number("primary", "confidence_level", lambda v: 0 < v < 1, "between 0 and 1",
                                "", required=False)
    if get("primary", "confidence_level") is None:
        plan["confidence"] = 0.95
        warnings.append(f"{name}:primary.confidence_level: not set. The readout will use 0.95.")
    plan["power"] = number("primary", "power", lambda v: 0 < v < 1, "between 0 and 1", "", required=False)
    if get("primary", "power") is None:
        plan["power"] = 0.8

    mech = data.get("mechanism")
    plan["mech_metric"] = None
    plan["mech_direction"] = "increase"
    if mech is not None:
        if not isinstance(mech, dict):
            errors.append(f"{name}:mechanism: expected a table.")
        else:
            plan["mech_metric"] = text("mechanism", "metric",
                                       "A [mechanism] table needs the metric column it measures.")
            md = mech.get("direction", "increase")
            if md not in ("increase", "decrease"):
                errors.append(f"{name}:mechanism.direction: must be \"increase\" or \"decrease\", got {md!r}.")
            else:
                plan["mech_direction"] = md
    if plan["mech_metric"] and plan["mech_metric"] == plan["metric"]:
        warnings.append(f"{name}:mechanism.metric: same column as the primary metric.")

    if not isinstance(data.get("gates"), dict):
        errors.append(f"{name}:gates: missing. The integrity gates must be sealed with the plan.")
    plan["reach_min"] = number("gates", "treatment_reach_min", lambda v: 0 < v <= 1, "above 0 and at most 1",
                               "Without a reach minimum an untreated treatment arm could still produce a verdict.")
    plan["sla_hours"] = number("gates", "first_contact_sla_hours", lambda v: v > 0, "greater than 0",
                               "Treatment reach is measured within this many hours of assignment.")
    plan["max_missing"] = number("gates", "max_missing_outcome_share", lambda v: 0 <= v < 1,
                                 "at least 0 and below 1", "Blank outcomes need a sealed limit.")
    plan["srm_p_min"] = number("gates", "srm_p_min", lambda v: 0 < v < 1, "between 0 and 1",
                               "The sample-ratio gate needs a sealed threshold.")
    cca = get("gates", "control_contact_allowed")
    if cca is None:
        errors.append(f"{name}:gates.control_contact_allowed: missing. The control-contact gate needs to know "
                      "whether control users may be sent anything.")
        plan["control_contact_allowed"] = None
    else:
        try:
            plan["control_contact_allowed"] = parse_bool(cca, f"{name}:gates.control_contact_allowed")
        except InputError as exc:
            errors.append(str(exc))
            plan["control_contact_allowed"] = None

    cs, ce, anb = plan["cohort_start"], plan["cohort_end"], plan["analysis_not_before"]
    if cs and ce and cs > ce:
        errors.append(f"{name}:experiment.cohort_end: is before cohort_start.")
    if ce and anb and anb.date() <= ce.date():
        errors.append(f"{name}:experiment.analysis_not_before: must be a later date than cohort_end, so the "
                      "last users assigned can still be measured.")
    pol = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    plan["policy_treatment"] = pol.get("treatment")
    plan["policy_control"] = pol.get("control")
    return errors, warnings, plan


def prereg_sha256(path):
    """SHA-256 of the file's bytes after line endings are normalised to \\n."""
    data = Path(path).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def check_seal(prereg_path):
    lock = prereg_path.with_name(prereg_path.stem + ".lock")
    seal = {"lock": lock.name, "lock_exists": lock.exists(), "sha256": prereg_sha256(prereg_path),
            "locked_sha256": None, "sealed_at": None, "match": None}
    if not seal["lock_exists"]:
        return seal
    try:
        doc = json.loads(lock.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise InputError(f"{lock}: not valid JSON ({exc})") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("sha256"), str):
        raise InputError(f"{lock}:sha256: missing. A lock must hold the sealed hash.")
    seal["locked_sha256"] = doc["sha256"].lower()
    seal["sealed_at"] = doc.get("sealed_at")
    seal["match"] = seal["locked_sha256"] == seal["sha256"]
    return seal


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

def load_assignments(path):
    rows = read_csv(path, required=["user_id", "arm", "assigned_at"])
    if not rows:
        raise InputError(f"{path}: no rows below the header")
    columns = set(rows[0])
    has_eligible = "eligible" in columns
    has_stratum = "stratum" in columns
    users, seen = [], {}
    eligible_blank = 0
    for r in rows:
        where = r["_where"]
        uid = r.get("user_id") or ""
        if uid == "":
            raise InputError(f"{where}: user_id is blank")
        if uid in seen:
            raise InputError(f"{where}: user_id repeats {seen[uid]}. A user can be randomised only once.")
        seen[uid] = where
        arm = (r.get("arm") or "").strip().lower()
        if arm not in ARMS:
            raise InputError(f"{where}: arm must be 'treatment' or 'control', got {r.get('arm')!r}")
        at = parse_time(r.get("assigned_at"), f"{where}: assigned_at")
        if at is None:
            raise InputError(f"{where}: assigned_at is blank. Every randomised user needs an assignment time.")
        eligible = True
        if has_eligible:
            parsed = parse_bool(r.get("eligible"), f"{where}: eligible")
            if parsed is None:
                eligible_blank += 1
            else:
                eligible = parsed
        users.append({"uid": uid, "arm": arm, "at": at, "eligible": eligible,
                      "reason": (r.get("exclusion_reason") or "").strip() or "unspecified",
                      "stratum": (r.get("stratum") or "") if has_stratum else None})
    return users, {"rows": len(users), "eligible_blank": eligible_blank, "has_stratum": has_stratum,
                   "has_eligible": has_eligible}


def load_outcomes(path, metrics):
    rows = read_csv(path, required=["user_id"] + metrics)
    out = {}
    for r in rows:
        where = r["_where"]
        uid = r.get("user_id") or ""
        if uid == "":
            raise InputError(f"{where}: user_id is blank")
        if uid in out:
            raise InputError(f"{where}: user_id appears twice in outcomes. Keep one row per user.")
        out[uid] = {m: parse_bool(r.get(m), f"{where}: {m}") for m in metrics}
    return out


def load_sends(path):
    rows = read_csv(path, required=["user_id", "sent_at", "status"])
    sends = []
    for r in rows:
        where = r["_where"]
        uid = r.get("user_id") or ""
        if uid == "":
            raise InputError(f"{where}: user_id is blank")
        status = (r.get("status") or "").strip().lower()
        if status not in SEND_STATUSES:
            raise InputError(f"{where}: status must be one of {', '.join(SEND_STATUSES)}, got {r.get('status')!r}")
        at = parse_time(r.get("sent_at"), f"{where}: sent_at")
        if at is None:
            raise InputError(f"{where}: sent_at is blank")
        sends.append({"uid": uid, "at": at, "status": status})
    return sends


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def compare(users, values, metric, z, direction):
    """Per-arm rates and the treatment-minus-control difference for one binary metric."""
    res = {"metric": metric, "direction": direction}
    for arm in ARMS:
        vals = [values.get(u["uid"], {}).get(metric) for u in users if u["arm"] == arm]
        n = sum(1 for v in vals if v is not None)
        k = sum(1 for v in vals if v is True)
        lo, hi = wilson(k, n, z)
        res[arm] = {"analysed": len(vals), "n": n, "k": k, "blank": len(vals) - n,
                    "rate": k / n if n else None, "ci": [lo, hi] if n else None}
    t, c = res["treatment"], res["control"]
    d, lo, hi = newcombe_diff(t["k"], t["n"], c["k"], c["n"], z)
    ok = _finite(d)
    res["diff"] = d if ok else None
    res["diff_ci"] = [lo, hi] if ok else None
    res["relative"] = (d / c["rate"]) if ok and c["rate"] else None
    res["p_value"] = two_prop_p(t["k"], t["n"], c["k"], c["n"]) if ok else None
    sign = 1 if direction == "increase" else -1
    res["directional_diff"] = sign * d if ok else None
    res["directional_diff_ci"] = sorted([sign * lo, sign * hi]) if ok else None
    return res


def classify(directional_ci, delta):
    if not directional_ci:
        return "INCONCLUSIVE"
    lo, hi = directional_ci
    if lo >= delta:
        return "SUPPORTED_AT_TARGET"
    if hi < 0:
        return "HARMFUL"
    if hi < delta:
        return "FALSIFIED_AS_WORTHWHILE"
    return "INCONCLUSIVE"


def compute_reach(plan, population, in_cohort, users, sends, as_of):
    """Treatment reach (the gate), context reach figures and control contact."""
    sla = timedelta(hours=plan["sla_hours"])
    reach = {"sends_file_given": sends is not None, "sla_hours": plan["sla_hours"],
             "threshold": plan["reach_min"]}
    if sends is None:
        reach.update(verified=False, timely_reach=None, due=None, timely_reached=None)
        return reach, None
    known = {u["uid"]: u for u in users}
    counted = [s for s in sends if s["at"] <= as_of]
    by_user = defaultdict(list)
    for s in counted:
        if s["uid"] in known:
            by_user[s["uid"]].append(s)
    reach["send_rows"] = len(sends)
    reach["send_rows_after_as_of"] = len(sends) - len(counted)
    reach["send_rows_unknown_user"] = sum(1 for s in counted if s["uid"] not in known)
    reach["send_rows_before_assignment"] = sum(1 for s in counted
                                               if s["uid"] in known and s["at"] < known[s["uid"]]["at"])
    reach["status_counts"] = dict(Counter(s["status"] for s in sends))

    due = reached = late = failed_only = no_rows = not_due = 0
    delays = []
    per_day = defaultdict(lambda: [0, 0])
    for u in population:
        if u["arm"] != "treatment":
            continue
        deadline = u["at"] + sla
        if deadline > as_of:
            not_due += 1
            continue
        due += 1
        rows = by_user.get(u["uid"], [])
        first = min((s["at"] for s in rows if s["status"] in FIRST_CONTACT), default=None)
        day = u["at"].date()
        per_day[day][0] += 1
        if first is not None:
            delays.append((first - u["at"]).total_seconds() / 3600)
        if first is not None and first <= deadline:
            reached += 1
            per_day[day][1] += 1
        elif first is not None:
            late += 1
        elif rows:
            failed_only += 1
        else:
            no_rows += 1

    gap_days = sorted(d for d, (n_due, n_hit) in per_day.items() if n_due > 0 and n_hit == 0)
    windows = []
    for d in gap_days:
        if windows and d - windows[-1]["_end"] == timedelta(days=1):
            windows[-1]["_end"] = d
            windows[-1]["due_users"] += per_day[d][0]
            windows[-1]["days"] += 1
        else:
            windows.append({"_start": d, "_end": d, "days": 1, "due_users": per_day[d][0]})
    for w in windows:
        w["start"], w["end"] = w.pop("_start").isoformat(), w.pop("_end").isoformat()

    pop_t = [u for u in population if u["arm"] == "treatment"]
    cohort_t = [u for u in in_cohort if u["arm"] == "treatment"]

    def delivered(group):
        hit = sum(1 for u in group if any(s["status"] in REACHED for s in by_user.get(u["uid"], [])))
        return {"reached": hit, "users": len(group), "rate": hit / len(group) if group else None}

    reach.update(
        verified=due > 0, due=due, not_yet_due=not_due, timely_reached=reached,
        timely_reach=reached / due if due else None,
        not_reached={"late_first_contact": late, "only_unsuccessful_attempts": failed_only,
                     "no_send_rows": no_rows},
        first_contact_hours={"median": percentile(delays, 0.5), "p90": percentile(delays, 0.9),
                             "users": len(delays)},
        gap_windows=windows,
        delivered_reach=delivered(pop_t),
        all_assigned_reach=delivered(cohort_t),
    )
    control_all = {u["uid"] for u in users if u["arm"] == "control"}
    control_pop = {u["uid"] for u in population if u["arm"] == "control"}
    contacted = {s["uid"] for s in counted if s["status"] in REACHED and s["uid"] in control_all}
    control = {"users": len(contacted), "in_analysed_population": len(contacted & control_pop),
               "allowed": plan["control_contact_allowed"]}
    reach["control_contacted"] = control
    return reach, control


def build_gates(plan, seal, prereg_name, counts, reach, control, missing, as_of):
    gates = {}

    def add(gid, passed, value, threshold, shown_value, shown_threshold, message):
        gates[gid] = {"id": gid, "family": GATE_FAMILY[gid], "passed": bool(passed), "value": value,
                      "threshold": threshold, "shown_value": shown_value, "shown_threshold": shown_threshold,
                      "message": message}

    alloc = plan["allocation"]
    n_t, n_c = counts["treatment"], counts["control"]
    p = srm_p(n_t, n_c, alloc)
    ok = p >= plan["srm_p_min"]
    add("srm", ok, p, plan["srm_p_min"], f"p = {fmt_p(p)}", f"p ≥ {plan['srm_p_min']:g}",
        (f"Arm sizes match the sealed {pct(alloc)} allocation" if ok else
         f"Arm sizes do not match the sealed {pct(alloc)} allocation; randomisation or logging is broken")
        + f" (treatment {n_t:,}, control {n_c:,}).")

    sla = f"{plan['sla_hours']:g} hours"
    if not reach["sends_file_given"]:
        add("treatment_reach", False, None, plan["reach_min"], "unknown", f"≥ {pct(plan['reach_min'])}",
            "delivery unverified: no sends file was given, and the readout never assumes delivery.")
    elif not reach["due"]:
        add("treatment_reach", False, None, plan["reach_min"], "unknown", f"≥ {pct(plan['reach_min'])}",
            f"delivery unverified: no eligible treatment user had reached the {sla} contact deadline by the "
            "as-of time.")
    else:
        v = reach["timely_reach"]
        add("treatment_reach", v >= plan["reach_min"], v, plan["reach_min"],
            f"{pct(v)} ({reach['timely_reached']:,} of {reach['due']:,})", f"≥ {pct(plan['reach_min'])}",
            f"{reach['timely_reached']:,} of {reach['due']:,} eligible treatment users had a first sent, delivered "
            f"or not_needed row within {sla} of assignment.")

    allowed = plan["control_contact_allowed"]
    if control is None:
        add("control_contacted", bool(allowed), None, None if allowed else 0, "unknown",
            "allowed" if allowed else "0 users",
            "Control contact is allowed by the plan." if allowed else
            "delivery unverified: no sends file was given, so control contact cannot be ruled out.")
    elif allowed:
        add("control_contacted", True, control["users"], None, f"{control['users']:,} users", "allowed",
            f"Control contact is allowed by the plan. {control['users']:,} control users have a sent or "
            "delivered row.")
    else:
        add("control_contacted", control["users"] == 0, control["users"], 0, f"{control['users']:,} users",
            "0 users",
            f"{control['users']:,} control users have a sent or delivered row "
            f"({control['in_analysed_population']:,} in the analysed population). The plan does not allow "
            "control contact.")

    lock = seal["lock"]
    if not seal["lock_exists"]:
        add("prereg_hash", True, seal["sha256"], None, f"{seal['sha256'][:12]}…", "no lock",
            f"NOT SEALED: there is no {lock} next to {prereg_name}. Nothing proves the plan was fixed before "
            "launch.")
    elif seal["match"]:
        add("prereg_hash", True, seal["sha256"], seal["locked_sha256"], f"{seal['sha256'][:12]}…",
            f"{lock} {seal['locked_sha256'][:12]}…",
            f"{prereg_name} matches {lock} (sealed {seal['sealed_at'] or 'at an unknown time'}).")
    else:
        add("prereg_hash", False, seal["sha256"], seal["locked_sha256"], f"{seal['sha256'][:12]}…",
            f"{lock} {seal['locked_sha256'][:12]}…",
            f"PREREGISTRATION_DRIFT: {prereg_name} changed after it was sealed "
            f"({seal['sealed_at'] or 'time unknown'}). The question may have changed after the data arrived.")

    if missing["analysed"] == 0:
        add("missing_outcomes", False, None, plan["max_missing"], "no users", f"≤ {pct(plan['max_missing'])}",
            "No users are in the analysed population, so nothing was measured.")
    else:
        share = missing["blank"] / missing["analysed"]
        add("missing_outcomes", share <= plan["max_missing"], share, plan["max_missing"],
            f"{pct(share)} blank", f"≤ {pct(plan['max_missing'])}",
            f"{missing['blank']:,} of {missing['analysed']:,} analysed users have no {plan['metric']} value "
            f"(treatment {missing['treatment']:,}, control {missing['control']:,}).")

    anb = plan["analysis_not_before"]
    mature = as_of >= anb
    add("maturity", mature, as_of.isoformat(), anb.isoformat(), f"as of {fmt_day(as_of)}",
        f"not before {fmt_day(anb)}",
        f"As of {fmt_time(as_of)}; the pre-registered analysis date {fmt_day(anb)} has passed." if mature else
        f"As of {fmt_time(as_of)}, before the pre-registered analysis date {fmt_day(anb)}. Outcomes are not "
        "mature yet.")
    return [gates[g] for g in GATE_ORDER]


def decide(gates, primary, delta):
    failed_families = {g["family"] for g in gates if not g["passed"]}
    for family, verdict in (("assignment", "INVALID_ASSIGNMENT"), ("delivery", "INVALID_DELIVERY"),
                            ("measurement", "INVALID_MEASUREMENT"), ("maturity", "NOT_READY")):
        if family in failed_families:
            return verdict
    return classify(primary["directional_diff_ci"], delta)


def verdict_meaning(verdict, gates, plan, primary, as_of, counts):
    g = {x["id"]: x for x in gates}
    metric = plan["metric"]
    delta = pp(plan["delta"] if plan["direction"] == "increase" else -plan["delta"])
    if verdict == "INVALID_ASSIGNMENT":
        s = g["srm"]
        return (f"Refused to learn: the arm split (treatment {counts['treatment']:,}, control "
                f"{counts['control']:,}) does not match the sealed {pct(plan['allocation'])} allocation "
                f"(sample-ratio p = {fmt_p(s['value'])}, minimum {plan['srm_p_min']:g}). Randomisation or logging "
                f"is broken, so the arms are not comparable. {CANNOT_REVISE}")
    if verdict == "INVALID_DELIVERY":
        r, c = g["treatment_reach"], g["control_contacted"]
        parts = []
        if not r["passed"]:
            if r["value"] is None:
                why = r["message"].removeprefix("delivery unverified: ")
                parts.append(f"Refused to learn: delivery unverified. {why[:1].upper()}{why[1:]} The treatment arm "
                             f"cannot be shown to have been treated. {CANNOT_REVISE}")
            else:
                parts.append(f"Refused to learn: treatment reach was {pct(r['value'])} against a pre-registered "
                             f"{pct(r['threshold'])} minimum, so the treatment arm was not reliably treated. "
                             f"{CANNOT_REVISE}")
            if not c["passed"] and c["value"] is not None:
                parts.append(f"Also, {c['value']:,} control users were contacted although the plan forbids it, "
                             "so the control arm is contaminated.")
        else:
            parts.append(f"Refused to learn: {c['value']:,} control users were contacted although the plan "
                         f"forbids control contact, so the control arm is not a clean comparison. {CANNOT_REVISE}")
        parts.append("Repair delivery and repeat the same hypothesis; it was never tested.")
        return " ".join(parts)
    if verdict == "INVALID_MEASUREMENT":
        reasons = []
        if not g["prereg_hash"]["passed"]:
            reasons.append("the pre-registration changed after it was sealed (PREREGISTRATION_DRIFT)")
        if not g["missing_outcomes"]["passed"]:
            m = g["missing_outcomes"]
            if m["value"] is None:
                reasons.append("no users are in the analysed population")
            else:
                reasons.append(f"{pct(m['value'])} of primary outcomes are blank against a pre-registered "
                               f"{pct(m['threshold'])} maximum")
        return (f"Refused to learn: {'; and '.join(reasons)}. The measurement cannot be trusted. {CANNOT_REVISE} "
                "Repair it and repeat the same hypothesis; it was never tested.")
    if verdict == "NOT_READY":
        return (f"Not ready: this readout is as of {fmt_day(as_of)}, before the pre-registered analysis date "
                f"{fmt_day(plan['analysis_not_before'])}. The arm difference is {HIDDEN_REASON}. Run it again on "
                f"or after {fmt_day(plan['analysis_not_before'])}.")
    conf = conf_label(plan["confidence"])
    if not primary["diff_ci"]:
        return (f"The difference on {metric} cannot be estimated because an arm has no measured users. Nothing "
                "was settled; this cannot be relabelled as a win or a loss.")
    est = (f"Treatment minus control on {metric}: {pp(primary['diff'])} ({conf} interval "
           f"{pp(primary['diff_ci'][0])} to {pp(primary['diff_ci'][1])}).")
    if plan["direction"] == "decrease":
        dci = primary["directional_diff_ci"]
        est += (f" Lower is better here, so the improvement is {pp(primary['directional_diff'])} "
                f"({pp(dci[0])} to {pp(dci[1])}).")
    rule = {
        "SUPPORTED_AT_TARGET": (f"The whole interval is at or beyond the pre-registered minimum worthwhile effect "
                                f"of {delta}. The claim survived a test that could have rejected it."),
        "HARMFUL": (f"The whole interval is on the wrong side of zero. The treatment made {metric} worse than "
                    "control."),
        "FALSIFIED_AS_WORTHWHILE": (f"The interval stops short of the pre-registered minimum worthwhile effect of "
                                    f"{delta}. The data rule out the effect the hypothesis promised, even if a "
                                    "smaller effect is still possible."),
        "INCONCLUSIVE": (f"The interval still contains the pre-registered minimum worthwhile effect of {delta}. "
                         "The data cannot say whether the policy is worth it. This stays unresolved; it cannot be "
                         "relabelled as a win or a loss."),
    }[verdict]
    return f"{est} {rule}"


def mechanism_reading(mech, primary, primary_verdict, plan):
    """Plain sentence comparing the behaviour change with the outcome change (valid readouts only)."""
    dci = mech["directional_diff_ci"]
    if not dci:
        return "The behaviour change cannot be estimated (an arm has no measured users)."
    moved = dci[0] > 0
    wrong_way = dci[1] < 0
    m, p = plan["mech_metric"], plan["metric"]
    m_eff = f"{m} {pp(mech['diff'])} {fmt_pp_ci(mech['diff_ci'])}"
    p_eff = f"{p} {pp(primary['diff'])} {fmt_pp_ci(primary['diff_ci'])}"
    if moved and primary_verdict == "SUPPORTED_AT_TARGET":
        return (f"The behaviour moved ({m_eff}) and the outcome moved ({p_eff}). The registered mechanism is "
                "consistent with the result. That is still not proof that the behaviour caused the outcome.")
    if moved and primary_verdict == "HARMFUL":
        return (f"The behaviour moved ({m_eff}) but the outcome got worse ({p_eff}). Moving this behaviour did "
                f"not help {p}.")
    if moved and primary_verdict == "FALSIFIED_AS_WORTHWHILE":
        return (f"The behaviour moved but the outcome did not: {m_eff}, against {p_eff}. Moving the behaviour was "
                f"not enough to move the outcome by the registered effect. The assumption that {m} drives {p} did "
                "not hold in this test.")
    if moved:
        return (f"The behaviour moved but the outcome did not clearly move: {m_eff}, against {p_eff}. A moved "
                "indicator is not a moved outcome. Whether this behaviour drives the outcome is still untested.")
    if wrong_way:
        return f"The behaviour moved the wrong way ({m_eff})."
    if primary_verdict == "SUPPORTED_AT_TARGET":
        return (f"The outcome moved ({p_eff}) but the registered behaviour did not clearly move ({m_eff}). The "
                "mechanism is unconfirmed; something else may carry the effect.")
    return (f"The behaviour did not clearly move ({m_eff}). The policy may not have changed what users do, "
            "which would explain an outcome that did not move.")


def build_limitations(plan, verdict, seal, reach, primary, cohort, missing, as_of_source, as_of,
                      counts, data_notes, has_strata, prereg_name):
    lim = []
    if verdict not in VALID_VERDICTS:
        if verdict == "NOT_READY":
            lim.append("No effect classification was made because the cohort is not mature. The arm "
                       f"difference is {HIDDEN_REASON}.")
        else:
            lim.append(f"No effect classification was made. {CANNOT_REVISE}")
    if verdict in VALID_VERDICTS and reach.get("timely_reach") is not None:
        lim.append(f"Intent-to-treat: the estimate is the effect of assigning the policy, including eligible "
                   f"treatment users it did not reach in time (timely reach {pct(reach['timely_reach'])}). It is "
                   "not the effect of reading an email.")
    elif not reach["sends_file_given"]:
        lim.append("Delivery is unverified because no sends file was given. The readout never assumes delivery.")
    if reach.get("gap_windows"):
        spans = "; ".join(f"{w['start']} to {w['end']} ({w['days']} days, {w['due_users']:,} users)"
                          for w in reach["gap_windows"])
        lim.append(f"Treatment users assigned on these dates got no timely contact at all: {spans}. The treatment "
                   "arm mixes treated and untreated users.")
    if reach["sends_file_given"]:
        lim.append("\"Sent\" means the email provider accepted the message. It does not prove inbox delivery.")
    lim.append(f"The result describes eligible users assigned from {fmt_day(plan['cohort_start'])} to "
               f"{fmt_day(plan['cohort_end'])} (UTC). {cohort['outside_cohort']['total']:,} users assigned outside "
               f"that window and {cohort['excluded_by_design']['total']:,} excluded by design are not in it.")
    if missing["blank"]:
        lim.append(f"{missing['blank']:,} analysed users have no {plan['metric']} value (treatment "
                   f"{missing['treatment']:,}, control {missing['control']:,}). They are left out of the rates, not "
                   "counted as 0. If blanks are not random, the estimate can be biased.")
    if cohort["eligible_blank"]:
        lim.append(f"{cohort['eligible_blank']:,} assignment rows had a blank eligible value and were treated as "
                   "eligible (the contract default).")
    req = primary.get("n_required_by_arm")
    if req is None:
        lim.append(f"No baseline_rate was registered in {prereg_name}, so pre-launch power is unknown.")
    elif not primary["powered"]:
        text = (f"NOT POWERED for the registered effect: {req['control']:,} users per arm were needed and this "
                f"study measured {primary['treatment']['n']:,} treatment and {primary['control']['n']:,} control "
                "users.")
        if verdict == "SUPPORTED_AT_TARGET":
            text += (" The verdict stands because the whole interval cleared the bar, but an underpowered study "
                     "that clears the bar tends to overstate the effect. Expect a smaller effect on replication.")
        elif verdict in ("INCONCLUSIVE",):
            text += " The experiment did not answer the registered question."
        lim.append(text)
    if seal["lock_exists"] is False:
        lim.append(f"The plan was not sealed (no {seal['lock']}). Nothing proves the question was fixed before the "
                   "data arrived.")
    if verdict in VALID_VERDICTS:
        lim.append(f"The two-proportion p-value is {P_VALUE_LABEL}.")
    lim.append("No single email gets credit. The treatment is the whole policy; this readout cannot say which "
               "message worked.")
    if plan["mech_metric"]:
        lim.append(f"The mechanism metric ({plan['mech_metric']}) shows whether a behaviour moved. It cannot show "
                   "that the behaviour caused the outcome.")
    if has_strata:
        lim.append("Stratum results are diagnostic. They are smaller samples and must not be used to pick a "
                   "winner after the fact.")
    if as_of_source != "from --as-of":
        lim.append(f"The as-of time ({fmt_time(as_of)}) is the latest timestamp in the inputs. Pass --as-of with "
                   "the extraction date if the outcomes were pulled later.")
    lim.extend(data_notes)
    return lim


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def arm_table(res, confidence, hidden, k_label):
    if hidden:
        lines = ["| Arm | Analysed users | Measured | Blank |", "|---|---|---|---|"]
        for arm in ARMS:
            a = res[arm]
            lines.append(f"| {arm} | {a['analysed']:,} | {a['n']:,} | {a['blank']:,} |")
        return lines
    lines = [f"| Arm | Analysed users | Measured (n) | {k_label} (k) | Rate | {conf_label(confidence)} interval | Blank |",
             "|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        a = res[arm]
        lines.append(f"| {arm} | {a['analysed']:,} | {a['n']:,} | {a['k']:,} | {pct(a['rate'])} | {fmt_ci(a['ci'])} "
                     f"| {a['blank']:,} |")
    return lines


def render(model):
    plan, verdict, gates = model["plan"], model["verdict"], model["gates_full"]
    primary, reach, cohort = model["primary"], model["reach"], model["cohort"]
    hidden = not model["feedback_eligible"]
    conf = conf_label(plan["confidence"])
    L = [f"# Experiment readout: {plan['name']}", "",
         f"As of {fmt_time(model['as_of'])} ({model['as_of_source']}). Pre-registration: {model['prereg_name']}.", ""]

    # 1 Verdict
    failed = [g["id"] for g in gates if not g["passed"]]
    L += ["## 1. Verdict", "", f"**Verdict: {verdict}**", "", model["verdict_meaning"], "",
          f"Failed gates: {', '.join(failed) if failed else 'none'}. "
          f"Feedback eligible: {'yes' if model['feedback_eligible'] else 'no'}.", "",
          "| Gate | Result | Value | Threshold | Detail |", "|---|---|---|---|---|"]
    for g in gates:
        L.append(f"| {g['id']} | {'PASS' if g['passed'] else 'FAIL'} | {g['shown_value']} | {g['shown_threshold']} "
                 f"| {g['message']} |")

    # 2 Delivery integrity
    g = {x["id"]: x for x in gates}
    L += ["", "## 2. Delivery integrity", "",
          "A treatment arm that was not treated cannot test the treatment, so delivery is checked before any "
          "outcome.", ""]
    rg, cg = g["treatment_reach"], g["control_contacted"]
    if not reach["sends_file_given"]:
        L += [f"- Delivery unverified: no sends file was given (`--sends`). The readout never assumes delivery, "
              f"so treatment_reach fails{' and control contact cannot be ruled out' if not cg['passed'] else ''}."]
    else:
        sla = f"{plan['sla_hours']:g} hours"
        if reach["due"]:
            L.append(f"- Timely treatment reach (the gate): {pct(reach['timely_reach'])}. {reach['timely_reached']:,} "
                     f"of {reach['due']:,} eligible treatment users had a first sent, delivered or not_needed row "
                     f"within {sla} of assignment. Minimum: {pct(plan['reach_min'])}. "
                     f"{'PASS' if rg['passed'] else 'FAIL'}.")
        else:
            L.append(f"- Timely treatment reach (the gate): unknown. {rg['message']} FAIL.")
        L.append(f"- Not yet due: {reach['not_yet_due']:,} eligible treatment users whose {plan['sla_hours']:g}-hour window had not "
                 "ended by the as-of time. They are left out of the denominator.")
        nr = reach["not_reached"]
        missed = sum(nr.values())
        L.append(f"- Not reached in time: {missed:,} users. First contact came after {sla}: "
                 f"{nr['late_first_contact']:,}. Only suppressed, blocked or failed attempts: "
                 f"{nr['only_unsuccessful_attempts']:,}. No send row at all: {nr['no_send_rows']:,}.")
        fc = reach["first_contact_hours"]
        L.append(f"- Time from assignment to first contact: median {fmt_hours(fc['median'])}, 90th percentile "
                 f"{fmt_hours(fc['p90'])} ({fc['users']:,} users).")
        if reach["gap_windows"]:
            spans = "; ".join(f"{w['start']} to {w['end']} ({w['days']} days, {w['due_users']:,} users)"
                              for w in reach["gap_windows"])
            L.append(f"- Assignment dates with no timely contact for anyone: {spans}.")
        else:
            L.append("- Assignment dates with no timely contact for anyone: none.")
        dr, ar = reach["delivered_reach"], reach["all_assigned_reach"]
        L.append(f"- Delivered reach (context, not the gate): {pct(dr['rate'])} of eligible treatment users "
                 f"({dr['reached']:,} of {dr['users']:,}) have at least one sent or delivered row.")
        L.append(f"- Reach over all assigned treatment users in the cohort window, including those excluded by "
                 f"design (context): {pct(ar['rate'])} ({ar['reached']:,} of {ar['users']:,}).")
        cc = reach["control_contacted"]
        L.append(f"- Control contact: {cc['users']:,} control users have a sent or delivered row "
                 f"({cc['in_analysed_population']:,} in the analysed population). Control contact allowed: "
                 f"{'yes' if plan['control_contact_allowed'] else 'no'}. {'PASS' if cg['passed'] else 'FAIL'}.")
        L.append("- \"Sent\" means the email provider accepted the message. It does not prove inbox delivery.")

    # 3 Assignment and data health
    oc, ex, an = cohort["outside_cohort"], cohort["excluded_by_design"], cohort["analysed"]
    L += ["", "## 3. Assignment and data health", "",
          f"- Assignment rows: {cohort['assigned_rows']['total']:,} (treatment {cohort['assigned_rows']['treatment']:,}, "
          f"control {cohort['assigned_rows']['control']:,}). Arms come only from the assignments file.",
          f"- Outside the cohort window ({fmt_day(plan['cohort_start'])} to {fmt_day(plan['cohort_end'])}, by UTC "
          f"assignment date): {oc['total']:,} (before: {oc['before']:,}, after: {oc['after']:,}; treatment "
          f"{oc['treatment']:,}, control {oc['control']:,}). Left out.",
          f"- Excluded by design (eligible = 0): {ex['total']:,} (treatment {ex['treatment']:,}, control "
          f"{ex['control']:,})."
          + (" Reasons: " + ", ".join(f"{k} {v:,}" for k, v in sorted(ex["by_reason"].items())) + "."
             if ex["by_reason"] else "") + " Left out.",
          f"- Analysed population (intent-to-treat): {an['total']:,} (treatment {an['treatment']:,}, control "
          f"{an['control']:,}). Check: {cohort['assigned_rows']['total']:,} = {oc['total']:,} outside + "
          f"{ex['total']:,} excluded + {an['total']:,} analysed.",
          f"- Sample-ratio check: treatment share {pct(an['treatment'] / an['total']) if an['total'] else '—'} "
          f"against a sealed {pct(plan['allocation'])}. {g['srm']['shown_value']} (needs "
          f"{g['srm']['shown_threshold']}). {'PASS' if g['srm']['passed'] else 'FAIL'}."]
    if cohort["eligible_blank"]:
        L.append(f"- Blank eligible values treated as eligible (contract default): {cohort['eligible_blank']:,}.")
    miss = model["missing"]
    L.append(f"- Primary outcome `{plan['metric']}`: {miss['blank']:,} blank or missing of {miss['analysed']:,} "
             f"analysed (treatment {miss['treatment']:,}, control {miss['control']:,}). "
             f"{g['missing_outcomes']['shown_value']}, maximum {pct(plan['max_missing'])}. "
             f"{'PASS' if g['missing_outcomes']['passed'] else 'FAIL'}. Blank means not measured; it is never "
             "counted as 0.")
    if model["mechanism"]:
        mm = model["mechanism"]
        mb = mm["treatment"]["blank"] + mm["control"]["blank"]
        L.append(f"- Mechanism `{plan['mech_metric']}`: {mb:,} blank or missing (treatment {mm['treatment']['blank']:,}, "
                 f"control {mm['control']['blank']:,}).")
    dh = model["data_health"]
    L.append(f"- Analysed users with no outcomes row (counted as blank): {dh['analysed_without_outcome_row']:,}. "
             f"Outcome rows for users not in the assignments file (ignored): {dh['outcome_rows_unknown_user']:,}.")
    if reach["sends_file_given"]:
        sc = reach["status_counts"]
        L.append(f"- Send rows: {reach['send_rows']:,} ("
                 + ", ".join(f"{s} {sc.get(s, 0):,}" for s in SEND_STATUSES) + "). "
                 f"After the as-of time (ignored): {reach['send_rows_after_as_of']:,}. For users not in the "
                 f"assignments file (ignored): {reach['send_rows_unknown_user']:,}. Timed before the user's "
                 f"assignment: {reach['send_rows_before_assignment']:,}.")
    L.append(f"- Maturity: as of {fmt_time(model['as_of'])} ({model['as_of_source']}); analysis not before "
             f"{fmt_day(plan['analysis_not_before'])}. {'PASS' if g['maturity']['passed'] else 'FAIL'}.")
    L.append(f"- Pre-registration seal: {g['prereg_hash']['message']} {'PASS' if g['prereg_hash']['passed'] else 'FAIL'}.")
    for w in model["prereg_warnings"]:
        L.append(f"- Pre-registration note: {w}")

    # 4 Definition
    seal = model["seal"]
    if not seal["lock_exists"]:
        seal_text = f"NOT SEALED (no {seal['lock']})."
    elif seal["match"]:
        seal_text = f"sealed {seal['sealed_at'] or 'at an unknown time'}; sha256 {seal['sha256'][:12]}… matches."
    else:
        seal_text = (f"PREREGISTRATION_DRIFT: sealed {seal['sealed_at'] or 'at an unknown time'} as "
                     f"{seal['locked_sha256'][:12]}…, but the file is now {seal['sha256'][:12]}….")
    signed_delta = plan["delta"] if plan["direction"] == "increase" else -plan["delta"]
    L += ["", "## 4. Definition", "",
          f"- Experiment: {plan['name']}",
          f"- Hypothesis: {plan['hypothesis']}",
          f"- Mechanism: {plan['mechanism_text'] or 'not stated'}",
          f"- Unit: {plan['unit']}. Allocation: {pct(plan['allocation'])} treatment.",
          f"- Primary metric: `{plan['metric']}`, direction {plan['direction']}, minimum worthwhile effect "
          f"{pp(signed_delta)} (absolute), baseline "
          f"{pct(plan['baseline']) if plan['baseline'] is not None else 'not registered'}, confidence level {conf}.",
          f"- Mechanism metric: " + (f"`{plan['mech_metric']}` (direction {plan['mech_direction']})"
                                     if plan["mech_metric"] else "none registered"),
          f"- Cohort: {fmt_day(plan['cohort_start'])} to {fmt_day(plan['cohort_end'])} (UTC assignment date, "
          f"inclusive). Analysis not before: {fmt_day(plan['analysis_not_before'])}.",
          f"- Treatment policy: {plan['policy_treatment'] or 'not stated'}",
          f"- Control policy: {plan['policy_control'] or 'not stated'}",
          f"- Gates: timely treatment reach ≥ {pct(plan['reach_min'])} within {plan['sla_hours']:g} hours; blank "
          f"primary outcomes ≤ {pct(plan['max_missing'])}; sample-ratio p ≥ {plan['srm_p_min']:g}; control "
          f"contact allowed: {'yes' if plan['control_contact_allowed'] else 'no'}.",
          f"- Seal: {seal_text}"]

    # 5 Primary
    L += ["", "## 5. Primary outcome by arm", "", ITT_STATEMENT, ""]
    if hidden:
        L += [f"The arm difference is {HIDDEN_REASON}. Verdict: {verdict}.", ""]
    L += [f"Metric `{plan['metric']}`:", ""] + arm_table(primary, plan["confidence"], hidden, plan["metric"])
    L.append("")
    if not hidden:
        L.append(f"- Difference (treatment − control): {pp(primary['diff'])}, {conf} interval "
                 f"{fmt_pp_ci(primary['diff_ci'])}. Pre-registered minimum worthwhile effect: {pp(signed_delta)}.")
        if plan["direction"] == "decrease":
            L.append(f"- Lower is better, so the improvement (control − treatment) is "
                     f"{pp(primary['directional_diff'])}, interval {fmt_pp_ci(primary['directional_diff_ci'])}. "
                     f"The verdict compares this with a minimum improvement of {pp(plan['delta'])}.")
        L.append(f"- Relative change: {fmt_relative(primary['relative'])} of the control rate.")
        L.append(f"- Two-proportion p-value: {fmt_p(primary['p_value'])} ({P_VALUE_LABEL}).")
    req = primary["n_required_by_arm"]
    if req is None:
        L.append("- Pre-launch power: unknown (no baseline_rate registered).")
    else:
        status = "Powered for the registered effect." if primary["powered"] else "NOT POWERED for the registered effect."
        L.append(f"- Pre-launch power: {req['control']:,} control and {req['treatment']:,} treatment users were needed "
                 f"to detect {pp(signed_delta)} from a {pct(plan['baseline'])} baseline with "
                 f"{plan['power'] * 100:g}% power. This study measured {primary['treatment']['n']:,} treatment and "
                 f"{primary['control']['n']:,} control users. {status} This uses the registered effect, not the "
                 "observed one.")

    # 6 Mechanism
    L += ["", "## 6. Mechanism", ""]
    mech = model["mechanism"]
    if not mech:
        L.append("No mechanism metric was registered.")
    else:
        L += [f"Metric `{plan['mech_metric']}`. {MECHANISM_LABEL}", ""]
        if hidden:
            L += [f"The arm difference is {HIDDEN_REASON}.", ""]
        L += arm_table(mech, plan["confidence"], hidden, plan["mech_metric"])
        if not hidden:
            L += ["", f"- Difference (treatment − control): {pp(mech['diff'])}, {conf} interval "
                      f"{fmt_pp_ci(mech['diff_ci'])}.",
                  f"- Two-proportion p-value: {fmt_p(mech['p_value'])} ({P_VALUE_LABEL}).",
                  f"- Reading: {model['mechanism_reading']}"]

    # 7 Strata
    L += ["", "## 7. Strata", ""]
    strata = model["strata"]
    if strata is None:
        L.append("The assignments file has no stratum column. Nothing to show.")
    else:
        L += [STRATA_LABEL, ""]
        if hidden:
            L += [f"The arm difference is {HIDDEN_REASON}.", "",
                  "| Stratum | Treatment analysed | Control analysed |", "|---|---|---|"]
            for s in strata:
                L.append(f"| {s['stratum']} | {s['treatment']['analysed']:,} | {s['control']['analysed']:,} |")
        else:
            L += [f"| Stratum | Treatment n | Treatment rate | Control n | Control rate | Difference | {conf} interval |",
                  "|---|---|---|---|---|---|---|"]
            for s in strata:
                L.append(f"| {s['stratum']} | {s['treatment']['n']:,} | {pct(s['treatment']['rate'])} | "
                         f"{s['control']['n']:,} | {pct(s['control']['rate'])} | {pp(s['diff'])} | "
                         f"{fmt_pp_ci(s['diff_ci'])} |")

    # 8 Limitations
    L += ["", "## 8. Limitations", ""] + [f"- {x}" for x in model["limitations"]]

    # 9 Decision record
    dr = model["decision_record"]
    L += ["", "## 9. Decision record", "",
          "Fill this in at the decision meeting. The system sets the evidence class; a person owns the action.", "",
          f"1. **What the evidence class says:** {verdict}. It cannot be relabelled.",
          f"2. **Which assumption survived or failed:** ______ ({dr['assumption_hint']})",
          "3. **What one thing changes next** (population, state trigger, timing or message policy): ______",
          "4. **New prediction and its minimum worthwhile effect:** ______ (seal it as a new pre-registration "
          "before the next cycle)",
          f"5. **Human action** (adopt / repeat / revise / stop): ______. {dr['allowed_actions_note']}",
          "6. **Decided by and date:** ______"]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(args):
    prereg_path = Path(args.prereg)
    data = load_toml(prereg_path)
    errors, prereg_warnings, plan = validate_prereg(data, prereg_path.name)
    if errors:
        raise InputError(f"{prereg_path}: the pre-registration is incomplete:\n  " + "\n  ".join(errors))
    seal = check_seal(prereg_path)

    users, a_info = load_assignments(args.assignments)
    metrics = [plan["metric"]] + ([plan["mech_metric"]] if plan["mech_metric"] else [])
    outcomes = load_outcomes(args.outcomes, metrics)
    sends = load_sends(args.sends) if args.sends else None

    if args.as_of:
        as_of = parse_time(args.as_of, "--as-of")
        if as_of is None:
            raise InputError("--as-of: blank")
        as_of_source = "from --as-of"
    else:
        stamps = [u["at"] for u in users] + [s["at"] for s in (sends or [])]
        as_of = max(stamps)
        as_of_source = "latest timestamp in the inputs"
    z = z_for(plan["confidence"])

    # Population: in the cohort window by UTC date, then eligible.
    start_d, end_d = plan["cohort_start"].date(), plan["cohort_end"].date()
    population, in_cohort = [], []
    outside = {"total": 0, "before": 0, "after": 0, "treatment": 0, "control": 0}
    excluded = {"total": 0, "treatment": 0, "control": 0, "by_reason": Counter()}
    for u in users:
        d = u["at"].date()
        if d < start_d or d > end_d:
            outside["total"] += 1
            outside["before" if d < start_d else "after"] += 1
            outside[u["arm"]] += 1
            continue
        in_cohort.append(u)
        if not u["eligible"]:
            excluded["total"] += 1
            excluded[u["arm"]] += 1
            excluded["by_reason"][u["reason"]] += 1
            continue
        population.append(u)
    excluded["by_reason"] = dict(excluded["by_reason"])
    counts = {arm: sum(1 for u in population if u["arm"] == arm) for arm in ARMS}
    cohort = {
        "start": start_d.isoformat(), "end": end_d.isoformat(),
        "analysis_not_before": plan["analysis_not_before"].isoformat(),
        "assigned_rows": {"total": len(users), **{arm: sum(1 for u in users if u["arm"] == arm) for arm in ARMS}},
        "outside_cohort": outside, "excluded_by_design": excluded,
        "analysed": {"total": len(population), **counts},
        "eligible_blank": a_info["eligible_blank"],
    }

    reach, control = compute_reach(plan, population, in_cohort, users, sends, as_of)

    primary = compare(population, outcomes, plan["metric"], z, plan["direction"])
    missing = {"analysed": len(population), "blank": primary["treatment"]["blank"] + primary["control"]["blank"],
               "treatment": primary["treatment"]["blank"], "control": primary["control"]["blank"]}
    primary["delta_min"] = plan["delta"]
    primary["confidence_level"] = plan["confidence"]
    primary["baseline_rate"] = plan["baseline"]
    primary["p_value_note"] = P_VALUE_LABEL
    target = None
    if plan["baseline"] is not None:
        target = plan["baseline"] + (plan["delta"] if plan["direction"] == "increase" else -plan["delta"])
    if target is not None and 0 < target < 1:
        n_c, n_t = sample_size_per_arm(plan["baseline"], target, alpha=1 - plan["confidence"],
                                       power=plan["power"], allocation_treatment=plan["allocation"])
        primary["n_required_per_arm"] = int(n_c)
        primary["n_required_by_arm"] = {"control": int(n_c), "treatment": int(n_t)}
        primary["powered"] = primary["treatment"]["n"] >= n_t and primary["control"]["n"] >= n_c
    else:
        primary["n_required_per_arm"] = None
        primary["n_required_by_arm"] = None
        primary["powered"] = None

    gates = build_gates(plan, seal, prereg_path.name, counts, reach, control, missing, as_of)
    verdict = decide(gates, primary, plan["delta"])
    feedback_eligible = verdict in VALID_VERDICTS
    primary["feedback_eligible"] = feedback_eligible
    primary["shown_in_report"] = feedback_eligible

    mechanism = None
    mech_reading = None
    if plan["mech_metric"]:
        mechanism = compare(population, outcomes, plan["mech_metric"], z, plan["mech_direction"])
        mechanism["label"] = MECHANISM_LABEL
        mechanism["feedback_eligible"] = feedback_eligible
        mechanism["shown_in_report"] = feedback_eligible
        if feedback_eligible:
            mech_reading = mechanism_reading(mechanism, primary, verdict, plan)
            mechanism["reading"] = mech_reading
            mechanism["moved"] = bool(mechanism["directional_diff_ci"] and mechanism["directional_diff_ci"][0] > 0)

    strata = None
    if a_info["has_stratum"]:
        strata = []
        for s in sorted({u["stratum"] for u in population}):
            group = [u for u in population if u["stratum"] == s]
            res = compare(group, outcomes, plan["metric"], z, plan["direction"])
            res["stratum"] = s if s != "" else "(blank)"
            res["feedback_eligible"] = feedback_eligible
            strata.append(res)

    known = {u["uid"] for u in users}
    pop_ids = {u["uid"] for u in population}
    data_health = {"analysed_without_outcome_row": sum(1 for uid in pop_ids if uid not in outcomes),
                   "outcome_rows_unknown_user": sum(1 for uid in outcomes if uid not in known)}
    data_notes = []
    if data_health["outcome_rows_unknown_user"]:
        data_notes.append(f"{data_health['outcome_rows_unknown_user']:,} outcome rows belong to users who are not in "
                          "the assignments file. They were ignored.")
    if sends is not None:
        if reach["send_rows_unknown_user"]:
            data_notes.append(f"{reach['send_rows_unknown_user']:,} send rows belong to users who are not in the "
                              "assignments file. They were ignored.")
        if reach["send_rows_before_assignment"]:
            data_notes.append(f"{reach['send_rows_before_assignment']:,} send rows are timed before the user's "
                              "assignment. Check the clocks; a send before randomisation is not the treatment.")
        if reach["send_rows_after_as_of"]:
            data_notes.append(f"{reach['send_rows_after_as_of']:,} send rows are after the as-of time and were "
                              "ignored.")

    meaning = verdict_meaning(verdict, gates, plan, primary, as_of, counts)
    limitations = build_limitations(plan, verdict, seal, reach, primary, cohort, missing, as_of_source, as_of,
                                    counts, data_notes, strata is not None, prereg_path.name)
    actions, actions_note = ALLOWED_ACTIONS[verdict]
    if verdict in VALID_VERDICTS:
        hint = ("Did the mechanism move too? See section 6." if mechanism else
                "No mechanism was registered; say which assumption the result tested.")
        if verdict == "INCONCLUSIVE":
            hint = ("Nothing was settled. Say which assumption is still untested and why, for example too few "
                    "users.")
        elif verdict != "SUPPORTED_AT_TARGET":
            hint = ("Name the assumption that failed: the behaviour did not move, or it moved and the outcome "
                    "did not. See section 6." if mechanism else "Name the assumption that failed.")
    elif verdict == "NOT_READY":
        hint = "Not yet: the cohort is not mature."
    else:
        hint = "No product assumption was tested. Name the operational failure and its repair."
    decision_record = {
        "evidence_class": verdict, "relabel_allowed": False, "feedback_eligible": feedback_eligible,
        "allowed_actions": actions, "allowed_actions_note": actions_note, "assumption_hint": hint,
        "assumption_survived_or_failed": None, "one_change_next": None, "new_prediction": None,
        "new_minimum_worthwhile_effect": None, "human_action": None, "decided_by": None, "decided_at": None,
    }

    model = {"plan": plan, "verdict": verdict, "verdict_meaning": meaning, "gates_full": gates,
             "feedback_eligible": feedback_eligible, "primary": primary, "mechanism": mechanism,
             "mechanism_reading": mech_reading, "strata": strata, "reach": reach, "cohort": cohort,
             "missing": missing, "data_health": data_health, "limitations": limitations,
             "decision_record": decision_record, "seal": seal, "as_of": as_of, "as_of_source": as_of_source,
             "prereg_name": prereg_path.name, "prereg_warnings": prereg_warnings}
    report = render(model)

    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "readout.py",
        "experiment": plan["name"],
        "verdict": verdict,
        "verdict_meaning": meaning,
        "feedback_eligible": feedback_eligible,
        "decision_allowed": ("adopt_repeat_revise_or_stop" if feedback_eligible else
                             "wait" if verdict == "NOT_READY" else "repair_or_repeat_only"),
        "failed_gates": [g["id"] for g in gates if not g["passed"]],
        "gates": [{k: g[k] for k in ("id", "family", "passed", "value", "threshold", "message")} for g in gates],
        "as_of": as_of.isoformat(),
        "as_of_source": as_of_source,
        "cohort": cohort,
        "primary": primary,
        "mechanism": mechanism,
        "strata": strata,
        "reach": reach,
        "data_health": data_health,
        "prereg": {"file": prereg_path.name, "sha256": seal["sha256"], "lock": seal["lock"],
                   "lock_exists": seal["lock_exists"], "locked_sha256": seal["locked_sha256"],
                   "sealed_at": seal["sealed_at"], "match": seal["match"], "warnings": prereg_warnings},
        "itt_statement": ITT_STATEMENT,
        "limitations": limitations,
        "decision_record": decision_record,
    }
    write_outputs(args.out, report, result)
    return 0


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="readout.py",
        description="Write a decision-grade readout for a sealed holdout experiment. It checks the integrity "
                    "gates first (sample ratio, delivery, control contact, pre-registration seal, blank outcomes, "
                    "maturity). Only if all pass does it compare the intent-to-treat difference with the "
                    "pre-registered minimum worthwhile effect. It can say no.",
        epilog="Exit codes: 0 = the readout ran (an INVALID_* or NOT_READY verdict is still a successful run); "
               "2 = malformed input (the message names the file and row or key).")
    p.add_argument("--prereg", required=True, metavar="FILE",
                   help="The pre-registration (prereg.toml). If prereg.lock sits next to it, the file's hash must "
                        "still match the lock.")
    p.add_argument("--assignments", required=True, metavar="FILE",
                   help="assignments.csv: one row per randomised user with user_id, arm and assigned_at (optional: "
                        "eligible, exclusion_reason, stratum). Arms come only from this file.")
    p.add_argument("--outcomes", required=True, metavar="FILE",
                   help="outcomes.csv: one row per user with the primary (and mechanism) metric columns named in "
                        "the pre-registration. Values are 1/0; blank means not measured.")
    p.add_argument("--sends", metavar="FILE",
                   help="sends.csv: one row per send attempt (user_id, sent_at, status). Needed to check delivery. "
                        "Without it the delivery gate fails as 'delivery unverified'.")
    p.add_argument("--as-of", metavar="DATE",
                   help="When the data was extracted, as an ISO date or timestamp (UTC if no zone). Sends after "
                        "it are ignored and maturity is judged against it. Default: the latest timestamp in the "
                        "inputs.")
    p.add_argument("--out", required=True, metavar="DIR",
                   help="Folder for report.md and result.json. The report is also printed.")
    return p.parse_args(argv)


def main(argv=None):
    return run(parse_args(argv))


if __name__ == "__main__":
    run_main(main)
