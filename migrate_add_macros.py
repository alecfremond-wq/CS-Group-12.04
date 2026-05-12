"""
Migration — add macro columns to the recipes table.

Run this ONCE if your schema.sql doesn't already have protein_g / carbs_g / fat_g.
It's safe to run multiple times — ALTER TABLE is wrapped in try/except.

Usage:
    python migrate_add_macros.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "cooktogether.db"

COLUMNS = [
    ("protein_g", "REAL"),
    ("carbs_g",   "REAL"),
    ("fat_g",     "REAL"),
]

with sqlite3.connect(DB_PATH) as conn:
    for col, col_type in COLUMNS:
        try:
            conn.execute(f"ALTER TABLE recipes ADD COLUMN {col} {col_type}")
            conn.commit()
            print(f"✅ Added column: recipes.{col}")
        except sqlite3.OperationalError:
            print(f"ℹ️  Column already exists (skipped): recipes.{col}")

print("Done.")
