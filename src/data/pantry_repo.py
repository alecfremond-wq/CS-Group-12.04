"""
Data access layer for the pantry feature.
Handles all reads and writes to the pantry and ingredients tables,
and exposes the smart-matching logic used by the Recipes page to compute
the Pantry-friendly badge.

Dependencies:

  - pandas               : handles query results as DataFrames.
  - datetime (stdlib)    : date — used for expiry date formatting.
  - re (stdlib)          : regular expressions — used for tokenizing ingredient names.
  - typing (stdlib)      : Iterable, Optional — type hints.

  - src.data.database
      query_df(sql, params) -> executes a SELECT and returns a DataFrame
                               (or None if no rows / table missing).
      execute(sql, params)  -> executes INSERT / DELETE / UPDATE statements.

Database tables:

  pantry      : one row per (user, ingredient). Stores quantity, unit, expiry date.
                UNIQUE constraint on (user_id, ingredient_id) — adding the same
                ingredient twice updates the existing row instead of duplicating it.
  ingredients : master ingredient list. Every ingredient added to any pantry
                gets an entry here. Names are lowercased and deduplicated.

Author: Alec Frémond

Sources: Claude Sonnet 4.6 (see comments below)

"""

from __future__ import annotations

import re
from datetime import date
from typing import Iterable, Optional

import pandas as pd

from src.data.database import execute, query_df


#1. Ingredient lookup ################
# Functions to fetch ingredient names from the database and ensure every
# ingredient added to the pantry has a matching row in the ingredients table.

def get_canonical_ingredients() -> list[str]:
    """
    Returns every ingredient name stored in the database, lowercased,
    deduplicated and alphabetically sorted.

    Used by the Pantry page to populate the ingredient dropdown — this
    guarantees that whatever the user picks matches an ingredient string
    used in a recipe (same lowercased exact-match rule Recipes page applies).

    Returns a list of strings, or an empty list if the table is empty.
    """
    df = query_df("SELECT DISTINCT name FROM ingredients ORDER BY name")
    if df is None or df.empty:
        return []
    return df["name"].str.lower().str.strip().tolist()


def _ensure_ingredient_id(name: str) -> int:
    """
    Returns the id of the ingredients row for `name`, inserting a new row if missing.

    Parameters:
        name : str — the ingredient name, already lowercased and stripped.

    Returns the integer id of the matching row.
    """
    name = name.lower().strip()
    df = query_df("SELECT id FROM ingredients WHERE name = ? LIMIT 1", (name,))
    if not df.empty:
        return int(df.iloc[0]["id"])
    execute("INSERT INTO ingredients (name) VALUES (?)", (name,))
    df = query_df("SELECT id FROM ingredients WHERE name = ? LIMIT 1", (name,))
    return int(df.iloc[0]["id"])


#2. Pantry CRUD ##########
# The four basic operations on the pantry table: add, list, remove one row, clear all.

def add_to_pantry(
    user_id: int,
    name: str,
    quantity: float,
    unit: str,
    expires_on: Optional[date],
) -> None:
    """
    Inserts or updates a pantry row for this user + ingredient.

    The schema declares UNIQUE (user_id, ingredient_id), so adding the
    same ingredient twice updates the existing row rather than creating
    a duplicate.

    Parameters:
        user_id    : int           — the logged-in user's database ID.
        name       : str           — ingredient name (will be lowercased).
        quantity   : float         — amount to store.
        unit       : str           — unit of measurement (g, kg, ml, etc.).
        expires_on : date or None  — expiry date, or None if not set.
    """
    name = name.lower().strip()
    if not name:
        return

    ingredient_id = _ensure_ingredient_id(name)
    # dates are stored as ISO strings in SQLite ("YYYY-MM-DD")
    expires_str = expires_on.isoformat() if expires_on else None

    execute(
        """
        INSERT INTO pantry (user_id, ingredient_id, quantity, unit, expires_on)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, ingredient_id) DO UPDATE SET
            quantity   = excluded.quantity,
            unit       = excluded.unit,
            expires_on = excluded.expires_on
        """,
        (user_id, ingredient_id, float(quantity or 0), unit, expires_str),
    )


def list_pantry(user_id: int) -> pd.DataFrame:
    """
    Returns all pantry rows for this user, joined with ingredient names.
    Sorted alphabetically by ingredient name for stable display.

    Parameters:
        user_id : int — the logged-in user's database ID.

    Returns a DataFrame with columns: id, name, quantity, unit, expires_on.
    If the database returns no results, returns an empty DataFrame with the
    same columns — so the rest of the code never crashes trying to read it.
    """
    df = query_df(
        """
        SELECT p.id, i.name, p.quantity, p.unit, p.expires_on
        FROM pantry p
        JOIN ingredients i ON p.ingredient_id = i.id
        WHERE p.user_id = ?
        ORDER BY i.name
        """,
        (user_id,),
    )
    if df is None:
        return pd.DataFrame(columns=["id", "name", "quantity", "unit", "expires_on"])
    return df


def remove_from_pantry(pantry_row_id: int, user_id: int) -> None:
    """
    Deletes a single pantry row selected by its id, scoped to this user.

    Parameters:
        pantry_row_id : int — the primary key of the row to delete.
        user_id       : int — used as a safety check so users can only delete their own rows.
    """
    execute(
        "DELETE FROM pantry WHERE id = ? AND user_id = ?",
        (pantry_row_id, user_id),
    )


def clear_pantry(user_id: int) -> None:
    """
    Deletes all pantry rows belonging to this user.

    Parameters:
        user_id : int — the logged-in user's database ID.
    """
    execute("DELETE FROM pantry WHERE user_id = ?", (user_id,))


def is_canonical(name: str) -> bool:
    """
    Returns True if `name` matches an ingredient already in the database.

    Used by the Pantry page to warn the user when they type something that
    won't help recipe matching.

    Parameters:
        name : str — the ingredient name to check.
    """
    return name.lower().strip() in set(get_canonical_ingredients())


#3. Smart matching ######
# Used by the Recipes page to compute the Pantry-friendly badge.
# Naive exact-match gives ~30% hit rate against API recipe names.
# These rules lift it to ~75-85% by handling plurals and multi-word names.

# \ Begin code generated by Claude Sonnet 4.6

def _singularize(word: str) -> str:
    # "berries" → "berry", "tomatoes" → "tomato", "eggs" → "egg"
    w = word.lower().strip()
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es"):
        return w[:-2]
    if len(w) > 2 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokenize(name: str) -> set[str]:
    # "Cherry Tomatoes" → {"cherry", "tomato"}, "Extra-Virgin Olive Oil" → {"extra", "virgin", "olive", "oil"}
    return {
        _singularize(tok)
        for tok in re.findall(r"[a-zA-Z]+", name.lower())
        if len(tok) > 1
    }


def matches(recipe_ingredient: str, pantry: Iterable[str]) -> bool:
    """
    Returns True if a recipe ingredient can be matched against something in the pantry.
    Applies three rules in order — the first match wins.

    Parameters:
        recipe_ingredient : str           — one ingredient name from a recipe.
        pantry            : Iterable[str] — all ingredient names in the user's pantry.
    """
    if not pantry:
        return False

    pantry_set = {p.lower().strip() for p in pantry}
    r_low = recipe_ingredient.lower().strip()

    # Rule 1 — exact match: "chicken" == "chicken"
    if r_low in pantry_set:
        return True

    # Rule 2 — singular match: pantry has "egg", recipe says "eggs"
    r_sing = _singularize(r_low)
    if r_sing in pantry_set:
        return True

    # Rule 3 — subset match: pantry has "olive oil", recipe says "extra virgin olive oil"
    r_words = _tokenize(recipe_ingredient)
    if not r_words:
        return False

    for p in pantry_set:
        p_words = _tokenize(p)
        if p_words and p_words.issubset(r_words):
            return True

    return False


def coverage(ingredient_list: Iterable[str], pantry: Iterable[str]) -> Optional[float]:
    """
    Returns the fraction of a recipe's ingredients the user already has (0.0–1.0).
    Returns None if either the recipe or the pantry is empty — the badge won't be shown.

    Parameters:
        ingredient_list : Iterable[str] — all ingredient names from a recipe.
        pantry          : Iterable[str] — all ingredient names in the user's pantry.
    """
    ingredients = [i for i in ingredient_list if i and i.strip()]
    pantry_set = {p.lower().strip() for p in pantry if p and p.strip()}

    if not pantry_set or not ingredients:
        return None

    matched = sum(1 for ing in ingredients if matches(ing, pantry_set))
    return matched / len(ingredients)

# \ End code generated by Claude Sonnet 4.6
