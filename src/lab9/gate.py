"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    for mid, val in (pr.get("metrics") or {}).items():
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            problems.append(f"metric {mid} is NaN or inf")
    manifest = pr.get("manifest") or {}
    rows = pr.get("rows") or []
    expected = int(manifest.get("items") or 0) * len(manifest.get("seeds") or [])
    if len(rows) != expected:
        problems.append(f"row count {len(rows)} != items × seeds {expected}")
    pairs = [(r.get("item_id"), r.get("seed")) for r in rows]
    if len(pairs) != len(set(pairs)):
        problems.append("duplicated (item_id, seed) rows")
    base_pairs = {(r.get("item_id"), r.get("seed")) for r in base.get("rows") or []}
    if set(pairs) != base_pairs:
        problems.append("(item_id, seed) set differs from the baseline")
    if pr.get("evaluator_failures"):
        problems.append("evaluator_failures is non-empty")
    graded = {m["id"] for m in spec.get("metrics") or [] if m.get("kind") in ("safety", "capability")}
    blank = sorted({m for r in rows for m in graded if m in r and r[m] is None})
    if blank:
        problems.append(f"graded metric is None on a row: {', '.join(blank)}")

    def tags(rep: dict) -> dict[tuple, tuple]:
        return {(r.get("item_id"), r.get("seed")): tuple(sorted(r.get("slices") or []))
                for r in rep.get("rows") or []}

    if tags(pr) != tags(base):
        problems.append("slice tags differ from the baseline")
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        problems += _ratchet(spec, base_spec)
    return problems


def _looser(new: dict, old: dict, label: str) -> list[str]:
    """Ways `new` is an easier bar than `old`."""
    found = []
    for key, looser in (("min", lambda a, b: a < b), ("max", lambda a, b: a > b),
                        ("max_increase", lambda a, b: a > b)):
        if key in old and key not in new:
            found.append(f"{label} dropped {key}")
        elif key in old and key in new and looser(new[key], old[key]):
            found.append(f"{label} {key} {old[key]} -> {new[key]}")
    if old.get("no_significant_drop") and not new.get("no_significant_drop"):
        found.append(f"{label} dropped no_significant_drop")
    return found


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    problems = []
    old_metrics = {m["id"]: m for m in base_spec.get("metrics") or []}
    new_metrics = {m["id"]: m for m in spec.get("metrics") or []}
    for mid, old in old_metrics.items():
        new = new_metrics.get(mid)
        if new is None:
            problems.append(f"metric {mid} disappeared")
            continue
        if old.get("blocking") and not new.get("blocking"):
            problems.append(f"metric {mid} is no longer blocking")
        problems += _looser(new.get("threshold") or {}, old.get("threshold") or {}, f"metric {mid}")
    old_slices = {(s.get("name"), s.get("metric")): s for s in base_spec.get("slices") or []}
    new_slices = {(s.get("name"), s.get("metric")): s for s in spec.get("slices") or []}
    for key, old in old_slices.items():
        new = new_slices.get(key)
        label = f"slice {key[0]}/{key[1]}"
        if new is None:
            problems.append(f"{label} disappeared")
            continue
        if old.get("blocking") and not new.get("blocking"):
            problems.append(f"{label} is no longer blocking")
        problems += _looser(new, old, label)
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        sid = f"slice:{name}/{metric}"
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        if not a:
            lines.append(f"  {sid:<22} {'(empty)':<8} {'':<40} {'':<28} warn")
            continue
        val = round(sum(a.values()) / len(a), 4)
        th = {k: sl[k] for k in ("min", "no_significant_drop") if k in sl}
        verdict, note = "ok", ""
        if "min" in sl and val < sl["min"]:
            verdict = "fail"
        if sl.get("no_significant_drop"):
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [a[k] for k in keys], [b[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        label = "ok" if verdict == "ok" else ("BLOCK" if sl.get("blocking") else "warn")
        lines.append(f"  {sid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
