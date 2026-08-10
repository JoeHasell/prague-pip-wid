"""
00_fetch_wid.py — fetch raw percentile data from the WID API (via Stata).

*** THIS IS THE ONLY PIPELINE STEP THAT NEEDS STATA, AND THE ONLY SLOW ONE ***

It runs on a machine with Stata and the `wid` Stata package installed
(ssc install wid). It takes ~1-2 hours for the full pull. Everything
downstream of this script is pure Python and runs off the committed raw
files in data/raw/wid/ — so DON'T run this unless you want to refresh the
raw data itself.

This script is carried over (with paths adapted to this repo's layout) from
the original data project where it was developed and battle-tested:
    ~/Documents/GitHub/data_work/global_inequality_pip_wid
The country-by-country design is deliberate: the WID API is unreliable for
big requests, so we fetch one country at a time, save progress after each,
and resume after interruptions.

WHAT IT FETCHES (year = 2023, "equal-split adults" j, adults = age 992)
-----------------------------------------------------------------------
For each of the ~211 countries that have a PIP counterpart
(raw/wid/country_mapping.csv):

  109 percentile bins  p0p1 ... p98p99, p99p99.1 ... p99.8p99.9, p99.9p100
  aptinc / sptinc      average & share, PRE-TAX NATIONAL income
  adiinc / sdiinc      average & share, POST-TAX NATIONAL income
                       (DINA concept: all taxes and government spending
                        redistributed, so each country's post-tax total
                        equals its pre-tax national income total — verified
                        to hold in the data, see 99_verify.py.
                        NOTE: post-tax DISPOSABLE/cash income is a different,
                        narrower WID concept, code cainc; not fetched here.
                        Add acainc/scainc to the indicators() call if wanted.)

Income values are ANNUAL amounts in LOCAL CURRENCY per adult. Conversion to
international dollars happens downstream (02_process_wid.py) using:

  fetch_ppp.do        -> raw/wid/WID_ppp.csv          (xlcusp PPP factors)
  fetch_population.do -> raw/wid/WID_aggregate_population.csv
                                                      (adult 992 / total 999)

OUTPUTS (all in data/raw/wid/, committed to the repo)
-----------------------------------------------------
  WID_percentiles.csv            all countries combined  <- the raw cache
  WID_ppp.csv
  WID_aggregate_population.csv
  temp_country_data/*.csv        transient per-country files (not committed)
  fetch_progress.json            transient progress state (not committed)

USAGE
-----
  python data/scripts/00_fetch_wid.py                   # validate, confirm, fetch all
  python data/scripts/00_fetch_wid.py --validate-only   # check existing files only
  python data/scripts/00_fetch_wid.py --resume          # continue an interrupted run
  python data/scripts/00_fetch_wid.py --country US      # one country (for testing)
  python data/scripts/00_fetch_wid.py --combine-only    # rebuild WID_percentiles.csv
                                                        # from temp_country_data/
"""

import os
import sys
import json
import time
import subprocess
import argparse
from datetime import datetime

import pandas as pd

from config import (
    RAW_WID_DIR, WID_TEMP_DIR, WID_FETCH_STATE_FILE, COUNTRY_MAPPING_FILE,
    WID_PPP_FILE, WID_POPULATION_FILE, WID_PERCENTILES_RAW,
    SCRIPTS_DIR, STATA_PATH, TARGET_YEAR,
)

EXPECTED_COLUMNS = {"country", "percentile", "year", "avg_posttax", "avg_pretax",
                    "share_posttax", "share_pretax", "p_low", "p_high"}
EXPECTED_ROWS = 109


# =============================================================================
# STATE MANAGEMENT (progress survives interruptions)
# =============================================================================

def load_state():
    if WID_FETCH_STATE_FILE.exists():
        return json.loads(WID_FETCH_STATE_FILE.read_text())
    return {"completed_countries": [], "failed_countries": [],
            "last_updated": None, "ppp_done": False, "population_done": False}


def save_state(state):
    state["last_updated"] = datetime.now().isoformat()
    WID_FETCH_STATE_FILE.write_text(json.dumps(state, indent=2))


# =============================================================================
# STATA EXECUTION
# =============================================================================

def run_stata_script(do_file, timeout=600):
    """Run a .do file with Stata in batch mode, cwd = data/raw/wid/."""
    if not os.path.exists(STATA_PATH):
        print(f"ERROR: Stata not found at {STATA_PATH} (edit config.py)")
        return False
    try:
        result = subprocess.run(
            [STATA_PATH, "-b", "do", str(do_file)],
            cwd=RAW_WID_DIR, capture_output=True, text=True, timeout=timeout,
        )
        # Stata writes its log next to the cwd; scan it for API errors
        log_file = RAW_WID_DIR / (do_file.stem + ".log")
        if log_file.exists():
            log = log_file.read_text()
            if "could not access the online WID.world database" in log:
                print("ERROR: WID API connection error")
                return False
            if "r(677)" in log or "r(603)" in log:
                return False
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"ERROR: Stata timed out after {timeout}s")
        return False


# =============================================================================
# VALIDATION (run before fetching — a full pull costs 1-2 hours, so check
# whether the existing files are actually broken first)
# =============================================================================

def validate_country_file(code):
    """Return a list of issues with one country's file ([] = all good)."""
    path = WID_TEMP_DIR / f"{code}_percentiles.csv"
    if not path.exists():
        return ["file missing"]
    issues = []
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return [f"unreadable: {e}"]
    missing_cols = EXPECTED_COLUMNS - set(df.columns)
    if missing_cols:
        issues.append(f"missing columns: {sorted(missing_cols)}")
    if len(df) != EXPECTED_ROWS:
        issues.append(f"{len(df)} rows (expected {EXPECTED_ROWS})")
    for col in ["country", "percentile", "year", "p_low", "p_high"]:
        if col in df.columns and df[col].isna().any():
            issues.append(f"NAs in {col}")
    if {"p_low", "p_high"} <= set(df.columns):
        bad = ((df.p_low < 0) | (df.p_high > 1) | (df.p_low >= df.p_high)).sum()
        if bad:
            issues.append(f"{bad} invalid percentile bounds")
    if "year" in df.columns and (df.year != TARGET_YEAR).any():
        issues.append("wrong year present")
    return issues


def validate_all(codes):
    print(f"Validating per-country files for {len(codes)} countries...")
    problems = {c: iss for c in codes if (iss := validate_country_file(c))}
    print(f"  valid: {len(codes) - len(problems)} / {len(codes)}")
    for c, iss in list(problems.items())[:15]:
        print(f"  {c}: {'; '.join(iss)}")
    if len(problems) > 15:
        print(f"  ... and {len(problems) - 15} more")
    return problems


# =============================================================================
# FETCHING
# =============================================================================

def load_country_codes():
    df = pd.read_csv(COUNTRY_MAPPING_FILE)
    df = df[df["PIP country name"].notna() & (df["PIP country name"] != "")]
    return df["country"].tolist()


# The per-country Stata job. {code} and {year} are filled in per country.
# perc list = the 109 WID percentile bins (see config.wid_bin_labels()).
COUNTRY_DO_TEMPLATE = r"""
* Fetch WID percentiles for {code} (auto-generated by 00_fetch_wid.py)
local perc_list ///
p0p1 p1p2 p2p3 p3p4 p4p5 p5p6 p6p7 p7p8 p8p9 p9p10 ///
p10p11 p11p12 p12p13 p13p14 p14p15 p15p16 p16p17 p17p18 p18p19 p19p20 ///
p20p21 p21p22 p22p23 p23p24 p24p25 p25p26 p26p27 p27p28 p28p29 p29p30 ///
p30p31 p31p32 p32p33 p33p34 p34p35 p35p36 p36p37 p37p38 p38p39 p39p40 ///
p40p41 p41p42 p42p43 p43p44 p44p45 p45p46 p46p47 p47p48 p48p49 p49p50 ///
p50p51 p51p52 p52p53 p53p54 p54p55 p55p56 p56p57 p57p58 p58p59 p59p60 ///
p60p61 p61p62 p62p63 p63p64 p64p65 p65p66 p66p67 p67p68 p68p69 p69p70 ///
p70p71 p71p72 p72p73 p73p74 p74p75 p75p76 p76p77 p77p78 p78p79 p79p80 ///
p80p81 p81p82 p82p83 p83p84 p84p85 p85p86 p86p87 p87p88 p88p89 p89p90 ///
p90p91 p91p92 p92p93 p93p94 p94p95 p95p96 p96p97 p97p98 p98p99 ///
p99p99.1 p99.1p99.2 p99.2p99.3 p99.3p99.4 p99.4p99.5 ///
p99.5p99.6 p99.6p99.7 p99.7p99.8 p99.8p99.9 p99.9p100

* Two income concepts, "equal-split adults" (j), adults = age 992:
*   pre-tax national income : aptinc (avg), sptinc (share)
*   post-tax national income: adiinc (avg), sdiinc (share)
wid, indicators(aptinc sptinc adiinc sdiinc) ///
    areas({code}) years({year}) perc(`perc_list') ///
    ages(992) population(j) clear

keep country year percentile variable value
gen indicator = substr(variable, 1, 6)
drop variable
reshape wide value, i(country year percentile) j(indicator) string

* Not all countries have all concepts -> capture (no error if absent)
capture rename valueaptinc avg_pretax
capture rename valuesptinc share_pretax
capture rename valueadiinc avg_posttax
capture rename valuesdiinc share_posttax

* Parse "pXpY" into numeric bounds (fractions of the distribution)
gen str10 p_clean = substr(percentile, 2, .)
split p_clean, parse("p") gen(p_)
destring p_1 p_2, replace
gen double p_low = p_1 / 100
gen double p_high = p_2 / 100
drop p_clean p_1 p_2

keep country percentile year avg_* share_* p_low p_high
export delimited using "temp_country_data/{code}_percentiles.csv", replace delim(",")
"""


def fetch_country(code, retries=3):
    out = WID_TEMP_DIR / f"{code}_percentiles.csv"
    if out.exists():
        return True
    temp_do = RAW_WID_DIR / f"temp_fetch_{code}.do"
    for attempt in range(retries):
        temp_do.write_text(COUNTRY_DO_TEMPLATE.format(code=code, year=TARGET_YEAR))
        ok = run_stata_script(temp_do, timeout=180)
        temp_do.unlink(missing_ok=True)
        (RAW_WID_DIR / f"temp_fetch_{code}.log").unlink(missing_ok=True)
        if ok and out.exists():
            return True
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
    return False


def combine_country_files(codes):
    """Concatenate per-country files into the committed raw cache."""
    dfs, missing = [], []
    for code in codes:
        path = WID_TEMP_DIR / f"{code}_percentiles.csv"
        if path.exists():
            dfs.append(pd.read_csv(path))
        else:
            missing.append(code)
    if missing:
        print(f"WARNING: no data for {len(missing)} countries: {missing[:10]}...")
    if not dfs:
        print("ERROR: nothing to combine")
        return False
    combined = pd.concat(dfs, ignore_index=True).sort_values(
        ["country", "p_low"]).reset_index(drop=True)
    combined.to_csv(WID_PERCENTILES_RAW, index=False)
    print(f"Combined {len(dfs)} countries -> {WID_PERCENTILES_RAW} "
          f"({len(combined):,} rows)")
    return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="re-fetch PPP/population even if marked done")
    ap.add_argument("--country", type=str, help="fetch a single country code")
    ap.add_argument("--combine-only", action="store_true")
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    WID_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    codes = load_country_codes()
    print(f"{len(codes)} countries with a PIP counterpart")

    problems = validate_all(codes)
    if args.validate_only:
        return 0

    if args.combine_only:
        return 0 if combine_country_files(codes) else 1

    state = load_state() if args.resume else {
        "completed_countries": [], "failed_countries": [],
        "last_updated": None, "ppp_done": False, "population_done": False}

    if not args.country and not args.resume:
        print("\nA full fetch takes ~1-2 hours."
              + (f" ({len(problems)} countries currently have issues.)" if problems else ""))
        if input("Proceed? [y/N]: ").strip().lower() != "y":
            return 0

    # PPP + population (fast, all countries in one call each)
    if not args.country:
        if not (state["ppp_done"] and not args.force):
            if run_stata_script(SCRIPTS_DIR / "fetch_ppp.do", timeout=300) \
                    and WID_PPP_FILE.exists():
                state["ppp_done"] = True
                save_state(state)
            else:
                print("ERROR: PPP fetch failed")
                return 1
        if not (state["population_done"] and not args.force):
            if run_stata_script(SCRIPTS_DIR / "fetch_population.do", timeout=300) \
                    and WID_POPULATION_FILE.exists():
                state["population_done"] = True
                save_state(state)
            else:
                print("ERROR: population fetch failed")
                return 1

    # Percentiles, country by country
    todo = [args.country] if args.country else \
           [c for c in codes if c not in set(state["completed_countries"])]
    t0 = time.time()
    for i, code in enumerate(todo, 1):
        ok = fetch_country(code)
        state["completed_countries" if ok else "failed_countries"].append(code)
        save_state(state)
        status = "ok" if ok else "FAILED"
        if i % 10 == 0 or not ok:
            rate = i / (time.time() - t0)
            eta = (len(todo) - i) / rate / 60 if rate else 0
            print(f"[{i}/{len(todo)}] {code} {status} | ETA {eta:.0f} min")

    if not args.country:
        combine_country_files(codes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
