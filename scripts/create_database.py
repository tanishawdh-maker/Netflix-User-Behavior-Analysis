import csv
import sqlite3
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
SQL_DIR = ROOT_DIR / "sql"
DB_PATH = DATA_DIR / "netflix_analysis.db"


def load_csv(connection, table_name, csv_path):
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        columns = reader.fieldnames

    placeholders = ", ".join(["?"] * len(columns))
    column_names = ", ".join(columns)
    values = [[row[column] for column in columns] for row in rows]

    connection.executemany(
        f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})",
        values,
    )
    print(f"Loaded {len(rows):,} rows into {table_name}")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON;")
    schema_sql = (SQL_DIR / "01_schema.sql").read_text(encoding="utf-8")
    connection.executescript(schema_sql)

    load_csv(connection, "users", DATA_DIR / "users.csv")
    load_csv(connection, "shows", DATA_DIR / "shows.csv")
    load_csv(connection, "watch_history", DATA_DIR / "watch_history.csv")

    errors = connection.execute("PRAGMA foreign_key_check;").fetchall()
    if errors:
        raise RuntimeError(f"Foreign key errors found: {errors}")

    connection.commit()
    connection.close()
    print(f"Created SQLite database: {DB_PATH}")


if __name__ == "__main__":
    main()
