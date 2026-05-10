# ============================================================================
#  api_client.py  —  wrapper around TheMealDB (a free public recipe API)
# ----------------------------------------------------------------------------
#  Grading requirement #2 asks for data loaded via an API. We use TheMealDB
#  because it's free, key-less, and well-suited for a student project.
#
#  Docs: https://www.themealdb.com/api.php
#
#  Every function here follows the same pattern:
#    1. send an HTTP request to TheMealDB
#    2. parse the JSON response
#    3. return a list of dictionaries (one per recipe)
#
#  If the network is down, we warn the user and return an empty list so the
#  rest of the app keeps working.
# ============================================================================
#  AI-ASSISTED AUTHORSHIP: scaffold drafted with Anthropic Claude (04/2026),
#  reviewed by Group 12.04. See README.md.
# ============================================================================

import requests                    # popular Python library for HTTP requests
import streamlit as st             # we use st.cache_data to speed things up


# The base URL of TheMealDB's v1 public API. The '1' is the free API key
# everyone can use (their docs explain this is intentional).
THEMEALDB_BASE = "https://www.themealdb.com/api/json/v1/1"


# @st.cache_data stores the return value so we don't hammer the API.
# ttl = "time to live" in seconds. 60 * 60 = one hour.
@st.cache_data(ttl=60 * 60)
def search_recipes_by_name(query):
    """Search TheMealDB for recipes whose name contains `query`.

    Returns a list of meal dictionaries (could be empty if nothing matched
    or the network is down).
    """
    try:
        resp = requests.get(
            f"{THEMEALDB_BASE}/search.php",
            params={"s": query},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("meals") or []

    except requests.RequestException as exc:
        st.warning(f"Recipe search unavailable: {exc}")
        return []


# Cached for a whole day — the list of cuisines barely changes.
@st.cache_data(ttl=24 * 60 * 60)
def list_cuisines():
    """Return the list of cuisines (TheMealDB calls them 'areas')."""
    try:
        resp = requests.get(
            f"{THEMEALDB_BASE}/list.php",
            params={"a": "list"},
            timeout=20,
        )
        resp.raise_for_status()
        return [m["strArea"] for m in (resp.json().get("meals") or [])]

    except requests.RequestException:
        return []


@st.cache_data(ttl=60 * 60)
def filter_by_cuisine(cuisine):
    """Return a list of recipe stubs (id, name, thumbnail) for a cuisine.

    Note: TheMealDB's filter endpoint only returns minimal data —
    idMeal, strMeal, strMealThumb. Use get_meal_by_id() to fetch
    full details (instructions, ingredients, etc.) for each stub.
    """
    try:
        resp = requests.get(
            f"{THEMEALDB_BASE}/filter.php",
            params={"a": cuisine},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("meals") or []

    except requests.RequestException:
        return []


@st.cache_data(ttl=60 * 60)
def get_meal_by_id(meal_id: str) -> dict | None:
    """Fetch full details for a single meal by its TheMealDB ID.

    filter_by_cuisine() only returns stubs. This function fills in
    the missing fields (instructions, ingredients, area, category)
    by calling the lookup endpoint.

    Returns the full meal dict, or None if not found / network error.
    """
    try:
        resp = requests.get(
            f"{THEMEALDB_BASE}/lookup.php",
            params={"i": meal_id},
            timeout=20,
        )
        resp.raise_for_status()
        meals = resp.json().get("meals") or []
        return meals[0] if meals else None

    except requests.RequestException:
        return None


def extract_ingredients_from_meal(meal: dict) -> list[str]:
    """Extract ingredient names from a TheMealDB meal dict.

    TheMealDB stores ingredients in strIngredient1 … strIngredient20
    and measures in strMeasure1 … strMeasure20.
    Returns a list of "measure ingredient" strings, e.g. ["2 cups Rice", "1 clove Garlic"].
    Empty/null slots are skipped.
    """
    ingredients = []
    for i in range(1, 21):
        name    = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}")    or "").strip()
        if name:
            ingredients.append(f"{measure} {name}".strip() if measure else name)
    return ingredients


def fetch_nutrition_from_ingredients(ingredients: list[str]) -> dict:
    """Send a list of ingredient strings to Spoonacular's nutrition parser.

    Uses the /recipes/parseIngredients endpoint to get per-ingredient
    nutrition, then sums up calories, protein, carbs and fat across all
    ingredients to produce recipe-level totals.

    NOTE: this returns TOTAL nutrition for the whole recipe, not per serving.
    Only use this as a fallback — prefer fetch_nutrition_by_title() which
    returns accurate per-serving values directly from Spoonacular.

    Returns a dict with keys: kcal, protein_g, carbs_g, fat_g.
    All values are ints (rounded). Returns all-None on failure.
    """
    empty = {"kcal": None, "protein_g": None, "carbs_g": None, "fat_g": None}
    if not ingredients:
        return empty

    try:
        ingredient_list = "\n".join(ingredients)

        resp = requests.post(
            "https://api.spoonacular.com/recipes/parseIngredients",
            params={
                "apiKey": st.secrets["SPOONACULAR_API_KEY"],
                "includeNutrition": True,
            },
            data={"ingredientList": ingredient_list, "servings": 1},
            timeout=20,
        )
        resp.raise_for_status()
        parsed = resp.json()

        kcal = protein = carbs = fat = 0.0
        for item in parsed:
            nutrients = item.get("nutrition", {}).get("nutrients", [])
            for n in nutrients:
                name   = n.get("name", "")
                amount = n.get("amount", 0) or 0
                if name == "Calories":
                    kcal    += amount
                elif name == "Protein":
                    protein += amount
                elif name == "Carbohydrates":
                    carbs   += amount
                elif name == "Fat":
                    fat     += amount

        return {
            "kcal":      int(round(kcal)),
            "protein_g": round(protein, 1),
            "carbs_g":   round(carbs, 1),
            "fat_g":     round(fat, 1),
        }

    except Exception:
        return empty


def fetch_nutrition_by_title(title: str) -> dict:
    """Look up accurate per-serving nutrition for a dish by name via Spoonacular.

    Uses complexSearch with addRecipeNutrition=True, which returns macros
    already normalised to one serving — no manual division needed.

    This is the primary nutrition source. fetch_nutrition_from_ingredients()
    is only used as a fallback when this returns nothing.

    Returns a dict with keys: kcal, protein_g, carbs_g, fat_g.
    All values are None if the dish isn't found or the API is unavailable.
    """
    empty = {"kcal": None, "protein_g": None, "carbs_g": None, "fat_g": None}
    if not title:
        return empty

    try:
        resp = requests.get(
            "https://api.spoonacular.com/recipes/complexSearch",
            params={
                "apiKey": st.secrets["SPOONACULAR_API_KEY"],
                "query":  title,
                "number": 1,
                "addRecipeNutrition": True,
            },
            timeout=20,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return empty

        nutrients = results[0].get("nutrition", {}).get("nutrients", [])

        def _get(name):
            return next((n["amount"] for n in nutrients if n.get("name") == name), None)

        kcal    = _get("Calories")
        protein = _get("Protein")
        carbs   = _get("Carbohydrates")
        fat     = _get("Fat")

        return {
            "kcal":      int(round(kcal))    if kcal    is not None else None,
            "protein_g": round(protein, 1)   if protein is not None else None,
            "carbs_g":   round(carbs, 1)     if carbs   is not None else None,
            "fat_g":     round(fat, 1)       if fat     is not None else None,
        }

    except Exception:
        return empty


def fetch_nutrition_for_meal(meal: dict) -> dict:
    """High-level helper: given a TheMealDB meal dict, return per-serving nutrition.

    Strategy (in order):
      1. Spoonacular complexSearch by dish name — returns accurate per-serving
         macros directly, so no division is needed. This fixes the previous bug
         where raw ingredient weights were summed and divided by a hardcoded 4,
         producing wildly incorrect values (e.g. 3434 kcal for a mousse).
      2. Fallback to ingredient parser only when step 1 finds nothing (e.g. very
         obscure dishes). The parser returns whole-recipe totals, so we divide
         by 4 as a rough estimate — still better than the inflated raw sum.

    Returns a dict with keys: kcal, protein_g, carbs_g, fat_g.
    """
    # ── Primary: search by dish name (accurate per-serving) ──────────────────
    title = meal.get("strMeal", "")
    result = fetch_nutrition_by_title(title)
    if result["kcal"] is not None:
        return result

    # ── Fallback: ingredient parser ÷ 4 servings (rough estimate) ────────────
    ingredients = extract_ingredients_from_meal(meal)
    raw = fetch_nutrition_from_ingredients(ingredients)
    _srv = 4
    return {
        "kcal":      int(round(raw["kcal"] / _srv))      if raw["kcal"]      is not None else None,
        "protein_g": round(raw["protein_g"] / _srv, 1)   if raw["protein_g"] is not None else None,
        "carbs_g":   round(raw["carbs_g"] / _srv, 1)     if raw["carbs_g"]   is not None else None,
        "fat_g":     round(raw["fat_g"] / _srv, 1)       if raw["fat_g"]     is not None else None,
    }


def fetch_kcal_for_title(title: str) -> "int | None":
    """Look up calorie data for a recipe title using Spoonacular.

    Called when a TheMealDB recipe is saved to the Meal Planner and we
    need to backfill kcal_per_serv in the DB. Not cached because it is
    called imperatively (on button click), not during a render pass.

    Returns the kcal as an int, or None if not found / API unavailable.
    """
    result = fetch_nutrition_by_title(title)
    return result["kcal"]


@st.cache_data(ttl=60 * 60)
def search_spoonacular(query="", vegetarian=False, vegan=False,
                       gluten_free=False, dairy_free=False):
    """Search Spoonacular for recipes, filtered by the user diet profile.

    We request addRecipeNutrition=True so that each result includes calorie
    data. The kcal value is stored in the returned dict under 'kcal_per_serv'
    so that 2_Recipes.py can persist it to the DB when the user saves a recipe
    to the Meal Planner — which then feeds the Nutrition Analytics page.
    """
    try:
        diet = None
        if vegan:
            diet = "vegan"
        elif vegetarian:
            diet = "vegetarian"

        intolerances = []
        if gluten_free:
            intolerances.append("gluten")
        if dairy_free:
            intolerances.append("dairy")

        params = {
            "apiKey": st.secrets["SPOONACULAR_API_KEY"],
            "query": query,
            "number": 20,
            "addRecipeInformation": True,
            "fillIngredients": True,
            "addRecipeNutrition": True,   # ← request calorie + macro data
        }
        if diet:
            params["diet"] = diet
        if intolerances:
            params["intolerances"] = ",".join(intolerances)

        resp = requests.get(
            "https://api.spoonacular.com/recipes/complexSearch",
            params=params,
            timeout=20,
        )
        resp.raise_for_status()

        results = []
        for r in resp.json().get("results", []):
            import re
            raw_summary = r.get("summary", "")
            clean_summary = re.sub(r"<[^>]+>", "", raw_summary)

            ing = [
                i.get("name", "").strip()
                for i in r.get("extendedIngredients", [])
                if i.get("name", "").strip()
            ]

            # ── Extract calorie data from the nutrition block ─────────────
            # Spoonacular returns: { "nutrition": { "nutrients": [ {...}, ...] } }
            # Each nutrient dict has "name", "amount", and "unit".
            nutrition = r.get("nutrition", {})
            nutrients = nutrition.get("nutrients", [])
            kcal = next(
                (int(n["amount"]) for n in nutrients if n.get("name") == "Calories"),
                None,
            )

            results.append({
                "strMeal":      r.get("title", ""),
                "strMealThumb": r.get("image", ""),
                "strArea":      "International",
                "strCategory":  r.get("dishTypes", [""])[0].title() if r.get("dishTypes") else "—",
                "strInstructions": clean_summary,
                "_ingredients": ing,
                "source":       "spoonacular",
                "kcal_per_serv": kcal,   # ← None if Spoonacular didn't return it
            })

        return results

    except Exception as exc:
        st.warning(f"Spoonacular unavailable: {exc}")
        return []
