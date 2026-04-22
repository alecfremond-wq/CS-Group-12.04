"""
Recipes — search and browse recipes (API + DB).
Owner: <assign on Apr 22>
Grading coverage:
    * Req. 2 (API — TheMealDB)
    * Req. 4 (user interaction — search, filter, add-to-wishlist)
TODOs for the owner:
    - when a user clicks "Save recipe", persist to the `recipes` table
      so the Recommender has data to learn from.
    - respect the user's allergies from Onboarding (filter them out).
"""
import streamlit as st
from src.components.ui import empty_state, page_header
from src.data.api_client import list_cuisines, search_recipes_by_name, search_spoonacular
from src.utils.session import init_session_state, require_profile

init_session_state()
require_profile()

page_header("🍲 Recipes", "Search recipes or browse by cuisine.")
tab_search, tab_cuisine = st.tabs(["🔎 Search", "🌍 Browse by cuisine"])

with tab_search:
    query = st.text_input("What would you like to cook?", placeholder="e.g. pasta, curry…")
    if query:
        # Diätpräferenzen aus Onboarding laden
        veg = st.session_state.get("vegetarian", False)
        vgn = st.session_state.get("vegan", False)
        gf  = st.session_state.get("gluten_free", False)
        df  = st.session_state.get("dairy_free", False)

        # TheMealDB + Spoonacular kombinieren
        results = search_recipes_by_name(query) + search_spoonacular(
            query=query,
            vegetarian=veg,
            vegan=vgn,
            gluten_free=gf,
            dairy_free=df,
        )

        if not results:
            empty_state("No recipes found — try another word.")
        for meal in results[:10]:
            with st.container(border=True):
                col_img, col_meta = st.columns([1, 3])
                with col_img:
                    st.image(meal.get("strMealThumb"), use_container_width=True)
                with col_meta:
                    st.subheader(meal["strMeal"])
                    st.caption(f"{meal.get('strArea', '—')} · {meal.get('strCategory', '—')}")
                    with st.expander("Instructions"):
                        st.write(meal.get("strInstructions", ""))

with tab_cuisine:
    cuisines = list_cuisines()
    if not cuisines:
        empty_state("Cuisine list couldn't be loaded — check your internet.")
    else:
        choice = st.selectbox("Cuisine", cuisines)
        st.caption(f"(Owner: render recipes for cuisine = **{choice}**)")
