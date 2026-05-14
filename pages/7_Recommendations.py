"""
Recommendations: ML-powered recipe suggestions based on what you've saved.

This is the machine-learning page of CookMate (Requirement 5).
It uses a k-Nearest Neighbours (k-NN) model to find recipes that match
the user's taste profile, built from the ingredient lists of everything
they've saved to their wishlist or rated highly.

How the recommendations work:
  1. We load a catalogue of ~40 recipes from TheMealDB across 10 cuisines.
  2. Each recipe is turned into a binary ingredient vector by the Recommender
     (one column per ingredient, 1 if the recipe has it, 0 if not).
  3. The user's wishlist and feedback history are averaged into one
     "taste profile" vector, the centre of gravity of what they like.
  4. k-NN finds the catalogue recipes closest to that centre using cosine similarity.
  5. Scores are normalised so the best match = 100%, others relative to it.
  6. Recipes the user already saved, or that contain their allergens, are hidden.

Dependencies:

  re               (stdlib) — used in _strip_measures() to clean ingredient strings
                              with regular expressions.
  concurrent.futures (stdlib) — runs the 40 TheMealDB API calls in parallel so the
                                page loads in ~2s instead of ~40s.
  datetime          (stdlib) — date.today() for writing feedback to cooking_history.

  pandas                    — DataFrames for the recipe catalogue and history.

  src.components.ui         — Shared UI helpers:
                                page_header(title, subtitle) → renders the title banner.

  src.data.api_client       — API calls:
                                extract_ingredients_from_meal(meal) → pulls the ingredient
                                  list out of a TheMealDB meal dict.
                                filter_by_cuisine(cuisine)          → TheMealDB: stubs for
                                  one cuisine area (id + title only).
                                get_meal_by_id(id)                  → TheMealDB: full recipe
                                  with ingredients + instructions.

  src.models.recommender    — Recommender class: the actual k-NN model.
                                recommend(history, top_n, wishlist, liked_ingredients)
                                  → returns top_n recipes sorted by cosine similarity
                                    to the user's taste profile.

  src.utils.session         — Session management:
                                init_session_state() → seeds all default session keys.
                                require_profile()    → stops the page if not logged in.

Database tables used:
- wishlist        : read to build the taste profile (titles + ingredients of saved recipes).
- cooking_history : read for rated recipes; written when the user clicks 👍 or 👎.

Author: Ines Buzel (ML model + wishlist integration + feedback system)
        Julsroma  (recipe loading, UI layout, filtering)

Sources: Claude Sonnet 4.6 (see comments below)

"""

import re
import concurrent.futures
from datetime import date

import pandas as pd
import streamlit as st

from src.components.ui import page_header

from src.data.api_client import (
    extract_ingredients_from_meal,
    filter_by_cuisine,
    get_meal_by_id,
)

from src.models.recommender import Recommender

from src.utils.session import init_session_state, require_profile


## Section 1: Allergy filtering
# Allergen names like "Gluten" never appear literally in ingredient lists.
# This dictionary maps each allergen to the ingredient keywords that indicate it.

_ALLERGY_KEYWORDS: dict[str, list[str]] = {
    "Gluten":    ["flour", "wheat", "bread", "pasta", "barley", "rye",
                  "semolina", "couscous", "crouton", "soy sauce", "breadcrumb",
                  "noodle", "tortilla", "pita", "bun", "roll", "baguette"],
    "Celiac":    ["flour", "wheat", "bread", "pasta", "barley", "rye",
                  "semolina", "couscous", "crouton", "soy sauce", "breadcrumb",
                  "noodle", "tortilla", "pita"],
    "Lactose":   ["milk", "cheese", "butter", "cream", "yogurt", "yoghurt",
                  "mozzarella", "parmesan", "ricotta", "whey", "lactose",
                  "cheddar", "brie", "gouda", "feta", "ghee", "custard"],
    "Eggs":      ["egg", "eggs", "mayonnaise", "mayo", "meringue",
                  "aioli", "hollandaise"],
    "Nuts":      ["almond", "walnut", "cashew", "hazelnut", "pistachio",
                  "pecan", "macadamia", "pine nut", "chestnut", "brazil nut"],
    "Peanut":    ["peanut", "groundnut", "peanut butter", "monkey nut"],
    "Soy":       ["soy", "tofu", "tempeh", "miso", "edamame", "soya",
                  "soy sauce", "tamari", "natto"],
    "Shellfish": ["shrimp", "prawn", "lobster", "crab", "crayfish",
                  "scallop", "clam", "mussel", "oyster", "barnacle",
                  "langoustine", "crawfish"],
}


def _is_safe_for_user(ingredients: list[str], allergies: list[str]) -> bool:
    """Check if a recipe is safe for the user based on their allergy list.

    Joins all ingredient strings into one big text block and checks whether
    any allergen keyword appears anywhere in it.

    Example: user has "Lactose", recipe has ["garlic", "parmesan", "pasta"]
    → "parmesan" is in the Lactose keyword list → not safe → returns False.

    Returns True if the recipe is safe (no allergen found), False if not.
    """
    if not allergies:
        return True  # No allergies set → every recipe is safe.

    # Join all ingredient strings into one searchable text block.
    # e.g. ["garlic", "parmesan", "pasta"] → "garlic parmesan pasta"
    all_ingredients_text = " ".join(ingredients).lower()

    for allergy in allergies:
        # Get the keyword list for this allergen.
        # If the allergen isn't in our dictionary (e.g. a custom entry like "mushroom"),
        # fall back to using the allergen name itself as the only keyword.
        keywords = _ALLERGY_KEYWORDS.get(allergy, [allergy.lower()])
        for keyword in keywords:
            if keyword in all_ingredients_text:
                return False  # Found an allergen → not safe.

    return True  # No allergen found → safe to recommend.

#/ Begin code generated with Claude Sonnet 4.6

## Section 2: Ingredient cleaning helpers
# We strip quantities/units before passing ingredients to the ML model.
# "500g chicken" and "300g chicken" should count as the same ingredient.

def _strip_measures(ingredient: str) -> str:
    """Remove quantity/unit prefix from an ingredient string.
    e.g. "2 cups all-purpose flour" → "all-purpose flour", "½ tsp cumin" → "cumin"
    """
    s = ingredient.strip()
    # Pass 1: remove leading English quantity phrases
    s = re.sub(r"^(to serve|juice of|zest of|handful of|a pinch of)\s+", "", s, flags=re.IGNORECASE)
    # Pass 2: remove leading numbers and fractions (e.g. "2 ", "½ ", "1/2 ")
    s = re.sub(r"^[\d\s½¼¾⅓⅔⅛./-]+x?\s*", "", s)
    # Pass 3: remove leading metric amounts like "500g" or "200ml"
    s = re.sub(r"^\d+\s*(g|kg|ml|l|oz|lbs?)\s+", "", s, flags=re.IGNORECASE)
    # Pass 4: remove unit words like "cups", "tbsp", "cloves", "large", "fresh" etc.
    units = (
        r"^(cups?|tbsp?|tsp?|tablespoons?|teaspoons?|grams?|g|kg|oz|lbs?|"
        r"pounds?|ml|liters?|litres?|cloves?|slices?|pieces?|pinch|handful|"
        r"bunch|cans?|large|medium|small|whole|finely|chopped|shredded|"
        r"sliced|diced|minced|fresh|dried|ground|packed)\s+"
    )
    s = re.sub(units, "", s, flags=re.IGNORECASE)
    return s.strip().lower()


def _clean_ingredients(raw: list[str]) -> list[str]:
    """Apply _strip_measures to every ingredient and drop anything shorter than 2 chars."""
    return [s for s in (_strip_measures(i) for i in raw) if len(s) > 1]
#/ End code generated with Claude Sonnet 4.6

## Section 3: Time and difficulty helpers
# TheMealDB recipes don't include a cook time, so we estimate it from
# how long the instruction text is. More words → more complex → more time.
# Difficulty is then derived from the estimated time.

def _estimate_time(instructions: str) -> int:
    """Estimate cook time in minutes based on how long the instruction text is."""
    words = len((instructions or "").split())
    if words < 80:   return 15
    if words < 200:  return 30
    if words < 400:  return 45
    return 60


def _difficulty_from_time(minutes: int | None) -> str:
    """Map an estimated cook time to a difficulty label (Easy / Medium / Hard)."""
    if minutes is None: return "Medium"
    if minutes <= 20:   return "Easy"
    if minutes <= 45:   return "Medium"
    return "Hard"


## Section 4: Recipe catalogue loader
# Fetches ~40 recipes from TheMealDB (10 cuisines × 4 each) for the k-NN model.
# Uses parallel HTTP calls so it loads in ~2s instead of ~40s sequentially.

_MEALDB_CUISINES    = ["Italian", "Mexican", "Indian", "Japanese", "French",
                       "Chinese", "Thai", "American", "British", "Greek"]
_MEALDB_PER_CUISINE = 4   # how many recipes to fetch per cuisine


# \ Begin code generated with Claude Sonnet 4.6
@st.cache_data(ttl=60 * 60, show_spinner=False)
def _load_mealdb_recipes() -> list[dict]:
    """Fetch TheMealDB recipes using parallel HTTP calls instead of sequential ones.

    Previously this made 10 × 4 = 40 sequential HTTP calls (one per stub).
    With ThreadPoolExecutor all get_meal_by_id calls run at the same time —
    wall-clock time drops from ~40s to roughly the time of one slow request (~2–3s).

    Returns a list of recipe dicts, each with:
      id, title, image, ingredients (cleaned for ML), ingredients_display
      (with measures for the UI), instructions, time_minutes, difficulty, country.
    """
    # Step 1: collect all (cuisine, idMeal) stubs, one API call per cuisine, fast.
    all_stubs: list[tuple[str, str]] = []
    for cuisine in _MEALDB_CUISINES:
        stubs = filter_by_cuisine(cuisine)[:_MEALDB_PER_CUISINE]
        for stub in stubs:
            all_stubs.append((cuisine, stub["idMeal"]))

    # Step 2: fetch all full meal details in parallel.
    def fetch(cuisine_and_id: tuple[str, str]) -> tuple[str, dict | None]:
        cuisine, meal_id = cuisine_and_id
        return cuisine, get_meal_by_id(meal_id)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        meals = list(pool.map(fetch, all_stubs))

    # Step 3: normalise each meal into a row dict for the DataFrame.
    rows = []
    for recipe_id, (cuisine, meal) in enumerate(meals, start=1):
        if not meal:
            continue

        # Clean ingredient names for the ML model (strip measures, lowercase).
        # e.g. "2 cups all-purpose flour" → "all-purpose flour"
        ingredients  = _clean_ingredients(extract_ingredients_from_meal(meal))
        instructions = meal.get("strInstructions", "")
        time_min     = _estimate_time(instructions)

        # Build a display version WITH measures so the "Show details" expander
        # can show "500g Chicken" instead of just "chicken".
        # TheMealDB stores up to 20 ingredient/measure pairs as numbered fields.
        ingredients_display = []
        for j in range(1, 21):
            name    = (meal.get(f"strIngredient{j}") or "").strip()
            measure = (meal.get(f"strMeasure{j}")    or "").strip()
            if not name:
                continue
            ingredients_display.append(f"{measure} {name}" if measure else name)

        rows.append({
            "id":                  recipe_id,
            "title":               meal.get("strMeal", ""),
            "image":               meal.get("strMealThumb", ""),
            "ingredients":         ingredients,         # clean names → used by the ML model
            "ingredients_display": ingredients_display, # with measures → shown in the UI
            "instructions":        instructions,
            "calories":            None,
            "time_minutes":        time_min,
            "difficulty":          _difficulty_from_time(time_min),
            "country":             meal.get("strArea", cuisine),
        })
    return rows
# \ End code generated with Claude Sonnet 4.6


def load_all_recipes() -> pd.DataFrame:
    """Return the recipe catalogue as a DataFrame, cached in session_state after first load.
    The CACHE_KEY version number can be bumped to force a fresh reload if the row structure changes.
    """
    CACHE_KEY = "rec_recipes_df_v6"

    # Remove any stale cache entries from older versions of this page.
    for k in [k for k in st.session_state if k.startswith("rec_recipes_df_") and k != CACHE_KEY]:
        del st.session_state[k]

    if CACHE_KEY not in st.session_state:
        rows = _load_mealdb_recipes()
        df   = pd.DataFrame(rows)
        #/ Begin code generated with Claude Sonnet 4.6
        # Drop duplicate titles so the same recipe from two cuisines only appears once.
        df   = df.drop_duplicates(subset="title", keep="first").reset_index(drop=True)
        df["id"] = range(1, len(df) + 1)
        #/ End code generated with Claude Sonnet 4.6
        st.session_state[CACHE_KEY] = df

    return st.session_state[CACHE_KEY]


## Section 5: Page setup and recipe loading

init_session_state()
require_profile()
page_header("✨ Recommendations", "Recipes picked just for you by a k-NN model.")

# Load the catalogue once — subsequent renders come from the session cache.
with st.spinner("Loading recipe catalogue…"):
    recipes_df = load_all_recipes()


## Section 6: Build the taste profile inputs
# The k-NN model needs two things to build a taste profile:
#   1. wishlist_ids      — local recipe IDs for anything in the catalogue we saved
#   2. liked_ingredients — cleaned ingredient lists for everything we saved
#                          (includes API recipes that don't have a local ID)
#
# Both come from st.session_state["wishlist"] which is populated when the user
# clicks "❤️ Save to wishlist" anywhere in the app.

wishlist   = st.session_state.get("wishlist", [])
history_df = pd.DataFrame(st.session_state.get("cooking_history", []))

wishlist_ids = [
    w["local_id"] for w in wishlist
    if isinstance(w, dict) and w.get("local_id") is not None
]
liked_ingredients = [
    _clean_ingredients(w["ingredients"])
    for w in wishlist
    if isinstance(w, dict) and w.get("ingredients")
]

# Show a helpful message depending on whether the user has saved anything.
total_saved = len(wishlist)
if total_saved == 0:
    st.info(
        "Nothing saved to your wishlist yet. "
        "Search for recipes on the **Recipes** page and click ❤️ Save — "
        "the more you save, the more personalised these picks become."
    )
else:
    st.caption(
        f"Based on {total_saved} saved recipe(s). "
        "Save more to keep improving the recommendations."
    )

st.divider()


## Section 7: Run the k-NN model
# We rank ALL recipes first, then filter out allergens and already-saved ones.
# Scores are normalised so the best match = 100%.

rec          = Recommender(recipes_df)
saved_titles = {w["title"].lower() for w in wishlist if isinstance(w, dict) and w.get("title")}
has_signal   = bool(liked_ingredients) or bool(wishlist_ids)

if has_signal:
    # We have a taste profile → run personalised k-NN recommendations.
    candidates = rec.recommend(
        history_df,
        top_n=len(recipes_df),
        wishlist=wishlist_ids,
        liked_ingredients=liked_ingredients,
    )
    # Remove recipes the user already saved, we want new discoveries, not repeats.
    filtered = candidates[~candidates["title"].str.lower().isin(saved_titles)].copy()

    # Normalise scores so the best result = 100% and the rest are relative to it.
    # Without this, scores like 0.12 and 0.09 would display as "12%" and "9%",
    # which looks low even if those are genuinely good matches.
    if not filtered.empty and filtered["score"].notna().any():
        max_score = filtered["score"].max()
        if max_score > 0:
            filtered["score"] = filtered["score"] / max_score

    picks = filtered.head(5).reset_index(drop=True)
else:
    # Cold start: no profile yet → just return the first 5 recipes from the catalogue.
    picks = rec.recommend(history_df, top_n=5)


## Section 8: Allergy filtering
# We filter AFTER the ML ranking so the model can consider the full catalogue —
# we just hide the unsafe results at display time.
# The allergy list comes from the user profile (set during Onboarding).

profile   = st.session_state.get("user_profile") or {}
allergies = profile.get("allergies") or []

# Allergies are sometimes stored as a comma-separated string in the DB
# (e.g. "Gluten,Lactose") split it into a list if that's the case.
if isinstance(allergies, str):
    allergies = [a.strip() for a in allergies.split(",") if a.strip()]

if allergies:
    #/ Begin code generated with Claude Sonnet 4.6
    safe_mask = picks["ingredients"].apply(
        lambda ing: _is_safe_for_user(list(ing) if isinstance(ing, list) else [], allergies)
    )
    n_removed = (~safe_mask).sum()
    picks = picks[safe_mask].reset_index(drop=True)
    #/ End code generated with Claude Sonnet 4.6

    if n_removed > 0:
        st.caption(
            f"ℹ️ {n_removed} recipe(s) were hidden because they contain "
            f"ingredients from your allergy list ({', '.join(allergies)})."
        )

if picks.empty:
    st.info("Nothing to recommend yet — save some recipes on the **Recipes** page first.")
    st.stop()


## Section 9: Feedback helper
# When the user clicks 👍 or 👎 we write a rating to cooking_history.
# The k-NN model reads this on the next render and adjusts its recommendations
# liked recipes (rating ≥ 4) pull the taste profile towards similar dishes.

import json
from src.data.database import execute


def record_feedback(recipe_row: pd.Series, rating: int) -> None:
    """Save a 👍 (rating=5) or 👎 (rating=1) to session state and the database."""
    # 1. Write to session_state so the model can use it right away.
    st.session_state["cooking_history"].append({
        "recipe_id":   int(recipe_row["id"]),
        "title":       recipe_row["title"],
        "ingredients": recipe_row["ingredients"],
        "rating":      rating,
    })
    # 2. Persist to the database so the feedback survives a page reload.
    try:
        user_id = st.session_state.get("user_id")
        if user_id is not None:
            execute(
                "INSERT INTO cooking_history (user_id, recipe_id, cooked_on, rating) VALUES (?, ?, ?, ?)",
                (user_id, int(recipe_row["id"]), date.today().isoformat(), rating),
            )
    except Exception:
        pass  # If the DB write fails, the in-memory rating still helps the model.


## Section 10: Display
# One card per recommended recipe: image | title + score + save button | cook time + feedback.
# Below each card: expandable ingredient list and instructions.

for _, row in picks.iterrows():

    recipe_id = int(row["id"])

    with st.container(border=True):

        # Three columns: thumbnail (left), recipe info (middle), stats + feedback (right).
        # [1, 3, 1] means the middle column gets 3× as much space as the side columns.
        col_img, col_info, col_stats = st.columns([1, 3, 1])

        # Left column: thumbnail image
        with col_img:
            image_url = row.get("image", "")
            if image_url:
                st.image(image_url, use_container_width=True)

        # Middle column: title, match score bar, cuisine country, save button
        with col_info:
            st.subheader(row["title"])

            # st.progress draws a coloured bar from 0.0 (empty) to 1.0 (full).
            # We display the score as a percentage → 0.87 shows as "Match score: 87%".
            if pd.notna(row.get("score")):
                st.progress(float(row["score"]), text=f"Match score: {row['score']:.0%}")

            country = row.get("country", "")
            if country:
                st.caption(f"🌍 {country}")

            # Check whether this recipe is already in the wishlist so we don't
            # show a duplicate Save button.
            already_saved = any(
                isinstance(w, dict) and w.get("local_id") == recipe_id
                for w in st.session_state.get("wishlist", [])
            )

            if already_saved:
                st.caption("✅ Already in your wishlist")
            else:
                if st.button("＋ Save to wishlist", key=f"wish_{recipe_id}"):
                    ingredients = list(row.get("ingredients", []))

                    # 1. Add to session so the Wishlist page and ML model see it immediately.
                    st.session_state["wishlist"].append({
                        "title":       row["title"],
                        "image":       row.get("image", ""),
                        "area":        row.get("country", ""),
                        "local_id":    recipe_id,
                        "ingredients": ingredients,
                    })
                    # 2. Persist to the DB so it survives closing and reopening the browser.
                    user_id = st.session_state.get("user_id")
                    if user_id:
                        execute(
                            """
                            INSERT OR IGNORE INTO wishlist
                                (user_id, title, image, area, local_id, ingredients)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                user_id,
                                row["title"],
                                row.get("image", ""),
                                row.get("country", ""),
                                recipe_id,
                                json.dumps(ingredients),
                            ),
                        )
                    st.rerun()

        # Right column: cook time, difficulty, and feedback buttons
        with col_stats:
            st.metric("Cook time",  f"{row.get('time_minutes', '—')} min")
            st.metric("Difficulty", row.get("difficulty", "—"))

            # Feedback buttons: 👍 records a rating of 5, 👎 records a rating of 1.
            # These ratings feed into the taste profile so the model gets smarter over time.
            st.caption("Was this a good pick?")
            fb_col1, fb_col2 = st.columns(2)
            with fb_col1:
                if st.button("👍", key=f"up_{recipe_id}",
                             use_container_width=True, help="Good recommendation"):
                    record_feedback(row, rating=5)
                    st.toast("Thanks! This helps the model learn your taste.", icon="✅")
                    st.rerun()
            with fb_col2:
                if st.button("👎", key=f"dn_{recipe_id}",
                             use_container_width=True, help="Not for me"):
                    record_feedback(row, rating=1)
                    st.toast("Got it! We'll show you fewer recipes like this.", icon="❌")
                    st.rerun()

        # Expandable details: full ingredient list + step-by-step instructions.
        # Sits below all three columns so it spans the full card width.
        with st.expander("📖 Show details"):
            col_ing, col_inst = st.columns([1, 2])

            with col_ing:
                st.markdown("**Ingredients**")
                # ingredients_display has "measure + name" strings like "500g Chicken".
                # Fall back to the plain ML ingredient list if the display version is missing.
                display_ingredients = row.get("ingredients_display") or row.get("ingredients", [])
                for ing in display_ingredients:
                    st.caption(f"• {ing}")

            with col_inst:
                st.markdown("**Instructions**")
                instructions = row.get("instructions", "")
                if instructions:
                    st.write(instructions)
                else:
                    st.caption("No instructions available.")
