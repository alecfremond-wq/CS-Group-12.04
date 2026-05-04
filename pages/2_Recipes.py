"""
Recipes — search and browse recipes (API + DB).
Owner: <assign on Apr 22>
Grading coverage:
    * Req. 2 (API — TheMealDB)
    * Req. 4 (user interaction — search, filter, add-to-wishlist)

EXTENSION (SAFE ADDITION):
    - Pantry-aware recipe ranking (only show what user can mostly cook)
    - Add-to-meal-plan feature (NO schema changes)
"""

import streamlit as st
from datetime import date, timedelta

from src.components.ui import empty_state, page_header
from src.data.api_client import (
    list_cuisines,
    search_recipes_by_name,
    search_spoonacular
)
from src.data.database import execute, query_df
from src.utils.session import init_session_state, require_profile

# ─────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────
init_session_state()
require_profile()

page_header("🍲 Recipes", "Search recipes and plan your week")

tab_search, tab_cuisine = st.tabs(["🔎 Search", "🌍 Browse by cuisine"])

# ─────────────────────────────────────────────
# WEEK HELPERS (used for meal planner integration)
# ─────────────────────────────────────────────
def get_week_start():
    if "week_start" not in st.session_state:
        today = date.today()
        st.session_state.week_start = today - timedelta(days=today.weekday())
    return st.session_state.week_start


DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
MEALS = ["Breakfast","Lunch","Dinner"]

week_start = get_week_start()

# ─────────────────────────────────────────────
# 🧺 PANTRY HELPERS (NEW BUT SIMPLE)
# ─────────────────────────────────────────────
def get_pantry_items():
    df = query_df(
        """
        SELECT i.name AS ingredient
        FROM pantry p
        JOIN ingredients i ON p.ingredient_id = i.id
        WHERE p.user_id = ? AND p.quantity > 0
        """,
        (st.session_state.user_id,)
    )
    return set(df["ingredient"].str.lower()) if not df.empty else set()


def recipe_match_score(recipe_id, pantry_items):
    """Simple % match between recipe ingredients and pantry."""
    ing = query_df(
        """
        SELECT i.name AS ingredient
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE ri.recipe_id = ?
        """,
        (recipe_id,)
    )

    items = ing["ingredient"].str.lower().tolist() if not ing.empty else []
    if not items:
        return 0

    match = sum(1 for x in items if x in pantry_items)
    return match / len(items)


# ─────────────────────────────────────────────
# SEARCH TAB
# ─────────────────────────────────────────────
with tab_search:
    query = st.text_input(
        "What would you like to cook?",
        placeholder="e.g. pasta, curry…"
    )

    if query:
        veg = st.session_state.get("vegetarian", False)
        vgn = st.session_state.get("vegan", False)
        gf  = st.session_state.get("gluten_free", False)
        df  = st.session_state.get("dairy_free", False)

        results = search_recipes_by_name(query) + search_spoonacular(
            query=query,
            vegetarian=veg,
            vegan=vgn,
            gluten_free=gf,
            dairy_free=df,
        )

        if not results:
            empty_state("No recipes found — try another word.")

        pantry_items = get_pantry_items()

        # ─────────────────────────────────────────────
        # PANTRY-AWARE SORTING
        # ─────────────────────────────────────────────
        scored_results = []
        for meal in results[:15]:
            score = recipe_match_score(meal.get("id"), pantry_items)
            scored_results.append((score, meal))

        scored_results.sort(key=lambda x: x[0], reverse=True)

        # ─────────────────────────────────────────────
        # DISPLAY RECIPES
        # ─────────────────────────────────────────────
        for score, meal in scored_results[:10]:
            with st.container(border=True):
                col_img, col_meta = st.columns([1, 3])

                with col_img:
                    st.image(meal.get("strMealThumb"), use_container_width=True)

                with col_meta:
                    st.subheader(meal["strMeal"])
                    st.caption(
                        f"{meal.get('strArea', '—')} · {meal.get('strCategory', '—')}"
                    )

                    # pantry label
                    if score > 0.6:
                        st.success("🟢 Mostly in your pantry")
                    elif score > 0.3:
                        st.warning("🟡 Partially available")
                    else:
                        st.error("🔴 Needs shopping items")

                    with st.expander("Instructions"):
                        st.write(meal.get("strInstructions", ""))

                    # ─────────────────────────────
                    # ADD TO MEAL PLAN (SAFE EXTENSION)
                    # ─────────────────────────────
                    st.markdown("**Add to your week**")

                    c1, c2, c3 = st.columns(3)

                    day_choice = c1.selectbox(
                        "Day",
                        DAYS,
                        key=f"day_{meal.get('id')}_{meal['strMeal']}"
                    )

                    meal_type = c2.selectbox(
                        "Meal",
                        MEALS,
                        key=f"type_{meal.get('id')}_{meal['strMeal']}"
                    )

                    if c3.button("➕ Add", key=f"add_{meal.get('id')}"):
                        try:
                            day_index = DAYS.index(day_choice)
                            meal_date = week_start + timedelta(days=day_index)

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
                                    meal.get("id")
                                )
                            )

                            st.success("Added to meal plan!")
                        except Exception:
                            st.error("Could not add meal.")

# ─────────────────────────────────────────────
# CUISINE TAB (UNCHANGED 
# ─────────────────────────────────────────────
with tab_cuisine:
    cuisines = list_cuisines()

    if not cuisines:
        empty_state("Cuisine list couldn't be loaded — check your internet.")
    else:
        choice = st.selectbox("Cuisine", cuisines)
        st.caption(
            f"(Owner: render recipes for cuisine = **{choice}**) "
            "— feature unchanged"
        )
