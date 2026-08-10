"""
config.py — shared paths and constants for the PIP/WID data pipeline.

All pipeline scripts import from this file, so paths are defined once.
Paths are resolved relative to this file's location, so scripts can be run
from any working directory:

    python data/scripts/02_process_wid.py      # from the repo root
    python 02_process_wid.py                   # from data/scripts/

Pipeline layout (all under data/):

    raw/        Data as it arrives from the source. Never edited by hand.
                - raw/wid/  : output of the WID fetch (00_fetch_wid.py, needs Stata)
                - raw/pip/  : cached 2023 extract of the PIP thousand-bins file
                              (01_fetch_pip.py, pure Python)
    processed/  Data produced by the pipeline scripts. Fully regenerable:
                delete the folder and re-run scripts 02-03 to rebuild it.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1]   # .../data
SCRIPTS_DIR = DATA_DIR / "scripts"
RAW_WID_DIR = DATA_DIR / "raw" / "wid"
RAW_PIP_DIR = DATA_DIR / "raw" / "pip"
PROCESSED_DIR = DATA_DIR / "processed"

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

# The single reference year for this phase of the project.
# (The WID fetch was run for 2023 only; PIP has many years but we extract 2023
# to match. When we extend to a time series this becomes a list.)
TARGET_YEAR = 2023

# PIP source: World Bank PIP "thousand bins" dataset, republished in the
# Our World in Data catalog. 1000 quantile bins (0.1% of population each) per
# country-year; `avg` = mean DAILY income/consumption within the bin, in 2021
# PPP international dollars, PER CAPITA; `pop` = number of people in the bin.
PIP_URL = (
    "https://catalog.ourworldindata.org/garden/wb/2025-10-13/"
    "thousand_bins_distribution/thousand_bins_distribution.feather"
)

# ---------------------------------------------------------------------------
# Raw files (inputs to the pipeline)
# ---------------------------------------------------------------------------

# WID raw files — produced by 00_fetch_wid.py (requires Stata; takes ~1-2h).
# These are COMMITTED to the repo so that everything downstream is
# reproducible without Stata and without the slow API pull.
WID_PERCENTILES_RAW = RAW_WID_DIR / "WID_percentiles.csv"        # combined, all countries
WID_PPP_FILE = RAW_WID_DIR / "WID_ppp.csv"                        # market-exchange->PPP factors (xlcusp)
WID_POPULATION_FILE = RAW_WID_DIR / "WID_aggregate_population.csv"  # adult & total population
COUNTRY_MAPPING_FILE = RAW_WID_DIR / "country_mapping.csv"        # WID 2-letter code -> PIP country name

# Transient per-country files created while 00_fetch_wid.py runs (not committed).
WID_TEMP_DIR = RAW_WID_DIR / "temp_country_data"
WID_FETCH_STATE_FILE = RAW_WID_DIR / "fetch_progress.json"

# PIP raw cache — produced by 01_fetch_pip.py (pure Python, ~30s).
PIP_RAW_FILE = RAW_PIP_DIR / f"pip_thousand_bins_{TARGET_YEAR}.csv.gz"

# ---------------------------------------------------------------------------
# Processed files (outputs of the pipeline)
# ---------------------------------------------------------------------------

# Step 02 output: WID percentiles converted to daily 2021-PPP international
# dollars, with per-adult AND per-capita income for both income concepts.
WID_PROCESSED_FILE = PROCESSED_DIR / f"wid_percentiles_{TARGET_YEAR}.csv"

# Step 03 output: the harmonized PIP + WID quantile dataset — one tidy file,
# identical 109-bin structure for every source. This is THE dataset that all
# analyses and deck figures should start from.
HARMONIZED_FILE = PROCESSED_DIR / f"pip_wid_harmonized_{TARGET_YEAR}.csv"

# ---------------------------------------------------------------------------
# Stata (only needed for 00_fetch_wid.py)
# ---------------------------------------------------------------------------

STATA_PATH = "/Applications/Stata/StataSE.app/Contents/MacOS/stata-se"

# ---------------------------------------------------------------------------
# The WID percentile-bin structure (109 bins)
# ---------------------------------------------------------------------------
# 99 one-percent bins (p0p1 ... p98p99), then the top 1% split into
# 9 tenth-of-a-percent bins (p99p99.1 ... p99.8p99.9) and the top 0.1%
# (p99.9p100). PIP's 1000 equal 0.1% bins can be aggregated to EXACTLY this
# structure, which is what 03_harmonize.py does.

def wid_bin_labels():
    """Return the 109 WID percentile labels in ascending order."""
    labels = [f"p{i}p{i + 1}" for i in range(99)]                       # p0p1 ... p98p99
    tenths = [round(99 + 0.1 * k, 1) for k in range(10)] + [100]        # 99, 99.1, ... 99.9, 100
    labels += [f"p{fmt(lo)}p{fmt(hi)}" for lo, hi in zip(tenths[:-1], tenths[1:])]
    return labels


def fmt(x):
    """Format a percentile bound the way WID does: 99 not 99.0, but 99.1."""
    return f"{x:g}"
