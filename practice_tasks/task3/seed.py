"""Заполнить SQLite тестовыми строками (по умолчанию 1000 id)."""
import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.environ.get("SQLITE_PATH", os.path.join(DATA_DIR, "app.db"))
N = int(os.environ.get("SEED_COUNT", "1000"))


def main() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    conn.executemany(
        "INSERT INTO items (id, value) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET value = excluded.value",
        [(i, f"seed-{i}") for i in range(1, N + 1)],
    )
    conn.commit()
    conn.close()
    print(f"seeded {N} rows -> {DB_PATH}")


if __name__ == "__main__":
    main()
