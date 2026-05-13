"""
Entry point for the CookTogether Streamlit app.
This file is run first on every page load. It configures the browser tab,
initialises the database and session, registers all pages in the sidebar,
and shows a login status indicator.

Dependencies:

  - streamlit : UI framework; st.set_page_config, st.navigation, st.sidebar.

  - src.data.database
      init_db() -> creates all tables from schema.sql if they don't exist yet.

  - src.utils.session
      init_session_state() -> seeds st.session_state with default keys.

Author: Alec Frémond

"""

import streamlit as st

from src.data.database import init_db
from src.utils.session import init_session_state


#1. Page configuration ################
# Sets the browser tab title, icon, and default layout for every page in the app.
# Must be the first Streamlit call — Streamlit raises an error if anything else runs first.

st.set_page_config(
    page_title="Cooktogether",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)


#2. Initialisation ################
# Creates all database tables (if they don't exist yet) and seeds session_state
# with default values so every page can read keys without KeyError.

init_db()
init_session_state()


#3. Navigation ################
# Registers all pages in the sidebar. Streamlit renders the sidebar links
# automatically — the order here controls the order they appear.

pg = st.navigation([
    st.Page("Home.py",                        title="Home",            icon=":material/home:"),
    st.Page("pages/3_Pantry.py",              title="Pantry",          icon=":material/kitchen:"),
    st.Page("pages/2_Recipes.py",             title="Recipes",         icon=":material/menu_book:"),
    st.Page("pages/4_Meal_Planner.py",        title="Meal Planner",    icon=":material/calendar_month:"),
    st.Page("pages/5_Nutrition_Analytics.py", title="Nutrition",       icon=":material/bar_chart:"),
    st.Page("pages/7_Recommendations.py",     title="Recommendations", icon=":material/auto_awesome:"),
    st.Page("pages/8_Wishlist.py",            title="Wishlist",        icon=":material/favorite:"),
    st.Page("pages/9_My_Recipes.py",          title="My Recipes",      icon=":material/edit_note:"),
    st.Page("pages/6_Friends.py",             title="Friends",         icon=":material/group:"),
])


#4. Sidebar footer ################
# Shows the logged-in user's name at the bottom of the sidebar on every page,
# or a prompt to go to Home if no profile is loaded yet.

with st.sidebar:
    st.divider()
    if st.session_state.get("user_profile"):
        st.success(
            f"Signed in as **{st.session_state['user_profile'].get('name', 'you')}**"
        )
    else:
        st.info("No profile yet — go to **Home** to get started.")


#5. Run the app ################
# Hands control to Streamlit — renders whichever page the user navigated to.

pg.run()
