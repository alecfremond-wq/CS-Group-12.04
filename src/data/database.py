# ============================================================================
#  database.py  —  thin wrapper around SQLite
# ----------------------------------------------------------------------------


import sqlite3                                 # built-in Python module for SQLite
from contextlib import contextmanager          # lets us write a clean `with ...` helper
from pathlib import Path                       # clean way to work with file paths

import pandas as pd                            # turns SQL results into DataFrames


# Locate the project root by going up two levels from this file's location:
#   src/data/database.py  →  src/data  →  src  →  <project root>
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH     = _PROJECT_ROOT / "data" / "cooktogether.db"   # the SQLite database file
SCHEMA_PATH = _PROJECT_ROOT / "data" / "schema.sql"        # the SQL script that creates the tables


def _migrate(conn) -> None:
    # Add columns that were introduced after the initial schema was created
    # try/except is needed because SQLite raises an error if the column already exists
    # This means the function is safe to call every time the app starts
    for column in ["username", "password_hash"]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass    # column already exists — nothing to do

    # Add mealdb_id to recipes if it was added after a teammate's initial schema
    try:
        conn.execute("ALTER TABLE recipes ADD COLUMN mealdb_id TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass    # column already exists

    # SQLite does not support UNIQUE constraints in ALTER TABLE
    # so we create a unique index separately to prevent duplicate usernames
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users (username)"
    )
    conn.commit()

    # Older databases created meal_plan without the "Snacks" option.
    # SQLite cannot edit CHECK constraints in place, so we rebuild the table.
    meal_plan_sql_row = conn.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = 'meal_plan'
        """
    ).fetchone()
    meal_plan_sql = meal_plan_sql_row["sql"] if meal_plan_sql_row else ""

    if meal_plan_sql and "Snacks" not in meal_plan_sql:
        conn.executescript(
            """
            ALTER TABLE meal_plan RENAME TO meal_plan_old;

            CREATE TABLE meal_plan (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                meal_date   TEXT    NOT NULL,
                meal_type   TEXT    NOT NULL
                                CHECK(meal_type IN ('Breakfast','Lunch','Dinner','Snacks')),
                recipe_id   INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
                UNIQUE (user_id, meal_date, meal_type)
            );

            INSERT INTO meal_plan (id, user_id, meal_date, meal_type, recipe_id)
            SELECT id, user_id, meal_date, meal_type, recipe_id
            FROM meal_plan_old;

            DROP TABLE meal_plan_old;

            CREATE INDEX IF NOT EXISTS idx_meal_plan_user_date
                ON meal_plan (user_id, meal_date);
            """
        )
        conn.commit()


def init_db():
    """Create the database file and its tables if they don't exist yet.

    Safe to call every time the app starts — the SQL in schema.sql uses
    'CREATE TABLE IF NOT EXISTS', so existing tables are never overwritten.

    Call this ONCE at app startup (in app.py), not on every query.
    """
    # Create the data/ folder if it doesn't exist yet
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        if SCHEMA_PATH.exists():
            # Run the full schema script to create all tables
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        # Then apply any migrations needed for columns added after the initial schema
        _migrate(conn)


@contextmanager
def get_connection():
    """Open a SQLite connection, yield it, then always close it when done.

    NOTE: do NOT call executescript() here. Schema initialisation belongs
    in init_db() only. Calling executescript() on every connection caused
    sqlite3.OperationalError on Streamlit Cloud.
    """
    conn = sqlite3.connect(DB_PATH)
    # row_factory lets us access columns by name (row["id"]) instead of index (row[0])
    conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()   # save any changes made during the with block

    finally:
        conn.close()    # always close, even if an error occurred


def query_df(sql, params=None):
    # Run a SELECT query and return the results as a pandas DataFrame
    # The '?' placeholders are safely replaced by params — prevents SQL injection
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params or ())


def execute(sql, params=None):
    # Run an INSERT, UPDATE or DELETE statement
    # The context manager commits and closes the connection automatically
    with get_connection() as conn:
        conn.execute(sql, params or ())
