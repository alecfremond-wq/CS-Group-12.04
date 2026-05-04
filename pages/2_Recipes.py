import streamlit as st
import requests
from datetime import date, timedelta

from src.components.ui import empty_state, page_header
from src.data.database import execute, query_df
from src.utils.session import init_session_state, require_profile

# ─────────────────────────────
# INIT
# ─────────────────────────────
init_session_state()
require_profile()

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
