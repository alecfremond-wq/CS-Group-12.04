# ============================================================================
#  CookTogether — HOME PAGE  (this file is the entry point of the whole app)
#  Run it from the terminal with:   streamlit run app.py
# ============================================================================
#  NOTE ON AUTHORSHIP (required by HSG plagiarism rules):
#  The initial scaffold of this file was generated with the help of an AI
#  assistant (Anthropic Claude, April 2026) and then reviewed and adapted
#  by Group 12.04. See README.md for full citation.
# ============================================================================

# --- imports ---------------------------------------------------------------
import streamlit as st                              # the library that turns this Python file into a web app

# We import two helper functions from our own source folder.
# "from src.data.database import init_db" means: in the file src/data/database.py,
# take the function called init_db and make it available here.
from src.data.database import init_db               # creates the SQLite tables on first run
from src.utils.session import init_session_state    # puts default values into Streamlit's memory


# --- page configuration (MUST be the very first Streamlit command) ---------
st.set_page_config(                                 # configures the browser tab + layout
    page_title="CookTogether",                      # title shown in the browser tab
    page_icon="🍳",                                 # emoji favicon
    layout="wide",                                  # use the full screen width instead of a narrow centred column
    initial_sidebar_state="expanded",               # sidebar is open by default so users see the navigation
)


# --- one-time initialisation -----------------------------------------------
# Both of these functions are safe to call on every page reload: they only
# create things that don't exist yet (idempotent).
init_db()                                           # make sure the database file and tables exist
init_session_state()                                # make sure user_profile, pantry, etc. have default values


# --- home page content ------------------------------------------------------
st.title("🍳 CookTogether")                         # big page title
st.subheader("Cook, plan, and eat well — together.")  # smaller tagline under the title

# st.markdown writes text formatted with Markdown (**bold**, lists, etc.).
# Triple-quoted strings (""" ... """) let us write multi-line text in Python.
st.markdown(
    """
    **CookTogether** helps students cook more joyfully by combining:

    - a personalised onboarding profile (diet, allergies, budget, skill),
    - recipe discovery based on what you already have in your pantry,
    - a weekly **meal planner** with budget tracking,
    - **nutrition analytics** so you can see what you actually eat,
    - a world map to explore recipes by origin, and
    - ML-powered **recommendations** that learn from your cooking history.

    Use the sidebar on the left to navigate.
    """
)

# --- sidebar content (shown on every page, but we define it here) ----------
# "with st.sidebar:" puts everything indented under it into the left sidebar.
with st.sidebar:
    st.markdown("### Getting started")              # small heading inside the sidebar
    st.markdown(                                    # step-by-step guidance for new users
        "1. Fill out **Onboarding** first.\n"
        "2. Add items to your **Pantry**.\n"
        "3. Browse **Recipes** and add favourites to your **Meal Planner**.\n"
        "4. Check **Nutrition** and **Recommendations** to see insights."
    )
    st.divider()                                    # horizontal line separator

    # st.session_state is a dictionary Streamlit keeps in memory between clicks.
    # .get("user_profile") returns the value if the key exists, or None otherwise.
    if st.session_state.get("user_profile"):        # if the user has already completed Onboarding
        # f-strings (the f before the quote) let us embed variables in text with {}.
        st.success(                                 # green success message
            f"Signed in as **{st.session_state['user_profile'].get('name', 'you')}**"
        )
    else:                                           # otherwise, prompt them to onboard
        st.info("No profile yet — head to Onboarding.")   # blue info message
