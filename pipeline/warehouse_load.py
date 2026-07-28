
import os
import logging
import psycopg2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    filename=os.path.join("logs", "warehouse_load.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_oltp_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def get_dwh_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DWH_DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def get_or_create_dim_team(dwh_cur, cache, team_name, league_name, country_code):
    key = (team_name, league_name)
    if key in cache:
        return cache[key]
    dwh_cur.execute("SELECT team_key FROM dim_team WHERE team_name=%s AND league_name=%s",
                     (team_name, league_name))
    row = dwh_cur.fetchone()
    if row:
        cache[key] = row[0]
        return row[0]
    dwh_cur.execute("""
        INSERT INTO dim_team (team_name, league_name, country_code)
        VALUES (%s,%s,%s) RETURNING team_key
    """, (team_name, league_name, country_code))
    new_key = dwh_cur.fetchone()[0]
    cache[key] = new_key
    return new_key


def get_or_create_dim_season(dwh_cur, cache, season_label, start_date, end_date):
    if season_label in cache:
        return cache[season_label]
    dwh_cur.execute("SELECT season_key FROM dim_season WHERE season_label=%s", (season_label,))
    row = dwh_cur.fetchone()
    if row:
        cache[season_label] = row[0]
        return row[0]
    dwh_cur.execute("""
        INSERT INTO dim_season (season_label, start_date, end_date)
        VALUES (%s,%s,%s) RETURNING season_key
    """, (season_label, start_date, end_date))
    new_key = dwh_cur.fetchone()[0]
    cache[season_label] = new_key
    return new_key


def get_or_create_dim_player(dwh_cur, cache, player_name, role):
    key = (player_name, role)
    if key in cache:
        return cache[key]
    dwh_cur.execute("SELECT player_key FROM dim_player WHERE player_name=%s AND role=%s",
                     (player_name, role))
    row = dwh_cur.fetchone()
    if row:
        cache[key] = row[0]
        return row[0]
    dwh_cur.execute("""
        INSERT INTO dim_player (player_name, role)
        VALUES (%s,%s) RETURNING player_key
    """, (player_name, role))
    new_key = dwh_cur.fetchone()[0]
    cache[key] = new_key
    return new_key


def get_date_key(stats_date):
    return int(stats_date.strftime("%Y%m%d"))


def run_warehouse_etl():
    oltp_conn = get_oltp_connection()
    dwh_conn = get_dwh_connection()
    oltp_cur = oltp_conn.cursor()
    dwh_cur = dwh_conn.cursor()

    team_cache, season_cache, player_cache = {}, {}, {}
    inserted, skipped = 0, 0

    try:
        oltp_cur.execute("""
            SELECT
                tss.stat_id, t.team_name, l.league_name, l.country_code,
                s.season_label, s.start_date, s.end_date, tss.stats_date,
                tss.mp, tss.w, tss.d, tss.l, tss.gf, tss.ga, tss.gd,
                tss.pts, tss.pts_per_mp, tss.xg, tss.xga, tss.xgd, tss.xgd_90,
                tss.attendance,
                sp.player_name AS scorer_name, sp.role AS scorer_role,
                gp.player_name AS keeper_name, gp.role AS keeper_role
            FROM team_season_stats tss
            JOIN teams t ON tss.team_id = t.team_id
            JOIN leagues l ON t.league_id = l.league_id
            JOIN seasons s ON tss.season_id = s.season_id
            LEFT JOIN LATERAL (
                SELECT player_id FROM team_top_scorer
                WHERE stat_id = tss.stat_id ORDER BY id LIMIT 1
            ) ts ON true
            LEFT JOIN players sp ON ts.player_id = sp.player_id
            LEFT JOIN LATERAL (
                SELECT player_id FROM team_goalkeeper
                WHERE stat_id = tss.stat_id ORDER BY id LIMIT 1
            ) tg ON true
            LEFT JOIN players gp ON tg.player_id = gp.player_id
        """)
        rows = oltp_cur.fetchall()
        logging.info(f"Fetched {len(rows)} rows from OLTP for warehouse load")

        for row in rows:
            (stat_id, team_name, league_name, country_code, season_label,
             start_date, end_date, stats_date, mp, w, d, l, gf, ga, gd,
             pts, pts_per_mp, xg, xga, xgd, xgd_90, attendance,
             scorer_name, scorer_role, keeper_name, keeper_role) = row

            team_key = get_or_create_dim_team(dwh_cur, team_cache, team_name, league_name, country_code)
            season_key = get_or_create_dim_season(dwh_cur, season_cache, season_label, start_date, end_date)
            date_key = get_date_key(stats_date)

            top_scorer_key = (get_or_create_dim_player(dwh_cur, player_cache, scorer_name, scorer_role)
                               if scorer_name else None)
            goalkeeper_key = (get_or_create_dim_player(dwh_cur, player_cache, keeper_name, keeper_role)
                               if keeper_name else None)

            dwh_cur.execute("""
                SELECT fact_id FROM fact_team_season_performance
                WHERE team_key=%s AND season_key=%s AND date_key=%s
            """, (team_key, season_key, date_key))
            if dwh_cur.fetchone():
                skipped += 1
                continue

            dwh_cur.execute("""
                INSERT INTO fact_team_season_performance
                (team_key, season_key, date_key, top_scorer_key, goalkeeper_key,
                 mp, w, d, l, gf, ga, gd, pts, pts_per_mp, xg, xga, xgd, xgd_90,
                 attendance, source)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (team_key, season_key, date_key, top_scorer_key, goalkeeper_key,
                  mp, w, d, l, gf, ga, gd, pts, pts_per_mp, xg, xga, xgd, xgd_90,
                  attendance, "oltp"))
            inserted += 1

        dwh_conn.commit()
        logging.info(f"Warehouse ETL complete: {inserted} inserted, {skipped} skipped")
        print(f"Warehouse ETL complete: {inserted} inserted, {skipped} skipped")

    except Exception as e:
        dwh_conn.rollback()
        logging.error(f"Warehouse ETL failed, rolled back: {e}")
        raise
    finally:
        oltp_cur.close()
        dwh_cur.close()
        oltp_conn.close()
        dwh_conn.close()


if __name__ == "__main__":

    run_warehouse_etl()
