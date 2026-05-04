"""
Recipes — search and browse recipes (API + DB).
Owner: <assign on Apr 22>
Grading coverage:
    * Req. 2 (API — TheMealDB + Spoonacular)
    * Req. 4 (user interaction — search, filter, add-to-wishlist)
    * Req. 5 (ML — search results ranked by taste profile when available)
TODOs for the owner:
    - when a user clicks "Save recipe", persist to the `recipes` table
      so the Recommender has data to learn from.
"""
import pandas as pd
import streamlit as st

from recipes_data import RECIPES as LOCAL_RECIPES
from src.components.ui import empty_state, page_header
from src.data.api_client import list_cuisines, search_recipes_by_name, search_spoonacular
from src.models.recommender import Recommender
=======
import streamlit as st
import requests
from datetime import date, timedelta

from src.components.ui import empty_state, page_header
from src.data.database import execute, query_df
>>>>>>> main
from src.utils.session import init_session_state, require_profile

# ─────────────────────────────
# INIT
# ─────────────────────────────
init_session_state()
# We capture the return value here — require_profile() already stops the page
# if the user hasn't done onboarding yet, so by the time we reach the next line
# we're guaranteed to have a real profile dict to work with.
profile = require_profile()

<<<<<<< feature/ml-recommendations
page_header("🍲 Recipes", "Search recipes or browse by cuisine.")

# Build a lookup table: lowercase recipe name → local ID.
# Used when saving: if the recipe title matches something in our local catalogue,
# we can link the saved item to the local ID so the ML model can use it.
local_title_to_id = {r["name"].lower(): r["id"] for r in LOCAL_RECIPES}


def extract_ingredients(meal: dict) -> list[str]:
    """Pull the ingredient list out of a TheMealDB result.

    TheMealDB stores ingredients in fields strIngredient1 … strIngredient20
    (yes, twenty separate fields — that's just how their API works).
    We loop through them and collect the non-empty ones.
    Spoonacular results don't have this structure, so they return an empty list
    and won't get an ML score — that's fine for now.
    """
    # TheMealDB sets unused ingredient slots to null (None in Python), not "".
    # Using `or ""` converts None → "" so .strip() never crashes.
    return [
        meal[f"strIngredient{i}"].strip()
        for i in range(1, 21)
        if (meal.get(f"strIngredient{i}") or "").strip()
    ]

# Grab the user's wishlist and history so we can check what's already saved
# and build a taste profile for ML ranking.
wishlist    = st.session_state.get("wishlist", [])
wishlist_ids = [
    w["local_id"]
    for w in wishlist
    if isinstance(w, dict) and w.get("local_id") is not None
]
# Ingredient lists from API-only saves (no local_id) — the model uses these too.
liked_ingredients = [
    w["ingredients"]
    for w in wishlist
    if isinstance(w, dict) and not w.get("local_id") and w.get("ingredients")
]
history_df = pd.DataFrame(st.session_state.get("cooking_history", []))

# A taste profile exists when the user has saved at least one recipe anywhere
# in the app — either a local recipe (wishlist_ids), an API recipe whose
# ingredients were stored (liked_ingredients), or a cooked + rated recipe
# from history (not yet available in the UI, but wired up for Sprint 2).
# We only activate ML ranking when this is true — a brand-new user with
# nothing saved gets results in plain API order, with no misleading scores.
has_taste_profile = (
    bool(wishlist_ids)
    or bool(liked_ingredients)
    or (
        not history_df.empty
        and "rating" in history_df.columns
        and (history_df["rating"] >= 4).any()
    )
)

tab_search, tab_cuisine = st.tabs(["🔎 Search", "🌍 Browse by cuisine"])

# ── Helper: render one recipe card ────────────────────────────────────────────

def render_meal_card(meal: dict, ml_score: float | None = None) -> None:
    """Draw a single recipe card.  ml_score is shown as a match bar when available."""
    meal_title = meal["strMeal"]

    with st.container(border=True):
        col_img, col_meta = st.columns([1, 3])

        with col_img:
            st.image(meal.get("strMealThumb"), use_container_width=True)

        with col_meta:
            st.subheader(meal_title)
            st.caption(f"{meal.get('strArea', '—')} · {meal.get('strCategory', '—')}")

            # If we have an ML score for this result, show it as a progress bar.
            # This only appears when the user has a taste profile — otherwise
            # we don't mislead them with a fake "match" percentage.
            if ml_score is not None and not pd.isna(ml_score):
                st.progress(float(ml_score), text=f"Match score: {ml_score:.0%}")

            with st.expander("Instructions"):
                st.write(meal.get("strInstructions", ""))

            # ── Save to wishlist ──────────────────────────────────────────────
            already_saved = any(
                isinstance(w, dict) and w.get("title") == meal_title
                for w in st.session_state.get("wishlist", [])
            )

            if already_saved:
                st.caption("❤️ Saved to wishlist")
            else:
                if st.button("❤️ Save to wishlist", key=f"wish_{meal_title}"):
                    # Try to find this recipe in our local catalogue by title.
                    # If we find it, we set local_id so the ML model can use it
                    # as a signal — the user's save will influence future rankings.
                    # If we don't find it, local_id stays None (saved for display only).
                    local_id = local_title_to_id.get(meal_title.lower())
                    # Store the ingredient list so the ML model can use this save
                    # as a signal even when it's an API recipe without a local_id.
                    st.session_state["wishlist"].append({
                        "title":       meal_title,
                        "image":       meal.get("strMealThumb"),
                        "area":        meal.get("strArea", ""),
                        "local_id":    local_id,
                        "ingredients": extract_ingredients(meal),
                    })
                    st.rerun()


# ── Search tab ────────────────────────────────────────────────────────────────

with tab_search:
    query = st.text_input("What would you like to cook?", placeholder="e.g. pasta, curry…")

    if query:
        # Pull the diet string and allergy list out of the profile the user
        # filled in during onboarding. The diet is stored as a plain string
        # like "vegan" or "omnivore", not as individual boolean flags —
        # so we convert it here to what the Spoonacular API actually expects.
        diet      = profile.get("diet", "omnivore")
        allergies = profile.get("allergies", [])

        # "vegan" implies vegetarian too, so we set both flags when diet is vegan.
        veg = diet in ("vegetarian", "vegan")
        vgn = diet == "vegan"
        # Allergies come from a separate multiselect in onboarding — "gluten"
        # maps to gluten_free and "lactose" maps to dairy_free for Spoonacular.
        gf  = "gluten" in allergies
        df  = "lactose" in allergies

        results = search_recipes_by_name(query) + search_spoonacular(
            query=query,
            vegetarian=veg,
            vegan=vgn,
            gluten_free=gf,
            dairy_free=df,
        )

        if not results:
            empty_state("No recipes found — try another word.")
        else:
            # ── ML ranking ───────────────────────────────────────────────────
            # Because the model now uses ingredients as features (not nutrition
            # numbers), we can score ANY recipe that has an ingredient list —
            # not just ones that happen to exist in our local catalogue.
            # TheMealDB results always include ingredients; Spoonacular results
            # currently don't, so those fall back to unscored.

            recipes_df      = pd.DataFrame(LOCAL_RECIPES).rename(columns={"name": "title"})
            rec             = Recommender(recipes_df)
            top_results     = results[:10]

            # Extract ingredient lists for every result.
            # extract_ingredients() returns [] for Spoonacular results —
            # those will get a score of None and appear at the bottom.
            ingredient_lists = [extract_ingredients(m) for m in top_results]

            # score_external() uses the ingredient-based k-NN model to compare
            # each recipe's ingredient vector against the user's taste profile.
            # Returns None for every recipe when there's no taste profile yet.
            raw_scores = rec.score_external(
                ingredient_lists, history_df, wishlist_ids, liked_ingredients
            ) if has_taste_profile else [None] * len(top_results)

            # Sort: scored recipes first (highest score first), unscored last.
            scored_results = sorted(
                zip(top_results, raw_scores),
                key=lambda pair: (0, -(pair[1] or 0)) if pair[1] is not None else (1, 0),
            )

            any_scored = any(s is not None for _, s in scored_results)
            if any_scored:
                st.caption(
                    "🎯 Results ranked by ingredient similarity to your taste profile. "
                    "Save more recipes to improve the ranking."
                )
            elif has_taste_profile:
                st.caption(
                    "ℹ️ These results don't have ingredient data, "
                    "so ML ranking isn't available here."
                )

            for meal, score in scored_results:
                render_meal_card(meal, ml_score=score)


# ── Cuisine tab ───────────────────────────────────────────────────────────────
=======
page_header("🍲 Recipes", "Search recipes and plan your week")

tab_search, tab_cuisine = st.tabs(["🔎 Search", "🌍 Browse"])

# ─────────────────────────────
# API SETUP
# ─────────────────────────────
API_KEY = st.secrets.get("SPOONACULAR_API_KEY")
BASE_URL = "https://api.spoonacular.com/recipes/complexSearch"

def fetch_recipes(query):
    if not API_KEY:
        st.warning("Missing API key")
        return []

    response = requests.get(
        BASE_URL,
        params={
            "query": query,
            "number": 10,
            "addRecipeInformation": True,
            "apiKey": API_KEY
        },
        timeout=10
    )

    data = response.json()
    return data.get("results", [])

# ─────────────────────────────
# WEEK HELPERS
# ─────────────────────────────
DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
MEALS = ["Breakfast","Lunch","Dinner"]

def get_week_start():
    today = date.today()
    return today - timedelta(days=today.weekday())

# ─────────────────────────────
# PANTRY
# ─────────────────────────────
def get_pantry():
    df = query_df(
        """
        SELECT i.name
        FROM pantry p
        JOIN ingredients i ON p.ingredient_id = i.id
        WHERE p.user_id = ? AND p.quantity > 0
        """,
        (st.session_state.user_id,)
    )

    if df.empty:
        return set()

    return set(df["name"].str.lower())

def score_recipe(recipe, pantry):
    ingredients = recipe.get("extendedIngredients", [])
    names = [i["name"].lower() for i in ingredients if "name" in i]

    if not names:
        return 0

    return sum(1 for n in names if n in pantry) / len(names)

# ─────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────
if "recipes" not in st.session_state:
    st.session_state.recipes = []

if "last_query" not in st.session_state:
    st.session_state.last_query = ""

# ─────────────────────────────
# SEARCH TAB
# ─────────────────────────────
with tab_search:
>>>>>>> main

    query = st.text_input("What do you want to cook?", placeholder="pasta, curry...")

    search_clicked = st.button("🔍 Search Recipes")

    # Run search ONLY when button is clicked
    if search_clicked and query:
        st.session_state.recipes = fetch_recipes(query)
        st.session_state.last_query = query

    results = st.session_state.recipes

    if not results:
        empty_state("Search for recipes to see results.")
        st.stop()

    pantry = get_pantry()

    # rank recipes
    ranked = sorted(
        [(score_recipe(r, pantry), r) for r in results],
        key=lambda x: x[0],
        reverse=True
    )

    # display
    for score_val, meal in ranked:

        st.divider()
        st.subheader(meal.get("title", "Unknown"))

        if meal.get("image"):
            st.image(meal["image"])

        # pantry status
        if score_val > 0.6:
            st.success("🟢 Pantry-friendly")
        elif score_val > 0.3:
            st.warning("🟡 Partially available")
        else:
            st.error("🔴 Needs shopping")

        st.write(meal.get("summary", "")[:200] + "...")

        # ─────────────────────────────
        # MEAL PLAN SECTION
        # ─────────────────────────────
        st.markdown("### ➕ Add to meal plan")

        col1, col2, col3 = st.columns(3)

        day = col1.selectbox("Day", DAYS, key=f"day_{meal['id']}")
        meal_type = col2.selectbox("Meal", MEALS, key=f"type_{meal['id']}")

        if col3.button("Add", key=f"add_{meal['id']}"):

            day_index = DAYS.index(day)
            meal_date = get_week_start() + timedelta(days=day_index)

            try:
                execute(
                    """
                    INSERT OR REPLACE INTO meal_plan
                    (user_id, meal_date, meal_type, recipe_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        st.session_state.user_id,
                        meal_date.isoformat(),
                        meal_type,
                        meal["id"]
                    )
                )
                st.success("Added to meal plan! 🍽️")

            except Exception:
                st.error("Could not add recipe")

# ─────────────────────────────
# CUISINE TAB
# ─────────────────────────────
with tab_cuisine:
    st.info("Cuisine browsing coming soon 🌍")
