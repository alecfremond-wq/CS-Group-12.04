import streamlit as st
from datetime import date, timedelta
import sys, os
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.data.database import query_df, execute
from src.utils.session import init_session_state, require_profile
from src.components.ui import page_header

# ── PAGE SETUP ──────────────────────────────
st.set_page_config(page_title="Meal Planner", page_icon="📅", layout="wide")
init_session_state()
require_profile()
page_header("📅 Meal Planner", "Plan your week simply")

DAYS  = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEALS = ["Breakfast", "Lunch", "Dinner", "Dessert"]


# ── HELPERS ──────────────────────────────────

def get_week_start():
    if "week_start" not in st.session_state:
        today = date.today()
        st.session_state.week_start = today - timedelta(days=today.weekday())
    return st.session_state.week_start


def load_meals(week_start):
    week_end = week_start + timedelta(days=6)
    result = query_df(
        """
        SELECT mp.id, mp.meal_date, mp.meal_type, mp.recipe_id, r.title
        FROM meal_plan mp
        JOIN recipes r ON mp.recipe_id = r.id
        WHERE mp.user_id = ? AND mp.meal_date BETWEEN ? AND ?
        """,
        (st.session_state.user_id, week_start.isoformat(), week_end.isoformat())
    )
    if result is None:
        return pd.DataFrame(columns=["id", "meal_date", "meal_type", "recipe_id", "title"])
    return result


def load_recipes():
    base = query_df("SELECT id, title FROM recipes LIMIT 100", ())
    pool = query_df(
        "SELECT recipe_id AS id, title FROM planner_pool WHERE user_id = ?",
        (st.session_state.user_id,)
    )
    if base is None:
        base = pd.DataFrame(columns=["id", "title"])
    if pool is None:
        pool = pd.DataFrame(columns=["id", "title"])
    combined = pd.concat([base, pool], ignore_index=True).drop_duplicates(subset=["id"])
    return combined


def add_meal(day, meal_type, recipe_id):
    execute(
        """
        INSERT OR REPLACE INTO meal_plan (user_id, meal_date, meal_type, recipe_id)
        VALUES (?, ?, ?, ?)
        """,
        (st.session_state.user_id, day.isoformat(), meal_type, recipe_id)
    )


def delete_meal(meal_id):
    execute(
        "DELETE FROM meal_plan WHERE id = ? AND user_id = ?",
        (meal_id, st.session_state.user_id)
    )


# ── LOAD DATA ────────────────────────────────

week_start = get_week_start()
week_end   = week_start + timedelta(days=6)
meals_df   = load_meals(week_start)
recipes_df = load_recipes()

# Build a lookup dict: (date_string, meal_type) -> meal row dict
plan = {}

for _, row in meals_df.iterrows():
    date_key = pd.to_datetime(row["meal_date"]).date().isoformat()
    key = (date_key, row["meal_type"])
    plan[key] = row.to_dict()


# ── WEEK NAVIGATION ──────────────────────────

col_prev, col_title, col_next = st.columns([1, 2, 1])

with col_prev:
    if st.button("← Prev week"):
        st.session_state.week_start = week_start - timedelta(days=7)
        st.rerun()

with col_title:
    st.markdown(f"### {week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}")

with col_next:
    if st.button("Next week →"):
        st.session_state.week_start = week_start + timedelta(days=7)
        st.rerun()

st.divider()


# ── MEAL GRID ────────────────────────────────

st.subheader("Your Week")

# Header row: empty first cell + one cell per day
header = st.columns(8)
header[0].write("")  # row label column
for i, day_name in enumerate(DAYS):
    day_date = week_start + timedelta(days=i)
    header[i + 1].markdown(f"**{day_name}**  \n{day_date.strftime('%d %b')}")

st.divider()

# One row per meal type
for meal_type in MEALS:
    row = st.columns(8)
    row[0].markdown(f"**{meal_type}**")

    for i in range(7):
        day_date = week_start + timedelta(days=i)
        key      = (day_date.isoformat(), meal_type)

        with row[i + 1]:
            if key in plan:
                # Show the meal title and a delete button
                meal_title = plan[key].get("title", "Unknown meal")
                meal_id    = plan[key]["id"]
                icons = {
                    "Breakfast": "🍳",
                    "Lunch": "🥗",
                    "Dinner": "🍝",
                    "Dessert": "🍰"
                }
                st.markdown(f"{icons.get(meal_type,'🍽')} **{meal_title}**")
                if st.button("✕", key=f"del_{meal_id}"):
                    delete_meal(meal_id)
                    st.rerun()
            else:
                select_key = f"select_{meal_type}_{i}_{day_date}"

                recipe_options = recipes_df.set_index("id")["title"].to_dict()

                selected = st.selectbox(
                    " ",
                    options=[None] + list(recipe_options.keys()),
                    format_func=lambda x: "Select..." if x is None else recipe_options[x],
                    key=select_key,
                    label_visibility="collapsed"
                )   

                prev_key = f"{select_key}_prev"

                if selected and st.session_state.get(prev_key) != selected:
                    st.session_state[prev_key] = selected
                    add_meal(day_date, meal_type, selected)
                    st.rerun()

st.divider()

# ── SUMMARY ──────────────────────────────────

st.subheader("Summary")

if meals_df.empty:
    st.info("No meals planned yet this week.")
else:
    st.success(f"You have {len(meals_df)} meal(s) planned this week.")

    meals_df["meal_date"] = pd.to_datetime(meals_df["meal_date"])
    meals_df = meals_df.sort_values("meal_date")

    for i in range(7):
        day_date = week_start + timedelta(days=i)
        day_name = day_date.strftime("%A")

        day_meals = meals_df[
            meals_df["meal_date"].dt.date == day_date
        ]

        if day_meals.empty:
            continue

        st.markdown(f"### {day_name}")

        for _, m in day_meals.iterrows():
            st.write(f"- **{m['meal_type']}**: {m['title']}")