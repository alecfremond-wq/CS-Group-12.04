import streamlit as st

from src.components.ui import page_header
from src.data.user_repo import delete_profile, save_profile
from src.utils.session import init_session_state

init_session_state()
page_header(
    "👤 Onboarding",
    "Tell us about your diet, budget and cooking experience — "
    "this personalises every other page.",
)

DIETS = ["Omnivore", "Vegetarian", "Vegan", "Pescatarian", "Low-Carb", "High-Protein"]
ALLERGY_OPTIONS = ["Gluten", "Lactose", "Nuts", "Peanut", "Eggs", "Soy", "Shellfish", "Celiac"]
SKILLS = ["beginner", "intermediate", "advanced"]

def _render_form(existing: dict) -> None:

    with st.form("onboarding_form", clear_on_submit=False):
        name = st.text_input("Your name", value=existing.get("name", ""))
        diet = st.selectbox(
            "Diet",
            DIETS,
            index=DIETS.index(existing.get("diet", "omnivore"))
            if existing.get("diet", "omnivore") in DIETS else 0,
        )
        allergies = st.multiselect(
            "Allergies / intolerances",
            ALLERGY_OPTIONS,
            default=[a for a in existing.get("allergies", []) if a in ALLERGY_OPTIONS],
        )
        budget = st.slider(
            "Weekly food budget (CHF)",
            min_value=20, max_value=200, step=10,
            value=int(existing.get("budget_weekly", 80)),
        )
        skill = st.radio(
            "Cooking skill",
            SKILLS,
            horizontal=True,
            index=SKILLS.index(existing.get("skill_level", "beginner"))
            if existing.get("skill_level", "beginner") in SKILLS else 0,
        )
        submitted = st.form_submit_button("Save profile")

    if submitted:

        if not name.strip():
            st.error("Please enter your name so we can personalise things.")
            return

        profile = {
            "name": name.strip(),
            "diet": diet,
            "allergies": allergies,
            "budget_weekly": budget,
            "skill_level": skill,
        }

        save_profile(profile)

        st.session_state["user_profile"] = profile

        st.session_state["onboarding_editing"] = False

        st.success("Profile saved. You can now use the other pages.")

        st.rerun()

def _render_summary(profile: dict) -> None:

    with st.container(border=True):
        st.markdown(f"### Welcome back, **{profile.get('name') or 'friend'}** 👋")
        st.caption(
            "Your profile is saved. Other pages are already personalised for you."
        )

        left, right = st.columns(2)
        with left:
            st.markdown(f"**Diet:** {profile.get('diet', '—')}")
            st.markdown(
                f"**Weekly budget:** {int(profile.get('budget_weekly', 0))} CHF"
            )
        with right:
            allergies = profile.get("allergies") or []
            st.markdown(
                "**Allergies:** "
                + (", ".join(allergies) if allergies else "_none_")
            )
            st.markdown(f"**Skill level:** {profile.get('skill_level', '—')}")

    edit_col, delete_col, _ = st.columns([1, 1, 3])
    with edit_col:
        if st.button("Edit profile", use_container_width=True, type="secondary"):
            st.session_state["onboarding_editing"] = True
            st.rerun()
    with delete_col:
        if st.button(
            "Delete profile",
            use_container_width=True,
            type="secondary",
            help="Removes the saved profile from the database and resets onboarding.",
        ):
            delete_profile()
            st.session_state["user_profile"] = None
            st.session_state["onboarding_editing"] = False
            st.toast("Profile deleted.")
            st.rerun()

profile = st.session_state.get("user_profile") or {}

editing = st.session_state.get("onboarding_editing", False)

if not profile or editing:
    _render_form(existing=profile)

    if profile and editing:
        if st.button("Cancel", type="secondary"):
            st.session_state["onboarding_editing"] = False
            st.rerun()
else:
    _render_summary(profile)
