import streamlit as st

from src.data.user_repo import check_login, create_account, delete_profile, load_profile, save_profile
from src.utils.session import init_session_state

init_session_state()


#1. Constants ################
DIETS           = ["Omnivore", "Vegetarian", "Vegan", "Pescatarian", "Low-Carb", "High-Protein"]
ALLERGY_OPTIONS = ["Gluten", "Lactose", "Nuts", "Peanut", "Eggs", "Soy", "Shellfish", "Celiac"]
SKILLS          = ["beginner", "intermediate", "advanced"]


#2. Helper functions ##########

def _logout() -> None:
    st.session_state["user_id"]            = None
    st.session_state["user_profile"]       = None
    st.session_state["pantry"]             = []
    st.session_state["meal_plan"]          = {}
    st.session_state["cooking_history"]    = []
    st.session_state["wishlist"]           = []
    st.session_state["onboarding_editing"] = False
    st.session_state["show_onboarding"]    = False
    st.query_params.clear()


def _render_auth() -> None:
    st.markdown("## Ready to get started?")
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

    with tab_login:
        with st.form("login_form"):
            username  = st.text_input("Username")
            password  = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", type="primary")

        if submitted:
            if not username or not password:
                st.error("Please fill in all fields.")
            else:
                user_id = check_login(username, password)
                if user_id is None:
                    st.error("Wrong username or password.")
                else:
                    st.session_state["user_id"]      = user_id
                    st.session_state["user_profile"] = load_profile(user_id)
                    st.session_state["pantry"]       = []
                    st.query_params["uid"]           = user_id
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
                    "name":        name.strip(),
                    "diet":        diet,
                    "allergies":   allergies,
                    "skill_level": skill,
                }
                try:
                    user_id = create_account(profile, username, password)
                    st.session_state["user_id"]      = user_id
                    st.session_state["user_profile"] = profile
                    st.session_state["pantry"]       = []
                    st.query_params["uid"]           = user_id
                    st.success("Account created! Welcome 🎉")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


def _render_edit_form(existing: dict) -> None:
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
            "name":        name.strip(),
            "diet":        diet,
            "allergies":   allergies,
            "skill_level": skill,
        }
        save_profile(profile, user_id=st.session_state["user_id"])
        st.session_state["user_profile"]       = profile
        st.session_state["onboarding_editing"] = False
        st.success("Profile updated.")
        st.rerun()

    if st.button("Cancel", type="secondary"):
        st.session_state["onboarding_editing"] = False
        st.rerun()


def _render_summary(profile: dict) -> None:
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


#3. Page content ####
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

#4. Onboarding / profile section ########
if "show_onboarding" not in st.session_state:
    st.session_state["show_onboarding"] = False

profile = st.session_state.get("user_profile") or {}
editing = st.session_state.get("onboarding_editing", False)

### \begin[Code generation by Claude Sonnet 4.6]
if not profile:
    if not st.session_state["show_onboarding"]:
        st.markdown("""
            <style>
            div.stButton > button {
                background: white;
                color: #3D5C22;
                border: 2px solid #6B9448;
                padding: 0.75rem 2.5rem;
                font-size: 1.1rem;
                font-weight: 600;
                border-radius: 50px;
                cursor: pointer;
                transition: all 0.25s ease;
            }
            div.stButton > button:hover {
                transform: scale(1.05);
                box-shadow: 0 4px 12px rgba(107, 148, 72, 0.3);
                background: #f4f9f0;
            }
            div[data-testid="stToggle"] input:checked + div {
                background-color: #6B9448 !important;
            }
            </style>
        """, unsafe_allow_html=True)

        if st.button("Get Started"):
            st.session_state["show_onboarding"] = True
            st.rerun()
    else:
        _render_auth()
### \end[Code generation by Claude Sonnet 4.6]

elif editing:
    _render_edit_form(existing=profile)
else:
    _render_summary(profile)
