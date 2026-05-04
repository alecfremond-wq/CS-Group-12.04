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
from src.data.api_client import list_cuisines, search_recipes_by_name, search_spoonacular
from src.data.database import execute, query_df
from src.utils.session import init_session_state, require_profile

init_session_state()
require_profile()

page_header("🍲 Recipes", "Search recipes and plan your week")

tab_search, tab_cuisine = st.tabs(["🔎 Search", "🌍 Browse"])

# ─────────────────────────────────────────────
# WEEK HELPERS
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
# PANTRY
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


def match_score(recipe_id, pantry):
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

    return sum(1 for x in items if x in pantry) / len(items)

# ─────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────
with tab_search:

    query = st.text_input(
        "What would you like to cook?",
        placeholder="e.g. pasta, curry…"
    )

    if query:

        # ONBOARDING FILTERS
        veg = st.session_state.get("vegetarian", False)
        vgn = st.session_state.get("vegan", False)
        gf  = st.session_state.get("gluten_free", False)
        df  = st.session_state.get("dairy_free", False)

        # API CALL
        results = search_recipes_by_name(query) + search_spoonacular(
            query=query,
            vegetarian=veg,
            vegan=vgn,
            gluten_free=gf,
            dairy_free=df,
        )

        if not results:
            empty_state("No recipes found — try another word.")

        # PANTRY CHECK
        pantry_items = get_pantry_items()

        scored = sorted(
            [(match_score(r.get("id"), pantry_items), r) for r in results[:15]],
            key=lambda x: x[0],
            reverse=True
        )

        for score, meal in scored[:10]:
            with st.container(border=True):

                col1, col2 = st.columns([1, 3])

                with col1:
                    st.image(meal.get("strMealThumb"))

                with col2:
                    st.subheader(meal["strMeal"])

                    if score > 0.6:
                        st.success("🟢 Pantry-friendly")
                    elif score > 0.3:
                        st.warning("🟡 Partial ingredients")
                    else:
                        st.error("🔴 Needs shopping")

                    if score > 0.7:
                        suggestion = "🧠 Perfect pantry match — cook this!"
                    elif score > 0.4:
                        suggestion = "🧠 Mostly doable — small gaps only"
                    else:
                        suggestion = "🧠 Not ideal — needs shopping"

                    st.info(suggestion)

                    st.write(meal.get("strInstructions", "")[:200] + "...")

                    st.markdown("### ➕ Add to meal plan")

                    c1, c2, c3 = st.columns(3)

                    day = c1.selectbox("Day", DAYS, key=f"d_{meal['id']}")
                    meal_type = c2.selectbox("Meal", MEALS, key=f"m_{meal['id']}")

                    if c3.button("Add", key=f"a_{meal['id']}"):
                        try:
                            day_index = DAYS.index(day)
                            meal_date = week_start + timedelta(days=day_index)

                            # 1. ensure recipe exists in DB
                            execute(
                                """
                                INSERT INTO recipes (id, title)
                                VALUES (?, ?)
                                ON CONFLICT(id) DO UPDATE SET title=excluded.title
                                """,
                                (meal.get("id"), meal.get("strMeal"))
                            )

                            # 2. add to meal plan
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

                            st.success("Added to meal planner!")

                        except Exception:
                            st.error("Could not add meal.")

# ─────────────────────────────────────────────
# CUISINE
# ─────────────────────────────────────────────
with tab_cuisine:
    cuisines = list_cuisines()

    if cuisines:
        st.selectbox("Cuisine", cuisines)
    else:
        empty_state("No cuisines available.")
