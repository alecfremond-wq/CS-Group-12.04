# ============================================================================
#  CookTogether — entry point and navigation
#  Run it from the terminal with:   streamlit run app.py
# ============================================================================
#  NOTE ON AUTHORSHIP (required by HSG plagiarism rules):
#  The initial scaffold of this file was generated with the help of an AI
#  assistant (Anthropic Claude, April 2026) and then reviewed and adapted
#  by Group 12.04. See README.md for full citation.
# ============================================================================
#  TO REVERT NAVIGATION CHANGES:
#    1. Delete Home.py
#    2. Run: git checkout app.py
#  The old file-based navigation is restored automatically.
# ============================================================================

import streamlit as st

from src.data.database import init_db
from src.utils.session import init_session_state


# ── Page configuration ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Cooktogether",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── One-time initialisation ───────────────────────────────────────────────────
# These run on EVERY page load because app.py is the entry point for all pages.
# Both functions are safe to call multiple times (idempotent).

init_db()           # creates database tables if they don't exist yet
init_session_state()  # fills in default session_state keys


# ── Navigation ────────────────────────────────────────────────────────────────
# st.navigation() replaces the old automatic file-based navigation.
# Each st.Page() entry defines one page: the file path, display name, and icon.
# Icons use Google Material Symbols syntax: :material/<icon_name>:
# Full icon list: https://fonts.google.com/icons

pg = st.navigation([
    st.Page("Home.py",                        title="Home",            icon=":material/home:"),
    st.Page("pages/3_Pantry.py",              title="Pantry",          icon=":material/kitchen:"),
    st.Page("pages/2_Recipes.py",             title="Recipes",         icon=":material/menu_book:"),
    st.Page("pages/4_Meal_Planner.py",        title="Meal Planner",    icon=":material/calendar_month:"),
    st.Page("pages/5_Nutrition_Analytics.py", title="Nutrition",       icon=":material/bar_chart:"),
    st.Page("pages/7_Recommendations.py",     title="Recommendations", icon=":material/auto_awesome:"),
    st.Page("pages/8_Wishlist.py",            title="Wishlist",        icon=":material/favorite:"),
    st.Page("pages/6_Friends.py",             title="Friends",         icon=":material/group:"),
])

# ── Sidebar footer ────────────────────────────────────────────────────────────
# This runs on EVERY page (because app.py is the entry point).
# It shows the logged-in username at the bottom of the sidebar on all pages.

with st.sidebar:
    st.divider()
    if st.session_state.get("user_profile"):
        st.success(
            f"Signed in as **{st.session_state['user_profile'].get('name', 'you')}**"
        )
    else:
        st.info("No profile yet — go to **Home** to get started.")

# ── Run the selected page ─────────────────────────────────────────────────────
# pg.run() executes the script of whichever page the user clicked in the sidebar.

pg.run()
