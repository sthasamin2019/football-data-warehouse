# =====================================================================
# pipeline/load.py
#
# Stage 4 of the pipeline: writes transformed + validated data into
# the normalized OLTP database.
#
# Key design principles:
#   - IDEMPOTENT: re-running never creates duplicates -- rows that
#     already exist are detected and skipped
#   - GET-OR-CREATE pattern: leagues/teams/seasons/players are looked
#     up first, only inserted if they don't already exist, and cached
#     in memory to avoid repeat database round-trips
#   - TRANSACTION SAFETY: if anything fails partway through, the whole
#     batch rolls back rather than leaving a half-loaded database
# =====================================================================

import os
import random
import logging
import psycopg2
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    filename=os.path.join("logs", "load.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Randomly assigned to synthetic scorers since Faker doesn't generate
# football positions -- goalkeepers are always tagged "Goalkeeper" instead
SCORER_ROLES = ["Striker", "Forward", "Midfielder", "Winger"]


def get_connection():
    """Opens a connection to the OLTP database using credentials from .env."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def get_or_create_league(cur, cache, league_name):
    """
    Leagues are pre-seeded (via migrations), so this only looks them up --
    it never creates a new one. If a league is missing, that signals a
    real data problem worth failing loudly on.
    """
    if league_name in cache:
        return cache[league_name]
    cur.execute("SELECT league_id FROM leagues WHERE league_name = %s", (league_name,))
    row = cur.fetchone()
    if row:
        cache[league_name] = row[0]
        return row[0]
    raise ValueError(f"League not found (should be pre-seeded): {league_name}")


def get_or_create_season(cur, cache, season_label):
    """Same pattern as leagues -- seasons are pre-seeded, only looked up here."""
    if season_label in cache:
        return cache[season_label]
    cur.execute("SELECT season_id FROM seasons WHERE season_label = %s", (season_label,))
    row = cur.fetchone()
    if row:
        cache[season_label] = row[0]
        return row[0]
    raise ValueError(f"Season not found (should be pre-seeded): {season_label}")


def get_or_create_team(cur, cache, team_name, league_id):
    """
    Teams ARE created here, since new teams (real or synthetic) show up
    with every dataset. Checks the cache first, then the database,
    only inserting if genuinely new.
    """
    key = (team_name, league_id)
    if key in cache:
        return cache[key]
    cur.execute("SELECT team_id FROM teams WHERE team_name = %s AND league_id = %s",
                (team_name, league_id))
    row = cur.fetchone()
    if row:
        cache[key] = row[0]
        return row[0]
    cur.execute("INSERT INTO teams (team_name, league_id) VALUES (%s, %s) RETURNING team_id",
                (team_name, league_id))
    new_id = cur.fetchone()[0]
    cache[key] = new_id
    return new_id


def get_or_create_player(cur, cache, player_name, role=None):
    """Same get-or-create pattern, used for both scorers and goalkeepers."""
    if player_name in cache:
        return cache[player_name]
    cur.execute("SELECT player_id FROM players WHERE player_name = %s", (player_name,))
    row = cur.fetchone()
    if row:
        cache[player_name] = row[0]
        return row[0]
    cur.execute("INSERT INTO players (player_name, role) VALUES (%s, %s) RETURNING player_id",
                (player_name, role))
    new_id = cur.fetchone()[0]
    cache[player_name] = new_id
    return new_id


def get_watermark(cur, pipeline_name="football_etl"):
    """Reads the last recorded run timestamp and cumulative row count."""
    cur.execute("SELECT last_run_at, last_row_count FROM pipeline_watermark WHERE pipeline_name=%s", (pipeline_name,))
    row = cur.fetchone()
    return row if row else (None, 0)


def update_watermark(cur, inserted_count, pipeline_name="football_etl"):
    """
    Records this run in the watermark table: updates the timestamp and
    adds this run's insert count to the running total. Acts as an audit
    trail of every successful pipeline execution.
    """
    cur.execute("""
        UPDATE pipeline_watermark
        SET last_run_at = NOW(), last_row_count = last_row_count + %s
        WHERE pipeline_name = %s
    """, (inserted_count, pipeline_name))


def pd_notna(value):
    """Small wrapper around pandas' null-check, used to guard against
    missing scorer/goalkeeper names before inserting them."""
    return pd.notna(value)


def load(stats_df, top_scorers_df=None, goalkeepers_df=None):
    """
    Main load function: inserts team-season stats, plus their linked
    scorer and goalkeeper records, into the OLTP database.

    Processes rows in FK-dependency order: league -> season -> team
    -> stat row -> scorer/goalkeeper links, since each step needs the
    ID generated by the step before it.
    """
    conn = get_connection()
    conn.autocommit = False  # manual transaction control -- see rollback below
    cur = conn.cursor()

    # In-memory caches avoid re-querying the database for every single
    # row -- important at thousands of rows
    league_cache, season_cache, team_cache, player_cache = {}, {}, {}, {}
    stat_id_map = {}
    inserted, skipped = 0, 0

    try:
        for idx, row in stats_df.iterrows():
            league_id = get_or_create_league(cur, league_cache, row["league_name"])
            season_id = get_or_create_season(cur, season_cache, row["season_label"])
            team_id = get_or_create_team(cur, team_cache, row["team_name"], league_id)

            # THE IDEMPOTENCY CHECK: if this exact team+season+date snapshot
            # already exists, skip it instead of inserting a duplicate.
            # This is what makes it safe to re-run the pipeline repeatedly.
            cur.execute("""
                SELECT stat_id FROM team_season_stats
                WHERE team_id = %s AND season_id = %s AND stats_date = %s
            """, (team_id, season_id, row["stats_date"]))
            existing = cur.fetchone()
            if existing:
                stat_id_map[idx] = existing[0]
                skipped += 1
                continue

            # New row -- insert the actual performance stats
            cur.execute("""
                INSERT INTO team_season_stats
                (team_id, season_id, stats_date, lg_rank, mp, w, d, l, gf, ga, gd,
                 pts, pts_per_mp, xg, xga, xgd, xgd_90, attendance)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING stat_id
            """, (
                team_id, season_id, row["stats_date"], row.get("lg_rank"),
                row["mp"], row["w"], row["d"], row["l"], row["gf"], row["ga"], row["gd"],
                row["pts"], row["pts_per_mp"], row.get("xg"), row.get("xga"),
                row.get("xgd"), row.get("xgd_90"), row.get("attendance")
            ))
            stat_id = cur.fetchone()[0]
            stat_id_map[idx] = stat_id
            inserted += 1

            # Link the top scorer, if this row has one
            if "scorer_name" in row and pd_notna(row["scorer_name"]):
                role = random.choice(SCORER_ROLES)
                player_id = get_or_create_player(cur, player_cache, row["scorer_name"], role)
                cur.execute("""
                    INSERT INTO team_top_scorer (stat_id, player_id, goals)
                    VALUES (%s, %s, %s)
                """, (stat_id, player_id, row.get("scorer_goals") or 0))

            # Link the goalkeeper, if this row has one
            if "goalkeeper_name" in row and pd_notna(row["goalkeeper_name"]):
                player_id = get_or_create_player(cur, player_cache, row["goalkeeper_name"], "Goalkeeper")
                cur.execute("""
                    INSERT INTO team_goalkeeper (stat_id, player_id)
                    VALUES (%s, %s)
                """, (stat_id, player_id))

        # Record this run in the watermark, then commit everything together --
        # either the whole batch succeeds, or none of it does
        update_watermark(cur, inserted)
        conn.commit()
        logging.info(f"Load complete: {inserted} new rows inserted, {skipped} rows skipped (already existed)")
        print(f"Load complete: {inserted} inserted, {skipped} skipped")

    except Exception as e:
        # If anything above fails, undo the entire batch rather than
        # leaving a half-loaded, inconsistent database
        conn.rollback()
        logging.error(f"Load failed, rolled back: {e}")
        raise
    finally:
        cur.close()
        conn.close()


# Entry point for running the load stage directly, e.g. python -m pipeline.load
if __name__ == "__main__":
    from pipeline.extract import extract
    from pipeline.transform import transform
    from pipeline.quality import run_quality_checks

    # A separate connection is opened here specifically so transform()
    # can read/update the incremental synthetic-data watermark BEFORE
    # load() opens its own connection to do the actual inserting
    conn = get_connection()
    cur = conn.cursor()

    raw = extract()
    result = transform(raw, cur=cur, synthetic_batch_size=500)

    conn.commit()
    cur.close()
    conn.close()

    # Quality gate: the load only proceeds if every check passes
    checks = run_quality_checks(result["team_season_stats"])
    failed = [c for c in checks if not c.passed]
    if failed:
        print("Quality checks failed - aborting load:")
        for f in failed:
            print(f)
    else:
        load(result["team_season_stats"], result.get("top_scorers"), result.get("goalkeepers"))