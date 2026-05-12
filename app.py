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
from src.data.user_repo import check_login, create_account, delete_profile, load_profile, save_profile
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
        "1. Create an account or log in below.\n"
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
        st.info("No profile yet — create an account to get started.")


# ===========================================================================
#  SECTION 1 — HOME / APP OVERVIEW
# ===========================================================================
st.title("🍳 CookTogether")
st.subheader("Cook, plan, and eat well — together.")

st.markdown(
    """
    **CookTogether** helps students cook more joyfully by combining:

    - a personalised profile (diet, allergies, skill),
    - recipe discovery based on what you already have in your pantry,
    - a weekly **meal planner**,
    - **nutrition analytics** so you can see what you actually eat,
    - a world map to explore recipes by origin, and
    - ML-powered **recommendations** that learn from your cooking history.

    Use the sidebar on the left to navigate between pages.
    """
)

st.divider()


# ===========================================================================
#  ONBOARDING HELPERS
# ===========================================================================

DIETS = ["Omnivore", "Vegetarian", "Vegan", "Pescatarian", "Low-Carb", "High-Protein"]
ALLERGY_OPTIONS = ["Gluten", "Lactose", "Nuts", "Peanut", "Eggs", "Soy", "Shellfish", "Celiac"]
SKILLS = ["beginner", "intermediate", "advanced"]


def _logout() -> None:
    """Clear all user data from the session so the next person starts fresh."""
    st.session_state["user_id"] = None
    st.session_state["user_profile"] = None
    st.session_state["pantry"] = []
    st.session_state["meal_plan"] = {}
    st.session_state["cooking_history"] = []
    st.session_state["wishlist"] = []
    st.session_state["onboarding_editing"] = False
    st.session_state["show_onboarding"] = False
    st.query_params.clear()


def _render_auth() -> None:
    """Login / Sign-up screen — shown when no user is logged in."""

    st.markdown("## Ready to get started?")

    # st.tabs creates two clickable tabs side by side
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            # type="password" masks what the user types
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", type="primary")

        if submitted:
            if not username or not password:
                st.error("Please fill in all fields.")
            else:
                # check_login returns the user_id if credentials match, else None
                user_id = check_login(username, password)
                if user_id is None:
                    st.error("Wrong username or password.")
                else:
                    st.session_state["user_id"] = user_id
                    st.session_state["user_profile"] = load_profile(user_id)
                    st.session_state["pantry"] = []
                    st.query_params["uid"] = user_id
                    st.rerun()

    with tab_signup:
        with st.form("signup_form"):
            name      = st.text_input("Your name")
            username  = st.text_input("Choose a username")
            password  = st.text_input("Choose a password", type="password")
            diet      = st.selectbox("Diet", DIETS)
            allergies = st.multiselect("Allergies / intolerances", ALLERGY_OPTIONS)
            skill     = st.radio("Cooking skill", SKILLS, horizontal=True)
            submitted = st.form_submit_button("Create account", type="primary")

        if submitted:
            if not name.strip() or not username.strip() or not password:
                st.error("Please fill in all fields.")
            else:
                profile = {
                    "name": name.strip(),
                    "diet": diet,
                    "allergies": allergies,
                    "skill_level": skill,
                }
                try:
                    # create_account raises ValueError if the username is already taken
                    user_id = create_account(profile, username, password)
                    st.session_state["user_id"] = user_id
                    st.session_state["user_profile"] = profile
                    st.session_state["pantry"] = []
                    st.query_params["uid"] = user_id
                    st.success("Account created! Welcome 🎉")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


def _render_edit_form(existing: dict) -> None:
    """Edit profile fields — username and password stay unchanged here."""

    with st.form("edit_form", clear_on_submit=False):
        name = st.text_input("Your name", value=existing.get("name", ""))
        diet = st.selectbox(
            "Diet", DIETS,
            index=DIETS.index(existing.get("diet", "Omnivore"))
            if existing.get("diet", "Omnivore") in DIETS else 0,
        )
        allergies = st.multiselect(
            "Allergies / intolerances", ALLERGY_OPTIONS,
            default=[a for a in existing.get("allergies", []) if a in ALLERGY_OPTIONS],
        )
        skill = st.radio(
            "Cooking skill", SKILLS, horizontal=True,
            index=SKILLS.index(existing.get("skill_level", "beginner"))
            if existing.get("skill_level", "beginner") in SKILLS else 0,
        )
        submitted = st.form_submit_button("Save changes", type="primary")

    if submitted:
        if not name.strip():
            st.error("Please enter your name.")
            return
        profile = {
            "name": name.strip(),
            "diet": diet,
            "allergies": allergies,
            "skill_level": skill,
        }
        save_profile(profile, user_id=st.session_state["user_id"])
        st.session_state["user_profile"] = profile
        st.session_state["onboarding_editing"] = False
        st.success("Profile updated.")
        st.rerun()

    if st.button("Cancel", type="secondary"):
        st.session_state["onboarding_editing"] = False
        st.rerun()


def _render_summary(profile: dict) -> None:
    """Profile card shown when the user is logged in."""

    with st.container(border=True):
        st.markdown(f"### Welcome back, **{profile.get('name') or 'friend'}** 👋")
        st.caption("Your profile is saved. Other pages are already personalised for you.")

        left, right = st.columns(2)
        with left:
            st.markdown(f"**Diet:** {profile.get('diet', '—')}")
        with right:
            allergies = profile.get("allergies") or []
            st.markdown("**Allergies:** " + (", ".join(allergies) if allergies else "_none_"))
            st.markdown(f"**Skill level:** {profile.get('skill_level', '—')}")

    edit_col, delete_col, logout_col, _ = st.columns([1, 1, 1, 2])

    with edit_col:
        if st.button("✏️ Edit profile", use_container_width=True):
            st.session_state["onboarding_editing"] = True
            st.rerun()

    with delete_col:
        if st.button("🗑️ Delete account", use_container_width=True):
            delete_profile(st.session_state["user_id"])
            _logout()
            st.toast("Account deleted.")
            st.rerun()

    with logout_col:
        if st.button("🚪 Log out", use_container_width=True):
            _logout()
            st.rerun()


# ===========================================================================
#  SECTION 2 — ONBOARDING / PROFILE (rendered below the home text)
# ===========================================================================

if "show_onboarding" not in st.session_state:
    st.session_state["show_onboarding"] = False

profile = st.session_state.get("user_profile") or {}
editing = st.session_state.get("onboarding_editing", False)

if not profile:
    # Show "Get Started" button first, expand to login/signup on click
    if not st.session_state["show_onboarding"]:
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
            /* Allergy toggle — orange accent */
            div[data-testid="stToggle"] label {
                font-weight: 500;
            }
            div[data-testid="stToggle"] input:checked + div {
                background-color: #FF6B35 !important;
            }
            </style>
        """, unsafe_allow_html=True)

        if st.button("Get Started"):
            st.session_state["show_onboarding"] = True
            st.rerun()
    else:
        _render_auth()

elif editing:
    _render_edit_form(existing=profile)

else:
    _render_summary(profile)
