"""
Pantry — track what the user currently has at home.

Owner: <assign on Apr 22>
Grading coverage:
    * Req. 4 (user interaction — add/remove items)
    * Feeds the "Inventory-Based Recipes" feature from the project pitch.

TODOs for the owner:
    - propose recipes that use items expiring within 3 days.
    - auto-complete ingredient names from the `ingredients` DB table.
"""

from datetime import date

import pandas as pd
import streamlit as st

from src.components.ui import empty_state, page_header
from src.utils.session import init_session_state, require_profile


init_session_state()
require_profile()
page_header("🥫 Pantry", "What's currently in your kitchen?")

with st.form("add_item", clear_on_submit=True):
    cols = st.columns([3, 1, 1, 2])
    with cols[0]:
        name = st.text_input("Ingredient")
    with cols[1]:
        qty = st.number_input("Qty", min_value=0.0, step=0.5)
    with cols[2]:
        unit = st.selectbox("Unit", ["g", "kg", "ml", "l", "pcs"])
    with cols[3]:
        expires = st.date_input("Expires on", value=date.today())
    if st.form_submit_button("Add to pantry"):
        if name.strip():
            st.session_state["pantry"].append(
                {"name": name.strip(), "quantity": qty, "unit": unit, "expires_on": expires}
            )
            st.success(f"Added {name}.")

pantry = st.session_state["pantry"]
if not pantry:
    empty_state("Your pantry is empty — add something above.")
else:
    df = pd.DataFrame(pantry)
    st.dataframe(df, use_container_width=True, hide_index=True)
    if st.button("Clear pantry", type="secondary"):
        st.session_state["pantry"] = []
        st.rerun()
