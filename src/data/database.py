"""
SQLite database interface for the CookTogether application

This module is the single point of contact between the application and its SQLite database. 
It handles three responsibilities:
 
1. INITIALISATION  — creates the database file and all tables on first run,
                         by executing the SQL defined in data/schema.sql.

2. MIGRATION       — safely upgrades older databases that are missing columns
                         or have outdated table definitions (e.g. a meal_plan table
                        that pre-dates the "Snacks" meal-type option). Migrations
                        run automatically every time the app starts.

3. QUERYING        — provides two thin helpers used everywhere else in the app:
                           • query_df()  → runs a SELECT and returns a DataFrame
                           • execute()   → runs INSERT / UPDATE / DELETE

Dependencies: 
 — sqlite3        (built-in, no install needed)
 — contextlib     (built-in, provides @contextmanager)
 — pathlib        (built-in, cross-platform file paths)
 — pandas         (pip install pandas)

Authors: Ines, Alec, Giulia

Source: Claude Sonnet 4.6 (see comments below)


"""


import sqlite3                                 # built-in Python module for SQLite
from contextlib import contextmanager          # lets us write a clean `with ...` helper
from pathlib import Path                       # clean way to work with file paths

import pandas as pd                            # turns SQL results into DataFrames


# Locate the project root by going up two levels from this file's location:
#   src/data/database.py  →  src/data  →  src  →  <project root>
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH     = _PROJECT_ROOT / "data" / "cooktogether.db"   # the SQLite database file
SCHEMA_PATH = _PROJECT_ROOT / "data" / "schema.sql"        # the SQL script that creates the tables

# \ begin code generated with Claude Sonnet 4.6
def _migrate(conn) -> None:
    """When a new column or table constraint is added to schema.sql, existing
    databases (e.g. on a teammate's machine, or on a cloud deployment) will
    not automatically gain that change. This function bridges the gap.

    Every operation here is safe to run multiple times. Either we use
    try/except to catch "column already exists" errors, or we use
    'CREATE ... IF NOT EXISTS'. This means _migrate() is called on every
    app startup with no side effects on an already-up-to-date database.
    """
    # Add columns that were introduced after the initial schema was created
    # try/except is needed because SQLite raises an error if the column already exists
    # This means the function is safe to call every time the app starts
    for column in ["username", "password_hash"]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass    # column already exists. Nothing to do

    # Add mealdb_id to recipes if it was added after a teammate's initial schema
    try:
        conn.execute("ALTER TABLE recipes ADD COLUMN mealdb_id TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass    # catches ALL OperationalErrors, not just column already exists

    # SQLite does not support UNIQUE constraints in ALTER TABLE
    # so we create a unique index separately to prevent duplicate usernames
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users (username)"
    )
    conn.commit()

    # Older databases created meal_plan without the "Snacks" option.
    # SQLite cannot edit CHECK constraints in place, so we rebuild the table.
    # The only way to change a constraint is to:
    #    1. Rename the old table to a temporary name.
    #    2. Create the new table with the correct definition.
    #    3. Copy all data from the old table into the new one.
    #    4. Drop the old table.

    # First, read the current table definition to check whether it already
    # includes 'Snacks'. sqlite_master is SQLite's internal catalogue of all
    # objects (tables, indexes, views) in the database
    meal_plan_sql_row = conn.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = 'meal_plan'
        """
    ).fetchone()
    meal_plan_sql = meal_plan_sql_row["sql"] if meal_plan_sql_row else ""

    if meal_plan_sql and "Snacks" not in meal_plan_sql:
        # The table exists but predates the Snacks option and rebuild it.
        # executescript() runs multiple SQL statements separated by semicolons
        # as a single atomic operation (all succeed or all are rolled back)
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
#\ end code generated with the help of Claude Sonnet 4.6

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
    """ Run a SELECT query and return the results as a pandas DataFrame
    The '?' placeholders are safely replaced by params, to prevents SQL injection
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params or ())


def execute(sql, params=None):
    """ Run an INSERT, UPDATE or DELETE statement
    
    The context manager commits and closes the connection automatically after this function returns
    """
    with get_connection() as conn:
        #'?' placeholders are replaced safely by sqlite3
        #Don't ever use string formatting here, because that would open the door to SQL injection.
        conn.execute(sql, params or ())
