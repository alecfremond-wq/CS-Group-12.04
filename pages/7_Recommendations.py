"""
Recommendations — the machine-learning feature.
Owner: <assign on Apr 22>
Grading coverage:
    * Req. 5 (ML — content-based k-NN recommender)
    * Req. 3 (visualisation — match score bars)
"""
import re
import concurrent.futures

import pandas as pd
import streamlit as st

from src.components.ui import page_header
from src.data.api_client import (
    extract_ingredients_from_meal,
    filter_by_cuisine,
    get_meal_by_id,
)
from src.models.recommender import Recommender
from src.utils.session import init_session_state, require_profile


# ── Ingredient cleaning ───────────────────────────────────────────────────────

def _strip_measures(ingredient: str) -> str:
    s = ingredient.strip()
    s = re.sub(r"^(to serve|juice of|zest of|handful of|a pinch of)\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^[\d\s½¼¾⅓⅔⅛./-]+x?\s*", "", s)
    s = re.sub(r"^\d+\s*(g|kg|ml|l|oz|lbs?)\s+", "", s, flags=re.IGNORECASE)
    units = (
        r"^(cups?|tbsp?|tsp?|tablespoons?|teaspoons?|grams?|g|kg|oz|lbs?|"
        r"pounds?|ml|liters?|litres?|cloves?|slices?|pieces?|pinch|handful|"
        r"bunch|cans?|large|medium|small|whole|finely|chopped|shredded|"
        r"sliced|diced|minced|fresh|dried|ground|packed)\s+"
    )
    s = re.sub(units, "", s, flags=re.IGNORECASE)
    return s.strip().lower()


def _clean_ingredients(raw: list[str]) -> list[str]:
    return [s for s in (_strip_measures(i) for i in raw) if len(s) > 1]


# ── Time / difficulty helpers ─────────────────────────────────────────────────

def _estimate_time(instructions: str) -> int:
    words = len((instructions or "").split())
    if words < 80:   return 15
    if words < 200:  return 30
    if words < 400:  return 45
    return 60


def _difficulty_from_time(minutes: int | None) -> str:
    if minutes is None: return "Medium"
    if minutes <= 20:   return "Easy"
    if minutes <= 45:   return "Medium"
    return "Hard"


# ── Constants ─────────────────────────────────────────────────────────────────

_MEALDB_CUISINES     = ["Italian", "Mexican", "Indian", "Japanese", "French",
                        "Chinese", "Thai", "American", "British", "Greek"]
_MEALDB_PER_CUISINE  = 4


# ── Recipe loader (parallel HTTP, properly cached) ────────────────────────────

@st.cache_data(ttl=60 * 60, show_spinner=False)
def _load_mealdb_recipes() -> list[dict]:
    """Fetch MealDB recipes using parallel HTTP calls instead of sequential ones.

    Previously this made 10 × 4 = 40 sequential requests (one per stub).
    Now all get_meal_by_id calls run concurrently — wall-clock time drops
    from ~40s to roughly the time of a single slow request (~2–3s).
    """
    # Step 1: collect all stubs (one request per cuisine, sequential — fast)
    all_stubs: list[tuple[str, str]] = []   # (cuisine, idMeal)
    for cuisine in _MEALDB_CUISINES:
        stubs = filter_by_cuisine(cuisine)[:_MEALDB_PER_CUISINE]
        for stub in stubs:
            all_stubs.append((cuisine, stub["idMeal"]))

    # Step 2: fetch all full meals in parallel
    def fetch(cuisine_and_id: tuple[str, str]) -> tuple[str, dict | None]:
        cuisine, meal_id = cuisine_and_id
        return cuisine, get_meal_by_id(meal_id)

    meals: list[tuple[str, dict | None]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        meals = list(pool.map(fetch, all_stubs))

    # Step 3: normalise into rows
    rows = []
    for recipe_id, (cuisine, meal) in enumerate(meals, start=1):
        if not meal:
            continue
        ingredients  = _clean_ingredients(extract_ingredients_from_meal(meal))
        instructions = meal.get("strInstructions", "")
        time_min     = _estimate_time(instructions)
        rows.append({
            "id":           recipe_id,
            "title":        meal.get("strMeal", ""),
            "ingredients":  ingredients,
            "calories":     None,
            "time_minutes": time_min,
            "difficulty":   _difficulty_from_time(time_min),
            "country":      meal.get("strArea", cuisine),
        })
    return rows


def load_all_recipes() -> pd.DataFrame:
    """Return the recipe catalogue, cached in session_state after first load."""
    CACHE_KEY = "rec_recipes_df_v5"

    # Clear stale cache versions
    for k in [k for k in st.session_state if k.startswith("rec_recipes_df_") and k != CACHE_KEY]:
        del st.session_state[k]

    if CACHE_KEY not in st.session_state:
        rows = _load_mealdb_recipes()
        df   = pd.DataFrame(rows)
        df   = df.drop_duplicates(subset="title", keep="first").reset_index(drop=True)
        df["id"] = range(1, len(df) + 1)
        st.session_state[CACHE_KEY] = df

    return st.session_state[CACHE_KEY]


# ── App init ──────────────────────────────────────────────────────────────────

init_session_state()
require_profile()
page_header("✨ Recommendations", "Recipes picked just for you by a k-NN model.")


# ── Load catalogue (shown once, then served from cache) ───────────────────────

with st.spinner("Loading recipe catalogue…"):
    recipes_df = load_all_recipes()


# ── Build taste profile inputs ────────────────────────────────────────────────

wishlist   = st.session_state.get("wishlist", [])
history_df = pd.DataFrame(st.session_state.get("cooking_history", []))

wishlist_ids = [
    w["local_id"] for w in wishlist
    if isinstance(w, dict) and w.get("local_id") is not None
]
liked_ingredients = [
    _clean_ingredients(w["ingredients"])
    for w in wishlist
    if isinstance(w, dict) and w.get("ingredients")
]

total_saved = len(wishlist)
if total_saved == 0:
    st.info(
        "Nothing saved to your wishlist yet. "
        "Search for recipes on the **Recipes** page and click ❤️ Save — "
        "the more you save, the more personalised these picks become."
    )
else:
    st.caption(
        f"Based on {total_saved} saved recipe(s). "
        "Save more to keep improving the recommendations."
    )

st.divider()


# ── Run k-NN ──────────────────────────────────────────────────────────────────

rec         = Recommender(recipes_df)
saved_titles = {w["title"].lower() for w in wishlist if isinstance(w, dict) and w.get("title")}
has_signal   = bool(liked_ingredients) or bool(wishlist_ids)

if has_signal:
    candidates = rec.recommend(
        history_df,
        top_n=len(recipes_df),
        wishlist=wishlist_ids,
        liked_ingredients=liked_ingredients,
    )
    filtered = candidates[~candidates["title"].str.lower().isin(saved_titles)].copy()

    if not filtered.empty and filtered["score"].notna().any():
        max_score = filtered["score"].max()
        if max_score > 0:
            filtered["score"] = filtered["score"] / max_score

    picks = filtered.head(5).reset_index(drop=True)
else:
    picks = rec.recommend(history_df, top_n=5)

if picks.empty:
    st.info("Nothing to recommend yet — save some recipes on the **Recipes** page first.")
    st.stop()


# ── Feedback helper ───────────────────────────────────────────────────────────

def record_feedback(recipe_row: pd.Series, rating: int) -> None:
    st.session_state["cooking_history"].append({
        "recipe_id":   int(recipe_row["id"]),
        "title":       recipe_row["title"],
        "ingredients": recipe_row["ingredients"],
        "rating":      rating,
    })
    try:
        from src.data.database import execute
        user_id = st.session_state.get("user_id")
        if user_id is not None:
            execute(
                "INSERT INTO cooking_history (user_id, recipe_id, rating) VALUES (?, ?, ?)",
                (user_id, int(recipe_row["id"]), rating),
            )
    except Exception:
        pass


# ── Display ───────────────────────────────────────────────────────────────────

for _, row in picks.iterrows():
    with st.container(border=True):
        col_info, col_stats = st.columns([3, 1])

        with col_info:
            st.subheader(row["title"])

            if pd.notna(row.get("score")):
                st.progress(float(row["score"]), text=f"Match score: {row['score']:.0%}")

            ingredients = row.get("ingredients", [])
            if isinstance(ingredients, list):
                st.caption("Ingredients: " + ", ".join(ingredients))

            country = row.get("country", "")
            if country:
                st.caption(f"🌍 {country}")

            recipe_id     = int(row["id"])
            already_saved = any(
                isinstance(w, dict) and w.get("local_id") == recipe_id
                for w in st.session_state.get("wishlist", [])
            )
            if already_saved:
                st.caption("✅ Already in your wishlist")
            else:
                if st.button("＋ Save to wishlist", key=f"wish_{recipe_id}"):
                    st.session_state["wishlist"].append({
                        "title":       row["title"],
                        "image":       None,
                        "area":        row.get("country", ""),
                        "local_id":    recipe_id,
                        "ingredients": list(row.get("ingredients", [])),
                    })
                    st.rerun()

        with col_stats:
            st.metric("Cook time",  f"{row.get('time_minutes', '—')} min")
            st.metric("Difficulty", row.get("difficulty", "—"))

            st.caption("Was this a good pick?")
            fb_col1, fb_col2 = st.columns(2)
            with fb_col1:
                if st.button("👍", key=f"up_{recipe_id}", use_container_width=True, help="Good recommendation"):
                    record_feedback(row, rating=5)
                    st.toast("Thanks! This helps the model learn your taste.", icon="✅")
                    st.rerun()
            with fb_col2:
                if st.button("👎", key=f"dn_{recipe_id}", use_container_width=True, help="Not for me"):
                    record_feedback(row, rating=1)
                    st.toast("Got it — we'll show you fewer recipes like this.", icon="❌")
                    st.rerun()
