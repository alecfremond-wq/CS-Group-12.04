import streamlit as st
from datetime import date, timedelta
import sys
import os
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.data.database import query_df, execute
from src.utils.session import init_session_state, require_profile
from src.components.ui import page_header

st.set_page_config(page_title="Meal Planner", page_icon="📅", layout="wide")

init_session_state()
require_profile()

page_header("📅 Meal Planner", "Plan your week simply")

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEALS = ["Breakfast", "Lunch", "Dinner", "Dessert"]

# --- WEEK START ---
if "week_start" not in st.session_state:
    today = date.today()
    st.session_state.week_start = today - timedelta(days=today.weekday())

week_start = st.session_state.week_start
week_end = week_start + timedelta(days=6)

# --- LOAD MEALS ---
meals_df = query_df(
    """
    SELECT mp.id, mp.meal_date, mp.meal_type, mp.recipe_id, r.title
    FROM meal_plan mp
    JOIN recipes r ON mp.recipe_id = r.id
    WHERE mp.user_id = ?
    AND mp.meal_date BETWEEN ? AND ?
    """,
    (st.session_state.user_id, week_start.isoformat(), week_end.isoformat())
)

if meals_df is None:
    meals_df = pd.DataFrame(columns=["id", "meal_date", "meal_type", "recipe_id", "title"])

# --- LOAD RECIPES ---
recipes1 = query_df("SELECT id, title FROM recipes LIMIT 100", ())

recipes2 = query_df(
    "SELECT recipe_id AS id, title FROM planner_pool WHERE user_id = ?",
    (st.session_state.user_id,)
)

if recipes1 is None:
    recipes1 = pd.DataFrame(columns=["id", "title"])

if recipes2 is None:
    recipes2 = pd.DataFrame(columns=["id", "title"])

recipes_df = pd.concat([recipes1, recipes2]).drop_duplicates(subset=["id"])
recipe_dict = recipes_df.set_index("id")["title"].to_dict()

# --- PLAN DICT ---
plan = {}
for _, row in meals_df.iterrows():
    d = pd.to_datetime(row["meal_date"]).date().isoformat()
    plan[(d, row["meal_type"])] = row

# --- WEEK NAV ---
c1, c2, c3 = st.columns([1, 2, 1])

with c1:
    if st.button("← Prev week"):
        st.session_state.week_start = week_start - timedelta(days=7)
        st.rerun()

with c2:
    st.markdown(f"### {week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}")

with c3:
    if st.button("Next week →"):
        st.session_state.week_start = week_start + timedelta(days=7)
        st.rerun()

st.divider()

# --- GRID ---
st.subheader("Your Week")

cols = st.columns(8)
cols[0].write("")

for i in range(7):
    d = week_start + timedelta(days=i)
    cols[i + 1].markdown(f"**{DAYS[i]}**  \n{d.strftime('%d %b')}")

st.divider()

icons = {
    "Breakfast": "🍳",
    "Lunch": "🥗",
    "Dinner": "🍝",
    "Dessert": "🍰"
}

for meal in MEALS:
    row = st.columns(8)
    row[0].markdown(f"**{meal}**")

    for i in range(7):
        d = week_start + timedelta(days=i)
        key = (d.isoformat(), meal)

        with row[i + 1]:
            # --- IF MEAL EXISTS ---
            if key in plan:
                meal_data = plan[key]

                st.markdown(f"{icons.get(meal, '🍽')} **{meal_data['title']}**")

                if st.button("✕", key=f"del_{meal_data['id']}"):
                    execute(
                        "DELETE FROM meal_plan WHERE id = ? AND user_id = ?",
                        (meal_data["id"], st.session_state.user_id)
                    )
                    st.rerun()

            # --- IF EMPTY SLOT ---
            else:
                select_key = f"{meal}_{i}_{d}"

                selected = st.selectbox(
                    " ",
                    options=[None] + list(recipe_dict.keys()),
                    format_func=lambda x: "Select..." if x is None else recipe_dict[x],
                    key=select_key,
                    label_visibility="collapsed"
                )

                prev_key = select_key + "_prev"

                if selected and st.session_state.get(prev_key) != selected:
                    st.session_state[prev_key] = selected

                    execute(
                        """
                        INSERT OR REPLACE INTO meal_plan
                        (user_id, meal_date, meal_type, recipe_id)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            st.session_state.user_id,
                            d.isoformat(),
                            meal,
                            selected
                        )
                    )
                    st.rerun()

st.divider()

# --- SUMMARY ---
st.subheader("Summary")

if meals_df.empty:
    st.info("No meals planned yet this week.")
else:
    st.success(f"You have {len(meals_df)} meal(s) planned this week.")

    meals_df["meal_date"] = pd.to_datetime(meals_df["meal_date"])
    meals_df = meals_df.sort_values("meal_date")

    for i in range(7):
        d = week_start + timedelta(days=i)
        day_meals = meals_df[meals_df["meal_date"].dt.date == d]

        if len(day_meals) == 0:
            continue

        st.markdown(f"### {d.strftime('%A')}")

        for _, m in day_meals.iterrows():
            st.write(f"- **{m['meal_type']}**: {m['title']}")
