"""
Wishlist — all the recipes you've saved, in one place.

Owner: <assign>
Grading coverage:
    * Req. 4 (user interaction — save, view, remove recipes)
"""

import streamlit as st

from src.components.ui import page_header
from src.utils.session import init_session_state, require_profile


init_session_state()
require_profile()
page_header("❤️ Wishlist", "All the recipes you've saved.")

wishlist = st.session_state.get("wishlist", [])

# ── Empty state ───────────────────────────────────────────────────────────────

if not wishlist:
    st.info(
        "Nothing saved yet! "
        "Search for recipes on the **Recipes** page and click ❤️ Save, "
        "or go to **Recommendations** and save recipes there."
    )
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────

# A recipe feeds the ML model as long as we have its ingredient list —
# that's true for both local recipes AND recipes saved from the search page,
# because we store the ingredient list at save time in both cases.
feeding_model = sum(
    1 for w in wishlist
    if isinstance(w, dict) and (w.get("local_id") is not None or w.get("ingredients"))
)

col_stat1, col_stat2 = st.columns(2)
col_stat1.metric("Saved recipes", len(wishlist))
col_stat2.metric(
    "Feeding the ML model", feeding_model,
    help="Every recipe with a known ingredient list influences your recommendations.",
)

st.divider()

# ── Recipe cards ──────────────────────────────────────────────────────────────

for i, item in enumerate(wishlist):
    if isinstance(item, int):
        title       = f"Recipe #{item}"
        image       = None
        area        = ""
        has_signal  = True   # old format — local ID, definitely in the model
    else:
        title       = item.get("title", "Unknown recipe")
        image       = item.get("image")
        area        = item.get("area", "")
        # A recipe is useful to the model when it has a local_id OR stored ingredients.
        has_signal  = item.get("local_id") is not None or bool(item.get("ingredients"))

    with st.container(border=True):
        col_img, col_info = st.columns([1, 4])

        with col_img:
            if image:
                st.image(image, use_container_width=True)
            else:
                st.markdown("🍽️")

        with col_info:
            st.subheader(title)

            if area:
                st.caption(f"🌍 {area}")

            # Every saved recipe with ingredients (local or API) counts now.
            if has_signal:
                st.caption("✅ Used by the recommender")
            else:
                # This only happens for very old saves that predate ingredient storage.
                st.caption("ℹ️ No ingredient data — won't influence recommendations")

            # Removing a recipe from the wishlist also removes it as a signal
            # for the ML model on the next visit to the Recommendations page.
            if st.button("🗑️ Remove", key=f"remove_{i}"):
                st.session_state["wishlist"].pop(i)
                st.rerun()
