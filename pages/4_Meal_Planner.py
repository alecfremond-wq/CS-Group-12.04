"""
Meal Planner — assemble a weekly plan and track its cost.

Owner: <assign on Apr 22>
Grading coverage:
    * Req. 4 (user interaction — build a plan)
    * Req. 3 (visualisation — cost vs. budget bar)

TODOs for the owner:
    - let the user pick recipes from the DB (not just free text).
    - show a warning when the plan exceeds the weekly budget.
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.components.ui import empty_state, page_header
from src.utils.session import init_session_state, require_profile


init_session_state()
profile = require_profile()
page_header("📆 Meal Planner", "Plan your week and keep an eye on your budget.")

# --- week selector --------------------------------------------------------
today = date.today()
monday = today - timedelta(days=today.weekday())
week_days = [monday + timedelta(days=i) for i in range(7)]

st.write(f"Planning the week of **{monday.isoformat()}**.")

plan: dict = st.session_state["meal_plan"]

for day in week_days:
    key = day.isoformat()
    plan.setdefault(key, [])
    with st.expander(f"{day.strftime('%A')} · {key}"):
        new_meal = st.text_input(
            "Add a meal",
            key=f"new_meal_{key}",
            placeholder="e.g. Pasta al pesto",
        )
        if st.button("Add", key=f"add_{key}") and new_meal.strip():
            plan[key].append(new_meal.strip())
        if plan[key]:
            for meal in plan[key]:
                st.write(f"• {meal}")

# --- budget visualisation -------------------------------------------------
st.subheader("Budget vs. spend (placeholder)")
total_recipes = sum(len(v) for v in plan.values())
# Placeholder: assume CHF 5 per meal until the DB is wired up.
estimated_spend = total_recipes * 5
chart_df = pd.DataFrame(
    {"category": ["Budget", "Planned spend"],
     "CHF": [profile["budget_weekly"], estimated_spend]}
)
st.bar_chart(chart_df, x="category", y="CHF")

if total_recipes == 0:
    empty_state("No meals planned yet — add some above.")
