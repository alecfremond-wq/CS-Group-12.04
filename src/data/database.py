# ============================================================================
#  database.py  —  thin wrapper around SQLite
# ----------------------------------------------------------------------------
#  This file is the ONLY place in the project that talks to the database
#  directly. Every other file calls `query_df(...)` or `execute(...)` from
#  here. That way, if we ever switch to a different database (Postgres, etc.)
#  we only have to change this one file.
#
#  We use SQLite because:
#    * it's built into Python (no installation needed on anyone's laptop),
#    * it stores the whole database in a single file (data/cooktogether.db),
#    * it covers grading requirement #2 ("data provided via a database").
# ============================================================================
#  AI-ASSISTED AUTHORSHIP: scaffold drafted with Anthropic Claude (04/2026),
#  reviewed by Group 12.04. See README.md.
# ============================================================================

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
