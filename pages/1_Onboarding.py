"""
Onboarding — capture the user's diet, allergies, budget and skill level.

Owner: <assign on Apr 22>
Grading coverage:
    * Req. 4 (user interaction — form input)
    * Feeds Req. 5 (ML uses the profile to personalise recommendations)

TODOs for the owner:
    - persist the profile to the `users` table (see src/data/database.py)
    - add a "delete my profile" button for demos
"""

import streamlit as st

from src.components.ui import page_header
from src.utils.session import init_session_state


init_session_state()
page_header(
    "👤 Onboarding",
    "Tell us about your diet, budget and cooking experience — "
    "this personalises every other page.",
)

existing = st.session_state.get("user_profile") or {}

with st.form("onboarding_form", clear_on_submit=False):
    name = st.text_input("Your name", value=existing.get("name", ""))
    diet = st.selectbox(
        "Diet",
        ["omnivore", "vegetarian", "vegan", "pescatarian"],
        index=["omnivore", "vegetarian", "vegan", "pescatarian"].index(
            existing.get("diet", "omnivore")
        ),
    )
    allergies = st.multiselect(
        "Allergies / intolerances",
        ["gluten", "lactose", "nuts", "eggs", "soy", "shellfish"],
        default=existing.get("allergies", []),
    )
    budget = st.slider(
        "Weekly food budget (CHF)",
        min_value=20, max_value=200, step=10,
        value=int(existing.get("budget_weekly", 80)),
    )
    skill = st.radio(
        "Cooking skill",
        ["beginner", "intermediate", "advanced"],
        horizontal=True,
        index=["beginner", "intermediate", "advanced"].index(
            existing.get("skill_level", "beginner")
        ),
    )
    submitted = st.form_submit_button("Save profile", type="primary")

if submitted:
    st.session_state["user_profile"] = {
        "name": name,
        "diet": diet,
        "allergies": allergies,
        "budget_weekly": budget,
        "skill_level": skill,
    }
    st.success("Profile saved. You can now use the other pages.")
