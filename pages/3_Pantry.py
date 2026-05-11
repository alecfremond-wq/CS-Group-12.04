from datetime import date

import pandas as pd
import streamlit as st

from src.components.ui import empty_state, page_header
from src.data.api_client import get_themealdb_ingredients
from src.data.pantry_repo import (
    add_to_pantry,
    clear_pantry,
    list_pantry,
    remove_from_pantry,
)
from src.utils.session import init_session_state, require_profile

init_session_state()
require_profile()
page_header("🥫 Pantry", "What's currently in your kitchen?")

USER_ID = st.session_state.get("user_id", 1)
CUSTOM_OPTION = "✏️  Other (type a custom ingredient)"
CANONICAL = get_themealdb_ingredients()

st.caption(
    f"Tip — pick from the list of {len(CANONICAL)} ingredients used by TheMealDB recipes. "
    "Anything you pick from there will count toward the **Pantry-friendly** badge "
    "on the Recipes page."
)

with st.form("add_item", clear_on_submit=True):
    cols = st.columns([3, 1, 1, 2])
    with cols[0]:
        choice = st.selectbox(
            "Ingredient",
            options=[""] + CANONICAL + [CUSTOM_OPTION],
            index=0,
            help="Choose a name from this list to ensure it matches recipe ingredients.",
        )
        custom_name = ""
        if choice == CUSTOM_OPTION:
            custom_name = st.text_input(
                "Custom ingredient name",
                placeholder="e.g. miso paste",
            )
    with cols[1]:
        qty = st.number_input("Qty", min_value=0.0, step=0.5, value=1.0)
    with cols[2]:
        unit = st.selectbox("Unit", ["g", "kg", "ml", "l", "pcs"])
    with cols[3]:
        expires = st.date_input("Expires on", value=date.today())
    submitted = st.form_submit_button("Add to pantry", type="primary")

if submitted:
    if choice == CUSTOM_OPTION:
        ingredient_name = custom_name.strip().lower()
    elif choice and choice != CUSTOM_OPTION:
        ingredient_name = choice.strip().lower()
    else:
        ingredient_name = ""

    if not ingredient_name:
        st.warning("Please pick an ingredient (or type a custom name) before saving.")
    else:
        st.session_state["pantry"].append(
            {
                "name": ingredient_name,
                "quantity": qty,
                "unit": unit,
                "expires_on": expires,
            }
        )
        try:
            add_to_pantry(USER_ID, ingredient_name, qty, unit, expires)
            st.success(f"Added **{ingredient_name}** ✓")
        except Exception as exc:
            st.warning(
                f"Saved to this session, but couldn't sync to the database: {exc}. "
                "The Recipes page may not see it until next reload."
            )

db_pantry = list_pantry(USER_ID)

if db_pantry.empty and not st.session_state["pantry"]:
    empty_state("Your pantry is empty — add something above.")
else:
    if not db_pantry.empty:
        display_df = db_pantry[["name", "quantity", "unit", "expires_on"]].copy()
    else:
        display_df = pd.DataFrame(st.session_state["pantry"])

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    if not db_pantry.empty:
        st.markdown("##### Remove an item")
        for _, row in db_pantry.iterrows():
            col_label, col_btn = st.columns([5, 1])
            label = f"{row['name']} — {row['quantity']} {row['unit'] or ''}"
            col_label.write(label)
            if col_btn.button("🗑️", key=f"rm_{int(row['id'])}"):
                remove_from_pantry(int(row["id"]), USER_ID)
                st.session_state["pantry"] = [
                    p for p in st.session_state["pantry"]
                    if p.get("name", "").lower() != row["name"]
                ]
                st.rerun()

    if st.button("Clear pantry", type="secondary"):
        st.session_state["pantry"] = []
        try:
            clear_pantry(USER_ID)
        except Exception:
            pass
        st.rerun()
