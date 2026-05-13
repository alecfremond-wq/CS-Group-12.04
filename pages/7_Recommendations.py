"""
Recommendations — the machine-learning feature.
Owner: <assign on Apr 22>
Grading coverage:
    * Req. 5 (ML — content-based k-NN recommender)
    * Req. 3 (visualisation — match score bars)
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

# ── Allergy filtering ─────────────────────────────────────────────────────────
#
# We don't want to recommend recipes that contain ingredients the user is
# allergic to. To check this, we keep a simple dictionary that maps each
# allergy name to a list of ingredient keywords we should watch out for.
# For example, if the user is allergic to "Lactose", we look for words
# like "milk", "cheese", "butter" etc. in the recipe's ingredient list.
# If we find any of them → skip that recipe.

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
    """Check if a recipe is safe for the user based on their allergies.

    We go through each allergy the user has and check if any of the
    matching keywords show up anywhere in the ingredient list.
    If we find a match → the recipe is NOT safe → return False.
    If nothing matches → the recipe is safe → return True.

    Example: user has "Lactose" allergy, recipe has "parmesan" as ingredient
    → "parmesan" is in the Lactose keyword list → not safe → return False.
    """
    if not allergies:
        # No allergies set → every recipe is safe
        return True

    # Join all ingredients into one big string so we can search easily.
    # e.g. ["garlic", "parmesan", "pasta"] → "garlic parmesan pasta"
    all_ingredients_text = " ".join(ingredients).lower()

    for allergy in allergies:
        # Look up the keywords for this allergy.
        # If the allergy name isn't in our dictionary, use the allergy name
        # itself as the keyword (e.g. a custom allergy like "mushroom").
        keywords = _ALLERGY_KEYWORDS.get(allergy, [allergy.lower()])

        # Check if any keyword appears in the ingredient text
        for keyword in keywords:
            if keyword in all_ingredients_text:
                # Found a match → this recipe is not safe
                return False

    # No allergen found → recipe is safe
    return True


# ── Ingredient cleaning ───────────────────────────────────────────────────────

def _strip_measures(ingredient: str) -> str:
    s = ingredient.strip()
    s = re.sub(r"^(to serve|juice of|zest of|handful of|a pinch of)\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^[\d\s½¼¾⅓⅔⅛./-]+x?\s*", "", s)
    s = re.sub(r"^\d+\s*(g|kg|ml|l|oz|lbs?)\s+", "", s, flags=re.IGNORECASE)
    units = (
        r"^(cups?|tbsp?|tsp?|tablespoons?|teaspoons?|grams?|g|kg|oz|lbs?|"
        r"pounds?|ml|liters?|litres?|cloves?|slices?|pieces?|pinch|handful|"
        r"bunch|cans?|large|medium|small|whole|finely|chopped|shredded|"
        r"sliced|diced|minced|fresh|dried|ground|packed)\s+"
    )
    s = re.sub(units, "", s, flags=re.IGNORECASE)
    return s.strip().lower()


def _clean_ingredients(raw: list[str]) -> list[str]:
    return [s for s in (_strip_measures(i) for i in raw) if len(s) > 1]


# ── Time / difficulty helpers ─────────────────────────────────────────────────

def _estimate_time(instructions: str) -> int:
    words = len((instructions or "").split())
    if words < 80:   return 15
    if words < 200:  return 30
    if words < 400:  return 45
    return 60


def _difficulty_from_time(minutes: int | None) -> str:
    if minutes is None: return "Medium"
    if minutes <= 20:   return "Easy"
    if minutes <= 45:   return "Medium"
    return "Hard"


# ── Constants ─────────────────────────────────────────────────────────────────

_MEALDB_CUISINES     = ["Italian", "Mexican", "Indian", "Japanese", "French",
                        "Chinese", "Thai", "American", "British", "Greek"]
_MEALDB_PER_CUISINE  = 4


# ── Recipe loader (parallel HTTP, properly cached) ────────────────────────────

@st.cache_data(ttl=60 * 60, show_spinner=False)
def _load_mealdb_recipes() -> list[dict]:
    """Fetch MealDB recipes using parallel HTTP calls instead of sequential ones.

    Previously this made 10 × 4 = 40 sequential requests (one per stub).
    Now all get_meal_by_id calls run concurrently — wall-clock time drops
    from ~40s to roughly the time of a single slow request (~2–3s).
    """
    # Step 1: collect all stubs (one request per cuisine, sequential — fast)
    all_stubs: list[tuple[str, str]] = []   # (cuisine, idMeal)
    for cuisine in _MEALDB_CUISINES:
        stubs = filter_by_cuisine(cuisine)[:_MEALDB_PER_CUISINE]
        for stub in stubs:
            all_stubs.append((cuisine, stub["idMeal"]))

    # Step 2: fetch all full meals in parallel
    def fetch(cuisine_and_id: tuple[str, str]) -> tuple[str, dict | None]:
        cuisine, meal_id = cuisine_and_id
        return cuisine, get_meal_by_id(meal_id)

    meals: list[tuple[str, dict | None]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        meals = list(pool.map(fetch, all_stubs))

    # Step 3: normalise into rows
    rows = []
    for recipe_id, (cuisine, meal) in enumerate(meals, start=1):
        if not meal:
            continue

        # Clean ingredient names for the ML model (no measures, lowercase).
        # e.g. "2 cups all-purpose flour" → "all-purpose flour"
        ingredients  = _clean_ingredients(extract_ingredients_from_meal(meal))
        instructions = meal.get("strInstructions", "")
        time_min     = _estimate_time(instructions)

        # Build a display-friendly ingredient list WITH measures.
        # TheMealDB stores up to 20 ingredient/measure pairs as numbered fields.
        # We combine them so the expander can show "500g Chicken" instead of "chicken".
        ingredients_display = []
        for j in range(1, 21):
            name    = (meal.get(f"strIngredient{j}") or "").strip()
            measure = (meal.get(f"strMeasure{j}")    or "").strip()
            if not name:
                continue
            ingredients_display.append(f"{measure} {name}" if measure else name)

        rows.append({
            "id":                   recipe_id,
            "title":                meal.get("strMeal", ""),
            "image":                meal.get("strMealThumb", ""),   # thumbnail URL
            "ingredients":          ingredients,          # clean names for ML
            "ingredients_display":  ingredients_display,  # with measures for display
            "instructions":         instructions,         # full cooking steps
            "calories":             None,
            "time_minutes":         time_min,
            "difficulty":           _difficulty_from_time(time_min),
            "country":              meal.get("strArea", cuisine),
        })
    return rows


def load_all_recipes() -> pd.DataFrame:
    """Return the recipe catalogue, cached in session_state after first load."""
    CACHE_KEY = "rec_recipes_df_v6"

    # Clear stale cache versions
    for k in [k for k in st.session_state if k.startswith("rec_recipes_df_") and k != CACHE_KEY]:
        del st.session_state[k]

    if CACHE_KEY not in st.session_state:
        rows = _load_mealdb_recipes()
        df   = pd.DataFrame(rows)
        df   = df.drop_duplicates(subset="title", keep="first").reset_index(drop=True)
        df["id"] = range(1, len(df) + 1)
        st.session_state[CACHE_KEY] = df

    return st.session_state[CACHE_KEY]


# ── App init ──────────────────────────────────────────────────────────────────

init_session_state()
require_profile()
page_header("✨ Recommendations", "Recipes picked just for you by a k-NN model.")


# ── Load catalogue (shown once, then served from cache) ───────────────────────

with st.spinner("Loading recipe catalogue…"):
    recipes_df = load_all_recipes()


# ── Build taste profile inputs ────────────────────────────────────────────────

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


# ── Run k-NN ──────────────────────────────────────────────────────────────────

rec         = Recommender(recipes_df)
saved_titles = {w["title"].lower() for w in wishlist if isinstance(w, dict) and w.get("title")}
has_signal   = bool(liked_ingredients) or bool(wishlist_ids)

if has_signal:
    candidates = rec.recommend(
        history_df,
        top_n=len(recipes_df),
        wishlist=wishlist_ids,
        liked_ingredients=liked_ingredients,
    )
    filtered = candidates[~candidates["title"].str.lower().isin(saved_titles)].copy()

    if not filtered.empty and filtered["score"].notna().any():
        max_score = filtered["score"].max()
        if max_score > 0:
            filtered["score"] = filtered["score"] / max_score

    picks = filtered.head(5).reset_index(drop=True)
else:
    picks = rec.recommend(history_df, top_n=5)

# ── Filter out recipes that contain the user's allergens ──────────────────────
#
# We get the allergy list from the user profile (set during Onboarding).
# Then we go through each recommended recipe and remove any that contain
# allergen ingredients. We do this AFTER the ML ranking so the model can
# still consider all recipes — we just hide the unsafe ones at the end.

profile    = st.session_state.get("user_profile") or {}
allergies  = profile.get("allergies") or []

# Make sure allergies is a list — in the DB it's sometimes stored as a
# comma-separated string like "Gluten,Lactose", so we split it if needed.
if isinstance(allergies, str):
    allergies = [a.strip() for a in allergies.split(",") if a.strip()]

if allergies:
    # Keep only recipes that are safe for this user.
    safe_mask = picks["ingredients"].apply(
        lambda ing: _is_safe_for_user(list(ing) if isinstance(ing, list) else [], allergies)
    )
    n_removed = (~safe_mask).sum()
    picks = picks[safe_mask].reset_index(drop=True)

    if n_removed > 0:
        st.caption(
            f"ℹ️ {n_removed} recipe(s) were hidden because they contain "
            f"ingredients from your allergy list ({', '.join(allergies)})."
        )

if picks.empty:
    st.info("Nothing to recommend yet — save some recipes on the **Recipes** page first.")
    st.stop()


# ── Feedback helper ───────────────────────────────────────────────────────────

def record_feedback(recipe_row: pd.Series, rating: int) -> None:
    st.session_state["cooking_history"].append({
        "recipe_id":   int(recipe_row["id"]),
        "title":       recipe_row["title"],
        "ingredients": recipe_row["ingredients"],
        "rating":      rating,
    })
    try:
        from src.data.database import execute
        user_id = st.session_state.get("user_id")
        if user_id is not None:
            execute(
                "INSERT INTO cooking_history (user_id, recipe_id, cooked_on, rating) VALUES (?, ?, ?, ?)",
                (user_id, int(recipe_row["id"]), date.today().isoformat(), rating),
            )
    except Exception:
        pass


# ── Display ───────────────────────────────────────────────────────────────────
#
# One card per recommended recipe.
# Layout:
#   [ image ] [ title + score + country + save button ] [ time / difficulty / feedback ]
#   [          📖 Show details expander (ingredients + instructions)                   ]

import json
from src.data.database import execute

for _, row in picks.iterrows():

    recipe_id = int(row["id"])

    with st.container(border=True):

        # Three columns: thumbnail (left), recipe info (middle), stats (right).
        # [1, 3, 1] means the middle column gets 3× as much space as the others.
        col_img, col_info, col_stats = st.columns([1, 3, 1])

        # ── Left: thumbnail image ─────────────────────────────────────────
        with col_img:
            image_url = row.get("image", "")
            if image_url:
                # use_container_width=True makes the image fill the column cleanly.
                st.image(image_url, use_container_width=True)

        # ── Middle: title, match score, country, save button ─────────────
        with col_info:
            st.subheader(row["title"])

            # st.progress draws a coloured bar from 0.0 (empty) to 1.0 (full).
            # We show it as a percentage so "0.87" appears as "Match score: 87%".
            if pd.notna(row.get("score")):
                st.progress(float(row["score"]), text=f"Match score: {row['score']:.0%}")

            country = row.get("country", "")
            if country:
                st.caption(f"🌍 {country}")

            # Check whether this recipe is already in the user's wishlist.
            # We compare by local_id (the internal recipe number we assigned).
            already_saved = any(
                isinstance(w, dict) and w.get("local_id") == recipe_id
                for w in st.session_state.get("wishlist", [])
            )

            if already_saved:
                st.caption("✅ Already in your wishlist")
            else:
                if st.button("＋ Save to wishlist", key=f"wish_{recipe_id}"):
                    ingredients = list(row.get("ingredients", []))

                    # 1. Add to the in-memory session list so the Wishlist page
                    #    and ML model can use it right away without a reload.
                    st.session_state["wishlist"].append({
                        "title":       row["title"],
                        "image":       row.get("image", ""),   # now stored!
                        "area":        row.get("country", ""),
                        "local_id":    recipe_id,
                        "ingredients": ingredients,
                    })

                    # 2. Persist to the database so the wishlist survives
                    #    closing and reopening the browser.
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

        # ── Right: cook time, difficulty, thumbs up/down ──────────────────
        with col_stats:
            st.metric("Cook time",  f"{row.get('time_minutes', '—')} min")
            st.metric("Difficulty", row.get("difficulty", "—"))

            # Feedback buttons: clicking them records a rating in cooking_history
            # so the k-NN model learns the user's taste over time.
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

        # ── Expandable details ────────────────────────────────────────────
        # The expander sits below all three columns.
        # It shows the full ingredient list (with measures) on the left
        # and the step-by-step instructions on the right.
        with st.expander("📖 Show details"):

            col_ing, col_inst = st.columns([1, 2])

            with col_ing:
                st.markdown("**Ingredients**")
                # ingredients_display has "measure + name" strings like "500g Chicken".
                # We fall back to the plain ML ingredient list if display list is missing.
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
