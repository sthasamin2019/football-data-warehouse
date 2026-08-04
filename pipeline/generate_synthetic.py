# =====================================================================
# pipeline/generate_synthetic.py
#
# Generates realistic fake football data using Faker, since the real
# dataset only has 98 rows -- too small to meaningfully test quality
# checks or the warehouse at scale.
#
# Uses INCREMENTAL generation: instead of regenerating the same fixed
# batch every run, each run reads the watermark table to see where the
# last run left off, then generates a fresh new batch continuing from
# there. This means re-running the pipeline grows the dataset over
# time instead of staying at a fixed size.
# =====================================================================

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
    """Builds a fake but plausible-sounding football club name,
    e.g. 'Millerport Wanderers'."""
    return f"{fake.city()} {random.choice(FOOTBALL_SUFFIXES)}"


def generate_stat_row(stats_date) -> dict:
    """
    Builds one synthetic team-season row.

    Key design choice: stats are CALCULATED, not random --
    pts = 3*w + d, gd = gf - ga, etc. This means every synthetic row
    automatically satisfies the pipeline's quality checks
    (e.g. w+d+l=mp, gd=gf-ga) instead of failing by chance.
    """
    mp = random.randint(28, 32)
    w = random.randint(0, mp)
    d = random.randint(0, mp - w)
    l = mp - w - d
    gf = random.randint(20, 80)
    ga = random.randint(15, 70)
    gd = gf - ga
    pts = 3 * w + d
    # xG (expected goals) is derived from actual goals with small random
    # noise, mimicking the real relationship between actual and expected
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
    """
    Generate synthetic rows.

    start_index offsets both the random seed AND the row numbering.
    This is what makes incremental generation actually work:
    seeding with (42 + start_index) means each batch draws from a
    DIFFERENT point in Faker's random sequence, so batch 2 doesn't
    just repeat the same names as batch 1 with different numbers
    tacked on.
    """
    Faker.seed(42 + start_index)
    random.seed(42 + start_index)

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
        # Appending the row's own index guarantees the team name is
        # unique even at tens of thousands of rows -- zero collision risk
        row["team_name"] = f"{row['team_name']} {i}"
        rows.append(row)

    df = pd.DataFrame(rows)
    logging.info(f"Generated {len(df)} synthetic rows (index {start_index} to {start_index+n_rows-1})")
    return df


def generate_synthetic_incremental(cur, batch_size: int = 500) -> pd.DataFrame:
    """
    Reads the watermark to determine how many synthetic rows already
    exist, then generates only the NEXT batch -- true incremental
    growth instead of regenerating the full dataset every run.

    Example: if last_synthetic_seed = 500, this generates rows
    500-999, then advances the watermark to 1000 for next time.
    """
    cur.execute("SELECT last_synthetic_seed FROM pipeline_watermark WHERE pipeline_name='football_etl'")
    row = cur.fetchone()
    start_index = row[0] if row and row[0] else 0

    new_batch = generate_synthetic_dataset(n_rows=batch_size, start_index=start_index)

    # Advance the watermark so the NEXT run starts where this one ended
    cur.execute("""
        UPDATE pipeline_watermark
        SET last_synthetic_seed = %s
        WHERE pipeline_name = 'football_etl'
    """, (start_index + batch_size,))

    logging.info(f"Incremental synthetic batch: rows {start_index} to {start_index+batch_size-1}")
    return new_batch


# Lets this file be run directly for a one-off large batch,
# e.g. python -m pipeline.generate_synthetic
if __name__ == "__main__":
    synthetic_df = generate_synthetic_dataset(n_rows=14000)
    print(f"Generated {len(synthetic_df)} synthetic rows")
    print(synthetic_df.head(5))