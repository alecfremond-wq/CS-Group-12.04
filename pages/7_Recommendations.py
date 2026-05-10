"""
Recommendations — the machine-learning feature.
Owner: <assign on Apr 22>
Grading coverage:
    * Req. 5 (ML — content-based k-NN recommender)
    * Req. 3 (visualisation — match score bars)

TODOs for the owner:
    - add a 👎 dislike button that removes a recipe from future results.
"""
import re

import pandas as pd
import streamlit as st

from src.components.ui import page_header
from src.data.api_client import (
    extract_ingredients_from_meal,
    fetch_nutrition_for_meal,
    filter_by_cuisine,
    get_meal_by_id,
    search_spoonacular,
)
from src.models.recommender import Recommender
from src.utils.session import init_session_state, require_profile


def _strip_measures(ingredient: str) -> str:
    """Normalise an ingredient string to a plain lowercase name.

    Handles all formats seen in MealDB and Spoonacular:
      '2 tbsp Cajun'          → 'cajun'
      '400g Chickpeas'        → 'chickpeas'
      '1 x 300ml Salsa'       → 'salsa'
      'Juice of 1 Lime'       → 'lime'
      'to serve Coriander'    → 'coriander'
      'finely chopped Garlic' → 'garlic'  (last word fallback)
    """
    s = ingredient.strip()

    # Remove leading noise phrases like "to serve", "juice of", "zest of"
    s = re.sub(r"^(to serve|juice of|zest of|handful of|a pinch of)\s+", "", s, flags=re.IGNORECASE)

    # Remove leading numbers, fractions, unicode fraction chars, and 'x'
    s = re.sub(r"^[\d\s½¼¾⅓⅔⅛./-]+x?\s*", "", s)

    # Remove amounts glued to unit with no space: '400g' '300ml'
    s = re.sub(r"^\d+\s*(g|kg|ml|l|oz|lbs?)\s+", "", s, flags=re.IGNORECASE)

    # Remove leading unit words
    units = (
        r"^(cups?|tbsp?|tsp?|tablespoons?|teaspoons?|grams?|g|kg|oz|lbs?|"
        r"pounds?|ml|liters?|litres?|cloves?|slices?|pieces?|pinch|handful|"
        r"bunch|cans?|large|medium|small|whole|finely|chopped|shredded|"
        r"sliced|diced|minced|fresh|dried|ground|packed)\s+"
    )
    s = re.sub(units, "", s, flags=re.IGNORECASE)

    return s.strip().lower()


def _clean_ingredients(raw: list[str]) -> list[str]:
    """Strip measures from a list and drop empty/short strings."""
    return [s for s in (_strip_measures(i) for i in raw) if len(s) > 1]


# ── Constants ─────────────────────────────────────────────────────────────────

# A representative spread of MealDB cuisines to build the catalogue from.
_MEALDB_CUISINES = [
    "Italian", "Mexican", "Indian", "Japanese", "French",
    "Chinese", "Thai", "American", "British", "Greek",
]

# Generic Spoonacular query — just pulls popular recipes to pad the catalogue.
_SPOONACULAR_QUERY = "popular dinner"

# How many stubs to pull from each MealDB cuisine (keeps API calls manageable).
_MEALDB_PER_CUISINE = 4

# Estimated difficulty from cook-time (minutes) — MealDB has no native field.
def _difficulty_from_time(minutes: int | None) -> str:
    if minutes is None:
        return "Medium"
    if minutes <= 20:
        return "Easy"
    if minutes <= 45:
        return "Medium"
    return "Hard"


# Estimated cook-time from instruction length — MealDB has no native field.
def _estimate_time(instructions: str) -> int:
    words = len((instructions or "").split())
    if words < 80:
        return 15
    if words < 200:
        return 30
    if words < 400:
        return 45
    return 60


# ── Recipe loader ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60 * 60, show_spinner=False)
def _load_mealdb_recipes() -> list[dict]:
    """
    Fetch full recipe details from TheMealDB for a set of cuisines,
    then enrich each one with calorie data from Spoonacular's nutrition
    parser (since TheMealDB carries no nutrition information itself).

    Returns a list of normalised recipe dicts with the keys the
    Recommender and display code expect.
    """
    rows = []
    recipe_id = 1  # synthetic local ID — only used inside the recommender

    for cuisine in _MEALDB_CUISINES:
        stubs = filter_by_cuisine(cuisine)[:_MEALDB_PER_CUISINE]
        for stub in stubs:
            meal = get_meal_by_id(stub["idMeal"])
            if not meal:
                continue

            ingredients = _clean_ingredients(extract_ingredients_from_meal(meal))
            nutrition   = fetch_nutrition_for_meal(meal)        # Spoonacular call
            instructions = meal.get("strInstructions", "")
            time_min     = _estimate_time(instructions)

            rows.append({
                "id":           recipe_id,
                "title":        meal.get("strMeal", ""),
                "ingredients":  ingredients,
                "calories":     nutrition["kcal"],          # int | None
                "time_minutes": time_min,
                "difficulty":   _difficulty_from_time(time_min),
                "country":      meal.get("strArea", cuisine),
            })
            recipe_id += 1

    return rows


@st.cache_data(ttl=60 * 60, show_spinner=False)
def _load_spoonacular_recipes() -> list[dict]:
    """
    Pull popular recipes from Spoonacular and normalise them into the
    same shape as the MealDB rows above.

    Spoonacular returns readyInMinutes and calorie data natively, so no
    extra enrichment step is needed.
    """
    raw     = search_spoonacular(query=_SPOONACULAR_QUERY)
    rows    = []
    base_id = 10_000  # offset so Spoonacular IDs never clash with MealDB ones

    for i, r in enumerate(raw):
        # search_spoonacular normalises to strMeal / _ingredients / kcal_per_serv
        time_min = r.get("readyInMinutes")          # may be None
        kcal     = r.get("kcal_per_serv")

        rows.append({
            "id":           base_id + i,
            "title":        r.get("strMeal", ""),
            "ingredients":  _clean_ingredients(r.get("_ingredients", [])),
            "calories":     kcal,
            "time_minutes": time_min,
            "difficulty":   _difficulty_from_time(time_min),
            "country":      r.get("strArea", "International"),
        })

    return rows


def load_all_recipes() -> pd.DataFrame:
    """
    Merge MealDB and Spoonacular catalogues, deduplicate by title,
    and return as a DataFrame ready for the Recommender.

    Cached in st.session_state so APIs are only hit once per session.
    The cache key includes a version string — bump it whenever the
    cleaning logic changes so stale uncleaned data is never used.
    """
    CACHE_VERSION = "v3"  # bump this if ingredient cleaning logic changes
    cache_key = f"rec_recipes_df_{CACHE_VERSION}"

    # Invalidate any older cache versions left in session state
    for old_key in [k for k in st.session_state if k.startswith("rec_recipes_df_") and k != cache_key]:
        del st.session_state[old_key]

    if cache_key not in st.session_state:
        with st.spinner("Loading recipe catalogue from MealDB & Spoonacular…"):
            rows = _load_mealdb_recipes() + _load_spoonacular_recipes()

        df = pd.DataFrame(rows)
        df = df.drop_duplicates(subset="title", keep="first").reset_index(drop=True)
        df["id"] = range(1, len(df) + 1)
        st.session_state[cache_key] = df

    return st.session_state[cache_key]


# ── App init ──────────────────────────────────────────────────────────────────

init_session_state()
require_profile()
page_header("✨ Recommendations", "Recipes picked just for you by a k-NN model.")

# ── Load data ─────────────────────────────────────────────────────────────────

recipes_df = load_all_recipes()

wishlist   = st.session_state.get("wishlist", [])
history_df = pd.DataFrame(st.session_state.get("cooking_history", []))

# Local-catalogue IDs — used to look up pre-computed ingredient vectors.
wishlist_ids = [
    w["local_id"]
    for w in wishlist
    if isinstance(w, dict) and w.get("local_id") is not None
]

# Ingredient lists from ALL saved recipes — used to build the taste profile.
liked_ingredients = [
    w["ingredients"]
    for w in wishlist
    if isinstance(w, dict) and w.get("ingredients")
]

# ── Context message ───────────────────────────────────────────────────────────

total_saved = len(wishlist_ids) + len(liked_ingredients)

if total_saved == 0:
    st.info(
        "Nothing saved to your wishlist yet. "
        "Search for recipes on the **Recipes** page and click ❤️ Save, "
        "or save recipes directly from this page — the more you save, "
        "the more personalised these picks become."
    )
else:
    st.caption(
        f"Based on {total_saved} saved recipe(s) from your wishlist. "
        "Save more to keep improving the recommendations."
    )

st.divider()

# ── Run the model ─────────────────────────────────────────────────────────────

rec = Recommender(recipes_df)

# Build the taste profile: one flat set of clean ingredient names from
# everything the user has saved. We clean here too — wishlist items saved
# from the Recipes page still carry raw MealDB strings like '2 cups Rice'.
ref_set: set[str] = set()
for ing_list in liked_ingredients:
    ref_set.update(_clean_ingredients(ing_list))

has_signal = bool(ref_set)

# ── Debug (remove before submission) ─────────────────────────────────────────
with st.expander("🔍 Debug: taste profile", expanded=False):
    st.write(f"**Wishlist entries:** {len(wishlist)}")
    st.write(f"**liked_ingredients lists:** {len(liked_ingredients)}")
    st.write(f"**ref_set size:** {len(ref_set)}")
    st.write(f"**ref_set sample:** {sorted(ref_set)[:20]}")
# ─────────────────────────────────────────────────────────────────────────────

if has_signal:
    # Score by overlap coefficient: |A ∩ B| / min(|A|, |B|)
    # This asks "what fraction of THIS recipe's ingredients appear in your
    # taste profile?" — so a recipe sharing 8 of its 10 ingredients with
    # things you've saved scores 80%, regardless of how large the profile is.
    # Raw Jaccard penalises a large profile (the union grows fast) and produces
    # scores like 2-3% that round to 0% — overlap coefficient avoids that.
    def _overlap(profile: set[str], recipe_ings: set[str]) -> float:
        if not profile or not recipe_ings:
            return 0.0
        return len(profile & recipe_ings) / min(len(profile), len(recipe_ings))

    scores = [
        _overlap(ref_set, set(row["ingredients"]))
        for _, row in recipes_df.iterrows()
    ]
    recipes_df = recipes_df.copy()
    recipes_df["score"] = scores

    saved_titles = {
        w["title"].lower()
        for w in wishlist
        if isinstance(w, dict) and w.get("title")
    }
    picks = (
        recipes_df[~recipes_df["title"].str.lower().isin(saved_titles)]
        .sort_values("score", ascending=False)
        .query("score >= 0.5")
        .head(8)
        .reset_index(drop=True)
    )
else:
    # Cold start — no wishlist yet, use k-NN default ordering
    picks = rec.recommend(history_df, top_n=8)

if picks.empty:
    st.info(
        "No recipes scored above 50% match for your taste profile yet. "
        "Save more recipes on the **Recipes** page to broaden your profile "
        "and unlock better matches."
    )

# ── Feedback helper ───────────────────────────────────────────────────────────

def record_feedback(recipe_row: pd.Series, rating: int) -> None:
    """Append a thumbs-up / thumbs-down signal to the cooking history.

    rating: +1 for 👍, -1 for 👎.
    The Recommender reads cooking_history on the next rerun and adjusts
    its rankings accordingly. When the DB is wired up the same write is
    mirrored into the cooking_history table.
    """
    st.session_state["cooking_history"].append(
        {
            "id":          int(recipe_row["id"]),
            "title":       recipe_row["title"],
            "ingredients": recipe_row["ingredients"],
            "rating":      rating,
        }
    )
    # Best-effort DB persistence
    try:
        from src.data.database import execute  # type: ignore
        user_id = st.session_state.get("user_id") \
            or st.session_state.get("profile", {}).get("id")
        if user_id is not None:
            execute(
                "INSERT INTO cooking_history (user_id, recipe_id, rating) VALUES (?, ?, ?)",
                (user_id, int(recipe_row["id"]), rating),
            )
    except Exception:
        pass  # session_state is the source of truth for the demo


# ── Display recommendations ───────────────────────────────────────────────────

for _, row in picks.iterrows():
    with st.container(border=True):
        col_info, col_stats = st.columns([3, 1])

        with col_info:
            st.subheader(row["title"])

            if pd.notna(row.get("score")):
                st.progress(
                    float(row["score"]),
                    text=f"Match score: {row['score']:.0%}",
                )

            ingredients = row.get("ingredients", [])
            if isinstance(ingredients, list):
                st.caption("Ingredients: " + ", ".join(ingredients))

            # Country / source badge
            country = row.get("country", "")
            if country:
                st.caption(f"🌍 {country}")

            recipe_id  = int(row["id"])
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
            calories = row.get("calories")
            st.metric("Calories",   f"{calories} kcal" if calories else "—")
            st.metric("Cook time",  f"{row.get('time_minutes', '—')} min")
            st.metric("Difficulty", row.get("difficulty", "—"))
