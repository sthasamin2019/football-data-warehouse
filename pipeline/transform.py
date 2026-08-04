# =====================================================================
# pipeline/transform.py
#
# Stage 2 of the pipeline: takes the raw DataFrame from extract.py and
# reshapes it into clean tables matching the OLTP schema.
#
# This is also where real data gets combined with Faker-generated
# synthetic data, since only 98 real rows exist -- too few to
# meaningfully test quality checks or the warehouse at scale.
# =====================================================================

import pandas as pd
import re
import logging
import os

logging.basicConfig(
    filename=os.path.join("logs", "transform.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# The raw CSV stores a country code, but the OLTP schema needs a
# league name -- this is the lookup used to bridge the two
COUNTRY_TO_LEAGUE = {
    "ENG": "Premier League",
    "ESP": "La Liga",
    "ITA": "Serie A",
    "FRA": "Ligue 1",
    "GER": "Bundesliga",
}

SEASON_LABEL = "2022-23"


def split_scorer_field(value: str):
    """
    Splits a messy source string like 'Robert Lewandowski - 17' into
    a clean name and goal count. Uses a regex anchored on ' - N' at
    the very end of the string, so it correctly captures the goal
    count even when the name portion has multiple words.

    Falls back gracefully (logs a warning, returns the raw string with
    no goal count) rather than crashing on an unexpected format.
    """
    match = re.match(r"^(.*)\s-\s(\d+)$", str(value).strip())
    if match:
        return match.group(1).strip(), int(match.group(2))
    logging.warning(f"Could not parse scorer field cleanly: '{value}'")
    return str(value).strip(), None


def clean_keeper_field(value: str):
    """
    The goalkeeper field has no reliable delimiter for rows listing
    two goalkeepers (e.g. 'Pepe Reina Geronimo Rulli'). Rather than
    guess wrong, this just flags suspicious multi-name entries in the
    log for visibility, and keeps the field as a single string.
    """
    name = str(value).strip()
    if len(name.split()) > 3:
        logging.info(f"Goalkeeper field may contain multiple names: '{name}'")
    return name


def transform(raw_df: pd.DataFrame, cur=None, synthetic_batch_size: int = 500) -> dict:
    """
    Main transform function.

    cur (optional): a database cursor. If provided, synthetic data is
    generated INCREMENTALLY using the watermark table (a new batch
    each run). If not provided (e.g. running this file standalone for
    testing), falls back to a simple one-shot generator instead.
    """
    df = raw_df.copy()

    # --- Clean and reshape the real data ---

    df["league_name"] = df["Country"].map(COUNTRY_TO_LEAGUE)
    unmapped = df[df["league_name"].isna()]
    if not unmapped.empty:
        logging.warning(f"Unmapped countries found: {unmapped['Country'].unique()}")

    df["stats_date"] = pd.to_datetime(df["stats_date"]).dt.date

    # Force all numeric columns to actual numbers -- errors="coerce"
    # turns anything unparseable into NaN instead of crashing
    numeric_cols = ["MP", "W", "D", "L", "GF", "GA", "GD", "Pts",
                     "Pts/MP", "xG", "xGA", "xGD", "xGD/90", "Attendance", "LgRk"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Split the messy scorer field into two clean columns
    df[["scorer_name", "scorer_goals"]] = df["Top Team Scorer"].apply(
        lambda x: pd.Series(split_scorer_field(x))
    )
    df["goalkeeper_name"] = df["Goalkeeper"].apply(clean_keeper_field)

    # --- Reshape into tables matching the OLTP schema ---

    teams = df[["Squad", "league_name"]].drop_duplicates().rename(
        columns={"Squad": "team_name"}
    )

    team_season_stats = df[[
        "Squad", "league_name", "stats_date", "LgRk", "MP", "W", "D", "L",
        "GF", "GA", "GD", "Pts", "Pts/MP", "xG", "xGA", "xGD", "xGD/90", "Attendance"
    ]].rename(columns={
        "Squad": "team_name", "LgRk": "lg_rank", "MP": "mp", "W": "w", "D": "d",
        "L": "l", "GF": "gf", "GA": "ga", "GD": "gd", "Pts": "pts",
        "Pts/MP": "pts_per_mp", "xG": "xg", "xGA": "xga", "xGD": "xgd",
        "xGD/90": "xgd_90", "Attendance": "attendance"
    })
    team_season_stats["season_label"] = SEASON_LABEL

    top_scorers = df[["Squad", "stats_date", "scorer_name", "scorer_goals"]].rename(
        columns={"Squad": "team_name"}
    )

    goalkeepers = df[["Squad", "stats_date", "goalkeeper_name"]].rename(
        columns={"Squad": "team_name"}
    )

    # --- Attach scorer/goalkeeper names onto the main stats table ---
    # team_season_stats alone doesn't carry player info -- it lives in
    # the separate top_scorers/goalkeepers tables above. This merge
    # brings those names onto each real row BEFORE combining with
    # synthetic data, so load.py can insert scorer/keeper links for
    # real rows the same way it does for synthetic ones.
    real_with_players = team_season_stats.merge(
        top_scorers[["team_name", "stats_date", "scorer_name", "scorer_goals"]],
        on=["team_name", "stats_date"], how="left"
    ).merge(
        goalkeepers[["team_name", "stats_date", "goalkeeper_name"]],
        on=["team_name", "stats_date"], how="left"
    )

    # --- Generate synthetic data to bring the dataset up to a usable scale ---
    if cur is not None:
        # Real pipeline run: generate the NEXT incremental batch,
        # continuing from wherever the watermark left off
        from pipeline.generate_synthetic import generate_synthetic_incremental
        synthetic = generate_synthetic_incremental(cur, batch_size=synthetic_batch_size)
    else:
        # Standalone/test run: no watermark tracking, just generate
        # a one-off batch starting from zero
        from pipeline.generate_synthetic import generate_synthetic_dataset
        synthetic = generate_synthetic_dataset(n_rows=synthetic_batch_size)

    # Combine real + synthetic into one dataset, tagged by source so
    # they can always be told apart later
    combined_stats = pd.concat(
        [real_with_players.assign(source="real"), synthetic.assign(source="synthetic")],
        ignore_index=True
    )

    logging.info(f"Transformed {len(df)} real rows + {len(synthetic)} new synthetic rows into "
                 f"{len(teams)} teams, {len(combined_stats)} total stat rows this run")

    return {
        "teams": teams,
        "team_season_stats": combined_stats,          # real + synthetic combined
        "team_season_stats_real_only": team_season_stats,  # real data only, for reference
        "top_scorers": top_scorers,
        "goalkeepers": goalkeepers,
    }


# Lets this file be run directly for quick standalone testing,
# e.g. python -m pipeline.transform
if __name__ == "__main__":
    from pipeline.extract import extract
    raw = extract()
    result = transform(raw)
    for name, table in result.items():
        print(f"\n--- {name} ({len(table)} rows) ---")
        print(table.head(3))