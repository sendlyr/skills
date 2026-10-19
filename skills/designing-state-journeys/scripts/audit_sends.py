#!/usr/bin/env python3
"""Audit what a state-routed email program actually sent, against its contact policy.

Part of the designing-state-journeys skill. Answers "why did our emails do nothing?"
from three files: who was randomised (assignments.csv), every send attempt (sends.csv)
and the rules (contact-policy.toml). It reports:

- reach: did eligible treatment users get a first contact inside the SLA (the gate)?
- where the sends went, and the share spent on users already in a success state;
- cap, spacing, control-contact and no-send-state violations;
- sends per user, how each user's sequence ended (termination), and render-to-send age.

Arms come only from assignments.csv. Standard library only. Formats are defined in
docs/data-contracts.md.

Example:
    python3 audit_sends.py --policy contact-policy.toml --assignments assignments.csv \\
        --sends sends.csv --outcomes outcomes.csv --outcome converted --out send-audit/
"""

import argparse
import csv
import math
from collections import Counter, defaultdict
from datetime import timedelta
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
ARMS = {"treatment", "control"}
STATUSES = {"sent", "delivered", "suppressed", "blocked", "failed", "not_needed"}
SUCCESSFUL = {"sent", "delivered"}                  # the message reached the user
CONTACT = {"sent", "delivered", "not_needed"}       # counts toward reach
NOT_DELIVERED = ("failed", "suppressed", "blocked")
TERMINATION_ORDER = ["never_contacted", "converted", "over_cap", "budget_complete",
                     "success_reached", "stopped_early"]
DEFAULT_TERMINATION = ["converted", "success_reached", "budget_complete", "over_cap",
                       "stopped_early", "never_contacted"]
TERMINATION_MEANING = {
    "never_contacted": "no successful send and no not_needed row: the policy never reached them",
    "converted": "reached the outcome (from --outcomes)",
    "over_cap": "more successful sends than the cap: a contact-policy violation, not extra completion",
    "budget_complete": "exactly the cap of successful sends",
    "success_reached": "a not_needed row (the policy saw success and stopped), or the last send "
                       "went out while the user was in a success state",
    "stopped_early": "fewer sends than the cap and no recorded success: either the user succeeded "
                     "after the last send and no row was logged, or the pipeline stopped",
}
FINDING_ORDER = ["reach_gate", "success_state_sends", "cap_violation", "spacing_violation",
                 "control_contacted", "no_send_state_sends", "stale_render"]
BLANK_STATE = "(blank)"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def read_header(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        first = next(csv.reader(fh), [])
    return [h.strip() for h in first]


def _number(table, key, where, minimum=None, maximum=None, integer=False):
    if key not in table:
        raise InputError(f"{where}.{key}: missing (required)")
    value = table[key]
    if isinstance(value, bool):
        raise InputError(f"{where}.{key}: expected a number, got {value!r}")
    if not isinstance(value, (int, float)):
        value = parse_number(value, f"{where}.{key}")
        if value is None:
            raise InputError(f"{where}.{key}: expected a number, got a blank")
    if integer:
        if float(value) != int(value):
            raise InputError(f"{where}.{key}: expected a whole number, got {value!r}")
        value = int(value)
    if minimum is not None and value < minimum:
        raise InputError(f"{where}.{key}: must be at least {minimum}, got {value!r}")
    if maximum is not None and value > maximum:
        raise InputError(f"{where}.{key}: must be at most {maximum}, got {value!r}")
    return value


def _name_list(table, key, where):
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
        raise InputError(f"{where}.{key}: expected a list of names")
    return [x.strip() for x in value]


def load_policy(path):
    data = load_toml(path)
    fname = Path(path).name
    pol = data.get("policy")
    if not isinstance(pol, dict):
        raise InputError(f"{fname}:policy: missing the [policy] table")
    w = f"{fname}:policy"
    allowed = parse_bool(pol.get("control_contact_allowed"), f"{w}.control_contact_allowed")
    states = data.get("states", None)
    if states is not None and not isinstance(states, dict):
        raise InputError(f"{fname}:states: expected a [states] table")
    states = states or {}
    term = data.get("termination")
    reasons = None
    if term is not None:
        if not isinstance(term, dict):
            raise InputError(f"{fname}:termination: expected a [termination] table")
        reasons = _name_list(term, "reasons", f"{fname}:termination")
    return {
        "file": fname,
        "max_sends_per_user": _number(pol, "max_sends_per_user", w, minimum=0, integer=True),
        "min_hours_between_sends": _number(pol, "min_hours_between_sends", w, minimum=0),
        "first_contact_sla_hours": _number(pol, "first_contact_sla_hours", w, minimum=0),
        "treatment_reach_min": _number(pol, "treatment_reach_min", w, minimum=0, maximum=1),
        "control_contact_allowed": bool(allowed),
        "states_declared": "states" in data and "success" in states,
        "success": _name_list(states, "success", f"{fname}:states"),
        "no_send": _name_list(states, "no_send", f"{fname}:states"),
        "termination_declared": reasons is not None,
        "termination_reasons": reasons if reasons is not None else list(DEFAULT_TERMINATION),
    }


def load_assignments(path):
    rows = read_csv(path, required=("user_id", "arm", "assigned_at"))
    users = {}
    for r in rows:
        w = r["_where"]
        uid = r.get("user_id") or ""
        if uid == "":
            raise InputError(f"{w}: column 'user_id' is blank")
        if uid in users:
            raise InputError(f"{w}: column 'user_id' repeats the user on {users[uid]['where']} "
                             f"(one row per randomised user)")
        arm = (r.get("arm") or "").lower()
        if arm not in ARMS:
            raise InputError(f"{w}: column 'arm': expected treatment or control, got {r.get('arm')!r}")
        at = parse_time(r.get("assigned_at"), f"{w}: column 'assigned_at'")
        if at is None:
            raise InputError(f"{w}: column 'assigned_at' is blank")
        eligible = parse_bool(r.get("eligible"), f"{w}: column 'eligible'")
        users[uid] = {"where": w, "arm": arm, "assigned_at": at,
                      "eligible": True if eligible is None else eligible}
    return users


def load_sends(path):
    rows = read_csv(path, required=("user_id", "sent_at", "status"))
    header = read_header(path)
    sends = []
    for r in rows:
        w = r["_where"]
        uid = r.get("user_id") or ""
        if uid == "":
            raise InputError(f"{w}: column 'user_id' is blank")
        at = parse_time(r.get("sent_at"), f"{w}: column 'sent_at'")
        if at is None:
            raise InputError(f"{w}: column 'sent_at' is blank")
        status = (r.get("status") or "").lower()
        if status not in STATUSES:
            raise InputError(f"{w}: column 'status': expected one of {', '.join(sorted(STATUSES))}, "
                             f"got {r.get('status')!r}")
        sends.append({
            "user_id": uid, "sent_at": at, "status": status,
            "state": (r.get("state_at_send") or "").strip(),
            "message_key": (r.get("message_key") or "").strip(),
            "rendered_at": parse_time(r.get("rendered_at"), f"{w}: column 'rendered_at'"),
        })
    return sends, "rendered_at" in header, "state_at_send" in header


def load_outcomes(path, column):
    rows = read_csv(path, required=("user_id", column))
    out, seen = {}, {}
    for r in rows:
        w = r["_where"]
        uid = r.get("user_id") or ""
        if uid == "":
            raise InputError(f"{w}: column 'user_id' is blank")
        if uid in seen:
            raise InputError(f"{w}: column 'user_id' repeats the user on {seen[uid]}")
        seen[uid] = w
        out[uid] = parse_bool(r.get(column), f"{w}: column {column!r}")
    return out


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _hours(delta):
    return delta.total_seconds() / 3600


def percentile(values, q):
    """Linear interpolation between closest ranks; values must be sorted."""
    if not values:
        return None
    pos = (len(values) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def _rate(k, n):
    return k / n if n else None


def _ci(k, n):
    if n <= 0:
        return None
    lo, hi = wilson(k, n)
    return [lo, hi]


def _h(x):
    return "—" if x is None else f"{x:.1f}h"


def analyse(policy, users, sends, has_rendered, outcomes=None, outcome_col=None, as_of=None,
            files=None):
    files = files or {}
    cap = policy["max_sends_per_user"]
    gap_min = policy["min_hours_between_sends"]
    sla = policy["first_contact_sla_hours"]
    success_states = set(policy["success"])
    no_send_states = set(policy["no_send"])

    stamps = [u["assigned_at"] for u in users.values()] + [s["sent_at"] for s in sends]
    as_of_source = "given with --as-of" if as_of is not None else "the latest timestamp in the files"
    if as_of is None:
        if not stamps:
            raise InputError(f"{files.get('assignments', 'assignments.csv')}: no rows, so there is "
                             f"nothing to audit")
        as_of = max(stamps)

    notes = []
    future_assign = [uid for uid, u in users.items() if u["assigned_at"] > as_of]
    users = {uid: u for uid, u in users.items() if u["assigned_at"] <= as_of}
    future_sends = sum(1 for s in sends if s["sent_at"] > as_of)
    sends = [s for s in sends if s["sent_at"] <= as_of]
    if future_assign:
        notes.append(f"{len(future_assign):,} users assigned after the as-of time were left out.")
    if future_sends:
        notes.append(f"{future_sends:,} send rows after the as-of time were left out.")

    by_user = defaultdict(list)
    unassigned = Counter()
    for s in sends:
        if s["user_id"] in users:
            by_user[s["user_id"]].append(s)
        else:
            unassigned[s["status"]] += 1
    if unassigned:
        n_users = len({s["user_id"] for s in sends if s["user_id"] not in users})
        notes.append(f"{sum(unassigned.values()):,} send rows ({n_users:,} users) belong to users who are "
                     f"not in assignments.csv. They are left out of every metric: arms come only from "
                     f"assignments.csv.")
    for rows in by_user.values():
        rows.sort(key=lambda s: s["sent_at"])

    # Per-user facts.
    per = {}
    pre_assignment = 0
    for uid, u in users.items():
        rows = by_user.get(uid, [])
        succ = [s for s in rows if s["status"] in SUCCESSFUL]
        contact = [s for s in rows if s["status"] in CONTACT]
        first = contact[0]["sent_at"] if contact else None
        deadline = u["assigned_at"] + timedelta(hours=sla)
        pre_assignment += sum(1 for s in rows if s["sent_at"] < u["assigned_at"])
        per[uid] = {
            "rows": rows, "succ": succ, "first_contact": first,
            "first_contact_hours": _hours(first - u["assigned_at"]) if first else None,
            "deadline": deadline, "sla_elapsed": deadline <= as_of,
            "timely": first is not None and first <= deadline,
            "not_needed": any(s["status"] == "not_needed" for s in rows),
        }
    if pre_assignment:
        notes.append(f"{pre_assignment:,} send rows are dated before the user's assignment. Check the "
                     f"clocks or the assignment export.")

    treat = [uid for uid, u in users.items() if u["arm"] == "treatment"]
    treat_el = [uid for uid in treat if users[uid]["eligible"]]
    control = [uid for uid, u in users.items() if u["arm"] == "control"]
    inelig_sent = [uid for uid in treat if not users[uid]["eligible"] and per[uid]["succ"]]
    if inelig_sent:
        notes.append(f"{len(inelig_sent):,} treatment users marked eligible = 0 still got a successful "
                     f"send. Excluded-by-design users should never be emailed.")

    # --- reach --------------------------------------------------------------
    denom = [uid for uid in treat_el if per[uid]["sla_elapsed"]]
    timely = [uid for uid in denom if per[uid]["timely"]]
    delivered = [uid for uid in denom if per[uid]["succ"]]
    all_denom = [uid for uid in treat if per[uid]["sla_elapsed"]]
    all_timely = [uid for uid in all_denom if per[uid]["timely"]]
    rate = _rate(len(timely), len(denom))
    if rate is None:
        gate = "not_evaluable"
    else:
        gate = "pass" if rate >= policy["treatment_reach_min"] else "fail"
    missed = [uid for uid in denom if not per[uid]["timely"]]
    late = [uid for uid in missed if per[uid]["first_contact"] is not None]
    only_failed = [uid for uid in missed if per[uid]["first_contact"] is None and per[uid]["rows"]]
    no_rows = [uid for uid in missed if not per[uid]["rows"]]
    failed_status = Counter()
    for uid in only_failed:
        for st in {s["status"] for s in per[uid]["rows"]}:
            failed_status[st] += 1
    late_hours = sorted(per[uid]["first_contact_hours"] for uid in late)
    contact_hours = sorted(per[uid]["first_contact_hours"] for uid in denom
                           if per[uid]["first_contact_hours"] is not None)
    reach = {
        "as_of": as_of, "sla_hours": sla, "threshold": policy["treatment_reach_min"],
        "treatment_assigned": len(treat), "treatment_eligible": len(treat_el),
        "eligible": len(denom), "sla_not_elapsed": len(treat_el) - len(denom),
        "timely": len(timely),
        "policy_coverage": rate, "rate": rate, "ci": _ci(len(timely), len(denom)),
        "gate": gate, "passed": gate == "pass",
        "delivered": {"users": len(delivered), "denominator": len(denom),
                      "rate": _rate(len(delivered), len(denom))},
        "all_assigned": {"users": len(all_timely), "denominator": len(all_denom),
                         "rate": _rate(len(all_timely), len(all_denom))},
        "first_contact_hours": {"p50": percentile(contact_hours, 0.5),
                                "p90": percentile(contact_hours, 0.9)},
        "non_contact": {
            "users": len(missed),
            "no_rows": len(no_rows),
            "only_not_delivered": len(only_failed),
            "only_not_delivered_by_status": {k: failed_status[k] for k in NOT_DELIVERED if failed_status[k]},
            "late_first_contact": len(late),
            "late_first_contact_hours_p50": percentile(late_hours, 0.5),
        },
    }

    # --- where the sends went (treatment-arm successful sends) ---------------
    policy_sends = [s for uid in treat for s in per[uid]["succ"]]
    by_state = Counter(s["state"] or BLANK_STATE for s in policy_sends)
    keys = defaultdict(Counter)
    for s in policy_sends:
        keys[s["state"] or BLANK_STATE][s["message_key"] or BLANK_STATE] += 1
    for st in list(policy["success"]) + list(policy["no_send"]):
        by_state.setdefault(st, 0)
    total_sends = len(policy_sends)
    sends_by_state = []
    for st, n in sorted(by_state.items(), key=lambda kv: (-kv[1], kv[0])):
        sends_by_state.append({
            "state": st, "sends": n, "share": _rate(n, total_sends),
            "is_success": st in success_states, "is_no_send": st in no_send_states,
            "message_keys": dict(keys[st].most_common()),
        })
    success_sends = sum(n for st, n in by_state.items() if st in success_states)
    success_users = len({s["user_id"] for s in policy_sends if s["state"] in success_states})
    budget = {
        "successful_sends": total_sends,
        "success_state_sends": success_sends,
        "success_state_send_share": _rate(success_sends, total_sends),
        "users_sent_in_success_state": success_users,
        "non_success_sends": total_sends - success_sends,
        "blank_state_sends": by_state.get(BLANK_STATE, 0),
        "design_budget": cap * len(treat_el),
        "design_budget_used": _rate(sum(len(per[uid]["succ"]) for uid in treat_el), cap * len(treat_el)),
    }

    # --- violations -----------------------------------------------------------
    over = [uid for uid in treat_el if len(per[uid]["succ"]) > cap]
    over_counts = Counter(len(per[uid]["succ"]) for uid in over)
    cap_v = {
        "count": len(over), "limit": cap,
        "max_sends": max((len(per[uid]["succ"]) for uid in treat_el), default=0),
        "excess_sends": sum(len(per[uid]["succ"]) - cap for uid in over),
        "by_sends": {str(k): over_counts[k] for k in sorted(over_counts)},
        "examples": [f"{n:,} users got {k} sends" for k, n in sorted(over_counts.items(), reverse=True)][:3],
    }
    gaps, gap_users = [], set()
    for uid in treat:
        succ = per[uid]["succ"]
        for a, b in zip(succ, succ[1:]):
            g = _hours(b["sent_at"] - a["sent_at"])
            if g < gap_min:
                gaps.append(g)
                gap_users.add(uid)
    gaps.sort()
    spacing_v = {
        "count": len(gaps), "users": len(gap_users), "limit_hours": gap_min,
        "shortest_gap_hours": gaps[0] if gaps else None,
        "median_violating_gap_hours": percentile(gaps, 0.5),
        "examples": ([f"shortest gap {gaps[0]:.1f}h", f"median gap among violations "
                      f"{percentile(gaps, 0.5):.1f}h", f"{sum(1 for g in gaps if g < 6):,} gaps under 6h"]
                     if gaps else []),
    }
    ctrl = [uid for uid in control if per[uid]["succ"]]
    ctrl_sends = [s for uid in ctrl for s in per[uid]["succ"]]
    ctrl_states = Counter(s["state"] or BLANK_STATE for s in ctrl_sends)
    control_v = {
        "count": len(ctrl), "sends": len(ctrl_sends), "control_users": len(control),
        "allowed": policy["control_contact_allowed"],
        "by_state": dict(ctrl_states.most_common()),
        "examples": ([f"{len(ctrl_sends):,} sends to {len(ctrl):,} control users",
                      "states at send: " + ", ".join(f"{k} {v:,}" for k, v in ctrl_states.most_common())]
                     if ctrl else []),
    }
    ns = [s for s in policy_sends if s["state"] in no_send_states]
    ns_states = Counter(s["state"] for s in ns)
    nosend_v = {
        "count": len(ns), "users": len({s["user_id"] for s in ns}),
        "by_state": dict(ns_states.most_common()),
        "examples": [f"{k}: {v:,} sends" for k, v in ns_states.most_common(3)],
    }
    violations = {"cap": cap_v, "spacing": spacing_v, "control_contacted": control_v,
                  "no_send_state_sends": nosend_v}

    # --- sends per user (eligible treatment) ----------------------------------
    labels = ["0", "1", "2", "3", "4", "5+"]
    dist = Counter(min(len(per[uid]["succ"]), 5) for uid in treat_el)
    sends_per_user = {
        "users": len(treat_el), "cap": cap,
        "distribution": {labels[i]: dist.get(i, 0) for i in range(6)},
        "mean": _rate(sum(len(per[uid]["succ"]) for uid in treat_el), len(treat_el)),
    }

    # --- termination ----------------------------------------------------------
    term_by_user = {}
    outcome_blank = 0
    for uid in treat_el:
        p = per[uid]
        n = len(p["succ"])
        conv = outcomes.get(uid) if outcomes is not None else None
        if outcomes is not None and conv is None:
            outcome_blank += 1
        if n == 0 and not p["not_needed"]:
            cls = "never_contacted"
        elif conv:
            cls = "converted"
        elif n > cap:
            cls = "over_cap"
        elif n == cap:
            cls = "budget_complete"
        elif p["not_needed"] or (p["succ"] and p["succ"][-1]["state"] in success_states):
            cls = "success_reached"
        else:
            cls = "stopped_early"
        term_by_user[uid] = cls
    term_counts = Counter(term_by_user.values())
    pending = sum(1 for uid, c in term_by_user.items() if c == "never_contacted" and not per[uid]["sla_elapsed"])
    declared = set(policy["termination_reasons"])
    termination = {
        "users": len(treat_el),
        "classes": {c: term_counts.get(c, 0) for c in TERMINATION_ORDER},
        "precedence": TERMINATION_ORDER,
        "declared": policy["termination_declared"],
        "declared_reasons": policy["termination_reasons"],
        "undeclared_classes_used": [c for c in TERMINATION_ORDER if term_counts.get(c) and c not in declared],
        "declared_not_computable": [c for c in policy["termination_reasons"] if c not in TERMINATION_ORDER],
        "converted_computed": outcomes is not None,
        "outcome_blank": outcome_blank if outcomes is not None else None,
        "never_contacted_window_open": pending,
    }
    for c in TERMINATION_ORDER:
        termination[c] = term_counts.get(c, 0)

    # --- staleness --------------------------------------------------------------
    staleness = None
    if has_rendered:
        ages, negative, blank = [], 0, 0
        for s in policy_sends:
            if s["rendered_at"] is None:
                blank += 1
                continue
            age = _hours(s["sent_at"] - s["rendered_at"])
            if age < 0:
                negative += 1
            else:
                ages.append(age)
        ages.sort()
        staleness = {
            "sends_measured": len(ages), "blank_rendered_at": blank, "rendered_after_send": negative,
            "p50_hours": percentile(ages, 0.5), "p90_hours": percentile(ages, 0.9),
            "max_hours": ages[-1] if ages else None,
            "over_24h": sum(1 for a in ages if a > 24),
        }

    # --- findings ---------------------------------------------------------------
    findings = []

    def add(fid, message, fix, states=(), **extra):
        findings.append({"id": fid, "states": list(states), "message": message, "fix": fix, **extra})

    nc = reach["non_contact"]
    if gate != "pass":
        if gate == "not_evaluable":
            msg = (f"No eligible treatment user's {sla:g}h first-contact window has closed by the as-of "
                   f"time, so reach cannot be measured yet.")
            fix = "Re-run the audit after the first-contact window has closed for the first cohort."
        else:
            msg = (f"Only {pct(rate)} of eligible treatment users ({len(timely):,} of {len(denom):,} whose "
                   f"{sla:g}h window had closed) got a first contact within {sla:g}h. The gate needs "
                   f"{pct(policy['treatment_reach_min'])}. A readout of this run measures the outage, not "
                   f"the policy.")
            parts = []
            if nc["no_rows"]:
                parts.append(f"{nc['no_rows']:,} users have no send row at all: find where the pipeline "
                             f"skipped them (an outage, a missing trigger) and alert on users with no row "
                             f"{sla:g}h after assignment")
            if nc["late_first_contact"]:
                parts.append(f"{nc['late_first_contact']:,} were first contacted after the SLA (median "
                             f"{_h(nc['late_first_contact_hours_p50'])} after assignment): send the first "
                             f"email sooner")
            if nc["only_not_delivered"]:
                parts.append(f"{nc['only_not_delivered']:,} only have failed, suppressed or blocked rows: "
                             f"check addresses and suppression lists before launch")
            fix = "; ".join(parts) + "." if parts else "Find out why these users were never contacted."
        add("reach_gate", msg, fix, value=rate, threshold=policy["treatment_reach_min"])
    if success_sends:
        add("success_state_sends",
            f"{pct(budget['success_state_send_share'])} of sends ({success_sends:,} of {total_sends:,}) went "
            f"to {success_users:,} users already in a success state ({', '.join(sorted(success_states))}). "
            f"That budget is spent on users who already did the thing.",
            "Make success states no-send and re-check the state right before each send. In Typesy "
            "Homeschool, 73% of sends went to households already past the key action; moving that budget "
            "to stuck users was the intervention.",
            states=sorted(st for st in success_states if by_state.get(st)),
            value=budget["success_state_send_share"])
    if cap_v["count"]:
        add("cap_violation",
            f"{cap_v['count']:,} eligible treatment users got more than the cap of {cap} successful sends "
            f"(up to {cap_v['max_sends']}; {cap_v['excess_sends']:,} sends over the cap).",
            f"Enforce the cap inside the send step, counted from the send log, using the design value "
            f"({cap}). In Typesy the code cap drifted to 5 while the design said 3. A config field that no "
            f"sender reads is not a control.", value=cap_v["count"])
    if spacing_v["count"]:
        add("spacing_violation",
            f"{spacing_v['count']:,} pairs of sends to the same user were less than {gap_min:g}h apart, "
            f"affecting {spacing_v['users']:,} users (shortest gap {spacing_v['shortest_gap_hours']:.1f}h).",
            f"Check the hours since the last successful send right before each send, and deduplicate "
            f"retries so a resend cannot land within {gap_min:g}h.", value=spacing_v["count"])
    if control_v["count"] and not policy["control_contact_allowed"]:
        add("control_contacted",
            f"{control_v['count']:,} control users got {control_v['sends']:,} successful sends. Control "
            f"must not receive the treatment, so the comparison is contaminated.",
            "Check the arm from assignments at send time and block control users in the same delivery "
            "machinery. Find the path that sent to them (a second campaign, a retry queue, a manual send).",
            value=control_v["count"])
    if nosend_v["count"]:
        add("no_send_state_sends",
            f"{nosend_v['count']:,} sends went out while the user was in a no-send state "
            f"({', '.join(f'{k} {v:,}' for k, v in ns_states.most_common())}).",
            "Re-check the state right before each send, skip no-send states, and log the blocked reason.",
            states=[k for k, _ in ns_states.most_common()], value=nosend_v["count"])
    if staleness and staleness["p50_hours"] is not None and (
            staleness["p50_hours"] > 1 or staleness["max_hours"] > 24):
        add("stale_render",
            f"Emails were rendered long before they were sent: median {_h(staleness['p50_hours'])}, p90 "
            f"{_h(staleness['p90_hours'])}, max {_h(staleness['max_hours'])}. {staleness['over_24h']:,} "
            f"sends were over 24h old. Their facts may have changed in between.",
            "Render at the last responsible moment: re-render right before the provider call, and reject "
            "drafts older than your data refresh interval.", value=staleness["p50_hours"])
    findings.sort(key=lambda f: FINDING_ORDER.index(f["id"]))

    result = {
        "schema_version": SCHEMA_VERSION,
        "tool": "audit_sends",
        "inputs": {
            "policy_file": policy["file"], "assignments_file": files.get("assignments"),
            "sends_file": files.get("sends"), "outcomes_file": files.get("outcomes"),
            "outcome": outcome_col, "as_of": as_of, "as_of_source": as_of_source,
            "assigned_users": len(users), "treatment": len(treat), "control": len(control),
            "treatment_eligible": len(treat_el), "send_rows": len(sends),
            "status_counts": dict(Counter(s["status"] for s in sends).most_common()),
            "has_rendered_at": has_rendered,
        },
        "policy": {k: policy[k] for k in ("max_sends_per_user", "min_hours_between_sends",
                                          "first_contact_sla_hours", "treatment_reach_min",
                                          "control_contact_allowed", "success", "no_send")},
        "reach": reach,
        "sends_by_state": sends_by_state,
        "budget": budget,
        "violations": violations,
        "sends_per_user": sends_per_user,
        "termination": termination,
        "staleness": staleness,
        "findings": findings,
        "finding_counts": dict(Counter(f["id"] for f in findings)),
        "notes": notes,
    }
    return result, per, term_by_user


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _n(x):
    return f"{x:,}"


def render_report(r):
    inp, pol, reach, budget, v = r["inputs"], r["policy"], r["reach"], r["budget"], r["violations"]
    out = []
    w = out.append
    as_of = inp["as_of"].strftime("%Y-%m-%d %H:%M UTC") if hasattr(inp["as_of"], "strftime") else inp["as_of"]
    w(f"# Send audit: {inp['sends_file'] or 'sends.csv'} against {inp['policy_file']}")
    w("")
    w(f"As of {as_of} ({inp['as_of_source']}). {_n(inp['assigned_users'])} assigned users "
      f"({_n(inp['treatment'])} treatment, {_n(inp['control'])} control) and {_n(inp['send_rows'])} send rows. "
      f"Arms come only from assignments.csv.")
    w("")

    # Headline
    w("## Headline")
    w("")
    sla = reach["sla_hours"]
    if reach["gate"] == "not_evaluable":
        w(f"- **Reach gate: NOT EVALUABLE.** No eligible treatment user's {sla:g}h window has closed yet.")
    else:
        w(f"- **Reach gate: {reach['gate'].upper()}.** {pct(reach['rate'])} of eligible treatment users "
          f"({_n(reach['timely'])} of {_n(reach['eligible'])} whose {sla:g}h window had closed) got a first "
          f"contact within {sla:g}h. The gate needs {pct(reach['threshold'])}.")
    if budget["successful_sends"]:
        w(f"- **{pct(budget['success_state_send_share'])} of sends went to users already in a success state** "
          f"({_n(budget['success_state_sends'])} of {_n(budget['successful_sends'])} treatment sends).")
    else:
        w("- No successful treatment sends, so there is no send budget to examine.")
    ctrl_word = " (allowed by policy)" if pol["control_contact_allowed"] else ""
    w(f"- **Violations:** {_n(v['cap']['count'])} users over the cap of {pol['max_sends_per_user']}; "
      f"{_n(v['spacing']['count'])} gaps under {pol['min_hours_between_sends']:g}h; "
      f"{_n(v['control_contacted']['count'])} control users contacted{ctrl_word}; "
      f"{_n(v['no_send_state_sends']['count'])} sends in no-send states.")
    st = r["staleness"]
    if st and st["p50_hours"] is not None:
        w(f"- **Render to send:** median {_h(st['p50_hours'])}, max {_h(st['max_hours'])}.")
    elif not inp["has_rendered_at"]:
        w("- **Render to send:** not measured (sends.csv has no rendered_at column).")
    if r["findings"]:
        ids = ", ".join(f"`{f['id']}`" for f in r["findings"])
        w(f"- **{len(r['findings'])} finding(s):** {ids}. Fixes are in the last section.")
    else:
        w("- **No findings.** Reach passed and no contact-policy rule was broken.")
    w("")

    # 1. Reach
    w("## 1. Reach")
    w("")
    w(f"The gate counts eligible treatment users whose {sla:g}h window had closed by the as-of time. A user "
      f"is reached if their first `sent`, `delivered` or `not_needed` row came within {sla:g}h of "
      f"assignment (`not_needed` means the policy checked them and correctly chose not to send).")
    w("")
    w("| Measure | Users | Of | Rate |")
    w("|---|---:|---:|---:|")
    w(f"| **Reached within {sla:g}h (the gate)** | {_n(reach['timely'])} | {_n(reach['eligible'])} | "
      f"**{pct(reach['rate'])}** |")
    w(f"| Delivered (`sent`/`delivered`, any time) | {_n(reach['delivered']['users'])} | "
      f"{_n(reach['delivered']['denominator'])} | {pct(reach['delivered']['rate'])} |")
    w(f"| Reached within {sla:g}h, all assigned treatment users (eligible or not) | "
      f"{_n(reach['all_assigned']['users'])} | {_n(reach['all_assigned']['denominator'])} | "
      f"{pct(reach['all_assigned']['rate'])} |")
    w("")
    w(f"{_n(reach['treatment_eligible'])} eligible treatment users in total; {_n(reach['sla_not_elapsed'])} "
      f"are still inside their {sla:g}h window and are not counted yet. Median time to first contact: "
      f"{_h(reach['first_contact_hours']['p50'])} (p90 {_h(reach['first_contact_hours']['p90'])}).")
    w("")
    nc = reach["non_contact"]
    w(f"**Why {_n(nc['users'])} eligible treatment users were not reached in time**")
    w("")
    w("| Reason | Users |")
    w("|---|---:|")
    w(f"| No send row at all | {_n(nc['no_rows'])} |")
    by = nc["only_not_delivered_by_status"]
    detail = f" ({', '.join(f'{k} {v:,}' for k, v in by.items())})" if by else ""
    w(f"| Only failed, suppressed or blocked rows{detail} | {_n(nc['only_not_delivered'])} |")
    w(f"| First contact after the {sla:g}h SLA (median {_h(nc['late_first_contact_hours_p50'])}) | "
      f"{_n(nc['late_first_contact'])} |")
    w("")

    # 2. Where the sends went
    w("## 2. Where the sends went")
    w("")
    w("Successful (`sent`/`delivered`) sends to treatment users, by the user's state at send time. "
      "Control sends are counted under violations.")
    w("")
    if r["sends_by_state"]:
        w("| State at send | Sends | Share | Success state? | No-send state? | Messages |")
        w("|---|---:|---:|---|---|---|")
        for row in r["sends_by_state"]:
            msgs = ", ".join(f"{k} {n:,}" for k, n in list(row["message_keys"].items())[:3]) or "—"
            w(f"| {row['state']} | {_n(row['sends'])} | {pct(row['share'])} | "
              f"{'**yes**' if row['is_success'] else 'no'} | {'**yes**' if row['is_no_send'] else 'no'} | "
              f"{msgs} |")
        w("")
    if budget["blank_state_sends"]:
        w(f"{_n(budget['blank_state_sends'])} sends have no state_at_send. Their targeting cannot be checked.")
        w("")
    if budget["design_budget"]:
        w(f"Design budget: {pol['max_sends_per_user']} sends × {_n(r['sends_per_user']['users'])} eligible "
          f"treatment users = {_n(budget['design_budget'])}; {pct(budget['design_budget_used'])} used.")
        w("")

    # 3. Violations
    w("## 3. Contact-policy violations")
    w("")
    w("| Check | Rule | Result | Detail |")
    w("|---|---|---:|---|")
    w(f"| Cap | at most {pol['max_sends_per_user']} successful sends per eligible treatment user | "
      f"{_n(v['cap']['count'])} users | {'; '.join(v['cap']['examples']) or '—'} |")
    w(f"| Spacing | at least {pol['min_hours_between_sends']:g}h between successful sends to one user | "
      f"{_n(v['spacing']['count'])} gaps ({_n(v['spacing']['users'])} users) | "
      f"{'; '.join(v['spacing']['examples']) or '—'} |")
    allowed = "allowed" if pol["control_contact_allowed"] else "not allowed"
    w(f"| Control contacted | control contact {allowed} | {_n(v['control_contacted']['count'])} users | "
      f"{'; '.join(v['control_contacted']['examples']) or '—'} |")
    w(f"| No-send states | no sends in {', '.join(pol['no_send']) or '(none declared)'} | "
      f"{_n(v['no_send_state_sends']['count'])} sends | {'; '.join(v['no_send_state_sends']['examples']) or '—'} |")
    w("")
    w("Exactly at a limit is allowed: the cap-th send and a gap of exactly the minimum are fine.")
    w("")

    # 4. Sends per user
    spu = r["sends_per_user"]
    w("## 4. Sends per eligible treatment user")
    w("")
    w("| Successful sends | " + " | ".join(spu["distribution"]) + " |")
    w("|---|" + "---:|" * len(spu["distribution"]))
    w("| Users | " + " | ".join(_n(x) for x in spu["distribution"].values()) + " |")
    w("")
    w(f"Mean {spu['mean']:.2f} sends per user; the cap is {spu['cap']}." if spu["mean"] is not None
      else "No eligible treatment users.")
    w("")

    # 5. Termination
    t = r["termination"]
    w("## 5. How each sequence ended (termination)")
    w("")
    w("Each eligible treatment user gets the first class that applies, in this order. Termination "
      "classes must be defined before launch; never infer them from whatever the last row says.")
    w("")
    w("| Class | Users | Share | Meaning |")
    w("|---|---:|---:|---|")
    for c in t["precedence"]:
        n = t["classes"][c]
        meaning = TERMINATION_MEANING[c]
        if c == "converted" and not t["converted_computed"]:
            meaning += "; not computed: no --outcomes given"
        w(f"| {c} | {_n(n)} | {pct(_rate(n, t['users']))} | {meaning} |")
    w("")
    if t["never_contacted_window_open"]:
        w(f"- {_n(t['never_contacted_window_open'])} of the never_contacted users are still inside their "
          f"first-contact window.")
    if t["outcome_blank"]:
        w(f"- {_n(t['outcome_blank'])} eligible treatment users have a blank outcome; they are not counted as "
          f"converted.")
    if not t["declared"]:
        w("- The policy has no [termination] section, so the default classes were used.")
    if t["undeclared_classes_used"]:
        w(f"- Classes used here but not declared in [termination]: {', '.join(t['undeclared_classes_used'])}. "
          f"What to fix: add them to the declared reasons before the next launch.")
    if t["declared_not_computable"]:
        w(f"- Declared reasons this audit cannot compute from these files: "
          f"{', '.join(t['declared_not_computable'])}. Log them as explicit rows in the send log.")
    w("")

    # 6. Staleness
    w("## 6. Render-to-send staleness")
    w("")
    if st is None:
        w("Not measured: sends.csv has no rendered_at column. What to fix: log when each email was rendered.")
    elif st["p50_hours"] is None:
        w(f"Not measured: rendered_at is blank on all {_n(st['blank_rendered_at'])} successful treatment sends.")
    else:
        w(f"Hours from rendered_at to sent_at, over {_n(st['sends_measured'])} successful treatment sends: "
          f"median {_h(st['p50_hours'])}, p90 {_h(st['p90_hours'])}, max {_h(st['max_hours'])}. "
          f"{_n(st['over_24h'])} were over 24h old.")
        if st["blank_rendered_at"]:
            w(f"{_n(st['blank_rendered_at'])} sends have a blank rendered_at.")
        if st["rendered_after_send"]:
            w(f"{_n(st['rendered_after_send'])} sends were rendered after they were sent (left out). Check "
              f"the clocks.")
        w("The flag fires when the median is over 1h or the maximum is over 24h.")
    w("")

    # 7. What to fix
    w("## 7. What to fix")
    w("")
    if not r["findings"]:
        w("No flagged problems. Reach passed and no contact-policy rule was broken. Keep this audit "
          "running on every batch.")
    for i, f in enumerate(r["findings"], start=1):
        w(f"{i}. **`{f['id']}`.** {f['message']}")
        w(f"   *What to fix:* {f['fix']}")
    w("")
    also = []
    if not t["declared"]:
        also.append("Declare the termination reasons in a [termination] section of contact-policy.toml "
                    "before launch (the defaults were used here).")
    if t["classes"]["stopped_early"]:
        also.append(f"{_n(t['classes']['stopped_early'])} sequences ended as stopped_early. Log a `not_needed` "
                    f"row whenever the policy stops because the user succeeded, so a legitimate stop can be "
                    f"told apart from a pipeline stop.")
    if st is None:
        also.append("Log rendered_at on every send so staleness can be checked.")
    if budget["blank_state_sends"]:
        also.append("Log state_at_send on every send so targeting can be checked.")
    if also:
        w("**Also (not flagged, but worth fixing)**")
        w("")
        for line in also:
            w(f"- {line}")
        w("")
    if r["notes"]:
        w("**Data notes**")
        w("")
        for note in r["notes"]:
            w(f"- {note}")
        w("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="audit_sends.py",
        description="Audit what a state-routed email program actually sent, against its contact policy. "
                    "Reports reach against the eligible treatment arm (the delivery gate), where the sends "
                    "went and how much went to users already in a success state, cap / spacing / "
                    "control-contact / no-send-state violations, sends per user, how each user's sequence "
                    "ended, and render-to-send staleness.",
        epilog="Exit codes: 0 = the audit ran (findings do not change the exit code); 2 = malformed input "
               "(the message names the file, row and column). Formats: docs/data-contracts.md.",
    )
    p.add_argument("--policy", required=True, metavar="FILE",
                   help="contact-policy.toml: [policy] with max_sends_per_user, min_hours_between_sends, "
                        "first_contact_sla_hours, treatment_reach_min and control_contact_allowed; "
                        "[states] with the success and no_send state lists; optional [termination].")
    p.add_argument("--assignments", required=True, metavar="FILE",
                   help="assignments.csv: one row per randomised user (user_id, arm, assigned_at, optional "
                        "eligible). The arm is taken from this file only.")
    p.add_argument("--sends", required=True, metavar="FILE",
                   help="sends.csv: one row per send attempt (user_id, sent_at, status; optional "
                        "state_at_send, message_key, rendered_at).")
    p.add_argument("--outcomes", metavar="FILE",
                   help="Optional outcomes.csv (user_id plus outcome columns). Used only to mark users "
                        "whose sequence ended because they converted. Needs --outcome.")
    p.add_argument("--outcome", metavar="COLUMN",
                   help="The outcome column in --outcomes (1/0; blank = not measured), e.g. converted.")
    p.add_argument("--as-of", metavar="DATE",
                   help="Audit the data as of this ISO 8601 time (a date means midnight UTC). Rows after "
                        "it are left out. Default: the latest assigned_at or sent_at in the files.")
    p.add_argument("--emit-user-file", action="store_true",
                   help="Also write users.csv (user_id, arm, termination, successful_sends, "
                        "first_contact_hours) to --out. It contains user IDs, so keep it internal. The "
                        "report never contains IDs.")
    p.add_argument("--out", required=True, metavar="DIR",
                   help="Folder for report.md and result.json (created if missing). The report is also "
                        "printed to stdout.")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if bool(args.outcomes) != bool(args.outcome):
        parser.error("--outcomes and --outcome must be given together")
    as_of = parse_time(args.as_of, "--as-of") if args.as_of else None
    policy = load_policy(args.policy)
    users = load_assignments(args.assignments)
    sends, has_rendered, _ = load_sends(args.sends)
    outcomes = load_outcomes(args.outcomes, args.outcome) if args.outcomes else None
    files = {"assignments": Path(args.assignments).name, "sends": Path(args.sends).name,
             "outcomes": Path(args.outcomes).name if args.outcomes else None}
    result, per, term = analyse(policy, users, sends, has_rendered, outcomes, args.outcome, as_of, files)
    write_outputs(args.out, render_report(result), result)
    if args.emit_user_file:
        path = Path(args.out) / "users.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow(["user_id", "arm", "termination", "successful_sends", "first_contact_hours"])
            for uid, u in users.items():
                if uid not in per:
                    continue
                fch = per[uid]["first_contact_hours"]
                writer.writerow([uid, u["arm"], term.get(uid, ""), len(per[uid]["succ"]),
                                 "" if fch is None else f"{fch:.2f}"])
    return 0


if __name__ == "__main__":
    run_main(main)
