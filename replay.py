"""Replay every result in this repository from a fresh copy and compare with the saved files.

  python replay.py            # core checks (standard library only)
  python replay.py --all      # also the planner, second solver, baseline and TCGA-CDR checks

Runs in a temporary copy, so regenerated outputs never overwrite the committed evidence.
Optional parts need: pip install -r requirements-verify.txt, and for the TCGA-CDR check
`python cdr/fetch_cdr.py` first. Exits non-zero on any mismatch.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd, cwd):
    r = subprocess.run([sys.executable] + cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode not in (0, 2):
        sys.exit("FAILED: %s\n%s%s" % (" ".join(cmd), r.stdout[-2000:], r.stderr[-2000:]))
    return r


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def ok(msg):
    print("ok   " + msg)


def core(fresh):
    r = run(["-m", "unittest", "discover", "-s", "tests"], fresh)
    assert r.returncode == 0 and "Ran 42 tests" in r.stderr, r.stderr[-1500:]
    ok("42 core tests")
    for p in sorted((fresh / "examples").glob("*.json")):
        r = run(["contracts.py", str(p)], fresh)
        actual, saved = json.loads(r.stdout), load(fresh / "demo" / p.stem / "evaluation.json")
        assert actual == saved, "evaluation differs from saved: " + p.stem
        expect = 0 if actual["status"] == "consistent" and actual["decision"]["state"] != "stale" else 2
        assert r.returncode == expect, p.stem
    ok("9 decision examples replay exactly, including stale-decision detection")


def planner(fresh):
    r = run(["-m", "unittest", "discover", "-s", "innovation", "-p", "test_frontier.py"], fresh)
    assert r.returncode == 0 and "Ran 14 tests" in r.stderr, r.stderr[-1500:]
    ok("14 planner tests")
    original = load(ROOT / "innovation/results.json")
    run(["innovation/experiment.py"], fresh)
    regenerated = load(fresh / "innovation/results.json")

    def semantic(d):
        return {"requests": [(x["request_sha256"], x["baseline"]["status"],
                              [(m["additional_components"], m["minimality_established"])
                               for m in x["frontier"]["minimal_supplements"]], x["frontier"]["status"])
                             for x in d["requests"]],
                "matrix": [{k: v["status"] for k, v in x["questions"].items()} for x in d["producer_release_matrix"]],
                "crosscheck": d["encoding_crosscheck"]}
    assert semantic(regenerated) == semantic(original), "planner results differ"
    ok("7 planning requests, release comparison and 640-case cross-check regenerate identically")
    run(["innovation/verify_solvers.py"], fresh)
    assert load(fresh / "innovation/solver-verification.json") == load(ROOT / "innovation/solver-verification.json")
    ok("second solver (cvc5) agrees on all saved solver inputs")


def baseline(fresh):
    run(["compare_baseline.py"], fresh)
    assert load(fresh / "evidence/baseline-results.json") == load(ROOT / "evidence/baseline-results.json")
    ok("schema baseline, RO-Crate reader and 28 admiral reference comparisons")


def cdr(fresh):
    if not (ROOT / "cdr/raw/TCGA-CDR-SupplementalTableS1.xlsx").exists():
        sys.exit("TCGA-CDR table missing: run python cdr/fetch_cdr.py first")
    shutil.copytree(ROOT / "cdr/raw", fresh / "cdr/raw", dirs_exist_ok=True)
    run(["cdr/run_cdr.py"], fresh)
    assert load(fresh / "cdr/results.json") == load(ROOT / "cdr/results.json"), "TCGA-CDR results differ"
    ok("TCGA-CDR published-endpoint check reproduces exactly")


def main():
    full = "--all" in sys.argv
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "repo"
        shutil.copytree(ROOT, fresh, ignore=shutil.ignore_patterns(".git", "__pycache__", "raw", "work"))
        core(fresh)
        if full:
            planner(fresh)
            baseline(fresh)
            cdr(fresh)
    print("all checks passed" if full else "core checks passed (use --all for the rest)")


if __name__ == "__main__":
    main()
