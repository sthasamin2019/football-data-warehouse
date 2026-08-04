# =====================================================================
# pipeline/extract.py
#
# Stage 1 of the pipeline: reads the raw standings CSV and performs
# basic structural validation before any data is transformed or loaded.
#
# This is intentionally the ONLY stage that touches the raw file --
# it doesn't clean or reshape anything, it just confirms the file
# exists and has the columns we expect.
# =====================================================================

import pandas as pd
import logging
import os

# All runs are logged to logs/extract.log with a timestamp,
# so every pipeline execution leaves a traceable record
logging.basicConfig(
    filename=os.path.join("logs", "extract.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Location of the source data file
RAW_CSV_PATH = os.path.join("data", "raw", "standings_2022_23.csv")

# The columns we expect to find in the CSV.
# If the source file is ever re-exported and a column gets renamed
# or dropped, extract() will fail loudly here instead of letting
# bad/incomplete data flow silently into the rest of the pipeline
EXPECTED_COLUMNS = [
    "Rk", "Squad", "Country", "stats_date", "LgRk", "MP", "W", "D", "L",
    "GF", "GA", "GD", "Pts", "Pts/MP", "xG", "xGA", "xGD", "xGD/90",
    "Attendance", "Top Team Scorer", "Goalkeeper"
]


def extract(csv_path: str = RAW_CSV_PATH) -> pd.DataFrame:
    """Read the raw standings CSV and do basic structural validation."""

    # Fail early and clearly if the file simply isn't there
    if not os.path.exists(csv_path):
        logging.error(f"File not found: {csv_path}")
        raise FileNotFoundError(f"Raw CSV not found at {csv_path}")

    # The source file uses ';' as a delimiter, not the usual comma
    df = pd.read_csv(csv_path, sep=";", encoding="utf-8")

    # Compare the columns we actually got against what we expect --
    # catches silent schema drift in the source file
    missing_cols = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing_cols:
        logging.error(f"Missing expected columns: {missing_cols}")
        raise ValueError(f"CSV is missing expected columns: {missing_cols}")

    row_count = len(df)
    logging.info(f"Extracted {row_count} rows from {csv_path}")

    # Not a hard failure, but worth flagging -- an empty file
    # usually means something upstream went wrong
    if row_count == 0:
        logging.warning("Extracted zero rows — check the source file.")

    # Returns the raw, unmodified DataFrame.
    # Cleaning/reshaping happens later in transform.py, not here --
    # keeps this stage's responsibility narrow and easy to test
    return df


# Lets this file be run directly (python -m pipeline.extract)
# for quick standalone testing, separate from the full pipeline
if __name__ == "__main__":
    data = extract()
    print(f"Extracted {len(data)} rows, {len(data.columns)} columns.")
    print(data.head(3))