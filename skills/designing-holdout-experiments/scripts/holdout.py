#!/usr/bin/env python3
"""Design a fixed holdout experiment: size it, assign users, seal the plan, verify the seal.

Part of the designing-holdout-experiments skill. Four subcommands:

  size    How many users each arm needs to detect the smallest effect worth having.
  assign  Deterministic hash assignment of users to treatment or control. Never re-drawn.
  seal    Check prereg.toml is complete and write prereg.lock with its SHA-256 hash.
  verify  Check prereg.toml still matches prereg.lock (exit 1 if it does not).

Standard library only. Formats are defined in docs/data-contracts.md.

Examples:
    python3 holdout.py size --baseline 0.23 --mde 0.02 --eligible-per-week 300
    python3 holdout.py assign --users users.csv --salt practica-2026q2 --out assignments.csv
    python3 holdout.py seal prereg.toml
    python3 holdout.py verify prereg.toml
"""

import argparse
import csv
import hashlib
import json
import math
from datetime import date, datetime, timezone
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
SENSITIVITY_MULTIPLIERS = (0.5, 1.0, 1.5, 2.0)
SLOW_WEEKS = 26
SLOW_WARNING = ("This is a slow fixed experiment, not an optimisation loop; consider a bigger effect "
                "target or a higher-volume population.")
ARMS = ("treatment", "control")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_z(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_p(p):
    if p is None or (isinstance(p, float) and not math.isfinite(p)):
        return "—"
    if p < 0.0001:
        return "< 0.0001"
    return f"{p:.4f}"


def _fmt_count(n):
    return "—" if n is None else f"{n:,}"


def _fmt_rate_per_week(x):
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.1f}"


def _require_open_unit(flag, value, hint=""):
    if not 0 < value < 1:
        raise InputError(f"{flag}: must be between 0 and 1, exclusive, got {value:g}.{hint}")


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
# size
# ---------------------------------------------------------------------------

def size_row(baseline, effect, direction, alpha, power, allocation, per_week):
    target = baseline + effect if direction == "increase" else baseline - effect
    row = {"effect": effect, "signed_effect": effect if direction == "increase" else -effect,
           "target_rate": target, "feasible": 0 < target < 1,
           "n_control": None, "n_treatment": None, "n_total": None, "weeks": None}
    if not row["feasible"]:
        return row
    n_c, n_t = sample_size_per_arm(baseline, target, alpha=alpha, power=power,
                                   allocation_treatment=allocation)
    row["n_control"], row["n_treatment"] = int(n_c), int(n_t)
    row["n_total"] = row["n_control"] + row["n_treatment"]
    if per_week:
        row["weeks"] = math.ceil(row["n_total"] / per_week)
    return row


def size_sentence(baseline, main, direction, alpha, power, allocation, per_week):
    verb = "rise" if direction == "increase" else "fall"
    head = (f"To detect a {verb} from {pct(baseline)} to {pct(main['target_rate'])} "
            f"({pp(main['signed_effect'])}) with {power * 100:g}% power at α = {alpha:g}, you need ")
    if main["n_control"] == main["n_treatment"]:
        need = f"{main['n_control']:,} users per arm ({main['n_total']:,} total)"
    else:
        need = (f"{main['n_control']:,} control users and {main['n_treatment']:,} treatment users "
                f"({main['n_total']:,} total, {pct(allocation, 0)} in treatment)")
    if per_week:
        unit = "week" if main["weeks"] == 1 else "weeks"
        tail = f", about {main['weeks']:,} {unit} at {_fmt_rate_per_week(per_week)} eligible users a week."
    else:
        tail = ". Pass --eligible-per-week to see how many weeks that takes."
    return head + need + tail


def cmd_size(args):
    _require_open_unit("--baseline", args.baseline, " Give a proportion, e.g. 0.23 for 23%.")
    _require_open_unit("--mde", args.mde, " Give an absolute change, e.g. 0.02 for 2 percentage points.")
    _require_open_unit("--alpha", args.alpha)
    _require_open_unit("--power", args.power)
    _require_open_unit("--allocation", args.allocation, " It is the share of users in treatment.")
    if args.eligible_per_week is not None and args.eligible_per_week <= 0:
        raise InputError(f"--eligible-per-week: must be greater than 0, got {args.eligible_per_week:g}.")
    per_week = args.eligible_per_week
    main_row = size_row(args.baseline, args.mde, args.direction, args.alpha, args.power,
                        args.allocation, per_week)
    if not main_row["feasible"]:
        raise InputError(f"--mde: a {args.direction} of {pp(args.mde)} from {pct(args.baseline)} gives "
                         f"{pct(main_row['target_rate'])}, which is not a possible rate.")
    sentence = size_sentence(args.baseline, main_row, args.direction, args.alpha, args.power,
                             args.allocation, per_week)
    sensitivity = []
    for m in SENSITIVITY_MULTIPLIERS:
        row = size_row(args.baseline, args.mde * m, args.direction, args.alpha, args.power,
                       args.allocation, per_week)
        row["multiplier"] = m
        sensitivity.append(row)

    warnings = []
    if main_row["weeks"] is not None and main_row["weeks"] > SLOW_WEEKS:
        warnings.append(SLOW_WARNING)

    lines = ["# Sample size", "", sentence, ""]
    for w in warnings:
        lines += [f"**Warning:** {w}", ""]
    lines += ["## Sensitivity", "",
              "How the requirement changes if the true effect is smaller or larger than your target.", "",
              "| Effect | Treatment rate | Control users | Treatment users | Total | Weeks |",
              "|---|---|---|---|---|---|"]
    for row in sensitivity:
        label = f"{pp(row['signed_effect'])} ({row['multiplier']:g}× target)"
        if not row["feasible"]:
            lines.append(f"| {label} | {pct(row['target_rate'])} | not a possible rate | | | |")
            continue
        weeks = _fmt_count(row["weeks"])
        lines.append(f"| {label} | {pct(row['target_rate'])} | {row['n_control']:,} | "
                     f"{row['n_treatment']:,} | {row['n_total']:,} | {weeks} |")
    lines += ["", "## Notes", "",
              "- Two-sided test of two proportions, normal approximation (docs/data-contracts.md).",
              "- This is pre-launch power for the effect you will register as `minimum_worthwhile_effect`. "
              "Never recompute it from an observed effect.",
              "- Count users whose outcome will be measured. After the last user is assigned, the outcome "
              "window must still close before the readout can run.",
              "- Copy `baseline_rate` and `minimum_worthwhile_effect` into prereg.toml exactly as used here, "
              "then seal it."]
    report = "\n".join(lines)
    result = {
        "schema_version": SCHEMA_VERSION,
        "command": "size",
        "inputs": {"baseline": args.baseline, "mde": args.mde, "direction": args.direction,
                   "alpha": args.alpha, "power": args.power, "allocation": args.allocation,
                   "eligible_per_week": per_week},
        "target_rate": main_row["target_rate"],
        "n_control": main_row["n_control"],
        "n_treatment": main_row["n_treatment"],
        "n_total": main_row["n_total"],
        "sentence": sentence,
        "sensitivity": sensitivity,
        "warnings": warnings,
    }
    if per_week:
        result["weeks"] = main_row["weeks"]
    _emit(args.out, report, result)
    return 0


# ---------------------------------------------------------------------------
# assign
# ---------------------------------------------------------------------------

def hash_u(salt, stratum, user_id):
    """The contract's assignment hash: uniform in [0, 1)."""
    digest = hashlib.sha256(f"{salt}:{stratum}:{user_id}".encode("utf-8")).hexdigest()
    return int(digest[:13], 16) / 16 ** 13


def assign_arm(salt, stratum, user_id, allocation):
    return "treatment" if hash_u(salt, stratum, user_id) < allocation else "control"


def cmd_assign(args):
    _require_open_unit("--allocation", args.allocation, " It is the share of users in treatment.")
    if not args.salt.strip():
        raise InputError("--salt: must not be blank. The salt makes the assignment reproducible.")
    default_at = None
    if args.assigned_at:
        default_at = _iso_z(parse_time(args.assigned_at, "--assigned-at"))
    now_at = _now_iso()

    required = ["user_id"] + ([args.stratum_column] if args.stratum_column else [])
    rows = read_csv(args.users, required=required)
    if not rows:
        raise InputError(f"{args.users}: no user rows below the header")
    columns = set(rows[0])
    has_at = "assigned_at" in columns
    has_eligible = "eligible" in columns
    has_reason = "exclusion_reason" in columns
    has_arm = "arm" in columns and args.stratum_column != "arm"

    seen = {}
    out_rows = []
    fallback_at = 0
    arm_disagree = 0
    for row in rows:
        where = row["_where"]
        uid = row.get("user_id") or ""
        if uid == "":
            raise InputError(f"{where}: user_id is blank")
        if uid in seen:
            raise InputError(f"{where}: user_id repeats {seen[uid]}. Each user is assigned once.")
        seen[uid] = where
        stratum = (row.get(args.stratum_column) or "") if args.stratum_column else ""
        arm = assign_arm(args.salt, stratum, uid, args.allocation)
        at = (row.get("assigned_at") or "") if has_at else ""
        if at:
            parse_time(at, f"{where}: assigned_at")
        else:
            at = default_at or now_at
            if has_at:
                fallback_at += 1
        rec = {"user_id": uid, "arm": arm, "assigned_at": at}
        if args.stratum_column:
            rec["stratum"] = stratum
        if has_eligible:
            parse_bool(row.get("eligible"), f"{where}: eligible")
            rec["eligible"] = row.get("eligible") or ""
        if has_reason:
            rec["exclusion_reason"] = row.get("exclusion_reason") or ""
        if has_arm:
            given = (row.get("arm") or "").strip().lower()
            if given in ARMS and given != arm:
                arm_disagree += 1
        out_rows.append(rec)

    # Never re-draw: an existing output file must agree with the hash for every user it holds.
    out = Path(args.out)
    kept = 0
    if out.exists():
        old_rows = read_csv(out, required=["user_id", "arm"])
        old = {r["user_id"]: r for r in old_rows}
        new_ids = {r["user_id"] for r in out_rows}
        changed = [r for r in out_rows
                   if r["user_id"] in old and (old[r["user_id"]].get("arm") or "").strip().lower() != r["arm"]]
        dropped = [uid for uid in old if uid not in new_ids]
        if changed or dropped:
            problems = []
            if changed:
                problems.append(f"{len(changed):,} user(s) already in it would change arm")
            if dropped:
                problems.append(f"{len(dropped):,} user(s) already in it are missing from {args.users}")
            raise InputError(f"{out}: refusing to overwrite: {' and '.join(problems)}. Assignment is never "
                             "re-drawn. Check the salt, allocation and stratum column, or write to a new file.")
        for r in out_rows:
            prev = old.get(r["user_id"])
            if prev is not None:
                kept += 1
                if prev.get("assigned_at"):
                    r["assigned_at"] = prev["assigned_at"]

    fields = ["user_id", "arm", "assigned_at"]
    if args.stratum_column:
        fields.append("stratum")
    if has_eligible:
        fields.append("eligible")
    if has_reason:
        fields.append("exclusion_reason")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)

    n_t = sum(1 for r in out_rows if r["arm"] == "treatment")
    n_c = len(out_rows) - n_t
    overall_p = srm_p(n_t, n_c, args.allocation)
    by_stratum = {}
    if args.stratum_column:
        for r in out_rows:
            cell = by_stratum.setdefault(r["stratum"], {"treatment": 0, "control": 0})
            cell[r["arm"]] += 1
        for cell in by_stratum.values():
            cell["srm_p"] = srm_p(cell["treatment"], cell["control"], args.allocation)

    srm_ok = overall_p >= 0.001
    lines = ["# Assignment", "",
             f"Assigned {len(out_rows):,} users with salt `{args.salt}` at {pct(args.allocation)} treatment. "
             f"Wrote {out.name}.", "",
             "| Arm | Users | Share |", "|---|---|---|"]
    total = max(len(out_rows), 1)
    for arm, n in (("treatment", n_t), ("control", n_c)):
        lines.append(f"| {arm} | {n:,} | {pct(n / total)} |")
    lines += ["", f"Sample-ratio check: p = {_fmt_p(overall_p)} against the {pct(args.allocation)} allocation. "
              + ("PASS." if srm_ok else
                 "WARNING: below 0.001. The user list or the allocation is wrong. Stop and investigate "
                 "before any send.")]
    if by_stratum:
        lines += ["", f"By stratum (column `{args.stratum_column}`):", "",
                  "| Stratum | Treatment | Control | Sample-ratio p |", "|---|---|---|---|"]
        for s in sorted(by_stratum):
            cell = by_stratum[s]
            label = s if s != "" else "(blank)"
            lines.append(f"| {label} | {cell['treatment']:,} | {cell['control']:,} | {_fmt_p(cell['srm_p'])} |")
        blanks = by_stratum.get("", {})
        if blanks:
            lines += ["", f"{blanks['treatment'] + blanks['control']:,} users have a blank stratum. "
                      "They were hashed with an empty stratum."]
    notes = ["Arms come from sha256(salt:stratum:user_id). Re-running with the same inputs gives the same "
             "arms. Assignment is never re-drawn.",
             "Record the salt in prereg.toml (`[experiment] salt`) and seal the plan before the first send."]
    if has_arm:
        notes.append(f"The input has an `arm` column. It was ignored. {arm_disagree:,} rows disagree with "
                     "the hash assignment.")
    if kept:
        notes.append(f"{kept:,} users were already in {out.name}. They keep their arm and assignment time.")
    if fallback_at:
        notes.append(f"{fallback_at:,} rows had a blank assigned_at and got {default_at or 'the current time'}.")
    if not has_at:
        notes.append(f"The input has no assigned_at column, so every user got {default_at or 'the current UTC time'}.")
    lines += ["", "## Notes", ""] + [f"- {n}" for n in notes]
    report = "\n".join(lines)
    result = {
        "schema_version": SCHEMA_VERSION,
        "command": "assign",
        "inputs": {"users": str(args.users), "allocation": args.allocation,
                   "stratum_column": args.stratum_column, "out": str(out)},
        "counts": {"treatment": n_t, "control": n_c, "total": len(out_rows), "by_stratum": by_stratum},
        "srm_p": overall_p,
        "input_arm_disagreements": arm_disagree if has_arm else None,
        "kept_from_existing_file": kept,
    }
    _emit(args.report_dir, report, result)
    return 0


# ---------------------------------------------------------------------------
# seal / verify
# ---------------------------------------------------------------------------

def prereg_sha256(path):
    """SHA-256 of the file's bytes after line endings are normalised to \\n."""
    data = Path(path).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def lock_path_for(path):
    p = Path(path)
    return p.with_name(p.stem + ".lock")


def validate_prereg(data, name):
    """Check a parsed prereg.toml. Return (errors, warnings, plan)."""
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


def cmd_seal(args):
    path = Path(args.file)
    data = load_toml(path)
    errors, warnings, plan = validate_prereg(data, path.name)
    if errors:
        raise InputError(f"{path}: cannot be sealed:\n  " + "\n  ".join(errors))
    sealed_at = _iso_z(parse_time(args.sealed_at, "--sealed-at")) if args.sealed_at else _now_iso()
    digest = prereg_sha256(path)
    lock = lock_path_for(path)
    previous = None
    if lock.exists():
        try:
            previous = json.loads(lock.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            previous = {}
        if not isinstance(previous, dict):
            previous = {}
        if not args.force:
            same = previous.get("sha256") == digest
            when = previous.get("sealed_at", "an unknown time")
            detail = ("The plan has not changed since then; run `verify` instead."
                      if same else "The plan has changed since then.")
            raise InputError(
                f"{lock}: already exists (sealed {when}). Refusing to overwrite it. {detail} Re-sealing after "
                "launch is a protocol deviation: it lets the question change after data started arriving, and "
                "the readout could no longer prove the plan was fixed in advance. If the plan must change, save "
                "it as a new version (new experiment.name and file) and seal that. Use --force only if no user "
                "has been assigned yet.")

    lock_doc = {"file": path.name, "sha256": digest, "sealed_at": sealed_at}
    lock.write_text(json.dumps(lock_doc, indent=2) + "\n", encoding="utf-8")

    if plan["cohort_start"] and parse_time(sealed_at) > plan["cohort_start"]:
        warnings.append(f"Sealed at {sealed_at}, after the cohort opened on {plan['cohort_start'].date()}. "
                        "A plan sealed after users were assigned is not a pre-registration.")
    if previous is not None:
        warnings.append(f"Overwrote an existing lock (previous sha256 {str(previous.get('sha256'))[:12]}…, "
                        f"sealed {previous.get('sealed_at', 'unknown')}). If any user was already assigned, "
                        "record this as a protocol deviation.")
    lines = ["# Seal", "",
             f"Sealed {path.name}. Wrote {lock.name}.", "",
             f"- sha256: `{digest}`",
             f"- sealed_at: {sealed_at}",
             f"- experiment: {plan['name']}",
             f"- primary: {plan['metric']}, {plan['direction']}, minimum worthwhile effect {pp(plan['delta'])}",
             f"- cohort: {plan['cohort_start'].date()} to {plan['cohort_end'].date()}, analysis not before "
             f"{plan['analysis_not_before'].date()}",
             "", "From now on, any edit to the file breaks the seal. The readout will report "
             "PREREGISTRATION_DRIFT and refuse to classify the effect."]
    if warnings:
        lines += ["", "## Warnings", ""] + [f"- {w}" for w in warnings]
    result = {"schema_version": SCHEMA_VERSION, "command": "seal", "file": path.name, "lock": lock.name,
              "sha256": digest, "sealed_at": sealed_at, "match": True, "forced": previous is not None,
              "warnings": warnings}
    _emit(args.out, "\n".join(lines), result)
    return 0


def cmd_verify(args):
    path = Path(args.file)
    if not path.exists():
        raise InputError(f"{path}: file not found")
    digest = prereg_sha256(path)
    lock = lock_path_for(path)
    result = {"schema_version": SCHEMA_VERSION, "command": "verify", "file": path.name, "lock": lock.name,
              "sha256": digest, "locked_sha256": None, "sealed_at": None, "match": False}
    if not lock.exists():
        lines = ["# Verify", "", f"NOT SEALED: there is no {lock.name} next to {path.name}.", "",
                 f"Run `holdout.py seal {path.name}` before the first user is assigned."]
        _emit(args.out, "\n".join(lines), result)
        return 1
    try:
        doc = json.loads(lock.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise InputError(f"{lock}: not valid JSON ({exc})") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("sha256"), str):
        raise InputError(f"{lock}:sha256: missing. A lock must hold the sealed hash.")
    result["locked_sha256"] = doc["sha256"]
    result["sealed_at"] = doc.get("sealed_at")
    result["match"] = doc["sha256"].lower() == digest
    lines = ["# Verify", ""]
    if result["match"]:
        lines.append(f"MATCH: {path.name} is unchanged since it was sealed ({doc.get('sealed_at', 'time unknown')}).")
    else:
        lines += [f"MISMATCH: {path.name} has changed since it was sealed ({doc.get('sealed_at', 'time unknown')}).",
                  "", "A readout on this plan reports PREREGISTRATION_DRIFT and refuses to classify the effect. "
                  "Restore the sealed file, or register the change as a new experiment version."]
    lines += ["", f"- file sha256: `{digest}`", f"- lock sha256: `{doc['sha256']}`"]
    if doc.get("file") not in (None, path.name):
        lines.append(f"- note: the lock names `{doc.get('file')}`, not `{path.name}`.")
    _emit(args.out, "\n".join(lines), result)
    return 0 if result["match"] else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _emit(out_dir, report, result):
    if out_dir:
        write_outputs(out_dir, report, result)
    else:
        print(report.rstrip())


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="holdout.py",
        description="Design a fixed holdout experiment: size it, assign users by hash, seal the "
                    "pre-registration, and verify the seal. Run `holdout.py COMMAND --help` for each command.",
        epilog="Exit codes: 0 = done; 1 = verify found a mismatch or no lock; 2 = malformed input or a "
               "refused seal (the message says why).")
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    s = sub.add_parser("size", help="users needed per arm to detect the smallest worthwhile effect",
                       description="Work out how many users each arm needs before launch. Uses a two-sided "
                                   "two-proportion test (normal approximation) and adds a sensitivity table "
                                   "for half, one, one and a half and two times the effect.")
    s.add_argument("--baseline", type=float, required=True, metavar="P",
                   help="Today's rate of the primary outcome in the control experience, as a proportion "
                        "(0.23 means 23%%).")
    s.add_argument("--mde", type=float, required=True, metavar="D",
                   help="The minimum worthwhile effect: the smallest absolute change worth acting on "
                        "(0.02 means 2 percentage points). This is what you will seal in prereg.toml.")
    s.add_argument("--direction", choices=("increase", "decrease"), default="increase",
                   help="Which way is better for the outcome (default: increase).")
    s.add_argument("--alpha", type=float, default=0.05, metavar="A",
                   help="False-positive rate of the two-sided test (default: 0.05).")
    s.add_argument("--power", type=float, default=0.8, metavar="P",
                   help="Chance of detecting the effect if it is real (default: 0.8).")
    s.add_argument("--allocation", type=float, default=0.5, metavar="SHARE",
                   help="Share of users assigned to treatment (default: 0.5).")
    s.add_argument("--eligible-per-week", type=float, metavar="N",
                   help="How many eligible users enter per week. If given, the report says how many weeks "
                        "the experiment needs.")
    s.add_argument("--out", metavar="DIR",
                   help="Optional folder for report.md and result.json. The report is always printed.")
    s.set_defaults(func=cmd_size)

    a = sub.add_parser("assign", help="deterministic hash assignment to treatment or control",
                       description="Assign every user in a CSV to treatment or control with "
                                   "sha256(salt:stratum:user_id). The same inputs always give the same arms; "
                                   "nothing is ever re-drawn. Prints counts by arm and stratum and a "
                                   "sample-ratio p-value.")
    a.add_argument("--users", required=True, metavar="FILE",
                   help="CSV with a user_id column (one row per user). Optional columns that are carried over: "
                        "assigned_at, eligible, exclusion_reason. Any arm column is ignored.")
    a.add_argument("--salt", required=True, metavar="S",
                   help="Experiment-specific text mixed into the hash, e.g. practica-2026q2. Record it in "
                        "prereg.toml.")
    a.add_argument("--allocation", type=float, default=0.5, metavar="SHARE",
                   help="Share of users assigned to treatment (default: 0.5).")
    a.add_argument("--stratum-column", metavar="C",
                   help="Name of a pre-randomisation column (e.g. plan) to stratify on. It is mixed into the "
                        "hash and written to the output as `stratum`.")
    a.add_argument("--assigned-at", metavar="ISO",
                   help="Assignment time for users whose input has no assigned_at value. Default: now (UTC).")
    a.add_argument("--out", required=True, metavar="FILE",
                   help="Where to write the assignments CSV (user_id, arm, assigned_at, stratum if any). If "
                        "the file exists, it must agree with the new assignment; it is never re-drawn.")
    a.add_argument("--report-dir", metavar="DIR",
                   help="Optional folder for report.md and result.json (counts by arm and stratum).")
    a.set_defaults(func=cmd_assign)

    se = sub.add_parser("seal", help="validate prereg.toml and write its lock",
                        description="Check that the pre-registration names everything a readout needs, then "
                                    "write <name>.lock next to it with the file's SHA-256 hash. Refuses an "
                                    "incomplete plan, and refuses to overwrite an existing lock.")
    se.add_argument("file", metavar="FILE", help="The pre-registration to seal, e.g. prereg.toml.")
    se.add_argument("--sealed-at", metavar="ISO",
                    help="Seal time to record in the lock (default: now, UTC).")
    se.add_argument("--force", action="store_true",
                    help="Overwrite an existing lock. Only before any user is assigned; after launch this is "
                         "a protocol deviation.")
    se.add_argument("--out", metavar="DIR",
                    help="Optional folder for report.md and result.json. The report is always printed.")
    se.set_defaults(func=cmd_seal)

    v = sub.add_parser("verify", help="check prereg.toml still matches its lock (exit 1 if not)",
                       description="Recompute the hash of the pre-registration and compare it with "
                                   "<name>.lock. Exit 0 on a match; exit 1 on a mismatch or a missing lock.")
    v.add_argument("file", metavar="FILE", help="The sealed pre-registration, e.g. prereg.toml.")
    v.add_argument("--out", metavar="DIR",
                   help="Optional folder for report.md and result.json. The report is always printed.")
    v.set_defaults(func=cmd_verify)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    run_main(main)
