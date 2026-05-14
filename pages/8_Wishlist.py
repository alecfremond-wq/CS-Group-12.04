"""
Wishlist: All the recipes you've saved, in one place.

This page gives users a personal collection of every recipe they've saved
from the Recipes page or the Recommendations page.

How this page works:
  1. We load the wishlist from st.session_state, session.py filled it in
     from the database when the app started, so it already has everything.
  2. Each saved recipe is shown as a card with its thumbnail always visible.
  3. Clicking "Show details" expands the card to load the full ingredient list
     and step-by-step instructions from TheMealDB on demand.
     If TheMealDB doesn't know the recipe (e.g. it came from Spoonacular),
     we fall back to the ingredient list we stored at save time.
  4. Clicking "Remove" deletes the recipe from BOTH session_state AND the
     database — without the database delete, it would come back on the next reload.

Dependencies:

  json      (stdlib)      — decodes the ingredient list stored as a JSON string.
                            e.g. '["egg","flour"]' → ["egg", "flour"]

  src.components.ui       — Shared UI helpers:
                              page_header(title, subtitle) → renders the title banner.

  src.data.api_client     — API calls:
                              search_recipes_by_name(title) → TheMealDB: search by name.
                                Used to load the full ingredient list and instructions
                                for each saved recipe. Cached for 1 hour so repeat
                                visits cost no network requests.

  src.data.database       — SQLite helpers:
                              execute() → INSERT / UPDATE / DELETE.
                              Used here to DELETE a recipe when the user clicks Remove.

  src.utils.session       — Session management:
                              init_session_state() → seeds all default session keys.
                              require_profile()    → stops the page if not logged in.

Database tables used:
- wishlist : one row per saved recipe per user.
             Read indirectly via st.session_state["wishlist"] (loaded by session.py).
             Written to directly when the user removes a recipe (DELETE).

Author: Ines Buzel

Sources: Claude Sonnet 4.6 (planning of the page + see comments below)

"""

import json

import streamlit as st

from src.components.ui import page_header

from src.data.api_client import search_recipes_by_name

from src.data.database import execute

from src.utils.session import init_session_state, require_profile


## Section 1: Page setup

init_session_state()
require_profile()
page_header("❤️ Wishlist", "All the recipes you've saved.")

# session.py already loaded this from the DB on startup.
wishlist = st.session_state.get("wishlist", [])


## Section 2: Empty state
# st.stop() prevents the rest of the page from running if there's nothing to show.

if not wishlist:
    st.info(
        "Nothing saved yet! "
        "Search for recipes on the **Recipes** page and click ❤️ Save, "
        "or go to **Recommendations** and save recipes there."
    )
    st.stop()


## Section 3: Stats row
# Show a quick summary at the top: total saved, and how many are feeding the ML model.
# A recipe "feeds the model" when we have either its local DB ID or its ingredient list —
# both are enough for the k-NN recommender to learn from it.

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


## Section 4: Helper functions
# fetch_full_recipe loads the complete meal data from TheMealDB by title.
# extract_full_ingredients turns TheMealDB's numbered fields into readable strings.
# Both are defined here and only used in Section 5 (the recipe cards below).

def fetch_full_recipe(title: str) -> dict | None:
    """Search TheMealDB by title and return the exact match.
    Returns None if not found (e.g. recipe originally came from Spoonacular).
    """
    # search_recipes_by_name is cached, so calling it again for the same title
    # costs nothing after the first network request.
    results = search_recipes_by_name(title)
    if not results:
        return None

    # The search can return partial matches (e.g. "pasta" returns many dishes),
    # so we look for an exact case-insensitive title match.
    for meal in results:
        if meal.get("strMeal", "").lower() == title.lower():
            return meal

    return None  # No exact match found.


def extract_full_ingredients(meal: dict) -> list[str]:
    """Build 'measure + name' strings from TheMealDB's numbered fields (strIngredient1..20).
    Skips empty slots and returns readable strings like "500g Chicken".
    """
    #/ Begin code generated with Claude Sonnet 4.6
    ingredients = []
    for i in range(1, 21):
        name    = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}")    or "").strip()
        if not name:
            continue
        ingredients.append(f"{measure} {name}" if measure else name)
    return ingredients
    #/ End code generated with Claude Sonnet 4.6


## Section 5: Recipe cards
# One card per saved recipe. Each card always shows the thumbnail and title.
# The "Show details" expander below loads ingredients + instructions on demand.
# The Remove button deletes from both session_state and the database.

for i, item in enumerate(wishlist):

    # Support the old format where wishlist items were just an integer ID.
    # All new saves are dicts, but we handle the old format just in case.
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

        # The ingredients field can be a Python list (fresh from session)
        # or a JSON string (loaded from the database). Normalise to a list.
        #/ Begin code generated with Claude Sonnet 4.6
        raw_ing = item.get("ingredients", [])
        if isinstance(raw_ing, str):
            try:
                stored_ing = json.loads(raw_ing)
            except Exception:
                stored_ing = []
        else:
            stored_ing = raw_ing or []
        #/ End code generated with Claude Sonnet 4.6

        # A recipe feeds the ML model if we have its local ID or ingredient list.
        has_signal = item.get("local_id") is not None or bool(stored_ing)

    # Fetch outside the expander so the image is available even when collapsed.
    full_meal = fetch_full_recipe(title)

    # Use the stored image if available, otherwise fall back to the TheMealDB thumbnail.
    #/ Begin code generated with Claude Sonnet 4.6
    display_image = image or (full_meal.get("strMealThumb") if full_meal else None)
    #/ End code generated with Claude Sonnet 4.6

    with st.container(border=True):

        # Card header: image on the left, title + info + Remove button on the right.
        # [1, 4] gives the image a narrow column and the info a wide one.
        col_img, col_info = st.columns([1, 4])

        with col_img:
            # We check isinstance(..., str) and startswith("http") before calling
            # st.image → a NaN or empty string from the DB would cause an error.
            if isinstance(display_image, str) and display_image.startswith("http"):
                st.image(display_image, use_container_width=True)
            else:
                st.markdown("🍽️")  # No valid image → placeholder emoji.

        with col_info:
            st.subheader(title)

            if area:
                st.caption(f"🌍 {area}")

            # Let the user know whether this recipe is improving their recommendations.
            if has_signal:
                st.caption("✅ Used by the recommender")
            else:
                st.caption("ℹ️ No ingredient data — won't influence recommendations")

            # Remove from session_state immediately AND from the DB so it doesn't come back.
            if st.button("🗑️ Remove", key=f"remove_{i}"):
                st.session_state["wishlist"].pop(i)
                user_id = st.session_state.get("user_id")
                if user_id:
                    execute(
                        "DELETE FROM wishlist WHERE user_id = ? AND title = ?",
                        (user_id, title),
                    )
                st.rerun()

        # Expandable details: sits below the two columns and spans the full card width.
        # full_meal was already fetched above, so this triggers no extra API call.
        with st.expander("📖 Show details"):

            if full_meal:
                # TheMealDB has this recipe, show ingredients left, instructions right.
                col_ing, col_inst = st.columns([1, 2])

                with col_ing:
                    st.markdown("**Ingredients**")
                    # extract_full_ingredients combines measure + name from TheMealDB's
                    # numbered fields into readable strings like "500g Chicken".
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
                # TheMealDB doesn't know this recipe, it probably came from Spoonacular.
                # Fall back to the ingredient list we stored in the DB at save time.
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
