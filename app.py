# ============================================================================
#  CookTogether — HOME PAGE + ONBOARDING (combined entry point)
#  Run it from the terminal with:   streamlit run app.py
# ============================================================================
#  NOTE ON AUTHORSHIP (required by HSG plagiarism rules):
#  The initial scaffold of this file was generated with the help of an AI
#  assistant (Anthropic Claude, April 2026) and then reviewed and adapted
#  by Group 12.04. See README.md for full citation.
# ============================================================================

import streamlit as st

from src.data.database import init_db
from src.data.user_repo import delete_profile, save_profile
from src.utils.session import init_session_state


# --- page configuration ----------------------------------------------------
st.set_page_config(
    page_title="Cooktogether",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- one-time initialisation -----------------------------------------------
init_db()
init_session_state()


# ===========================================================================
#  SIDEBAR
# ===========================================================================
with st.sidebar:
    st.markdown("### 🗺️ Getting started")
    st.markdown(
        "1. Fill out **Onboarding** below.\n"
        "2. Add items to your **Pantry**.\n"
        "3. Browse **Recipes** and add favourites to your **Meal Planner**.\n"
        "4. Check **Nutrition** and **Recommendations** to see insights."
    )
    st.divider()

    if st.session_state.get("user_profile"):
        st.success(
            f"Signed in as **{st.session_state['user_profile'].get('name', 'you')}**"
        )
    else:
        st.info("No profile yet — complete Onboarding below ⬇️")


# ===========================================================================
#  SECTION 1 — HOME / APP OVERVIEW
# ===========================================================================
st.title("🍳 CookTogether")
st.subheader("Cook, plan, and eat well — together.")

st.markdown(
    """
    **CookTogether** helps students cook more joyfully by combining:

    - a personalised onboarding profile (diet, allergies, budget, skill),
    - recipe discovery based on what you already have in your pantry,
    - a weekly **meal planner** with budget tracking,
    - **nutrition analytics** so you can see what you actually eat,
    - a world map to explore recipes by origin, and
    - ML-powered **recommendations** that learn from your cooking history.

    Use the sidebar on the left to navigate between pages.
    """
)


# ===========================================================================
#  TRANSITION
# ===========================================================================
st.divider()

st.markdown("## Ready to get started?")
st.caption("Create your profile to personalise every page of CookTogether.")

if "show_onboarding" not in st.session_state:
    st.session_state["show_onboarding"] = False

# Show the "Get Started" button only if there is no profile yet
if not st.session_state.get("user_profile") and not st.session_state["show_onboarding"]:
    st.markdown("""
        <style>
        div.stButton > button {
            background: white;
            color: #FF6B35;
            border: 2px solid #FF6B35;
            padding: 0.75rem 2.5rem;
            font-size: 1.1rem;
            font-weight: 600;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.25s ease;
        }
        div.stButton > button:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(255, 107, 53, 0.3);
            background: #fff5f2;
        }
        </style>
    """, unsafe_allow_html=True)

    if st.button("Get Started"):
        st.session_state["show_onboarding"] = True
        st.rerun()


# ===========================================================================
#  SECTION 2 — ONBOARDING (appears only after button click)
# ===========================================================================

DIETS = ["Omnivore", "Vegetarian", "Vegan", "Pescatarian", "Low-Carb", "High-Protein"]
ALLERGY_OPTIONS = ["Gluten", "Lactose", "Nuts", "Peanut", "Eggs", "Soy", "Shellfish", "Celiac"]
SKILLS = ["beginner", "intermediate", "advanced"]


def _render_form(existing: dict) -> None:
    with st.form("onboarding_form", clear_on_submit=False):
        name = st.text_input("Your name", value=existing.get("name", ""))

        diet = st.selectbox(
            "Diet",
            DIETS,
            index=DIETS.index(existing.get("diet", "Omnivore"))
            if existing.get("diet", "Omnivore") in DIETS else 0,
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
        st.session_state["show_onboarding"] = False
        st.success("✅ Profile saved! You can now use the other pages.")
        st.rerun()


def _render_summary(profile: dict) -> None:
    with st.container(border=True):
        st.markdown(f"### Welcome back, **{profile.get('name') or 'friend'}** 👋")
        st.caption("Your profile is saved. Other pages are already personalised for you.")

        left, right = st.columns(2)
        with left:
            st.markdown(f"**Diet:** {profile.get('diet', '—')}")
            st.markdown(f"**Weekly budget:** {int(profile.get('budget_weekly', 0))} CHF")
        with right:
            allergies = profile.get("allergies") or []
            st.markdown(
                "**Allergies:** " + (", ".join(allergies) if allergies else "_none_")
            )
            st.markdown(f"**Skill level:** {profile.get('skill_level', '—')}")

    edit_col, delete_col, _ = st.columns([1, 1, 3])

    with edit_col:
        if st.button("Edit profile", use_container_width=True):
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
            st.session_state["show_onboarding"] = False
            st.toast("Profile deleted.")
            st.rerun()


# --- render onboarding section ---------------------------------------------
if st.session_state.get("show_onboarding") or st.session_state.get("user_profile"):

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
