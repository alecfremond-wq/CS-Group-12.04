import streamlit as st
import requests
from datetime import date, timedelta

from src.components.ui import empty_state, page_header
from src.data.database import execute, query_df
from src.utils.session import init_session_state, require_profile

init_session_state()
require_profile()

page_header("🍲 Recipes", "Search recipes and plan your week")

tab_search, tab_cuisine = st.tabs(["🔎 Search", "🌍 Browse"])

# ─────────────────────────────
# SPOONACULAR SETUP
# ─────────────────────────────
API_KEY = st.secrets.get("SPOONACULAR_API_KEY", None)
BASE_URL = "https://api.spoonacular.com/recipes/complexSearch"

def spoonacular_search(query):
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

    st.write(response.json())  # 👈 ADD THIS DEBUG LINE

    return response.json().get("results", [])

# ─────────────────────────────
# WEEK HELPERS
# ─────────────────────────────
DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
MEALS = ["Breakfast","Lunch","Dinner"]

def get_week_start():
    today = date.today()
    return today - timedelta(days=today.weekday())

week_start = get_week_start()

# ─────────────────────────────
# PANTRY (simple)
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
    return set(df["name"].str.lower()) if not df.empty else set()

def score(recipe, pantry):
    ingredients = recipe.get("extendedIngredients", [])
    names = [i["name"].lower() for i in ingredients if "name" in i]

    if not names:
        return 0

    return sum(1 for i in names if i in pantry) / len(names)

# ─────────────────────────────
# SEARCH TAB
# ─────────────────────────────
with tab_search:

    query = st.text_input("What do you want to cook?", placeholder="pasta, curry...")

    if query:

        results = spoonacular_search(query)

        if not results:
            empty_state("No recipes found.")
            st.stop()

        pantry = get_pantry()

        ranked = []
        for r in results:
            s = score(r, pantry)
            ranked.append((s, r))

        ranked.sort(reverse=True, key=lambda x: x[0])

        for score_val, meal in ranked:

            st.divider()
            st.subheader(meal.get("title", "Unknown"))

            image = meal.get("image", "")
            if image:
                st.image(image)

            # pantry label
            if score_val > 0.6:
                st.success("🟢 Pantry-friendly")
            elif score_val > 0.3:
                st.warning("🟡 Partially available")
            else:
                st.error("🔴 Needs shopping")

            # summary
            st.write(meal.get("summary", "")[:200] + "...")

            # ─── MEAL PLAN ───
            st.markdown("### ➕ Add to meal plan")

            c1, c2, c3 = st.columns(3)

            day = c1.selectbox("Day", DAYS, key=f"d_{meal['id']}")
            meal_type = c2.selectbox("Meal", MEALS, key=f"m_{meal['id']}")

            if c3.button("Add", key=f"b_{meal['id']}"):

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
                    st.success("Added to meal plan!")
                except:
                    st.error("Could not add recipe")

# ─────────────────────────────
# CUISINE TAB (simple placeholder)
# ─────────────────────────────
with tab_cuisine:
    st.info("Cuisine browsing can be added later (optional feature).")
