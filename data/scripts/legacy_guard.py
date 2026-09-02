"""
legacy_guard.py — stop a superseded local-pipeline script from silently
overwriting an ETL-sourced figure.

WHY THIS EXISTS
---------------
Since the ETL port (2026-09-02), most figure JSONs in data/figures/ have TWO
programs that can write them: the original local-pipeline scripts (10-17) and
the ETL scripts (21-24, 28). They write the same filenames, so whichever runs
last wins — and nothing announces it.

Running an old one today replaces whole-panel ETL output (1990-2024, current
data vintage) with 2023-only output from the local pipeline. Measured on
2026-09-02, that moves the WID between-country share by 3-4pp (e.g. WID pre-tax
per adult 29.4% -> 26.2%) and deletes the per-year data from the file. The
slides still render perfectly normally afterwards, which is what makes it
dangerous: there is no error to notice.

The old scripts are kept ON PURPOSE — they are the reference implementation of
the method, and `99_verify.py` still checks the local pipeline end to end. This
module only makes running one a deliberate act rather than an accident, which is
easy to commit by following an out-of-date instruction.

USAGE (in a superseded script, as the first statement of main())

    require_ack(
        script="10_fig_raw_comparison.py",
        figures=["fig_raw_comparison.json"],
        replaced_by="21_fig_bridging_from_etl.py",
    )

To run one anyway, pass the flag:

    python data/scripts/10_fig_raw_comparison.py --write-legacy-figures

Then check `git diff data/figures/` before committing, and re-run
`python data/scripts/refresh_from_etl.py` to put the ETL figures back.
"""

import sys

FLAG = "--write-legacy-figures"


def require_ack(script, figures, replaced_by):
    """Exit unless FLAG was passed. `figures` are the files this script writes."""
    listed = ", ".join(figures)

    if FLAG in sys.argv:
        print(f"{FLAG} given — running the SUPERSEDED local-pipeline script {script}.")
        print(f"  It will overwrite: {listed}")
        print(f"  Those are normally produced by {replaced_by} from the ETL.")
        print("  Check `git diff data/figures/` before committing, and re-run")
        print("  `python data/scripts/refresh_from_etl.py` to restore them.")
        return

    print(f"REFUSING TO RUN {script} — it is the superseded local pipeline.")
    print()
    print(f"  It writes:            {listed}")
    print(f"  Now produced by:      {replaced_by}  (from OWID's ETL)")
    print()
    print("  Running it would replace whole-panel ETL output (1990-2024, current")
    print("  vintage) with 2023-only local-pipeline output. The WID between-country")
    print("  shares move by 3-4pp and the per-year data is lost. The slides would")
    print("  still render normally, so nothing would tell you it happened.")
    print()
    print("  To refresh the figures, run:")
    print("      python data/scripts/refresh_from_etl.py")
    print()
    print("  This script is kept as the reference implementation of the method. To")
    print("  run it anyway (e.g. to compare the two implementations), pass:")
    print(f"      {FLAG}")
    sys.exit(2)
