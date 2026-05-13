import streamlit as st

from src.data.database import init_db
from src.utils.session import init_session_state


#1. Page configuration #################

st.set_page_config(
    page_title="Cooktogether",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)

#2. Initialisation #################
init_db()           
init_session_state() 


#3. Navigation #################
# Define the app pages

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

#4. Sidebar footer ##############

with st.sidebar:
    st.divider()
    if st.session_state.get("user_profile"):
        st.success(
            f"Signed in as **{st.session_state['user_profile'].get('name', 'you')}**"
        )
    else:
        st.info("No profile yet — go to **Home** to get started.")

#5. Run the app ##############

pg.run()
