"""
Recommendations — the machine-learning feature.
Owner: <assign on Apr 22>
Grading coverage:
    * Req. 5 (ML — content-based k-NN recommender)
    * Req. 3 (visualisation — match score bars)

TODOs for the owner:
    - add a 👎 dislike button that removes a recipe from future results.
"""
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

            ingredients = extract_ingredients_from_meal(meal)
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
            "ingredients":  r.get("_ingredients", []),
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

    The result is cached in st.session_state so the APIs are only
    called once per session, not on every Streamlit rerun.
    """
    if "rec_recipes_df" not in st.session_state:
        with st.spinner("Loading recipe catalogue from MealDB & Spoonacular…"):
            rows = _load_mealdb_recipes() + _load_spoonacular_recipes()

        df = pd.DataFrame(rows)

        # Drop exact-title duplicates (can happen if both sources return the
        # same popular dish) — keep the first occurrence (MealDB wins).
        df = df.drop_duplicates(subset="title", keep="first").reset_index(drop=True)

        # Re-assign sequential IDs after deduplication so the Recommender's
        # index lookups are always consistent.
        df["id"] = range(1, len(df) + 1)

        st.session_state["rec_recipes_df"] = df

    return st.session_state["rec_recipes_df"]


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

# Step 1: get candidate recipes from k-NN (handles cold-start, seen filtering,
# wishlist exclusion). We ask for more than top_n so we have room to re-rank.
candidates = rec.recommend(
    history_df,
    top_n=20,
    wishlist=wishlist_ids,
    liked_ingredients=liked_ingredients,
)

# Step 2: overwrite the cosine scores with Jaccard scores.
# Cosine relies on vocabulary overlap inside the small catalogue and produces
# near-zero scores when liked ingredients don't match the training vocabulary.
# Jaccard compares ingredient strings directly so it always gives meaningful
# percentages — the same method used to rank search results.
has_signal = bool(wishlist_ids) or bool(liked_ingredients)
if not candidates.empty and has_signal:
    jaccard_scores = rec.score_external(
        candidates["ingredients"].tolist(),
        history_df,
        wishlist_ids,
        liked_ingredients,
    )
    candidates = candidates.copy()
    candidates["score"] = jaccard_scores
    # Sort by Jaccard score descending, NaNs last
    candidates = candidates.sort_values("score", ascending=False, na_position="last")

picks = candidates.head(5).reset_index(drop=True)

if picks.empty:
    st.success(
        "You've already seen everything in the current catalogue — nice work! "
        "Check back later as the catalogue refreshes hourly."
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
