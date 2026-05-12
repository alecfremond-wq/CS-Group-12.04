from datetime import date, datetime

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
    submitted = st.form_submit_button("➕ Add to pantry", type="primary")

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
    today = date.today()

    def _expiry_badge(expires_on_raw) -> tuple[str, str]:
        """Return (emoji, label) based on how close the expiry date is."""
        try:
            if isinstance(expires_on_raw, str):
                exp = datetime.strptime(expires_on_raw[:10], "%Y-%m-%d").date()
            elif hasattr(expires_on_raw, "date"):
                exp = expires_on_raw.date()
            else:
                exp = expires_on_raw
            days = (exp - today).days
            if days < 0:
                return "🔴", "Expired"
            elif days <= 3:
                return "🟡", f"Expires in {days}d"
            else:
                return "🟢", f"Expires {exp.strftime('%d %b')}"
        except Exception:
            return "⚪", ""

    st.markdown("---")

    if not db_pantry.empty:
        # Summary counts
        total = len(db_pantry)
        expired = sum(
            1 for _, r in db_pantry.iterrows()
            if _expiry_badge(r["expires_on"])[0] == "🔴"
        )
        expiring_soon = sum(
            1 for _, r in db_pantry.iterrows()
            if _expiry_badge(r["expires_on"])[0] == "🟡"
        )

        m1, m2, m3 = st.columns(3)
        m1.metric("Total items", total)
        m2.metric("Expiring soon 🟡", expiring_soon)
        m3.metric("Expired 🔴", expired)

        st.markdown("---")

        # Ingredient cards
        for _, row in db_pantry.iterrows():
            emoji, label = _expiry_badge(row["expires_on"])
            qty_str = f"{row['quantity']:g} {row['unit'] or ''}".strip()

            col_name, col_qty, col_exp, col_btn = st.columns([3, 1.5, 2, 0.7])
            col_name.markdown(f"**{row['name'].title()}**")
            col_qty.markdown(f"`{qty_str}`")
            col_exp.markdown(f"{emoji} {label}")
            if col_btn.button("🗑️", key=f"rm_{int(row['id'])}", help="Remove"):
                remove_from_pantry(int(row["id"]), USER_ID)
                st.session_state["pantry"] = [
                    p for p in st.session_state["pantry"]
                    if p.get("name", "").lower() != row["name"]
                ]
                st.rerun()

        st.markdown("---")
        if st.button("🗑️ Clear pantry", type="secondary"):
            st.session_state["pantry"] = []
            try:
                clear_pantry(USER_ID)
            except Exception:
                pass
            st.rerun()

    else:
        # Fallback: session-only data (no DB rows yet)
        for item in st.session_state["pantry"]:
            emoji, label = _expiry_badge(item.get("expires_on"))
            qty_str = f"{item['quantity']:g} {item['unit'] or ''}".strip()
            col_name, col_qty, col_exp = st.columns([3, 1.5, 2])
            col_name.markdown(f"**{item['name'].title()}**")
            col_qty.markdown(f"`{qty_str}`")
            col_exp.markdown(f"{emoji} {label}")
