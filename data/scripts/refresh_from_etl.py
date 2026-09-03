"""
refresh_from_etl.py — pull fresh ETL data into every figure, in one command.

WHY THIS EXISTS
---------------
Nothing watches the ETL. The figures the deck renders are JSON files committed to
this repo, built from a small cached extract in data/raw/etl/. When the ETL
changes — a new PIP or WID release, or a fix to the garden steps — the deck keeps
showing the old numbers until someone re-runs the cache refresh and then every
figure script, in the right order. This does both and reports what moved.

    python data/scripts/refresh_from_etl.py                      # from the public catalog
    python data/scripts/refresh_from_etl.py --staging <branch>   # while an ETL PR is open
    python data/scripts/refresh_from_etl.py --check              # report drift, change nothing

The committed figures currently come from an ETL branch, not the catalog: etl_source.WID_VERSION
is 2026-09-02, which the catalog does not carry until owid/etl#6806 merges. Until then the catalog
modes (including --check) stop with a message naming the missing path; use
`--staging worktree-etl-data-wid-update`.

AFTER RUNNING
-------------
Commit both data/raw/etl/ and data/figures/. The --check mode is the useful one in
CI or before a talk: it rebuilds into a temporary directory and tells you whether
the committed figures are stale, without touching them.

THE ONE THING THIS CANNOT DO FOR YOU
------------------------------------
etl_source.ETL_VERSION pins the dataset version. Data flowing through the SAME
version folder is picked up automatically, but when the ETL mints a new version
folder (which it does whenever a derived step is repointed at newer dependencies)
that constant has to be bumped first, or you will faithfully refresh the old
version — exactly the trap config.PIP_URL set for the old pipeline. Both modes
print the pinned version on the first line; check it against the ETL before
trusting a refresh that reports no drift.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import etl_source as es

SCRIPTS = Path(__file__).resolve().parent
FIGURES = SCRIPTS.parent / "figures"

# In dependency order: the bridging series feed the explainers and the top-of-distribution figures.
FIGURE_SCRIPTS = [
    "21_fig_bridging_from_etl.py",
    "22_fig_reference_year_trends.py",
    "23_fig_explainers_from_etl.py",
    "24_fig_top_of_distribution_from_etl.py",
    "25_fig_scatters_from_etl.py",
    "26_fig_reference_year_observed.py",
    "27_fig_between_share_trend.py",
    "28_fig_means_from_etl.py",
]


def run(script: str, *args: str) -> None:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    print(f"\n$ {' '.join(cmd[1:])}")
    subprocess.run(cmd, check=True, cwd=SCRIPTS.parent.parent)


def figure_values(path: Path) -> dict:
    """Every number in a figure JSON, flattened, so two builds can be compared."""
    out = {}

    def walk(node, trail):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{trail}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{trail}[{i}]")
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            out[trail] = float(node)

    walk(json.loads(path.read_text()), "")
    return out


def compare(before: Path, after: Path) -> bool:
    """Report per-figure drift. True when something moved."""
    moved = False
    for f in sorted(after.glob("*.json")):
        old = before / f.name
        if not old.exists():
            print(f"  NEW      {f.name}")
            moved = True
            continue
        a, b = figure_values(old), figure_values(f)
        keys = set(a) | set(b)
        diffs = [
            (k, a.get(k), b.get(k)) for k in keys if a.get(k) != b.get(k) and not (a.get(k) == 0 and b.get(k) == 0)
        ]
        rel = [abs(y - x) / abs(x) for _, x, y in diffs if x not in (None, 0) and y is not None]
        if not diffs:
            print(f"  same     {f.name}")
        else:
            moved = True
            worst = f"{max(rel):.2%}" if rel else "structural"
            print(f"  CHANGED  {f.name:<38}{len(diffs):>6} of {len(keys)} values, worst {worst}")
    return moved


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("WHY")[0].strip())
    p.add_argument("--staging", metavar="BRANCH", help="read from an OWID staging server")
    p.add_argument("--check", action="store_true", help="report drift without changing anything")
    args = p.parse_args()

    print(f"ETL version pinned in etl_source.py: {es.ETL_VERSION}")
    cache_args = ["--staging", args.staging] if args.staging else []

    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            keep = Path(tmp) / "committed"
            shutil.copytree(FIGURES, keep)
            try:
                run("20_cache_from_etl.py", *cache_args)
                for s in FIGURE_SCRIPTS:
                    run(s)
                print("\n=== drift against the committed figures ===")
                moved = compare(keep, FIGURES)
            finally:
                # --check must leave the tree exactly as it found it, including when a
                # script above raised part-way through writing the figures.
                for f in FIGURES.glob("*.json"):
                    f.unlink()
                for f in keep.glob("*.json"):
                    shutil.copy(f, FIGURES / f.name)
                print("committed figures restored.")
        print("\nfigures differ from the ETL." if moved else "\nup to date.")
        sys.exit(1 if moved else 0)

    run("20_cache_from_etl.py", *cache_args)
    for s in FIGURE_SCRIPTS:
        run(s)
    print("\nDone. Commit data/raw/etl/ and data/figures/ together.")


if __name__ == "__main__":
    main()
