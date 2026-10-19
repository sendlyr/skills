#!/usr/bin/env python3
"""Score candidate leading indicators in event data.

For every event that enough accounts do, and every (window, threshold) pair, this
script asks one yes/no question per account: "did it do this event at least T times
in its first W days?" It compares the outcome rate of accounts that did (hits) with
accounts that did not (misses) on an early discovery cohort, ranks the candidates by
lift x coverage, and re-checks the best ones on a later holdout cohort.

Guards built in:
- Only mature accounts count: the full outcome window must be observed.
- The outcome window and the behavior window share the anchor, so an account whose
  outcome happened inside the behavior window is dropped from that window's
  candidates (otherwise post-outcome behaviour leaks into the signal).
- Windows longer than the decision window are refused: you cannot act on them.
- Ranking uses the discovery cohort only; the holdout cohort checks replication.

Results are predictive, not causal. Test any signal with a holdout experiment
(designing-holdout-experiments skill) before building on it.

Part of the finding-leading-indicators skill. Inputs and outputs follow
docs/data-contracts.md. Python 3.11+ standard library only.
"""

import argparse
import bisect
from collections import Counter, defaultdict

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
DAY_SECONDS = 86400.0
READY_MIN_POPULATION = 30      # readiness floor, also never below --min-users
MIN_CELL = 5                   # hits, misses, positives and negatives each need this many
TOO_BROAD = 0.95               # coverage at or above this cannot separate anyone
TOO_RARE = 0.05                # coverage below this reaches too few accounts
NVS_EVENTS = 3                 # nothing-vs-something covers this many top events
BUCKETS = (("0", 0, 0), ("1", 1, 1), ("2", 2, 2), ("3-4", 3, 4), ("5+", 5, None))
FLAG_ORDER = ("too_broad", "too_rare", "not_actionable_actor", "low_sample",
              "negative_lift", "did_not_replicate")
HOLDOUT_SKILL = "designing-holdout-experiments"


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def _positive_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a whole number of at least 1, got {text!r}")
    return value


def _int_list(text):
    parts = [p.strip() for p in str(text).split(",") if p.strip()]
    if not parts:
        raise argparse.ArgumentTypeError("expected a comma-separated list such as 1,3,7")
    values = []
    for part in parts:
        values.append(_positive_int(part))
    return sorted(set(values))


def _share(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a number between 0 and 1, got {text!r}") from None
    if not 0 < value < 1:
        raise argparse.ArgumentTypeError(f"expected a number strictly between 0 and 1, got {text!r}")
    return value


def build_parser():
    p = argparse.ArgumentParser(
        prog="score_signals.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Find events that predict an outcome (e.g. first payment) early enough to act on.\n"
            "Each candidate is 'did the account do EVENT at least T times in its first W days?'.\n"
            "Candidates are ranked on an early discovery cohort and the best are re-checked on\n"
            "a later holdout cohort. Results are predictive, not causal."
        ),
        epilog=(
            "example:\n"
            "  python3 score_signals.py --accounts accounts.csv --events events.csv \\\n"
            "      --outcome-window-days 14 --decision-window-days 7 --email-actor learner --out out/\n\n"
            "Exit codes: 0 = the analysis ran (refusals and flags are still a successful run);\n"
            "2 = malformed input (the message names the file, row and column)."
        ),
    )
    p.add_argument("--accounts", required=True, metavar="FILE",
                   help="CSV with one row per account. Required columns: account_id and anchor_at "
                        "(when the journey starts, e.g. signup or trial start). Optional: outcome_at "
                        "(when the outcome happened; blank means not observed) and observed_until "
                        "(the last moment this account's data is complete).")
    p.add_argument("--events", required=True, metavar="FILE",
                   help="CSV with one row per event. Required columns: account_id, event_name and "
                        "occurred_at. Optional: actor (who did it, e.g. learner, parent or system).")
    p.add_argument("--outcome-window-days", required=True, type=_positive_int, metavar="N",
                   help="An account counts as converted if outcome_at is within N days after "
                        "anchor_at. Accounts that have not been observed for N days yet are "
                        "immature and left out.")
    p.add_argument("--decision-window-days", required=True, type=_positive_int, metavar="N",
                   help="The day by which you must act (e.g. the trial length). Behavior windows "
                        "longer than this are refused, because a signal that fires after the "
                        "decision cannot be acted on. Must not be longer than the outcome window.")
    p.add_argument("--windows", type=_int_list, default=[1, 3, 7], metavar="LIST",
                   help="Behavior windows to try, in days after anchor_at, comma-separated. "
                        "Default: 1,3,7.")
    p.add_argument("--thresholds", type=_int_list, default=[1, 2, 3, 5], metavar="LIST",
                   help="Minimum event counts to try, comma-separated. A threshold of 2 means "
                        "'did it at least twice inside the window'. Default: 1,2,3,5.")
    p.add_argument("--min-users", type=_positive_int, default=30, metavar="N",
                   help="Only score an event that at least N mature accounts did. Candidates "
                        "whose population is below N are flagged low_sample. Default: 30.")
    p.add_argument("--holdout-share", type=_share, default=0.3, metavar="SHARE",
                   help="Share of mature accounts, the most recent by anchor_at, set aside to "
                        "re-check the top candidates. The earlier rest is the discovery cohort "
                        "used for all ranking. Default: 0.3.")
    p.add_argument("--email-actor", metavar="NAME",
                   help="Who reads your emails, e.g. learner. Events mostly done by someone else "
                        "(according to the actor column) are flagged not_actionable_actor and "
                        "left out of the ranking, because email can only ask the reader to act.")
    p.add_argument("--as-of", metavar="DATE",
                   help="Treat data as complete up to this date or timestamp. Default: the latest "
                        "observed_until, or else the latest timestamp anywhere in the data.")
    p.add_argument("--top", type=_positive_int, default=10, metavar="N",
                   help="How many top-ranked candidates to re-check on the holdout cohort and show "
                        "in the report table. Default: 10.")
    p.add_argument("--out", required=True, metavar="DIR",
                   help="Folder for report.md and result.json (created if missing). The report "
                        "is also printed to the screen.")
    return p


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

class Account:
    __slots__ = ("anchor", "outcome", "observed", "horizon", "mature", "outcome_off",
                 "positive", "events")

    def __init__(self, anchor, outcome, observed):
        self.anchor = anchor
        self.outcome = outcome
        self.observed = observed
        self.horizon = None
        self.mature = False
        self.outcome_off = None if outcome is None else (outcome - anchor).total_seconds()
        self.positive = False
        self.events = defaultdict(list)       # event_name -> sorted offsets (seconds from anchor)


def load_accounts(path):
    rows = read_csv(path, required=("account_id", "anchor_at"))
    if not rows:
        raise InputError(f"{path}: no data rows")
    has_outcome = "outcome_at" in rows[0]
    has_observed = "observed_until" in rows[0]
    accounts = {}
    first_seen = {}
    for row in rows:
        where = row["_where"]
        aid = row.get("account_id") or ""
        if not aid:
            raise InputError(f"{where} (account_id): blank account_id")
        if aid in first_seen:
            raise InputError(f"{where} (account_id): duplicate account_id, first seen at {first_seen[aid]}")
        first_seen[aid] = where
        anchor = parse_time(row.get("anchor_at"), f"{where} (anchor_at)")
        if anchor is None:
            raise InputError(f"{where} (anchor_at): blank; every account needs a start time")
        outcome = parse_time(row.get("outcome_at"), f"{where} (outcome_at)") if has_outcome else None
        observed = parse_time(row.get("observed_until"), f"{where} (observed_until)") if has_observed else None
        accounts[aid] = Account(anchor, outcome, observed)
    meta = {"has_outcome_column": has_outcome, "has_observed_until_column": has_observed}
    return accounts, meta


def load_events(path, accounts):
    rows = read_csv(path, required=("account_id", "event_name", "occurred_at"))
    has_actor = bool(rows) and "actor" in rows[0]
    actor_counts = defaultdict(Counter)       # event -> actor -> rows ("" = blank)
    stats = {"rows": len(rows), "unknown_account": 0, "before_anchor": 0, "blank_actor": 0,
             "has_actor_column": has_actor, "latest": None}
    latest = None
    for row in rows:
        where = row["_where"]
        aid = row.get("account_id") or ""
        if not aid:
            raise InputError(f"{where} (account_id): blank account_id")
        name = row.get("event_name") or ""
        if not name:
            raise InputError(f"{where} (event_name): blank event_name")
        t = parse_time(row.get("occurred_at"), f"{where} (occurred_at)")
        if t is None:
            raise InputError(f"{where} (occurred_at): blank; every event needs a time")
        if latest is None or t > latest:
            latest = t
        acc = accounts.get(aid)
        if acc is None:
            stats["unknown_account"] += 1
            continue
        off = (t - acc.anchor).total_seconds()
        if off < 0:
            stats["before_anchor"] += 1
        acc.events[name].append(off)
        if has_actor:
            actor = row.get("actor") or ""
            if not actor:
                stats["blank_actor"] += 1
            actor_counts[name][actor] += 1
    for acc in accounts.values():
        for offs in acc.events.values():
            offs.sort()
    stats["latest"] = latest
    return actor_counts, stats


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def window_pairs(group, event, window_days):
    """(event count in [anchor, anchor+W), positive) for each account in the group whose
    outcome did not happen inside the behavior window (the leakage guard)."""
    cut = window_days * DAY_SECONDS
    pairs = []
    for acc in group:
        if acc.outcome_off is not None and acc.outcome_off < cut:
            continue
        offs = acc.events.get(event)
        count = (bisect.bisect_left(offs, cut) - bisect.bisect_left(offs, 0.0)) if offs else 0
        pairs.append((count, acc.positive))
    return pairs


def _finite(x):
    return x is not None and x == x and x not in (float("inf"), float("-inf"))


def score_pairs(pairs, threshold):
    n = len(pairs)
    hits = hit_pos = pos = 0
    for count, positive in pairs:
        if positive:
            pos += 1
        if count >= threshold:
            hits += 1
            if positive:
                hit_pos += 1
    misses = n - hits
    miss_pos = pos - hit_pos
    coverage = hits / n if n else None
    hit_rate = hit_pos / hits if hits else None
    miss_rate = miss_pos / misses if misses else None
    lift = lift_ci = relative = rank_score = None
    if hit_rate is not None and miss_rate is not None:
        lift = hit_rate - miss_rate
        _, lo, hi = newcombe_diff(hit_pos, hits, miss_pos, misses)
        lift_ci = [lo, hi] if _finite(lo) and _finite(hi) else None
        relative = lift / miss_rate if miss_rate > 0 else None
        rank_score = lift * coverage
    return {
        "population": n, "hits": hits, "misses": misses, "positives": pos, "negatives": n - pos,
        "hit_positives": hit_pos, "miss_positives": miss_pos,
        "coverage": coverage, "hit_rate": hit_rate, "miss_rate": miss_rate,
        "lift": lift, "lift_ci": lift_ci, "relative_lift": relative, "rank_score": rank_score,
    }


def dominant_actor(counter):
    """Most common non-blank actor and its share of all rows; ties go to the name first
    in alphabetical order. (None, None) when no actor is known."""
    named = [(a, n) for a, n in counter.items() if a]
    if not named:
        return None, None
    named.sort(key=lambda x: (-x[1], x[0]))
    total = sum(counter.values())
    return named[0][0], named[0][1] / total


def readiness_of(c, min_users):
    floor = max(READY_MIN_POPULATION, min_users)
    enough = (c["population"] >= floor and c["hits"] >= MIN_CELL and c["misses"] >= MIN_CELL
              and c["positives"] >= MIN_CELL and c["negatives"] >= MIN_CELL)
    replicated_ok = c["holdout"] is None or c["holdout"]["replicated"]
    if enough and c["lift_ci"] is not None and c["lift_ci"][0] > 0 and replicated_ok:
        return "ready"
    if c["hits"] > 0 and c["misses"] > 0:
        return "directional"
    return "not_ready"


def base_flags(c, min_users, email_actor):
    flags = set()
    cov = c["coverage"]
    if cov is not None and cov >= TOO_BROAD:
        flags.add("too_broad")
    if cov is not None and cov < TOO_RARE:
        flags.add("too_rare")
    if (c["population"] < min_users or c["hits"] < MIN_CELL or c["misses"] < MIN_CELL
            or c["positives"] < MIN_CELL or c["negatives"] < MIN_CELL):
        flags.add("low_sample")
    if c["lift"] is not None and c["lift"] < 0:
        flags.add("negative_lift")
    if email_actor and c["actor"] and c["actor"].casefold() != email_actor.casefold():
        flags.add("not_actionable_actor")
    return flags


def ordered(flags):
    return [f for f in FLAG_ORDER if f in flags]


def rank_key(c):
    # rank_score desc, coverage desc, population desc, then the key ascending
    # (event name, then threshold and window compared as numbers).
    return (-c["rank_score"], -c["coverage"], -c["population"], c["event"], c["threshold"], c["window_days"])


def rankable(c):
    """In `ranked`: actionable, not too broad or too rare, and with both hits and misses."""
    return (c["rank_score"] is not None
            and not ({"not_actionable_actor", "too_broad", "too_rare"} & set(c["flags"])))


def qualifies(c):
    return (c["readiness"] == "ready" and c["holdout"] is not None and c["holdout"]["replicated"]
            and "too_broad" not in c["flags"] and "too_rare" not in c["flags"])


def nothing_vs_something(group, cand, min_users):
    pairs = window_pairs(group, cand["event"], cand["window_days"])
    buckets = []
    for label, lo, hi in BUCKETS:
        sel = [p for c, p in pairs if c >= lo and (hi is None or c <= hi)]
        n = len(sel)
        k = sum(1 for p in sel if p)
        buckets.append({"bucket": label, "n": n, "positives": k, "rate": (k / n) if n else None,
                        "small": n < min_users})
    b0, b1 = buckets[0], buckets[1]
    upper = [b for b in buckets[1:] if not b["small"] and b["rate"] is not None]
    share = None
    best = None
    if b0["small"] or b1["small"] or b0["rate"] is None or b1["rate"] is None:
        text = (f"Too few accounts did `{cand['event']}` exactly 0 or exactly 1 time to read this "
                f"(fewer than {min_users} in a bucket).")
    else:
        best = max(upper, key=lambda b: b["rate"])
        gap = best["rate"] - b0["rate"]
        if gap <= 0:
            text = (f"Accounts that did `{cand['event']}` did not convert more than accounts that "
                    f"did not. There is no separation to explain.")
        else:
            share = (b1["rate"] - b0["rate"]) / gap
            text = (f"{pct(share, 0)} of the gap between 0 times and the best bucket "
                    f"({bucket_times(best['bucket'])}) is already there at 1 time.")
            if share >= 0.75:
                text += " Nothing vs something matters more than a little vs a lot. Ask for the first time."
            elif share >= 0.4:
                text += " The first time does most of the work, but more still adds some."
            else:
                text += " The count matters: doing it more keeps adding."
    return {
        "event": cand["event"], "candidate": cand["key"], "window_days": cand["window_days"],
        "buckets": buckets,
        "reading": {"share_of_separation_at_1": share,
                    "best_bucket": best["bucket"] if best else None, "text": text},
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def md(text):
    return str(text).replace("|", "\\|").replace("`", "'")


def days_word(n):
    return f"{n} day" if n == 1 else f"{n} days"


def days_adj(n):
    return f"{n}-day"


def bucket_times(label):
    label = label.replace("3-4", "3–4")
    return f"{label} time" if label == "1" else f"{label} times"


def times_word(t):
    return "at least once" if t == 1 else f"at least {t} times"


def describe(c):
    return f"`{md(c['event'])}` {times_word(c['threshold'])} in the first {days_word(c['window_days'])}"


def ci_text(ci):
    if not ci:
        return "—"
    return f"{pp(ci[0])} to {pp(ci[1])}"


def lift_cell(c):
    if c.get("lift") is None:
        return "—"
    ci = c.get("lift_ci")
    return f"{pp(c['lift'])} [{pp(ci[0])}, {pp(ci[1])}]" if ci else pp(c["lift"])


def num(n):
    return f"{n:,}"


def plural(n, one, many=None):
    return f"{num(n)} {one if n == 1 else (many or one + 's')}"


def verb(n, one, many):
    return one if n == 1 else many


def date_of(dt):
    return dt.date().isoformat() if dt is not None else "—"


def round_floats(obj, digits=6):
    if isinstance(obj, float):
        return round(obj, digits) if _finite(obj) else None
    if isinstance(obj, dict):
        return {k: round_floats(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v, digits) for v in obj]
    return obj


def keys_by_event(cands):
    groups = defaultdict(list)
    for c in cands:
        groups[c["event"]].append(c)
    parts = []
    for event in sorted(groups):
        items = sorted(groups[event], key=lambda c: (c["window_days"], c["threshold"]))
        parts.append(f"`{md(event)}` (" + ", ".join(f">={c['threshold']}/{c['window_days']}d" for c in items) + ")")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyse(args):
    ow, dw = args.outcome_window_days, args.decision_window_days
    accounts, acc_meta = load_accounts(args.accounts)
    actor_counts, ev_stats = load_events(args.events, accounts)

    # as_of: --as-of, else the latest observed_until, else the latest timestamp in the data.
    if args.as_of:
        as_of = parse_time(args.as_of, "--as-of")
        as_of_source = "--as-of"
    else:
        observed = [a.observed for a in accounts.values() if a.observed is not None]
        if observed:
            as_of = max(observed)
            as_of_source = "latest observed_until"
        else:
            stamps = [a.anchor for a in accounts.values()]
            stamps += [a.outcome for a in accounts.values() if a.outcome is not None]
            if ev_stats["latest"] is not None:
                stamps.append(ev_stats["latest"])
            as_of = max(stamps)
            as_of_source = "latest timestamp in the data"

    ow_seconds = ow * DAY_SECONDS
    counts = Counter()
    for acc in accounts.values():
        horizon = acc.observed if acc.observed is not None else as_of
        acc.horizon = min(horizon, as_of)
        if acc.observed is None:
            counts["observed_until_blank"] += 1
        acc.mature = (acc.horizon - acc.anchor).total_seconds() >= ow_seconds
        if not acc.mature:
            if acc.anchor > as_of:
                counts["immature_started_after_as_of"] += 1
            continue
        if acc.outcome_off is None:
            counts["outcome_blank"] += 1
        elif acc.outcome_off <= 0:
            counts["outcome_at_or_before_anchor"] += 1
        elif acc.outcome_off > ow_seconds:
            counts["outcome_after_window"] += 1
        else:
            acc.positive = True
            counts["positives"] += 1

    mature = sorted(((a.anchor, aid, a) for aid, a in accounts.items() if a.mature), key=lambda x: (x[0], x[1]))
    n_mature = len(mature)
    n_disc = int(round(n_mature * (1 - args.holdout_share)))
    n_disc = max(0, min(n_mature, n_disc))
    discovery = [a for _, _, a in mature[:n_disc]]
    holdout = [a for _, _, a in mature[n_disc:]]
    mature_accs = [a for _, _, a in mature]

    scored_windows = [w for w in args.windows if w <= dw]
    refused_windows = [w for w in args.windows if w > dw]

    # Leakage guard counts, per scored window.
    def leaked(group, w):
        cut = w * DAY_SECONDS
        return sum(1 for a in group if a.outcome_off is not None and a.outcome_off < cut)

    excluded = {str(w): leaked(mature_accs, w) for w in scored_windows}
    excluded_split = {"discovery": {str(w): leaked(discovery, w) for w in scored_windows},
                      "holdout": {str(w): leaked(holdout, w) for w in scored_windows}}

    # Event eligibility: distinct mature accounts with the event at any time up to their horizon.
    event_accounts = Counter()
    for acc in mature_accs:
        limit = (acc.horizon - acc.anchor).total_seconds()
        for name, offs in acc.events.items():
            if offs and offs[0] <= limit:
                event_accounts[name] += 1
    all_events = sorted(set(actor_counts) | {n for a in accounts.values() for n in a.events})
    events_summary = {}
    eligible = []
    for name in all_events:
        actor, share = dominant_actor(actor_counts.get(name, Counter()))
        n_acc = event_accounts.get(name, 0)
        ok = n_acc >= args.min_users
        events_summary[name] = {
            "mature_accounts": n_acc, "actor": actor, "actor_share": share,
            "blank_actor_rows": actor_counts.get(name, Counter()).get("", 0),
            "scored": ok and bool(scored_windows),
        }
        if ok:
            eligible.append(name)

    # Score every candidate on the discovery cohort.
    candidates = []
    for event in eligible:
        actor = events_summary[event]["actor"]
        for w in scored_windows:
            pairs = window_pairs(discovery, event, w)
            for t in args.thresholds:
                c = {"key": f"{event}@>={t}/{w}d", "event": event, "threshold": t, "window_days": w,
                     "actor": actor, "actor_share": events_summary[event]["actor_share"]}
                c.update(score_pairs(pairs, t))
                c["flags"] = base_flags(c, args.min_users, args.email_actor)
                c["holdout"] = None
                c["rank"] = None
                candidates.append(c)

    pool = [c for c in candidates if rankable(c)]
    pool.sort(key=rank_key)
    for i, c in enumerate(pool, start=1):
        c["rank"] = i
    for c in pool[:args.top]:
        h = score_pairs(window_pairs(holdout, c["event"], c["window_days"]), c["threshold"])
        replicated = h["lift_ci"] is not None and h["lift_ci"][0] > 0
        c["holdout"] = {"population": h["population"], "hits": h["hits"], "coverage": h["coverage"],
                        "hit_rate": h["hit_rate"], "miss_rate": h["miss_rate"], "lift": h["lift"],
                        "lift_ci": h["lift_ci"], "replicated": replicated}
        if not replicated:
            c["flags"].add("did_not_replicate")
    for c in candidates:
        c["readiness"] = readiness_of(c, args.min_users)
        c["flags"] = ordered(c["flags"])

    primary = next((c for c in pool if qualifies(c)), None)
    supporting = None
    if primary is not None:
        supporting = next((c for c in pool if qualifies(c) and c["event"] != primary["event"]), None)

    # Nothing vs something for the top distinct events.
    nvs_cands, seen = [], set()
    for c in pool:
        if c["event"] not in seen:
            seen.add(c["event"])
            nvs_cands.append(c)
        if len(nvs_cands) == NVS_EVENTS:
            break
    nvs = [nothing_vs_something(discovery, c, args.min_users) for c in nvs_cands]

    refused = []
    for w in refused_windows:
        refused.append({
            "kind": "window", "window_days": w, "reason": "window_beyond_decision",
            "candidates_not_scored": len(eligible) * len(args.thresholds),
            "message": (f"The {days_adj(w)} window ends after the decision on day {dw}. "
                        f"A signal that fires after the decision cannot be acted on."),
        })
    for name in all_events:
        if name not in eligible:
            refused.append({
                "kind": "event", "event": name, "reason": "low_sample",
                "mature_accounts": events_summary[name]["mature_accounts"],
                "message": (f"Only {events_summary[name]['mature_accounts']} mature accounts did "
                            f"this event; the minimum is {args.min_users}."),
            })

    ctx = {
        "args": args, "ow": ow, "dw": dw, "as_of": as_of, "as_of_source": as_of_source,
        "accounts": accounts, "acc_meta": acc_meta, "ev_stats": ev_stats, "counts": counts,
        "n_mature": n_mature, "discovery": discovery, "holdout": holdout,
        "scored_windows": scored_windows, "refused_windows": refused_windows,
        "excluded": excluded, "events_summary": events_summary, "eligible": eligible,
        "candidates": candidates, "pool": pool, "primary": primary, "supporting": supporting,
        "nvs": nvs, "refused": refused,
    }
    caveats = build_caveats(ctx)
    ctx["caveats"] = caveats
    result = build_result(ctx)
    report = build_report(ctx)
    return result, report


def split_info(group):
    if not group:
        return {"accounts": 0, "anchor_from": None, "anchor_to": None}
    return {"accounts": len(group), "anchor_from": date_of(group[0].anchor), "anchor_to": date_of(group[-1].anchor)}


def build_caveats(ctx):
    args, ow, dw = ctx["args"], ctx["ow"], ctx["dw"]
    counts, cands, pool = ctx["counts"], ctx["candidates"], ctx["pool"]
    out = []
    out.append(f"Predictive, not causal. These events mark accounts that tend to convert; they may not "
               f"cause conversion. Motivated users do more of everything. Test the primary signal with a "
               f"holdout experiment ({HOLDOUT_SKILL} skill) before you build on it.")
    if cands:
        checked = min(args.top, len(pool))
        if checked:
            check_text = (f"Only the top {checked} ranked {verb(checked, 'was', 'were')} re-checked on the "
                          f"holdout cohort; treat the rest as unchecked.")
        else:
            check_text = "No candidate was ranked, so none was re-checked on the holdout cohort."
        out.append(f"We scored {plural(len(cands), 'candidate')} ({plural(len(ctx['eligible']), 'event')} x "
                   f"{plural(len(ctx['scored_windows']), 'window')} x {plural(len(args.thresholds), 'threshold')}). "
                   f"With this many tries, some will look good by chance. {check_text}")
    else:
        out.append("No candidate could be scored. Check the windows, --min-users and the event names.")
    immature = len(ctx["accounts"]) - ctx["n_mature"]
    out.append(f"{plural(immature, 'account')} {verb(immature, 'was', 'were')} too new for a full "
               f"{days_adj(ow)} outcome window by {date_of(ctx['as_of'])}. Immature accounts are left out.")
    leak = ", ".join(f"{w}d: {num(n)}" for w, n in ctx["excluded"].items())
    if any(ctx["excluded"].values()):
        out.append(f"Accounts whose outcome happened inside the behavior window were dropped from that "
                   f"window's candidates, so post-outcome behavior cannot leak in ({leak}).")
    elif ctx["excluded"]:
        out.append(f"No mature account had its outcome inside a behavior window ({leak}), so the leakage "
                   f"guard dropped no one.")
    if counts["outcome_blank"]:
        n = counts["outcome_blank"]
        out.append(f"{plural(n, 'mature account')} {verb(n, 'has', 'have')} a blank outcome_at. Blank means "
                   f"not observed; after a full {days_adj(ow)} window it counts as not converted.")
    if counts["outcome_after_window"]:
        out.append(f"{plural(counts['outcome_after_window'], 'mature account')} had the outcome after the "
                   f"{days_adj(ow)} window. That counts as not converted in this analysis.")
    if counts["outcome_at_or_before_anchor"]:
        n = counts["outcome_at_or_before_anchor"]
        out.append(f"{plural(n, 'mature account')} {verb(n, 'has', 'have')} outcome_at at or before anchor_at. "
                   f"That counts as not converted, and the leakage guard drops them from every window. "
                   f"Check the data.")
    not_act = [c for c in cands if "not_actionable_actor" in c["flags"]]
    if not_act:
        evs = sorted({(c["event"], c["actor"]) for c in not_act})
        names = ", ".join(f"{e} (done by {a})" for e, a in evs)
        out.append(f"Not actionable by email: {names}. Email can only ask the {args.email_actor} to act, "
                   f"so these were left out of the ranking.")
    broad = [c for c in cands if "too_broad" in c["flags"]]
    if broad:
        evs = ", ".join(sorted({c["event"] for c in broad}))
        out.append(f"{plural(len(broad), 'candidate')} {verb(len(broad), 'is', 'are')} too broad: at least 95% "
                   f"of accounts did it ({evs}). That cannot separate anyone. Too-broad candidates are left "
                   f"out of the ranking and never recommended.")
    rare = [c for c in cands if "too_rare" in c["flags"]]
    if rare:
        out.append(f"{plural(len(rare), 'candidate')} {verb(len(rare), 'is', 'are')} too rare: under 5% of "
                   f"accounts did it. That reaches too few accounts. Too-rare candidates are left out of the "
                   f"ranking and never recommended.")
    norep = [c for c in pool if "did_not_replicate" in c["flags"]]
    if norep:
        out.append(f"{len(norep)} of the top {plural(min(args.top, len(pool)), 'candidate')} did not hold up "
                   f"in the later holdout cohort: {', '.join(c['key'] for c in norep)}.")
    if ctx["refused_windows"]:
        out.append(f"Refused windows beyond the day-{dw} decision: "
                   f"{', '.join(days_word(w) for w in ctx['refused_windows'])}. Not scored.")
    if not ctx["ev_stats"]["has_actor_column"]:
        out.append("events.csv has no actor column, so we could not check who performs each event.")
    elif not args.email_actor:
        out.append("No --email-actor was given, so events done by someone other than the email reader "
                   "were not filtered out.")
    unknown_actor = sorted(e for e, s in ctx["events_summary"].items() if s["actor"] is None)
    if ctx["ev_stats"]["has_actor_column"] and unknown_actor:
        out.append(f"The actor is blank for every row of: {', '.join(unknown_actor)}. We could not check "
                   f"who does these.")
    if ctx["ev_stats"]["unknown_account"]:
        n = ctx["ev_stats"]["unknown_account"]
        out.append(f"{plural(n, 'event row')} {verb(n, 'is', 'are')} for accounts that are not in "
                   f"accounts.csv. Those rows were ignored.")
    if ctx["primary"] is None:
        out.append("No candidate met the bar for a recommendation (ready, replicated on the holdout, "
                   "not too broad and not too rare).")
    return out


def public_candidate(c):
    keys = ("key", "event", "threshold", "window_days", "actor", "actor_share", "population", "hits",
            "misses", "positives", "negatives", "hit_positives", "miss_positives", "coverage", "hit_rate",
            "miss_rate", "lift", "lift_ci", "relative_lift", "rank_score", "rank", "readiness", "flags",
            "holdout")
    return {k: c[k] for k in keys}


def rec_entry(c):
    if c is None:
        return None
    h = c["holdout"] or {}
    return {"key": c["key"], "event": c["event"], "threshold": c["threshold"], "window_days": c["window_days"],
            "actor": c["actor"], "coverage": c["coverage"], "hit_rate": c["hit_rate"],
            "miss_rate": c["miss_rate"], "lift": c["lift"], "lift_ci": c["lift_ci"],
            "holdout_lift": h.get("lift"), "holdout_lift_ci": h.get("lift_ci")}


def build_result(ctx):
    args, counts, ev = ctx["args"], ctx["counts"], ctx["ev_stats"]
    n_accounts = len(ctx["accounts"])
    candidates = sorted(ctx["candidates"], key=lambda c: (c["event"], c["window_days"], c["threshold"]))
    result = {
        "schema_version": SCHEMA_VERSION,
        "script": "score_signals.py",
        "params": {
            "outcome_window_days": ctx["ow"], "decision_window_days": ctx["dw"],
            "windows": args.windows, "thresholds": args.thresholds, "min_users": args.min_users,
            "holdout_share": args.holdout_share, "email_actor": args.email_actor, "top": args.top,
            "as_of": ctx["as_of"].isoformat(), "as_of_source": ctx["as_of_source"],
        },
        "inputs": {
            "accounts": n_accounts,
            "mature": ctx["n_mature"],
            "immature": n_accounts - ctx["n_mature"],
            "immature_started_after_as_of": counts["immature_started_after_as_of"],
            "excluded_outcome_in_window": ctx["excluded"],
            "discovery": len(ctx["discovery"]),
            "holdout": len(ctx["holdout"]),
            "positives": counts["positives"],
            "outcome_blank": counts["outcome_blank"],
            "outcome_after_window": counts["outcome_after_window"],
            "outcome_at_or_before_anchor": counts["outcome_at_or_before_anchor"],
            "observed_until_blank": counts["observed_until_blank"],
            "has_outcome_column": ctx["acc_meta"]["has_outcome_column"],
            "event_rows": ev["rows"],
            "event_rows_unknown_account": ev["unknown_account"],
            "event_rows_before_anchor": ev["before_anchor"],
            "event_rows_blank_actor": ev["blank_actor"],
            "has_actor_column": ev["has_actor_column"],
        },
        "split": {"discovery": split_info(ctx["discovery"]), "holdout": split_info(ctx["holdout"])},
        "events": ctx["events_summary"],
        "candidates": [public_candidate(c) for c in candidates],
        "ranked": [c["key"] for c in ctx["pool"]],
        "recommendation": {
            "primary": rec_entry(ctx["primary"]),
            "supporting": rec_entry(ctx["supporting"]),
            "caveats": ctx["caveats"],
        },
        "nothing_vs_something": ctx["nvs"],
        "refused": ctx["refused"],
    }
    return round_floats(result)


def signal_paragraph(label, c, ow):
    lines = [f"- **{label}:** {describe(c)} (`{md(c['key'])}`)."]
    text = (f"  Accounts that did it converted at {pct(c['hit_rate'])} within {days_word(ow)}. "
            f"Accounts that did not converted at {pct(c['miss_rate'])}. "
            f"The gap is {pp(c['lift'])} (95% CI {ci_text(c['lift_ci'])}). "
            f"{pct(c['coverage'])} of accounts did it.")
    h = c["holdout"]
    if h:
        text += (f" In the later holdout cohort the gap was {pp(h['lift'])} "
                 f"(95% CI {ci_text(h['lift_ci'])}), so it replicated.")
    lines.append(text)
    return lines


def build_report(ctx):
    args, ow, dw, counts = ctx["args"], ctx["ow"], ctx["dw"], ctx["counts"]
    pool, cands = ctx["pool"], ctx["candidates"]
    n_accounts = len(ctx["accounts"])
    L = ["# Leading indicator scan", ""]
    L.append(f"Outcome: converted within {days_word(ow)} of the start. Decision point: day {dw}. "
             f"Data as of {date_of(ctx['as_of'])} ({ctx['as_of_source']}).")
    L.append("")

    # Summary
    L += ["## Summary", ""]
    if ctx["primary"]:
        L += signal_paragraph("Primary signal", ctx["primary"], ow)
        if ctx["supporting"]:
            L += signal_paragraph("Supporting signal", ctx["supporting"], ow)
        else:
            L.append("- **Supporting signal:** none. No second event met the same bar.")
    else:
        L.append("- **Primary signal:** none. No candidate was ready, replicated on the holdout, and "
                 "neither too broad nor too rare. See the table and flags below.")
    L.append(f"- **Predictive, not causal.** These events mark accounts that convert. They may not cause it. "
             f"Test the signal with a holdout ({HOLDOUT_SKILL} skill) before you build on it.")
    L.append("")

    # Data
    disc, hold = split_info(ctx["discovery"]), split_info(ctx["holdout"])
    L += ["## Data", ""]
    L.append(f"- Accounts: {num(n_accounts)}.")
    L.append(f"- Mature (full {days_adj(ow)} outcome window observed): {num(ctx['n_mature'])}.")
    imm_extra = ""
    if counts["immature_started_after_as_of"]:
        imm_extra = f" ({num(counts['immature_started_after_as_of'])} started after the as-of date)"
    L.append(f"- Immature (too new, left out): {num(n_accounts - ctx['n_mature'])}{imm_extra}.")
    L.append(f"- As of: {date_of(ctx['as_of'])} ({ctx['as_of_source']}).")
    L.append(f"- Converted within the window (mature accounts): {num(counts['positives'])}.")
    L.append(f"- Blank outcome_at among mature accounts (not observed, counted as not converted): "
             f"{num(counts['outcome_blank'])}.")
    if counts["outcome_after_window"] or counts["outcome_at_or_before_anchor"]:
        L.append(f"- Outcome outside the window, counted as not converted: "
                 f"{num(counts['outcome_after_window'])} after the window, "
                 f"{num(counts['outcome_at_or_before_anchor'])} at or before the start.")
    if ctx["excluded"]:
        leak = ", ".join(f"{w}-day window: {num(n)}" for w, n in ctx["excluded"].items())
        L.append(f"- Outcome inside the behavior window (dropped from that window to prevent leakage): {leak}.")
    if counts["observed_until_blank"]:
        L.append(f"- Blank observed_until (the as-of date was used): {num(counts['observed_until_blank'])}.")
    L.append(f"- Discovery cohort (used for ranking): {plural(disc['accounts'], 'account')}, started "
             f"{disc['anchor_from'] or '—'} to {disc['anchor_to'] or '—'}.")
    L.append(f"- Holdout cohort (later, used to re-check the top {args.top}): {plural(hold['accounts'], 'account')}, "
             f"started {hold['anchor_from'] or '—'} to {hold['anchor_to'] or '—'}.")
    ev = ctx["ev_stats"]
    ev_line = f"- Event rows: {num(ev['rows'])}"
    extras = []
    if ev["unknown_account"]:
        extras.append(f"{num(ev['unknown_account'])} for accounts not in accounts.csv (ignored)")
    if ev["before_anchor"]:
        extras.append(f"{num(ev['before_anchor'])} before the account's start (not counted)")
    if ev["has_actor_column"] and ev["blank_actor"]:
        extras.append(f"{num(ev['blank_actor'])} with a blank actor")
    L.append(ev_line + (f"; {'; '.join(extras)}." if extras else "."))
    L.append(f"- Events scored: {len(ctx['eligible'])} of {len(ctx['events_summary'])} "
             f"(each needs at least {plural(args.min_users, 'mature account')}).")
    L.append("")

    # Top candidates
    L += ["## Top candidates", ""]
    if pool:
        L.append("Discovery cohort, ranked by lift × coverage. Not shown: candidates done by someone other "
                 "than the email reader, and candidates that are too broad or too rare (see below). "
                 "Replicated means the lift's 95% CI stayed above zero in the later holdout cohort. "
                 "Lift × coverage is shown in points: lift in percentage points times the share of "
                 "accounts that did it (e.g. +40pp lift at 50% coverage = 20.0). Predictive, not causal.")
        L.append("")
        L.append("| # | Candidate | Actor | Coverage | Converts if hit | If miss | Lift [95% CI] | "
                 "Lift × coverage | Replicated | Readiness | Flags |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for c in pool[:args.top]:
            h = c["holdout"]
            rep = "—" if h is None else ("yes" if h["replicated"] else "no")
            L.append(f"| {c['rank']} | `{md(c['key'])}` | {md(c['actor'] or '—')} | {pct(c['coverage'])} | "
                     f"{pct(c['hit_rate'])} | {pct(c['miss_rate'])} | {lift_cell(c)} | "
                     f"{100 * c['rank_score']:.1f} | {rep} | {c['readiness']} | {', '.join(c['flags']) or '—'} |")
        if len(pool) > args.top:
            L.append("")
            extra = len(pool) - args.top
            L.append(f"result.json has {plural(extra, 'more ranked candidate')}. "
                     f"{verb(extra, 'It was', 'They were')} not re-checked on the holdout.")
    else:
        L.append("No candidate could be ranked. Every candidate was not actionable, too broad, too rare, "
                 "or had no hits or no misses to compare.")
    L.append("")

    # Nothing vs something
    L += ["## Nothing vs something", ""]
    if ctx["nvs"]:
        L.append("Outcome rate by how many times the event happened inside the window (discovery cohort). "
                 "It shows whether the first time matters more than doing it a lot.")
        for item in ctx["nvs"]:
            L += ["", f"### `{md(item['event'])}` in the first {days_word(item['window_days'])}", ""]
            L.append("| Times | Accounts | Converted | Rate |")
            L.append("|---|---|---|---|")
            for b in item["buckets"]:
                label = b["bucket"].replace("3-4", "3–4")
                note = " (small)" if b["small"] and b["n"] else ""
                L.append(f"| {label} | {num(b['n'])} | {num(b['positives'])} | {pct(b['rate'])}{note} |")
            L += ["", item["reading"]["text"]]
    else:
        L.append("Nothing to show: no ranked candidates.")
    L.append("")

    # Refused and flagged
    L += ["## Refused and flagged", ""]
    lines = []
    broad = [c for c in cands if "too_broad" in c["flags"]]
    if broad:
        lines.append(f"- **Too broad** (at least 95% of accounts did it, so it cannot separate anyone; never "
                     f"recommended): {keys_by_event(broad)}.")
    rare = [c for c in cands if "too_rare" in c["flags"]]
    if rare:
        lines.append(f"- **Too rare** (under 5% of accounts did it; never recommended): {keys_by_event(rare)}.")
    not_act = [c for c in cands if "not_actionable_actor" in c["flags"]]
    if not_act:
        evs = sorted({(c["event"], c["actor"]) for c in not_act})
        names = ", ".join(f"`{md(e)}` (done by {md(a)})" for e, a in evs)
        lines.append(f"- **Not actionable** (email can only ask the {md(args.email_actor)} to act; left out of "
                     f"the ranking): {names}. {plural(len(not_act), 'candidate')}.")
    for r in ctx["refused"]:
        if r["kind"] == "window":
            lines.append(f"- **Beyond the decision window** (refused, not scored): {days_word(r['window_days'])}. "
                         f"{r['message']}")
    few = [r for r in ctx["refused"] if r["kind"] == "event"]
    if few:
        lines.append(f"- **Too few accounts** (fewer than {args.min_users} mature accounts; not scored): "
                     + ", ".join(f"`{md(r['event'])}` ({num(r['mature_accounts'])})" for r in few) + ".")
    neg = [c for c in cands if "negative_lift" in c["flags"]]
    if neg:
        lines.append(f"- **Negative lift** (accounts that did it converted less): {keys_by_event(neg)}.")
    norep = [c for c in pool if "did_not_replicate" in c["flags"]]
    if norep:
        lines.append(f"- **Did not replicate** on the holdout: "
                     + ", ".join(f"`{md(c['key'])}`" for c in norep) + ".")
    low = [c for c in cands if "low_sample" in c["flags"]]
    if low:
        lines.append(f"- **Low sample** (population under {args.min_users}, or fewer than {MIN_CELL} hits, "
                     f"misses, conversions or non-conversions): {plural(len(low), 'candidate')}. See result.json.")
    unrankable = [c for c in cands if c["rank_score"] is None
                  and not ({"not_actionable_actor", "too_broad", "too_rare"} & set(c["flags"]))]
    if unrankable:
        lines.append(f"- **Not rankable** (no hits or no misses to compare): {keys_by_event(unrankable)}.")
    L += lines if lines else ["Nothing was refused or flagged."]
    L.append("")

    # Caveats
    L += ["## Caveats", ""]
    L += [f"- {c}" for c in ctx["caveats"]]
    return "\n".join(L)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.decision_window_days > args.outcome_window_days:
        parser.error("--decision-window-days must not be longer than --outcome-window-days: "
                     "the decision has to come before the outcome is known")
    result, report = analyse(args)
    write_outputs(args.out, report, result)
    return 0


if __name__ == "__main__":
    run_main(main)
