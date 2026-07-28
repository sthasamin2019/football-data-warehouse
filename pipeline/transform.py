
import pandas as pd
import re
import logging
import os

logging.basicConfig(
    filename=os.path.join("logs", "transform.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

COUNTRY_TO_LEAGUE = {
    "ENG": "Premier League",
    "ESP": "La Liga",
    "ITA": "Serie A",
    "FRA": "Ligue 1",
    "GER": "Bundesliga",
}

SEASON_LABEL = "2022-23"


def split_scorer_field(value: str):
    """Split 'Name - N' into (player_name, goals). Falls back gracefully."""
    match = re.match(r"^(.*)\s-\s(\d+)$", str(value).strip())
    if match:
        return match.group(1).strip(), int(match.group(2))
    logging.warning(f"Could not parse scorer field cleanly: '{value}'")
    return str(value).strip(), None


def clean_keeper_field(value: str):
    """Goalkeeper field has no reliable delimiter for multi-keeper rows.
    Kept as a single string; logged for visibility."""
    name = str(value).strip()
    if len(name.split()) > 3:
        logging.info(f"Goalkeeper field may contain multiple names: '{name}'")
    return name


def transform(raw_df: pd.DataFrame) -> dict:
    df = raw_df.copy()

    df["league_name"] = df["Country"].map(COUNTRY_TO_LEAGUE)
    unmapped = df[df["league_name"].isna()]
    if not unmapped.empty:
        logging.warning(f"Unmapped countries found: {unmapped['Country'].unique()}")

    df["stats_date"] = pd.to_datetime(df["stats_date"]).dt.date

    numeric_cols = ["MP", "W", "D", "L", "GF", "GA", "GD", "Pts",
                     "Pts/MP", "xG", "xGA", "xGD", "xGD/90", "Attendance", "LgRk"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df[["scorer_name", "scorer_goals"]] = df["Top Team Scorer"].apply(
        lambda x: pd.Series(split_scorer_field(x))
    )
    df["goalkeeper_name"] = df["Goalkeeper"].apply(clean_keeper_field)

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

    # --- Combine real data with Faker-generated synthetic data ---
    from pipeline.generate_synthetic import generate_synthetic_dataset
    synthetic = generate_synthetic_dataset(n_rows=14000)
    combined_stats = pd.concat(
        [team_season_stats.assign(source="real"), synthetic.assign(source="synthetic")],
        ignore_index=True
    )

    logging.info(f"Transformed {len(df)} real rows + {len(synthetic)} synthetic rows into "
                 f"{len(teams)} teams, {len(combined_stats)} total stat rows, "
                 f"{len(top_scorers)} scorer rows, {len(goalkeepers)} keeper rows")

    return {
        "teams": teams,
        "team_season_stats": combined_stats,
        "team_season_stats_real_only": team_season_stats,
        "top_scorers": top_scorers,
        "goalkeepers": goalkeepers,
    }


if __name__ == "__main__":
    from pipeline.extract import extract
    raw = extract()
    result = transform(raw)
    for name, table in result.items():
        print(f"\n--- {name} ({len(table)} rows) ---")
        print(table.head(3))
