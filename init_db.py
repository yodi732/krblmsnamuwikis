import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
DB_DIR = HERE / "instance"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "database.db"
SCHEMA_PATH = HERE / "schema.sql"

def main():
    if not SCHEMA_PATH.exists():
        print("schema.sql not found; nothing to initialize.")
        return
    with sqlite3.connect(DB_PATH) as conn:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    main()
