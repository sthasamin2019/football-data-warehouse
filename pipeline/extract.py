import pandas as pd
import logging
import os

logging.basicConfig(
    filename=os.path.join("logs", "extract.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

RAW_CSV_PATH = os.path.join("data", "raw", "standings_2022_23.csv")

EXPECTED_COLUMNS = [
    "Rk", "Squad", "Country", "stats_date", "LgRk", "MP", "W", "D", "L",
    "GF", "GA", "GD", "Pts", "Pts/MP", "xG", "xGA", "xGD", "xGD/90",
    "Attendance", "Top Team Scorer", "Goalkeeper"
]

def extract(csv_path: str = RAW_CSV_PATH) -> pd.DataFrame:
    """Read the raw standings CSV and do basic structural validation."""
    if not os.path.exists(csv_path):
        logging.error(f"File not found: {csv_path}")
        raise FileNotFoundError(f"Raw CSV not found at {csv_path}")

    df = pd.read_csv(csv_path, sep=";", encoding="utf-8")

    missing_cols = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing_cols:
        logging.error(f"Missing expected columns: {missing_cols}")
        raise ValueError(f"CSV is missing expected columns: {missing_cols}")

    row_count = len(df)
    logging.info(f"Extracted {row_count} rows from {csv_path}")

    if row_count == 0:
        logging.warning("Extracted zero rows — check the source file.")

    return df

if __name__ == "__main__":
    data = extract()
    print(f"Extracted {len(data)} rows, {len(data.columns)} columns.")
    print(data.head(3))