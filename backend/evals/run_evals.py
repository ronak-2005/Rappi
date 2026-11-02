"""Evaluation runner.

  python -m evals.run_evals --llm-envs llm.env evals/llm/other.env --repeats 3 [--scenarios S1,S4] [--fixtures id,id]

For every fixture × brain it runs the whole system in-process (fresh DB each run), grades the run with
evals/graders.py, and writes evals/reports/report.json (shown in the UI) and report.md (for the repo).
The deterministic baseline always runs once as the reference point. LLM runs are repeated because
LLM output varies between runs; we report pass RATES, not a single pass/fail.
"""

import argparse
import json
import logging
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from evals.graders import grade
from evals.harness import run_fixture
from shared.config.llm_settings import LLMSettings, load_llm_settings
from shared.config.settings import BACKEND_DIR
from shared.domain.fixtures import list_fixture_files

REPORTS = BACKEND_DIR / "evals" / "reports"
# Provider problems are not agent mistakes: such runs are reported separately and left out of pass rates.
INFRA_ERRORS = ("RateLimitError", "APIConnectionError", "APITimeoutError", "AuthenticationError",
                "InternalServerError", "ConfigurationError")


def brains(env_files: list[str], include_baseline: bool) -> list[tuple[str, LLMSettings, int]]:
    out = []
    if include_baseline:
        out.append(("baseline", LLMSettings(llm_mode="baseline"), 1))
    for env in env_files:
        s = load_llm_settings(env)
        if s.llm_mode != "live":
            print(f"skip {env}: LLM_MODE={s.llm_mode}")
            continue
        if not (s.llm_base_url and s.llm_model and s.llm_api_key):
            print(f"skip {env}: LLM_BASE_URL / LLM_MODEL / LLM_API_KEY not all set")
            continue
        out.append((s.llm_model, s, -1))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm-envs", nargs="*", default=["llm.env"])
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--scenarios", default="S1,S4,S2,S3")
    ap.add_argument("--fixtures", default="")
    ap.add_argument("--no-baseline", action="store_true")
    ap.add_argument("--pause", type=float, default=0.0, help="seconds to wait between LLM runs (free-tier rate limits)")
    a = ap.parse_args(argv)
    logging.getLogger().setLevel(logging.WARNING)  # service logs are noise here; results print below

    wanted = set(a.fixtures.split(",")) if a.fixtures else None
    fixtures = [f for f in list_fixture_files() if f.scenario in a.scenarios.split(",")
                and (wanted is None or f.id in wanted)]
    plan = brains(a.llm_envs, not a.no_baseline)
    if not plan:
        print("nothing to run")
        return 1

    results = []  # one row per run
    for label, settings, reps in plan:
        n = reps if reps > 0 else a.repeats
        quota_hit = False
        for fx in fixtures:
            for i in range(n):
                if quota_hit:
                    break
                if a.pause and label != "baseline":
                    time.sleep(a.pause)
                t0 = time.time()
                with tempfile.TemporaryDirectory() as tmp:
                    try:
                        rec = run_fixture(fx.id, str(Path(tmp) / "eval.db"), llm_settings=settings)
                        checks = grade(rec)
                        status, err = rec.run["status"], rec.error
                        decision = (rec.run.get("decision") or {}).get("type")
                        stats = {"tool_calls": rec.run["tool_calls"], "revisions": rec.run["revisions"],
                                 "replans": rec.run["replans"]}
                    except Exception as exc:  # a crashed run is a failed run, not a crashed eval
                        checks, status, err, decision, stats = [], "crashed", f"{type(exc).__name__}: {exc}", None, {}
                infra = bool(err) and any(e in err for e in INFRA_ERRORS)
                if infra:
                    status = "infra_error"
                    quota_hit = "per-day" in err or "per day" in err
                ok = bool(checks) and all(c.passed for c in checks)
                results.append({"brain": label, "fixture": fx.id, "scenario": fx.scenario, "repeat": i,
                                "status": status, "decision": decision, "all_pass": ok, "error": err, "infra": infra,
                                "seconds": round(time.time() - t0, 1), **stats,
                                "checks": [c.__dict__ for c in checks]})
                failed = [c.name for c in checks if not c.passed]
                verdict = "INFRA" if infra else ("PASS" if ok else "FAIL")
                print(f"{label:>22} {fx.id:<36} #{i} {verdict} {decision or '-':<11} "
                      f"{status:<11} {('failed: ' + ', '.join(failed)) if failed and not infra else ''}"
                      f"{(' ' + err[:160]) if err else ''}", flush=True)
                if quota_hit:
                    print(f"{label}: provider daily quota reached — skipping its remaining runs", flush=True)

    report = summarize(results, [b[0] for b in plan], a.repeats, fixtures)
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "report.json").write_text(json.dumps(report, indent=2, default=str))
    (REPORTS / "runs.json").write_text(json.dumps(results, indent=2, default=str))
    (REPORTS / "report.md").write_text(to_markdown(report))
    print(f"\nwrote {REPORTS / 'report.md'}")
    return 0


def summarize(results: list[dict], brain_labels: list[str], repeats: int, fixtures) -> dict:
    infra = [r for r in results if r.get("infra")]
    results = [r for r in results if not r.get("infra")]
    by_fb = defaultdict(list)
    for r in results:
        by_fb[(r["fixture"], r["brain"])].append(r)
    fx_rows = []
    for fx in fixtures:
        row = {"id": fx.id, "scenario": fx.scenario, "title": fx.title, "expected": fx.expected.decision, "by_brain": {}}
        for b in brain_labels:
            runs = by_fb.get((fx.id, b), [])
            if not runs:
                continue
            row["by_brain"][b] = {
                "runs": len(runs), "all_checks_pass_rate": sum(r["all_pass"] for r in runs) / len(runs),
                "decisions": [r["decision"] or r["status"] for r in runs],
                "failed_checks": sorted({c["name"] for r in runs for c in r["checks"] if not c["passed"]}),
                "avg_tool_calls": round(sum(r.get("tool_calls", 0) for r in runs) / len(runs), 1),
                "avg_seconds": round(sum(r["seconds"] for r in runs) / len(runs), 1),
            }
        fx_rows.append(row)

    check_rate = defaultdict(lambda: defaultdict(list))
    groups = {}
    for r in results:
        for c in r["checks"]:
            check_rate[c["name"]][r["brain"]].append(c["passed"])
            groups[c["name"]] = c["group"]
    checks = [{"name": n, "group": groups[n],
               "by_brain": {b: sum(v) / len(v) for b, v in per.items()}} for n, per in check_rate.items()]
    checks.sort(key=lambda c: ["decision", "evidence", "constraints", "action", "validation", "recovery"].index(c["group"]))

    overall = {}
    for b in brain_labels:
        runs = [r for r in results if r["brain"] == b]
        skipped = sum(1 for r in infra if r["brain"] == b)
        if runs or skipped:
            overall[b] = {"runs": len(runs), "all_checks_pass_rate": (sum(r["all_pass"] for r in runs) / len(runs)) if runs else None,
                          "crashed": sum(r["status"] == "crashed" for r in runs), "infra_errors": skipped}
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "repeats": repeats,
            "brains": brain_labels, "overall": overall, "fixtures": fx_rows, "checks": checks}


def to_markdown(rep: dict) -> str:
    pct = lambda x: f"{round(100 * x)}%"  # noqa: E731
    b = rep["brains"]
    lines = [f"# Evaluation report", "", f"Generated {rep['generated_at']} · LLM runs repeated {rep['repeats']}× "
             "(baseline is deterministic, run once).", "", "## Overall", "",
             "| Brain | Graded runs | All checks pass | Crashed | Not run / provider errors |", "|---|---|---|---|---|"]
    for name, o in rep["overall"].items():
        rate = pct(o['all_checks_pass_rate']) if o['all_checks_pass_rate'] is not None else "—"
        lines.append(f"| {name} | {o['runs']} | {rate} | {o['crashed']} | {o.get('infra_errors', 0)} |")
    lines += ["", "## Per scenario", "", "| Scenario | Expected | " + " | ".join(b) + " |",
              "|---|---|" + "---|" * len(b)]
    for f in rep["fixtures"]:
        cells = []
        for x in b:
            c = f["by_brain"].get(x)
            if not c:
                cells.append("—")
                continue
            fails = f" ✗ {', '.join(c['failed_checks'])}" if c["failed_checks"] else ""
            cells.append(f"{pct(c['all_checks_pass_rate'])} ({', '.join(c['decisions'])}){fails}")
        lines.append(f"| `{f['id']}` | {' / '.join(f['expected'])} | " + " | ".join(cells) + " |")
    lines += ["", "## Pass rate per check", "", "| Check | Group | " + " | ".join(b) + " |", "|---|---|" + "---|" * len(b)]
    for c in rep["checks"]:
        lines.append(f"| {c['name']} | {c['group']} | " + " | ".join(
            pct(c["by_brain"][x]) if x in c["by_brain"] else "—" for x in b) + " |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
