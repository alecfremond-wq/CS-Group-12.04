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
    WHERE mp.user_id = ? AND mp.meal_date BETWEEN ? AND ?
    """,
    (st.session_state.user_id, week_start.isoformat(), week_end.isoformat())
)

if meals_df is None:
    meals_df = pd.DataFrame(columns=["id", "meal_date", "meal_type", "recipe_id", "title"])

# normalize date ONCE (important fix)
meals_df["meal_date"] = pd.to_datetime(meals_df["meal_date"]).dt.date

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

# --- GRID HEADER ---
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

# --- GRID ---
for meal in MEALS:
    row = st.columns(8)
    row[0].markdown(f"**{meal}**")

    for i in range(7):
        d = week_start + timedelta(days=i)

        with row[i + 1]:

            day_meals = meals_df[
                (meals_df["meal_date"] == d) &
                (meals_df["meal_type"] == meal)
            ]

            if not day_meals.empty:
                m = day_meals.iloc[0]

                st.markdown(f"{icons.get(meal,'🍽')} **{m['title']}**")

                if st.button("Remove", key=f"del_{m['id']}"):
                    execute(
                        "DELETE FROM meal_plan WHERE id = ? AND user_id = ?",
                        (m["id"], st.session_state.user_id)
                    )
                    st.rerun()

            else:
                selected = st.selectbox(
                    "",
                    options=list(recipe_dict.keys()),
                    format_func=lambda x: recipe_dict[x],
                    key=f"{meal}_{i}_{d}",
                    label_visibility="collapsed"
                )

                if selected:
                    execute(
                        """
                        INSERT OR REPLACE INTO meal_plan (user_id, meal_date, meal_type, recipe_id)
                        VALUES (?, ?, ?, ?)
                        """,
                        (st.session_state.user_id, d.isoformat(), meal, selected)
                    )
                    st.rerun()

st.divider()

# --- SUMMARY ---
st.subheader("Summary")

if meals_df.empty:
    st.info("No meals planned yet this week.")
else:
    st.success(f"You have {len(meals_df)} meal(s) planned this week.")

    meals_df = meals_df.sort_values("meal_date")

    for d in sorted(meals_df["meal_date"].unique()):
        st.markdown(f"### {d.strftime('%A')}")

        for _, m in meals_df[meals_df["meal_date"] == d].iterrows():
            st.write(f"- **{m['meal_type']}**: {m['title']}")
