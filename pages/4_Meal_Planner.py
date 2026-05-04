""
4_Meal_Planner.py — Simplified Weekly Meal Planner
==================================================
"""

# ─────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import sys, os

# allow imports from src/
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.data.database import query_df, execute
from src.utils.session import require_profile, init_session_state
from src.components.ui import page_header

# ─────────────────────────────────────────────────────────────
# PAGE SETUP
# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Meal Planner", page_icon="📅", layout="wide")

init_session_state()
require_profile()

page_header("📅 Meal Planner", "Plan your week simply")

# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEALS = ["Breakfast", "Lunch", "Dinner"]

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def get_week_start():
    if "week_start" not in st.session_state:
        today = date.today()
        st.session_state.week_start = today - timedelta(days=today.weekday())
    return st.session_state.week_start


def get_meals(week_start):
    week_end = week_start + timedelta(days=6)
    return query_df(
        """
        SELECT mp.id, mp.meal_date, mp.meal_type, mp.recipe_id, r.title
        FROM meal_plan mp
        JOIN recipes r ON mp.recipe_id = r.id
        WHERE mp.user_id=? AND mp.meal_date BETWEEN ? AND ?
        """,
        (st.session_state.user_id, week_start.isoformat(), week_end.isoformat())
    )


def get_recipes():
    return query_df("SELECT id, title FROM recipes", ())


def add_meal(day, meal_type, recipe_id):
    execute(
        "INSERT OR REPLACE INTO meal_plan (user_id, meal_date, meal_type, recipe_id) VALUES (?, ?, ?, ?)",
        (st.session_state.user_id, day.isoformat(), meal_type, recipe_id)
    )


def delete_meal(meal_id):
    execute("DELETE FROM meal_plan WHERE id=? AND user_id=?",
            (meal_id, st.session_state.user_id))

# ─────────────────────────────────────────────────────────────
# WEEK NAVIGATION
# ─────────────────────────────────────────────────────────────
week_start = get_week_start()
week_end = week_start + timedelta(days=6)

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    if st.button("← Prev"):
        st.session_state.week_start = week_start - timedelta(days=7)
        st.rerun()

with col2:
    st.markdown(f"### {week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}")

with col3:
    if st.button("Next →"):
        st.session_state.week_start = week_start + timedelta(days=7)
        st.rerun()

st.divider()

# ─────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────
meals = get_meals(week_start)
recipes = get_recipes()

plan = {}
for _, m in meals.iterrows():
    plan[(str(m["meal_date"]), m["meal_type"])] = m.to_dict()

# ─────────────────────────────────────────────────────────────
# GRID
# ─────────────────────────────────────────────────────────────
st.subheader("Your Week")

cols = st.columns(8)
cols[0].write("")
for i, d in enumerate(DAYS):
    cols[i+1].write(d)

for meal in MEALS:
    row = st.columns(8)
    row[0].write(meal)

    for i in range(7):
        day = week_start + timedelta(days=i)
        key = (day.isoformat(), meal)

        with row[i+1]:
            if key in plan:
                st.write("🍽", plan[key]["title"])
                if st.button("x", key=f"del_{plan[key]['id']}"):
                    delete_meal(plan[key]["id"])
                    st.rerun()
            else:
                if st.button("+", key=f"add_{meal}_{i}"):
                    st.session_state.add = (day, meal)

# ─────────────────────────────────────────────────────────────
# ADD MEAL
# ─────────────────────────────────────────────────────────────
if "add" in st.session_state:
    day, meal = st.session_state.add

    st.subheader(f"Add {meal} - {day}")

    for _, r in recipes.iterrows():
        c1, c2 = st.columns([3,1])
        c1.write(r["title"])
        if c2.button("Add", key=f"pick_{r['id']}"):
            add_meal(day, meal, r["id"])
            del st.session_state["add"]
            st.rerun()

    if st.button("Cancel"):
        del st.session_state["add"]
        st.rerun()

# ─────────────────────────────────────────────────────────────
# SHOPPING LIST (simple)
# ─────────────────────────────────────────────────────────────
st.subheader("Shopping List")

if meals.empty:
    st.info("No meals planned yet")
else:
    ids = meals["recipe_id"].tolist()

    if ids:
        placeholders = ",".join("?"*len(ids))
        items = query_df(
            f"""
            SELECT i.name
            FROM recipe_ingredients ri
            JOIN ingredients i ON ri.ingredient_id = i.id
            WHERE ri.recipe_id IN ({placeholders})
            """,
            tuple(ids)
        )

        for _, row in items.iterrows():
            st.write("-", row["name"])
""

# ─────────────────────────────────────────────────────────────
# SIMPLE ML SUGGESTION BOX (PANTRY-AWARE, STILL SIMPLE)
# ─────────────────────────────────────────────────────────────
try:
    from src.models.recommender import Recommender

    st.subheader("✨ Suggestions")

    # recipes already planned
    exclude = meals["recipe_id"].tolist() if not meals.empty else []

    # pantry items (what user already has)
    pantry_df = query_df(
        """
        SELECT i.name AS ingredient
        FROM pantry p
        JOIN ingredients i ON p.ingredient_id = i.id
        WHERE p.user_id = ? AND p.quantity > 0
        """,
        (st.session_state.user_id,)
    )
    pantry_items = set(pantry_df["ingredient"].str.lower()) if not pantry_df.empty else set()

    rec = Recommender()
    rec.fit(recipes)

    raw_suggestions = rec.recommend(
        user_id=st.session_state.user_id,
        exclude_ids=exclude,
        n=10
    )

    if isinstance(raw_suggestions, dict):
        raw_suggestions = list(raw_suggestions.keys())

    # ── simple pantry scoring ──
    scored = []

    for _, r in recipes[recipes["id"].isin(raw_suggestions)].iterrows():
        rid = r["id"]

        ing_df = query_df(
            """
            SELECT i.name AS ingredient
            FROM recipe_ingredients ri
            JOIN ingredients i ON ri.ingredient_id = i.id
            WHERE ri.recipe_id = ?
            """,
            (rid,)
        )

        ingredients = ing_df["ingredient"].str.lower().tolist() if not ing_df.empty else []

        if not ingredients:
            score = 0
        else:
            match = sum(1 for i in ingredients if i in pantry_items)
            score = match / len(ingredients)

        scored.append((score, r))

    # sort best match first
    scored.sort(key=lambda x: x[0], reverse=True)

    top = scored[:3]

    if top:
        for score, r in top:
            label = "🍽 " + r["title"]
            if score > 0.6:
                label += " 🟢 (great pantry match)"
            elif score > 0.3:
                label += " 🟡 (partially in pantry)"
            else:
                label += " 🔴 (needs shopping)"

            col1, col2 = st.columns([3,1])
            col1.write(label)

            if col2.button("Add", key=f"ml_{r['id']}"):
                add_meal(week_start, "Dinner", r["id"])
                st.rerun()

except Exception:
    pass

# ─────────────────────────────────────────────────────────────
# SHOPPING LIST (simple)
# ───────────────────────────────────────────────────────────── (simple)
# ─────────────────────────────────────────────────────────────

