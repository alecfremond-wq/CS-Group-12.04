"""
Streamlit page that lets users manage their pantry.
Users can add ingredients with quantity, unit and expiry date, view what they
currently have, and remove individual items or clear everything at once.

Dependencies:

  - streamlit            : UI framework; renders every widget, column, and button.
  - pandas               : handles query results as DataFrames (iterrows).
  - datetime (stdlib)    : date, datetime — used for expiry date arithmetic.

  - src.data.pantry_repo
      add_to_pantry(user_id, name, qty, unit, expires_on) -> inserts or updates a pantry row.
      list_pantry(user_id)                                -> returns all pantry rows as a DataFrame.
      remove_from_pantry(pantry_row_id, user_id)         -> deletes a single pantry row.
      clear_pantry(user_id)                              -> deletes all pantry rows for this user.

  - src.data.api_client
      get_themealdb_ingredients() -> fetches ~500 ingredient names from TheMealDB API.
                                     Names must match exactly for the recipe badge to work.

  - src.components.ui
      page_header(title, subtitle) -> renders a styled h1 + subtitle banner.
      empty_state(message)         -> renders a placeholder when there is nothing to display.

  - src.utils.session
      init_session_state()  -> seeds st.session_state with default keys so
                               the rest of the app never hits KeyError.
      require_profile()     -> redirects to the Home page if the user has not
                               created a profile yet. Acts as a guard.

Database tables:

  pantry      : one row per (user, ingredient). Stores quantity, unit, expiry date.
                Primary key `id` is used for targeted deletes.
  ingredients : master ingredient list; joined to get human-readable names.

Author: Alec Frémond

Sources: Claude Sonnet 4.6 (see comments below)

"""

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

#setup
init_session_state()
require_profile()
page_header("🥫 Pantry", "What's currently in your kitchen?")

#constants
USER_ID = st.session_state.get("user_id", 1)
CUSTOM_OPTION = "✏️  Other (type a custom ingredient)"

# ~500 ingredients from TheMealDB — names must match exactly for the recipe badge to work
CANONICAL = get_themealdb_ingredients()

st.caption(
    f"Tip — pick from the list of {len(CANONICAL)} ingredients used by TheMealDB recipes. "
    "Anything you pick from there will count toward the **Pantry-friendly** badge "
    "on the Recipes page."
)

st.info(
    "**How the Recipes badge works** \n\n"
    "On the Recipes page, each recipe shows a badge based on how many of its "
    "ingredients you already have in your pantry:\n\n"
    "🟢 **Pantry-friendly** — you have more than 60% of the ingredients\n\n"
    "🟡 **Partially available** — you have between 30% and 60% of the ingredients\n\n"
    "No badge — you have less than 30% of the ingredients\n\n"
    "The more ingredients you add here, the more accurate the badges will be."
)

## ADD INGREDIENT FORM
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

## HANDLE FORM SUBMISSION
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

## LOAD AND DISPLAY PANTRY
db_pantry = list_pantry(USER_ID)

if db_pantry.empty and not st.session_state["pantry"]:
    empty_state("Your pantry is empty — add something above.")
else:
    today = date.today()

    # \ Begin code generated by Claude Sonnet 4.6
    def _expiry_badge(expires_on_raw) -> tuple[str, str]:
        """
        Returns a colored dot emoji and a text label based on how many days
        are left before the ingredient expires.

        SQLite can return dates as plain strings ("YYYY-MM-DD"), as datetime
        objects, or as date objects depending on how the row was inserted —
        the three branches below handle all three cases before doing the math.

        Parameters:
            expires_on_raw : the raw expiry value from the database row.

        Returns a tuple (emoji, label), e.g. ("🟡", "Expires in 2d").
        """
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
    # \ End code generated by Claude Sonnet 4.6

    st.markdown("---")

    if not db_pantry.empty:
        # summary metrics
        total = len(db_pantry)
        # \ Begin code generated by Claude Sonnet 4.6
        # Counting expired and expiring-soon items by iterating over the DataFrame
        # and calling _expiry_badge on each row — faster than filtering the DataFrame twice.
        expired = sum(1 for _, r in db_pantry.iterrows() if _expiry_badge(r["expires_on"])[0] == "🔴")
        expiring_soon = sum(1 for _, r in db_pantry.iterrows() if _expiry_badge(r["expires_on"])[0] == "🟡")
        # \ End code generated by Claude Sonnet 4.6

        m1, m2, m3 = st.columns(3)
        m1.metric("Total items", total)
        m2.metric("Expiring soon 🟡", expiring_soon)
        m3.metric("Expired 🔴", expired)

        st.markdown("---")

        # display each ingredient row
        for _, row in db_pantry.iterrows():
            emoji, label = _expiry_badge(row["expires_on"])
            qty_str = f"{row['quantity']:g} {row['unit'] or ''}".strip()

            col_name, col_qty, col_exp, col_btn = st.columns([3, 1.5, 2, 0.7])
            col_name.markdown(f"**{row['name'].title()}**")
            col_qty.markdown(f"`{qty_str}`")
            col_exp.markdown(f"{emoji} {label}")

            if col_btn.button("🗑️", key=f"rm_{int(row['id'])}", help="Remove"):
                remove_from_pantry(int(row["id"]), USER_ID)
                # filter session_state to keep it in sync with the database after deletion
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
        # fallback: database unavailable, show session items only
        for item in st.session_state["pantry"]:
            emoji, label = _expiry_badge(item.get("expires_on"))
            qty_str = f"{item['quantity']:g} {item['unit'] or ''}".strip()
            col_name, col_qty, col_exp = st.columns([3, 1.5, 2])
            col_name.markdown(f"**{item['name'].title()}**")
            col_qty.markdown(f"`{qty_str}`")
            col_exp.markdown(f"{emoji} {label}")
