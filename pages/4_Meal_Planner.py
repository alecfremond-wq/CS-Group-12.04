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
    key = (str(row["meal_date"]), row["meal_type"])
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
                meal_title = plan[key]["title"]
                meal_id    = plan[key]["id"]
                st.markdown(f"🍽 {meal_title}")
                if st.button("✕", key=f"del_{meal_id}"):
                    delete_meal(meal_id)
                    st.rerun()
            else:
                # Show add button
                if st.button("＋", key=f"add_{meal_type}_{i}"):
                    st.session_state["adding_slot"] = (day_date, meal_type)

st.divider()


# ── ADD MEAL FLOW ────────────────────────────

if "adding_slot" in st.session_state:
    chosen_day, chosen_meal = st.session_state["adding_slot"]

    st.subheader(f"Add {chosen_meal} for {chosen_day.strftime('%A, %d %b')}")

    if recipes_df.empty:
        st.warning("No recipes found. Go to the Recipes page and save some first.")
    else:
        # Filter by meal type if the planner_pool has type info
        pool_df = query_df(
            "SELECT recipe_id FROM planner_pool WHERE user_id = ? AND meal_type = ?",
            (st.session_state.user_id, chosen_meal)
        )

        if pool_df is not None and not pool_df.empty:
            allowed = set(pool_df["recipe_id"].tolist())
            filtered = recipes_df[recipes_df["id"].isin(allowed)]
        else:
            filtered = recipes_df  # fall back to all recipes

        if filtered.empty:
            st.info(f"No recipes tagged for {chosen_meal}. Showing all recipes instead.")
            filtered = recipes_df

        for _, recipe in filtered.iterrows():
            col_name, col_btn = st.columns([4, 1])
            col_name.write(recipe["title"])
            if col_btn.button("Add", key=f"pick_{recipe['id']}_{chosen_day}_{chosen_meal}"):
                add_meal(chosen_day, chosen_meal, recipe["id"])
                del st.session_state["adding_slot"]
                st.rerun()

    if st.button("Cancel"):
        del st.session_state["adding_slot"]
        st.rerun()

    st.divider()


# ── SUMMARY ──────────────────────────────────

st.subheader("Summary")

if meals_df.empty:
    st.info("No meals planned yet this week.")
else:
    st.success(f"You have {len(meals_df)} meal(s) planned this week.")

    for meal_type in MEALS:
        subset = meals_df[meals_df["meal_type"] == meal_type]
        if subset.empty:
            continue
        st.markdown(f"**{meal_type}**")
        for _, m in subset.iterrows():
            day_name = pd.to_datetime(m["meal_date"]).strftime("%A")
            st.write(f"• {day_name}: {m['title']}")
