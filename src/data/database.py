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

import sqlite3                                 # built-in Python module for SQLite databases
from contextlib import contextmanager          # lets us write a `with ...` helper for connections
from pathlib import Path                       # object-oriented way to work with file paths

import pandas as pd                            # pandas is great for turning SQL results into DataFrames


# --- locate the database file ---------------------------------------------
# __file__ is a special variable that holds the path to THIS .py file.
# .resolve() makes it an absolute path. .parents[2] goes up two folders:
#   src/data/database.py  ->  src/data  ->  src  ->  <project root>
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Build paths using '/' (Path supports this operator to join folders).
DB_PATH = _PROJECT_ROOT / "data" / "cooktogether.db"    # the actual .db file
SCHEMA_PATH = _PROJECT_ROOT / "data" / "schema.sql"     # the SQL script that creates the tables


def _migrate(conn) -> None:
    # Add login columns to any DB created before the login feature was added.
    # try/except is needed because SQLite errors if the column already exists.
    for column in ["username", "password_hash"]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass

    # Add mealdb_id to recipes if it doesn't exist yet
    try:
        conn.execute("ALTER TABLE recipes ADD COLUMN mealdb_id TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    # UNIQUE can't be set via ALTER TABLE in SQLite — we use an index instead
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
    'CREATE TABLE IF NOT EXISTS', so existing tables aren't overwritten.

    Call this ONCE at app startup (e.g. in app.py or main.py), not on
    every query. Running executescript() on every connection caused
    sqlite3.OperationalError on Streamlit Cloud.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        if SCHEMA_PATH.exists():
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _migrate(conn)


# The @contextmanager decorator turns this function into something you can
# use inside a `with ...:` block — like a recipe that says "set up, hand
# over, then always clean up even if there's an error".
@contextmanager
def get_connection():
    """Open a SQLite connection and always close it when done.

    NOTE: do NOT call executescript() here. Schema initialisation belongs
    in init_db() only. Calling executescript() on every connection caused
    sqlite3.OperationalError on Streamlit Cloud because executescript()
    opens an implicit transaction that conflicts with pd.read_sql_query().
    """

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()

    finally:
        conn.close()


def query_df(sql, params=None):
    """Run a SELECT and return the results as a pandas DataFrame.

    Example:
        df = query_df("SELECT * FROM recipes WHERE cuisine = ?", ("Italian",))
    """
    # Open a connection, pass it to pandas, close it when done.
    with get_connection() as conn:
        # `params or ()` means: use the given params, or an empty tuple if None.
        # The '?' placeholders in the SQL are safely replaced with the params
        # — this prevents SQL injection bugs.
        return pd.read_sql_query(sql, conn, params=params or ())


def execute(sql, params=None):
    """Run an INSERT, UPDATE or DELETE statement.

    Example:
        execute("INSERT INTO users (name, diet) VALUES (?, ?)", ("Alec", "vegan"))
    """
    with get_connection() as conn:                # open a connection
        conn.execute(sql, params or ())           # run the SQL with its parameters
        # The context manager (above) will commit and close automatically.
