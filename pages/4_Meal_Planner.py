import streamlit as st
from datetime import date, timedelta
import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.data.database import query_df, execute
from src.utils.session import init_session_state, require_profile
from src.components.ui import page_header

# ─────────────────────────────────────────────
# SETUP (MUST BE FIRST STREAMLIT CALL)
# ─────────────────────────────────────────────
st.set_page_config(page_title="Meal Planner", page_icon="📅", layout="wide")

init_session_state()
require_profile()

page_header("📅 Meal Planner", "Plan your week simply")

DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
MEALS = ["Breakfast","Lunch","Dinner"]

# ─────────────────────────────────────────────
# HELPERS (DEFINED FIRST → FIXES YOUR ERROR)
# ─────────────────────────────────────────────

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
    """
    SAFE loader:
    - tries DB first
    - falls back to empty list instead of crashing flow
    """

    df = query_df("SELECT id, title FROM recipes LIMIT 100", ())

    if df is None or df.empty:
        return []

    return df


def add_meal(day, meal_type, recipe_id):
    execute(
        """
        INSERT OR REPLACE INTO meal_plan
        (user_id, meal_date, meal_type, recipe_id)
        VALUES (?, ?, ?, ?)
        """,
        (st.session_state.user_id, day.isoformat(), meal_type, recipe_id)
    )


def delete_meal(meal_id):
    execute(
        "DELETE FROM meal_plan WHERE id=? AND user_id=?",
        (meal_id, st.session_state.user_id)
    )

# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
week_start = get_week_start()
week_end = week_start + timedelta(days=6)

meals = get_meals(week_start)
recipes = get_recipes()

plan = {}
for _, m in meals.iterrows():
    plan[(str(m["meal_date"]), m["meal_type"])] = m.to_dict()

# ─────────────────────────────────────────────
# NAVIGATION
# ─────────────────────────────────────────────
c1, c2, c3 = st.columns([1,2,1])

with c1:
    if st.button("← Prev"):
        st.session_state.week_start = week_start - timedelta(days=7)
        st.rerun()

with c2:
    st.markdown(f"### {week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}")

with c3:
    if st.button("Next →"):
        st.session_state.week_start = week_start + timedelta(days=7)
        st.rerun()

st.divider()

# ─────────────────────────────────────────────
# GRID
# ─────────────────────────────────────────────
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

                if st.button("✕", key=f"del_{plan[key]['id']}"):
                    delete_meal(plan[key]["id"])
                    st.rerun()

            else:
                if st.button("+", key=f"add_{meal}_{i}"):
                    st.session_state["adding_slot"] = (day, meal)

# ─────────────────────────────────────────────
# ADD MEAL FLOW
# ─────────────────────────────────────────────
if "adding_slot" in st.session_state:
    day, meal = st.session_state["adding_slot"]

    st.subheader(f"Add {meal} for {day.strftime('%A %d %b')}")

    # 🔥 fallback safety: if DB empty, tell user clearly
    if recipes is None or len(recipes) == 0:
        st.warning("No saved recipes yet. Go to Recipes page and search something first.")
    else:
        for _, r in recipes.iterrows():
            col1, col2 = st.columns([3, 1])

            col1.write(r["title"])

            if col2.button("Add", key=f"add_{r['id']}_{day}_{meal}"):
                add_meal(day, meal, r["id"])
                del st.session_state["adding_slot"]
                st.rerun()

    if st.button("Cancel"):
        del st.session_state["adding_slot"]
        st.rerun()

# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
st.subheader("Summary")

if meals.empty:
    st.info("No meals planned yet.")
else:
    st.success(f"You planned {len(meals)} meals this week.")
