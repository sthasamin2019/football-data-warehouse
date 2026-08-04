# =====================================================================
# pipeline/run_migrations.py
#
# A small migration runner: reads every .sql file in sql/migrations/,
# in filename order (001_, 002_, 003_...), and executes each one
# against the OLTP database.
#
# This is the repeatable "set up the database" command for the
# project -- run it once on a fresh database and it builds the entire
# schema (tables, constraints, seed data) from scratch.
#
# NOTE: this runner stops at the first failure it hits (e.g. "table
# already exists" on a re-run) rather than skipping past it -- so on
# a database that already has some migrations applied, later files
# won't run unless earlier ones are handled first.
# =====================================================================

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Points to the sql/migrations folder relative to this file's location,
# regardless of what directory the script is run from
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "sql", "migrations")


def run_migrations():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    conn.autocommit = False
    cur = conn.cursor()

    # sorted() ensures files run in numeric/alphabetical order --
    # 001_create_leagues.sql before 002_create_teams.sql, etc. --
    # since later migrations often depend on tables created earlier
    files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql"))
    print("Starting migration run...\n")

    for filename in files:
        path = os.path.join(MIGRATIONS_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            sql = f.read()
        try:
            cur.execute(sql)
            conn.commit()
            print(f"Running: {filename} ... OK")
        except Exception as e:
            # If a migration fails (e.g. it was already applied in a
            # previous run), roll back just that one file's changes
            # and stop -- prevents partially-applied migrations
            conn.rollback()
            print(f"Running: {filename} ... FAILED")
            print(e)
            break

    cur.close()
    conn.close()
    print("\nAll migrations completed.")


# Entry point: python pipeline/run_migrations.py
if __name__ == "__main__":
    run_migrations()