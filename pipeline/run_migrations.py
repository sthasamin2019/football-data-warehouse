import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

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
            conn.rollback()
            print(f"Running: {filename} ... FAILED")
            print(e)
            break

    cur.close()
    conn.close()
    print("\nAll migrations completed.")

if __name__ == "__main__":
    run_migrations()