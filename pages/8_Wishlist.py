"""
Wishlist — all the recipes you've saved, in one place.

How this page works:
    1. We load the wishlist from st.session_state (filled in by session.py
       from the database when the app starts).
    2. Each recipe is shown as a card with its thumbnail always visible.
    3. Clicking "Show details" expands the card to show ingredients
       and step-by-step instructions, loaded from TheMealDB.
       If TheMealDB doesn't know the recipe we fall back to the
       ingredient list we stored at save time.
    4. Clicking "Remove" deletes the recipe from BOTH the session state
       AND the database so it doesn't come back on the next reload.

Owner: <assign>
Grading coverage:
    * Req. 4 (user interaction — save, view, remove recipes)
"""

# ── Imports ───────────────────────────────────────────────────────────────────
# json      → we stored ingredients as a JSON string like '["egg","flour"]'
#             and need to decode it back into a Python list.
# streamlit → the framework that draws the whole web page.
import json

import streamlit as st

# page_header      → draws the consistent title banner at the top of every page.
from src.components.ui import page_header

# search_recipes_by_name → searches TheMealDB by title.
#   We use it to load the full ingredient list and cooking instructions
#   when the user opens the "Show details" expander.
#   Results are cached for 1 hour so repeat calls are free.
from src.data.api_client import search_recipes_by_name

# execute → runs INSERT / UPDATE / DELETE queries (no return value).
#   We use it here to DELETE a recipe from the wishlist table when
#   the user clicks "Remove", so the deletion survives a page reload.
from src.data.database import execute

# init_session_state → fills in default session keys before we read them.
# require_profile    → stops the page if the user hasn't completed Onboarding.
from src.utils.session import init_session_state, require_profile


# ── Page setup ────────────────────────────────────────────────────────────────

init_session_state()
require_profile()
page_header("❤️ Wishlist", "All the recipes you've saved.")

# Read the wishlist from session state.
# session.py loaded this from the database when the app started,
# so it contains every recipe the user has ever saved.
wishlist = st.session_state.get("wishlist", [])


# ── Empty state ───────────────────────────────────────────────────────────────

if not wishlist:
    # Nothing saved yet — show a helpful message and stop the page here.
    # st.stop() means the code below this point won't run.
    st.info(
        "Nothing saved yet! "
        "Search for recipes on the **Recipes** page and click ❤️ Save, "
        "or go to **Recommendations** and save recipes there."
    )
    st.stop()


# ── Stats row ─────────────────────────────────────────────────────────────────

# Count how many saved recipes have ingredient data.
# Those are the ones the ML recommender can actually learn from.
# A recipe qualifies if it has a local_id (in our own catalogue)
# OR if we stored its ingredient list as a JSON string.
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


# ── Helper: fetch full recipe details from TheMealDB ─────────────────────────

def fetch_full_recipe(title: str) -> dict | None:
    """Search TheMealDB for a recipe by title and return the first exact match.

    We can't look up by ID because we don't store the TheMealDB ID in the
    wishlist table — so we search by name and check for an exact title match.

    Returns the meal dict if found, or None if TheMealDB doesn't know it
    (e.g. the recipe was originally found via Spoonacular).
    """
    # search_recipes_by_name is cached, so calling it twice with the same
    # title costs nothing after the first network request.
    results = search_recipes_by_name(title)
    if not results:
        return None

    # The search can return partial matches, so we check for an exact title.
    for meal in results:
        if meal.get("strMeal", "").lower() == title.lower():
            return meal

    return None


# ── Helper: build "measure + ingredient" strings from a TheMealDB meal ───────

def extract_full_ingredients(meal: dict) -> list[str]:
    """Turn TheMealDB's numbered fields into a readable ingredient list.

    TheMealDB stores ingredients and their measures in separate numbered fields:
        strIngredient1 = "Chicken"   strMeasure1 = "500g"
        strIngredient2 = "Garlic"    strMeasure2 = "2 cloves"
        ...up to 20

    We combine them into "500g Chicken", "2 cloves Garlic" etc.
    Empty slots are skipped.
    """
    ingredients = []
    for i in range(1, 21):
        name    = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}")    or "").strip()
        if not name:
            continue
        ingredients.append(f"{measure} {name}" if measure else name)
    return ingredients


# ── Recipe cards ──────────────────────────────────────────────────────────────
# One card per saved recipe. Each card always shows the thumbnail image,
# the title, and a Remove button. The "Show details" expander below the
# card header loads ingredients and instructions on demand.

for i, item in enumerate(wishlist):

    # Support the old format where wishlist items were just an integer ID.
    # New saves are always dicts, but we keep this check just in case.
    if isinstance(item, int):
        title      = f"Recipe #{item}"
        image      = None
        area       = ""
        stored_ing = []
        has_signal = True
    else:
        title = item.get("title", "Unknown recipe")
        image = item.get("image")
        area  = item.get("area", "")

        # The ingredients field can be a Python list (if it came from a fresh
        # session) or a JSON string (if it was loaded from the database).
        # We normalise it to a plain Python list here.
        raw_ing = item.get("ingredients", [])
        if isinstance(raw_ing, str):
            try:
                stored_ing = json.loads(raw_ing)
            except Exception:
                stored_ing = []
        else:
            stored_ing = raw_ing or []

        # A recipe feeds the ML model when we have either its local DB ID
        # or at least a stored ingredient list.
        has_signal = item.get("local_id") is not None or bool(stored_ing)

    # Fetch the full recipe from TheMealDB once per card.
    # We do this OUTSIDE the expander so the image is available
    # for the card header even when the expander is collapsed.
    # search_recipes_by_name is cached for 1 hour — so after the first
    # visit this costs no network requests at all.
    full_meal = fetch_full_recipe(title)

    # Use the stored image if we have one, otherwise fall back to the
    # TheMealDB thumbnail. Many old wishlist entries were saved without
    # an image URL, so the API image is the only way to show something.
    display_image = image or (full_meal.get("strMealThumb") if full_meal else None)

    with st.container(border=True):

        # ── Card header: image always visible ─────────────────────────────
        # We split the card into two columns:
        #   col_img  (narrow, left)  → thumbnail, always shown
        #   col_info (wide, right)   → title, area badge, stats, remove button
        col_img, col_info = st.columns([1, 4])

        with col_img:
            # We check isinstance(..., str) and startswith("http") to make sure
            # display_image is a real URL before passing it to st.image.
            # Without this check, a NaN value or empty string from the database
            # would cause an AttributeError inside Streamlit's image renderer.
            if isinstance(display_image, str) and display_image.startswith("http"):
                st.image(display_image, use_container_width=True)
            else:
                # No valid image URL — show a placeholder emoji.
                st.markdown("🍽️")

        with col_info:
            st.subheader(title)

            if area:
                st.caption(f"🌍 {area}")

            if has_signal:
                st.caption("✅ Used by the recommender")
            else:
                st.caption("ℹ️ No ingredient data — won't influence recommendations")

            # Remove button: deletes from session state AND from the database.
            # Without the database delete, the recipe would come back on the
            # next page reload (session.py would reload it from the DB).
            if st.button("🗑️ Remove", key=f"remove_{i}"):
                st.session_state["wishlist"].pop(i)
                user_id = st.session_state.get("user_id")
                if user_id:
                    execute(
                        "DELETE FROM wishlist WHERE user_id = ? AND title = ?",
                        (user_id, title),
                    )
                st.rerun()

        # ── Expandable details ─────────────────────────────────────────────
        # The expander sits below the card header (outside the two columns).
        # It only shows ingredients and instructions — the image is already
        # visible above, so we don't repeat it here.
        # full_meal was already fetched above, so this is free (cached).
        with st.expander("📖 Show details"):

            if full_meal:
                # ── TheMealDB has this recipe ──────────────────────────────
                # Show ingredients on the left and instructions on the right.
                col_ing, col_inst = st.columns([1, 2])

                with col_ing:
                    st.markdown("**Ingredients**")
                    # extract_full_ingredients builds "measure + name" strings
                    # from TheMealDB's numbered strIngredient/strMeasure fields.
                    for ing in extract_full_ingredients(full_meal):
                        st.caption(f"• {ing}")

                with col_inst:
                    st.markdown("**Instructions**")
                    instructions = full_meal.get("strInstructions", "")
                    if instructions:
                        st.write(instructions)
                    else:
                        st.caption("No instructions available.")

            else:
                # ── TheMealDB doesn't know this recipe ─────────────────────
                # This happens for recipes found via Spoonacular. We fall back
                # to the ingredient list we stored at save time.
                if stored_ing:
                    col_ing2, col_inst2 = st.columns([1, 2])
                    with col_ing2:
                        st.markdown("**Ingredients**")
                        for ing in stored_ing:
                            st.caption(f"• {ing}")
                    with col_inst2:
                        st.caption("Full instructions not available for this recipe.")
                else:
                    st.caption("No details available for this recipe.")
