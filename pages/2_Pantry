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

# Initialize session state and make sure the user has completed onboarding
init_session_state()
require_profile()
page_header("🥫 Pantry", "What's currently in your kitchen?")

# Get the current user's ID from the session (set during login)
USER_ID = st.session_state.get("user_id", 1)
CUSTOM_OPTION = "✏️  Other (type a custom ingredient)"

# Fetch all ingredient names from TheMealDB API — this gives us ~500 ingredients
# that exactly match the names used in recipes, so the pantry badge works correctly
CANONICAL = get_themealdb_ingredients()

st.caption(
    f"Tip — pick from the list of {len(CANONICAL)} ingredients used by TheMealDB recipes. "
    "Anything you pick from there will count toward the **Pantry-friendly** badge "
    "on the Recipes page."
)

# Info box explaining how the pantry badge works on the Recipes page
st.info(
    "**How the Recipes badge works** \n\n"
    "On the Recipes page, each recipe shows a badge based on how many of its "
    "ingredients you already have in your pantry:\n\n"
    "🟢 **Pantry-friendly** — you have more than 60% of the ingredients\n\n"
    "🟡 **Partially available** — you have between 30% and 60% of the ingredients\n\n"
    "No badge — you have less than 30% of the ingredients\n\n"
    "The more ingredients you add here, the more accurate the badges will be."
)

# ── Add ingredient form ────────────────────────────────────────────────────────
# clear_on_submit=True resets all fields automatically after the user submits
with st.form("add_item", clear_on_submit=True):
    cols = st.columns([3, 1, 1, 2])
    with cols[0]:
        # Dropdown pre-filled with TheMealDB ingredients + a custom option at the end
        choice = st.selectbox(
            "Ingredient",
            options=[""] + CANONICAL + [CUSTOM_OPTION],
            index=0,
            help="Choose a name from this list to ensure it matches recipe ingredients.",
        )
        custom_name = ""
        # If the user picks "Other", show a free-text field to type any ingredient
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

# ── Handle form submission ─────────────────────────────────────────────────────
if submitted:
    # Determine the final ingredient name depending on whether the user
    # picked from the list or typed a custom name
    if choice == CUSTOM_OPTION:
        ingredient_name = custom_name.strip().lower()
    elif choice and choice != CUSTOM_OPTION:
        ingredient_name = choice.strip().lower()
    else:
        ingredient_name = ""

    if not ingredient_name:
        st.warning("Please pick an ingredient (or type a custom name) before saving.")
    else:
        # Add to session_state immediately so the UI updates right away
        st.session_state["pantry"].append(
            {
                "name": ingredient_name,
                "quantity": qty,
                "unit": unit,
                "expires_on": expires,
            }
        )
        # Also persist to the database so the data survives page navigation
        try:
            add_to_pantry(USER_ID, ingredient_name, qty, unit, expires)
            st.success(f"Added **{ingredient_name}** ✓")
        except Exception as exc:
            st.warning(
                f"Saved to this session, but couldn't sync to the database: {exc}. "
                "The Recipes page may not see it until next reload."
            )

# ── Load pantry from the database ─────────────────────────────────────────────
db_pantry = list_pantry(USER_ID)

if db_pantry.empty and not st.session_state["pantry"]:
    empty_state("Your pantry is empty — add something above.")
else:
    today = date.today()

    def _expiry_badge(expires_on_raw) -> tuple[str, str]:
        # Parse the expiry date — it can come as a string from SQLite or as a date object
        try:
            if isinstance(expires_on_raw, str):
                exp = datetime.strptime(expires_on_raw[:10], "%Y-%m-%d").date()
            elif hasattr(expires_on_raw, "date"):
                exp = expires_on_raw.date()
            else:
                exp = expires_on_raw

            # Calculate how many days are left before the ingredient expires
            days = (exp - today).days

            # Return a colored dot and a label based on urgency
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
        # Count how many items are expired or expiring soon for the summary metrics
        total = len(db_pantry)
        expired = sum(
            1 for _, r in db_pantry.iterrows()
            if _expiry_badge(r["expires_on"])[0] == "🔴"
        )
        expiring_soon = sum(
            1 for _, r in db_pantry.iterrows()
            if _expiry_badge(r["expires_on"])[0] == "🟡"
        )

        # Display 3 summary metrics at the top of the pantry
        m1, m2, m3 = st.columns(3)
        m1.metric("Total items", total)
        m2.metric("Expiring soon 🟡", expiring_soon)
        m3.metric("Expired 🔴", expired)

        st.markdown("---")

        # Display each ingredient as a row with name, quantity, expiry badge and delete button
        for _, row in db_pantry.iterrows():
            emoji, label = _expiry_badge(row["expires_on"])
            qty_str = f"{row['quantity']:g} {row['unit'] or ''}".strip()

            col_name, col_qty, col_exp, col_btn = st.columns([3, 1.5, 2, 0.7])
            col_name.markdown(f"**{row['name'].title()}**")
            col_qty.markdown(f"`{qty_str}`")
            col_exp.markdown(f"{emoji} {label}")

            # Delete button — scoped to this specific row using its database id as key
            if col_btn.button("🗑️", key=f"rm_{int(row['id'])}", help="Remove"):
                remove_from_pantry(int(row["id"]), USER_ID)
                # Also remove from session_state to keep UI in sync with the database
                st.session_state["pantry"] = [
                    p for p in st.session_state["pantry"]
                    if p.get("name", "").lower() != row["name"]
                ]
                st.rerun()

        st.markdown("---")

        # Clear all button — wipes both session_state and the database rows for this user
        if st.button("🗑️ Clear pantry", type="secondary"):
            st.session_state["pantry"] = []
            try:
                clear_pantry(USER_ID)
            except Exception:
                pass
            st.rerun()

    else:
        # Fallback: if the database is unavailable, display items from session_state only
        for item in st.session_state["pantry"]:
            emoji, label = _expiry_badge(item.get("expires_on"))
            qty_str = f"{item['quantity']:g} {item['unit'] or ''}".strip()
            col_name, col_qty, col_exp = st.columns([3, 1.5, 2])
            col_name.markdown(f"**{item['name'].title()}**")
            col_qty.markdown(f"`{qty_str}`")
            col_exp.markdown(f"{emoji} {label}")
