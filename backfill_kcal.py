"""
backfill_kcal.py — one-time script to fix recipes already in the DB
that were saved from TheMealDB and have kcal_per_serv = NULL.

Run once from the project root:
    python backfill_kcal.py

It reads every recipe with NULL kcal_per_serv, queries Spoonacular by
title, and writes the result back. Recipes that Spoonacular can't match
are left at NULL (the user can override them manually in Nutrition Analytics).
"""

import os
import sys
import sqlite3
import requests
import time

# ── Config ─────────────────────────────────────────────────────────────────────
# Adjust DB_PATH if your SQLite file lives elsewhere.
DB_PATH = os.path.join(os.path.dirname(__file__), "cooktogether.db")

# Read the Spoonacular key the same way Streamlit does (via .streamlit/secrets.toml)
# If you prefer, just hard-code it here temporarily:
#   SPOONACULAR_KEY = "your_key_here"
try:
    import toml
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    SPOONACULAR_KEY = toml.load(secrets_path)["SPOONACULAR_API_KEY"]
except Exception:
    SPOONACULAR_KEY = os.getenv("SPOONACULAR_API_KEY", "")

if not SPOONACULAR_KEY:
    print("ERROR: Spoonacular API key not found.")
    print("Set SPOONACULAR_API_KEY env var or check .streamlit/secrets.toml")
    sys.exit(1)

# ── Helpers ────────────────────────────────────────────────────────────────────

def fetch_kcal(title: str) -> int | None:
    """Ask Spoonacular for the calorie count of a recipe by title."""
    try:
        resp = requests.get(
            "https://api.spoonacular.com/recipes/complexSearch",
            params={
                "apiKey": SPOONACULAR_KEY,
                "query": title,
                "number": 1,
                "addRecipeNutrition": True,
            },
            timeout=20,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None
        nutrients = results[0].get("nutrition", {}).get("nutrients", [])
        return next(
            (int(n["amount"]) for n in nutrients if n.get("name") == "Calories"),
            None,
        )
    except Exception as e:
        print(f"  ⚠️  API error for '{title}': {e}")
        return None


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: DB not found at {DB_PATH}")
        print("Edit DB_PATH at the top of this script to point to your SQLite file.")
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    rows = cur.execute(
        "SELECT id, title FROM recipes WHERE kcal_per_serv IS NULL ORDER BY id"
    ).fetchall()

    if not rows:
        print("✅ No recipes with NULL kcal_per_serv — nothing to do.")
        return

    print(f"Found {len(rows)} recipe(s) with missing kcal. Fetching from Spoonacular...\n")

    updated = 0
    not_found = 0

    for recipe_id, title in rows:
        print(f"  [{recipe_id}] {title} ... ", end="", flush=True)
        kcal = fetch_kcal(title)

        if kcal is not None:
            cur.execute(
                "UPDATE recipes SET kcal_per_serv = ? WHERE id = ?",
                (kcal, recipe_id),
            )
            con.commit()
            print(f"{kcal} kcal ✅")
            updated += 1
        else:
            print("not found ⚠️")
            not_found += 1

        # Be polite to the API — 1 request/second stays within the free tier
        time.sleep(1)

    con.close()

    print(f"\nDone. Updated: {updated} | Not found: {not_found}")
    if not_found:
        print("Recipes not found can be edited manually in Nutrition Analytics (Edit panel).")


if __name__ == "__main__":
    main()
