from faker import Faker
import pandas as pd
import random
import logging
import os

logging.basicConfig(
    filename=os.path.join("logs", "synthetic.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

fake = Faker()

LEAGUES = ["Premier League", "La Liga", "Serie A", "Ligue 1", "Bundesliga"]
FOOTBALL_SUFFIXES = ["FC", "United", "City", "Athletic", "Rovers", "Town", "Wanderers"]


def generate_team_name() -> str:
    return f"{fake.city()} {random.choice(FOOTBALL_SUFFIXES)}"


def generate_stat_row(stats_date) -> dict:
    mp = random.randint(28, 32)
    w = random.randint(0, mp)
    d = random.randint(0, mp - w)
    l = mp - w - d
    gf = random.randint(20, 80)
    ga = random.randint(15, 70)
    gd = gf - ga
    pts = 3 * w + d
    xg = round(gf * random.uniform(0.85, 1.15), 1)
    xga = round(ga * random.uniform(0.85, 1.15), 1)

    return {
        "team_name": generate_team_name(),
        "league_name": random.choice(LEAGUES),
        "stats_date": stats_date,
        "lg_rank": None,
        "mp": mp, "w": w, "d": d, "l": l,
        "gf": gf, "ga": ga, "gd": gd,
        "pts": pts,
        "pts_per_mp": round(pts / mp, 2),
        "xg": xg, "xga": xga, "xgd": round(xg - xga, 1),
        "xgd_90": round((xg - xga) / mp, 2),
        "attendance": random.randint(4500, 83000),
        "scorer_name": fake.name(),
        "scorer_goals": random.randint(3, 25),
        "goalkeeper_name": fake.name(),
        "season_label": "2022-23",
    }


def generate_synthetic_dataset(n_rows: int, start_index: int = 0) -> pd.DataFrame:
    Faker.seed(42 + start_index)
    random.seed(42 + start_index)
    """Generate synthetic rows. start_index offsets the row numbering so
    incremental runs can generate a fresh, non-overlapping batch."""
    seasons = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
    snapshot_dates = ["-09-15", "-12-01", "-03-01", "-05-15"]

    rows = []
    for i in range(start_index, start_index + n_rows):
        season = random.choice(seasons)
        year = int(season[:4])
        date_suffix = random.choice(snapshot_dates)
        stats_date = f"{year}{date_suffix}"
        row = generate_stat_row(stats_date)
        row["season_label"] = season
        row["team_name"] = f"{row['team_name']} {i}"
        rows.append(row)

    df = pd.DataFrame(rows)
    logging.info(f"Generated {len(df)} synthetic rows (index {start_index} to {start_index+n_rows-1})")
    return df


def generate_synthetic_incremental(cur, batch_size: int = 500) -> pd.DataFrame:
    """Reads the watermark to determine how many synthetic rows already
    exist, then generates only the next batch ??? true incremental growth
    instead of regenerating the full dataset every run."""
    cur.execute("SELECT last_synthetic_seed FROM pipeline_watermark WHERE pipeline_name='football_etl'")
    row = cur.fetchone()
    start_index = row[0] if row and row[0] else 0

    new_batch = generate_synthetic_dataset(n_rows=batch_size, start_index=start_index)

    cur.execute("""
        UPDATE pipeline_watermark
        SET last_synthetic_seed = %s
        WHERE pipeline_name = 'football_etl'
    """, (start_index + batch_size,))

    logging.info(f"Incremental synthetic batch: rows {start_index} to {start_index+batch_size-1}")
    return new_batch


if __name__ == "__main__":
    synthetic_df = generate_synthetic_dataset(n_rows=14000)
    print(f"Generated {len(synthetic_df)} synthetic rows")
    print(synthetic_df.head(5))

