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

SCORER_ROLES = ["Striker", "Forward", "Midfielder", "Winger"]


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def get_or_create_league(cur, cache, league_name):
    if league_name in cache:
        return cache[league_name]
    cur.execute("SELECT league_id FROM leagues WHERE league_name = %s", (league_name,))
    row = cur.fetchone()
    if row:
        cache[league_name] = row[0]
        return row[0]
    raise ValueError(f"League not found (should be pre-seeded): {league_name}")


def get_or_create_season(cur, cache, season_label):
    if season_label in cache:
        return cache[season_label]
    cur.execute("SELECT season_id FROM seasons WHERE season_label = %s", (season_label,))
    row = cur.fetchone()
    if row:
        cache[season_label] = row[0]
        return row[0]
    raise ValueError(f"Season not found (should be pre-seeded): {season_label}")


def get_or_create_team(cur, cache, team_name, league_id):
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
    cur.execute("SELECT last_run_at, last_row_count FROM pipeline_watermark WHERE pipeline_name=%s", (pipeline_name,))
    row = cur.fetchone()
    return row if row else (None, 0)


def update_watermark(cur, inserted_count, pipeline_name="football_etl"):
    cur.execute("""
        UPDATE pipeline_watermark
        SET last_run_at = NOW(), last_row_count = last_row_count + %s
        WHERE pipeline_name = %s
    """, (inserted_count, pipeline_name))


def pd_notna(value):
    return pd.notna(value)


def load(stats_df, top_scorers_df=None, goalkeepers_df=None):
    conn = get_connection()
    conn.autocommit = False
    cur = conn.cursor()

    league_cache, season_cache, team_cache, player_cache = {}, {}, {}, {}
    stat_id_map = {}
    inserted, skipped = 0, 0

    try:
        for idx, row in stats_df.iterrows():
            league_id = get_or_create_league(cur, league_cache, row["league_name"])
            season_id = get_or_create_season(cur, season_cache, row["season_label"])
            team_id = get_or_create_team(cur, team_cache, row["team_name"], league_id)

            cur.execute("""
                SELECT stat_id FROM team_season_stats
                WHERE team_id = %s AND season_id = %s AND stats_date = %s
            """, (team_id, season_id, row["stats_date"]))
            existing = cur.fetchone()
            if existing:
                stat_id_map[idx] = existing[0]
                skipped += 1
                continue

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

            if "scorer_name" in row and pd_notna(row["scorer_name"]):
                role = random.choice(SCORER_ROLES)
                player_id = get_or_create_player(cur, player_cache, row["scorer_name"], role)
                cur.execute("""
                    INSERT INTO team_top_scorer (stat_id, player_id, goals)
                    VALUES (%s, %s, %s)
                """, (stat_id, player_id, row.get("scorer_goals") or 0))

            if "goalkeeper_name" in row and pd_notna(row["goalkeeper_name"]):
                player_id = get_or_create_player(cur, player_cache, row["goalkeeper_name"], "Goalkeeper")
                cur.execute("""
                    INSERT INTO team_goalkeeper (stat_id, player_id)
                    VALUES (%s, %s)
                """, (stat_id, player_id))

        update_watermark(cur, inserted)
        conn.commit()
        logging.info(f"Load complete: {inserted} new rows inserted, {skipped} rows skipped (already existed)")
        print(f"Load complete: {inserted} inserted, {skipped} skipped")

    except Exception as e:
        conn.rollback()
        logging.error(f"Load failed, rolled back: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    from pipeline.extract import extract
    from pipeline.transform import transform
    from pipeline.quality import run_quality_checks

    raw = extract()
    result = transform(raw)

    checks = run_quality_checks(result["team_season_stats"])
    failed = [c for c in checks if not c.passed]
    if failed:
        print("Quality checks failed - aborting load:")
        for f in failed:
            print(f)
    else:
        load(result["team_season_stats"], result.get("top_scorers"), result.get("goalkeepers"))
