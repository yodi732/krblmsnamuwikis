import sqlite3, os

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "instance", "database.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Database initialized at", DB_PATH)

if __name__ == "__main__":
    init_db()
