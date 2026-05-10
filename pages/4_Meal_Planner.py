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

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEALS = ["Breakfast", "Lunch", "Dinner", "Snacks"]

def load_meals_for_week(user_id: int, week_start: date, week_end: date):
    query = """
        SELECT mp.id, mp.meal_date, mp.meal_type, mp.recipe_id, r.title
        FROM meal_plan mp
        JOIN recipes r ON mp.recipe_id = r.id
        WHERE mp.user_id = ?
        AND mp.meal_date BETWEEN ? AND ?
        ORDER BY mp.meal_date, mp.meal_type
    """
    meals_df = query_df(
        query,
        (user_id, week_start.isoformat(), week_end.isoformat())
    )
    if meals_df is None:
        meals_df = pd.DataFrame(
            columns=["id", "meal_date", "meal_type", "recipe_id", "title"]
        )
    return meals_df

# --- WEEK START ---
if "week_start" not in st.session_state:
    today = date.today()
    st.session_state.week_start = today - timedelta(days=today.weekday())

week_current = date.today() - timedelta(days=date.today().weekday())
week_start = st.session_state.week_start
week_end = week_start + timedelta(days=6)
week_id = week_start.isoformat()

if st.session_state.get("active_week") != week_id:
    keys_to_delete = [
        k for k in list(st.session_state.keys())
        if isinstance(k, str) and k.startswith("meal_")
    ]
    for k in keys_to_delete:
        del st.session_state[k]
    st.session_state.active_week = week_id

require_profile()
page_header("📅 Meal Planner", "Choose your meals in the recipe page and plan your week")

# --- LOAD MEALS ---
meals_df = load_meals_for_week(
    user_id=st.session_state.user_id,
    week_start=week_start,
    week_end=week_end
)

# --- LOAD RECIPES ---
# IMPORTANT: only load from planner_pool, NOT from the full recipes table.
# This way, removing a recipe from the Recipes page immediately removes it
# from this dropdown too — both are driven by the same planner_pool table.
recipes_df = query_df(
    """
    SELECT pp.recipe_id AS id, r.title
    FROM planner_pool pp
    JOIN recipes r ON pp.recipe_id = r.id
    WHERE pp.user_id = ?
    ORDER BY r.title
    """,
    (st.session_state.user_id,)
)

if recipes_df is None or recipes_df.empty:
    recipes_df = pd.DataFrame(columns=["id", "title"])

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
    disable_next = week_start >= week_current
    if st.button("Next week →", disabled=disable_next):
        if not disable_next:
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
    "Snack": "🍰"
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
                if not recipe_dict:
                    st.caption("No recipes saved yet. Go to Recipes to add some!")
                else:
                    select_key = f"meal_{week_id}_{meal}_{d.isoformat()}_{i}"

                    # Use a string sentinel ("") instead of None so Streamlit
                    # doesn't render a clear (✕) button on the empty option.
                    PLACEHOLDER = ""
                    options = [PLACEHOLDER] + list(recipe_dict.keys())

                    selected_raw = st.selectbox(
                        " ",
                        options=options,
                        format_func=lambda x: "Select..." if x == PLACEHOLDER else recipe_dict.get(x, x),
                        key=select_key,
                        label_visibility="collapsed"
                    )

                    selected = selected_raw if selected_raw != PLACEHOLDER else None

                    if selected:
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
