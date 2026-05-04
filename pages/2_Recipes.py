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

import requests
from datetime import date, timedelta

from src.data.database import execute, query_df

from src.utils.session import init_session_state, require_profile

# ─────────────────────────────
# INIT
# ─────────────────────────────
init_session_state()
profile = require_profile()

page_header("🍲 Recipes", "Search recipes or browse by cuisine.")

local_title_to_id = {r["name"].lower(): r["id"] for r in LOCAL_RECIPES}


def extract_ingredients(meal: dict) -> list[str]:
    return [
        meal[f"strIngredient{i}"].strip()
        for i in range(1, 21)
        if (meal.get(f"strIngredient{i}") or "").strip()
    ]


wishlist = st.session_state.get("wishlist", [])
wishlist_ids = [
    w["local_id"]
    for w in wishlist
    if isinstance(w, dict) and w.get("local_id") is not None
]

liked_ingredients = [
    w["ingredients"]
    for w in wishlist
    if isinstance(w, dict) and not w.get("local_id") and w.get("ingredients")
]

history_df = pd.DataFrame(st.session_state.get("cooking_history", []))

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


def render_meal_card(meal: dict, ml_score: float | None = None) -> None:
    meal_title = meal["strMeal"]

    with st.container(border=True):
        col_img, col_meta = st.columns([1, 3])

        with col_img:
            st.image(meal.get("strMealThumb"), use_container_width=True)

        with col_meta:
            st.subheader(meal_title)
            st.caption(f"{meal.get('strArea', '—')} · {meal.get('strCategory', '—')}")

            if ml_score is not None and not pd.isna(ml_score):
                st.progress(float(ml_score), text=f"Match score: {ml_score:.0%}")

            with st.expander("Instructions"):
                st.write(meal.get("strInstructions", ""))

            already_saved = any(
                isinstance(w, dict) and w.get("title") == meal_title
                for w in st.session_state.get("wishlist", [])
            )

            if already_saved:
                st.caption("❤️ Saved to wishlist")
            else:
                if st.button("❤️ Save to wishlist", key=f"wish_{meal_title}"):
                    local_id = local_title_to_id.get(meal_title.lower())
                    st.session_state["wishlist"].append({
                        "title": meal_title,
                        "image": meal.get("strMealThumb"),
                        "area": meal.get("strArea", ""),
                        "local_id": local_id,
                        "ingredients": extract_ingredients(meal),
                    })
                    st.rerun()


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
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEALS = ["Breakfast", "Lunch", "Dinner"]


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

    if search_clicked and query:
        st.session_state.recipes = fetch_recipes(query)
        st.session_state.last_query = query

    results = st.session_state.recipes

    if not results:
        empty_state("Search for recipes to see results.")
        st.stop()

    pantry = get_pantry()

    ranked = sorted(
        [(score_recipe(r, pantry), r) for r in results],
        key=lambda x: x[0],
        reverse=True
    )
# ───── GRID LAYOUT (4 PER ROW) ─────
cols = st.columns(4)

for idx, (score_val, meal) in enumerate(ranked):
    col = cols[idx % 4]

    with col:
        with st.container(border=True):

            # ───── TITLE ─────
            st.markdown(f"### {meal.get('title', 'Unknown')}")

            # ───── CLICKABLE IMAGE → RECIPE DETAILS ─────
            if meal.get("image"):
                if st.button("View recipe", key=f"open_{meal['id']}"):
                    st.session_state["selected_recipe"] = meal

                st.image(meal["image"], use_container_width=True)

            # ───── SHORT DESCRIPTION ─────
            raw_summary = meal.get("summary", "")
            clean_summary = raw_summary.replace("<b>", "").replace("</b>", "")
            words = clean_summary.split()

            st.caption(" ".join(words[:18]) + ("..." if len(words) > 18 else ""))

            # ───── BUTTON ROW (CLOSE TOGETHER) ─────
            b1, b2 = st.columns([1, 1], gap="small")

            with b1:
                if st.button("❤️ Save", key=f"wish_{meal['id']}"):
                    st.session_state["wishlist"].append({
                        "title": meal.get("title"),
                        "image": meal.get("image"),
                        "local_id": None,
                        "ingredients": [],
                    })
                    st.success("Saved!")

            with b2:
                toggle_key = f"plan_toggle_{meal['id']}"

                if toggle_key not in st.session_state:
                    st.session_state[toggle_key] = False

                if st.button("📅 Add", key=f"plan_btn_{meal['id']}"):
                    st.session_state[toggle_key] = not st.session_state[toggle_key]

            # ───── ADD TO PLAN OPTIONS ─────
            if st.session_state[toggle_key]:

                c1, c2 = st.columns(2)

                def save_plan(meal_type):
                    try:
                        execute(
                            """
                            INSERT OR REPLACE INTO meal_plan
                            (user_id, meal_date, meal_type, recipe_id)
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                st.session_state.user_id,
                                get_week_start().isoformat(),
                                meal_type,
                                meal["id"]
                            )
                        )
                        st.success(f"Added: {meal_type}")
                    except Exception:
                        st.error("Could not add recipe")

                with c1:
                    if st.button("Breakfast", key=f"b_{meal['id']}"):
                        save_plan("Breakfast")
                    if st.button("Lunch", key=f"l_{meal['id']}"):
                        save_plan("Lunch")

                with c2:
                    if st.button("Dinner", key=f"d_{meal['id']}"):
                        save_plan("Dinner")
                    if st.button("Dessert", key=f"ds_{meal['id']}"):
                        save_plan("Dessert")

           
            # ───── PANTRY SCORE ─────
            if score_val > 0.6:
                st.success("🟢 Pantry-friendly")
            elif score_val > 0.3:
                st.warning("🟡 Partially available")
            else:
                st.error("🔴 Needs shopping")

# ─────────────────────────────
# CUISINE TAB
# ─────────────────────────────
with tab_cuisine:
    st.info("Cuisine browsing coming soon 🌍")
