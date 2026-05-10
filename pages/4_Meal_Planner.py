import streamlit as st
from datetime import date, timedelta
import sys, os
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from src.data.database import query_df, execute
from src.utils.session import init_session_state, require_profile
from src.components.ui import page_header

st.set_page_config(page_title="Meal Planner", page_icon="📅", layout="wide")
init_session_state()
require_profile()

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEALS = ["Breakfast", "Lunch", "Dinner", "Snacks"]
ICONS = {"Breakfast": "🍳", "Lunch": "🥗", "Dinner": "🍝", "Snacks": "🍰"}

# --- WEEK NAVIGATION ---
today = date.today()
if "week_start" not in st.session_state:
    st.session_state.week_start = today - timedelta(days=today.weekday())

week_start = st.session_state.week_start
week_end = week_start + timedelta(days=6)

# Clear meal selections when switching weeks
if st.session_state.get("active_week") != week_start.isoformat():
    for k in [k for k in st.session_state if str(k).startswith("meal_")]:
        del st.session_state[k]
    st.session_state.active_week = week_start.isoformat()

page_header("📅 Meal Planner", "Choose your meals in the recipe page and plan your week")

c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    if st.button("← Prev week"):
        st.session_state.week_start -= timedelta(days=7)
        st.rerun()
with c2:
    st.markdown(f"### {week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}")
with c3:
    if st.button("Next week →", disabled=week_start >= today - timedelta(days=today.weekday())):
        st.session_state.week_start += timedelta(days=7)
        st.rerun()

st.divider()

# --- LOAD DATA ---
meals_df = query_df(
    "SELECT mp.id, mp.meal_date, mp.meal_type, mp.recipe_id, r.title "
    "FROM meal_plan mp JOIN recipes r ON mp.recipe_id = r.id "
    "WHERE mp.user_id = ? AND mp.meal_date BETWEEN ? AND ? "
    "ORDER BY mp.meal_date, mp.meal_type",
    (st.session_state.user_id, week_start.isoformat(), week_end.isoformat())
) or pd.DataFrame(columns=["id", "meal_date", "meal_type", "recipe_id", "title"])

recipes_df = query_df(
    "SELECT pp.recipe_id AS id, r.title FROM planner_pool pp "
    "JOIN recipes r ON pp.recipe_id = r.id WHERE pp.user_id = ? ORDER BY r.title",
    (st.session_state.user_id,)
) or pd.DataFrame(columns=["id", "title"])

recipe_dict = recipes_df.set_index("id")["title"].to_dict()

# Build a lookup: (date_str, meal_type) -> meal row
plan = {
    (pd.to_datetime(row["meal_date"]).date().isoformat(), row["meal_type"]): row
    for _, row in meals_df.iterrows()
}

# --- GRID HEADER ---
st.subheader("Your Week")
cols = st.columns(8)
cols[0].write("")
for i, day in enumerate(DAYS):
    cols[i + 1].markdown(f"**{day}**  \n{(week_start + timedelta(days=i)).strftime('%d %b')}")

st.divider()

# --- MEAL GRID ---
for meal in MEALS:
    row = st.columns(8)
    row[0].markdown(f"**{meal}**")

    for i in range(7):
        d = (week_start + timedelta(days=i)).isoformat()
        with row[i + 1]:
            if (d, meal) in plan:
                entry = plan[(d, meal)]
                st.markdown(f"{ICONS.get(meal, '🍽')} **{entry['title']}**")
                if st.button("✕", key=f"del_{entry['id']}"):
                    execute("DELETE FROM meal_plan WHERE id = ? AND user_id = ?",
                            (entry["id"], st.session_state.user_id))
                    st.rerun()
            elif not recipe_dict:
                st.caption("No recipes yet!")
            else:
                chosen = st.selectbox(
                    " ",
                    options=[""] + list(recipe_dict.keys()),
                    format_func=lambda x: "Select..." if x == "" else recipe_dict.get(x, x),
                    key=f"meal_{week_start.isoformat()}_{meal}_{d}_{i}",
                    label_visibility="collapsed"
                )
                if chosen:
                    execute("INSERT OR REPLACE INTO meal_plan (user_id, meal_date, meal_type, recipe_id) VALUES (?, ?, ?, ?)",
                            (st.session_state.user_id, d, meal, chosen))
                    st.rerun()

st.divider()
