# ============================================================================
#  api_client.py  —  wrapper around TheMealDB (a free public recipe API)
# ----------------------------------------------------------------------------
#  Docs: https://www.themealdb.com/api.php
#
#  AI-ASSISTED AUTHORSHIP: scaffold drafted with Anthropic Claude (04/2026),
#  reviewed by Group 12.04. See README.md.
# ============================================================================

import requests
import streamlit as st

THEMEALDB_BASE = "https://www.themealdb.com/api/json/v1/1"


# ---------------------------------------------------------------------------
# TheMealDB helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60 * 60)
def search_recipes_by_name(query: str) -> list[dict]:
    """Search TheMealDB for recipes whose name contains `query`."""
    try:
        resp = requests.get(
            f"{THEMEALDB_BASE}/search.php", params={"s": query}, timeout=20
        )
        resp.raise_for_status()
        return resp.json().get("meals") or []
    except requests.RequestException as exc:
        st.warning(f"Recipe search unavailable: {exc}")
        return []


@st.cache_data(ttl=24 * 60 * 60)
def list_cuisines() -> list[str]:
    """Return the list of cuisines (TheMealDB calls them 'areas')."""
    try:
        resp = requests.get(
            f"{THEMEALDB_BASE}/list.php", params={"a": "list"}, timeout=20
        )
        resp.raise_for_status()
        return [m["strArea"] for m in (resp.json().get("meals") or [])]
    except requests.RequestException:
        return []


# TheMealDB area-name quirks: the /list endpoint returns adjective forms
# (e.g. "Venezuelan") but the /filter endpoint only works with the country-
# name form for some areas.  This table maps adjective → accepted filter name.
_AREA_FILTER_ALIAS: dict[str, str] = {
    "Venezuelan": "Venezuela",
}


@st.cache_data(ttl=60 * 60)
def filter_by_cuisine(cuisine: str) -> list[dict]:
    """Return recipe stubs (id, name, thumbnail) for a cuisine."""
    # Apply alias fix before hitting the API
    cuisine = _AREA_FILTER_ALIAS.get(cuisine, cuisine)
    try:
        resp = requests.get(
            f"{THEMEALDB_BASE}/filter.php", params={"a": cuisine}, timeout=20
        )
        resp.raise_for_status()
        return resp.json().get("meals") or []
    except requests.RequestException:
        return []


@st.cache_data(ttl=60 * 60)
def get_meal_by_id(meal_id: str) -> dict | None:
    """Fetch full details for a single meal by its TheMealDB ID."""
    try:
        resp = requests.get(
            f"{THEMEALDB_BASE}/lookup.php", params={"i": meal_id}, timeout=20
        )
        resp.raise_for_status()
        meals = resp.json().get("meals") or []
        return meals[0] if meals else None
    except requests.RequestException:
        return None


@st.cache_data(ttl=60 * 60)
def fetch_cuisine_meals(cuisine: str, limit: int = 10) -> list[dict]:
    """Return full meal dicts for a cuisine in ONE cached batch.

    Previously this was called uncached from 2_Recipes.py, firing up to
    10 sequential HTTP requests on every render. Now it's cached for 1 hour
    so subsequent renders cost zero network calls.
    """
    stubs = filter_by_cuisine(cuisine)[:limit]
    return [m for stub in stubs if (m := get_meal_by_id(stub["idMeal"]))]


# ---------------------------------------------------------------------------
# Ingredient extraction
# ---------------------------------------------------------------------------

def extract_ingredients_from_meal(meal: dict) -> list[str]:
    """Extract 'measure ingredient' strings from a TheMealDB meal dict."""
    ingredients = []
    for i in range(1, 21):
        name    = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}")    or "").strip()
        if name:
            ingredients.append(f"{measure} {name}".strip() if measure else name)
    return ingredients


# ---------------------------------------------------------------------------
# Nutrition — Spoonacular
# ---------------------------------------------------------------------------

@st.cache_data(ttl=24 * 60 * 60)
def fetch_nutrition_by_title(title: str) -> dict:
    """Per-serving nutrition for a dish by name via Spoonacular complexSearch.

    Returns macros already normalised to one serving — no division needed.
    Cached for 24 h so repeated lookups of the same dish cost nothing.
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


@st.cache_data(ttl=24 * 60 * 60)
def fetch_nutrition_from_ingredients(ingredients: tuple[str, ...]) -> dict:
    """Fallback: sum nutrition across raw ingredients via Spoonacular parser.

    Takes a tuple (not list) so it is hashable and cacheable.
    Returns whole-recipe totals — caller must divide by serving count.
    """
    empty = {"kcal": None, "protein_g": None, "carbs_g": None, "fat_g": None}
    if not ingredients:
        return empty
    try:
        resp = requests.post(
            "https://api.spoonacular.com/recipes/parseIngredients",
            params={
                "apiKey": st.secrets["SPOONACULAR_API_KEY"],
                "includeNutrition": True,
            },
            data={"ingredientList": "\n".join(ingredients), "servings": 1},
            timeout=20,
        )
        resp.raise_for_status()
        kcal = protein = carbs = fat = 0.0
        for item in resp.json():
            for n in item.get("nutrition", {}).get("nutrients", []):
                amt = n.get("amount", 0) or 0
                if n.get("name") == "Calories":       kcal    += amt
                elif n.get("name") == "Protein":      protein += amt
                elif n.get("name") == "Carbohydrates": carbs  += amt
                elif n.get("name") == "Fat":           fat    += amt
        return {
            "kcal":      int(round(kcal)),
            "protein_g": round(protein, 1),
            "carbs_g":   round(carbs, 1),
            "fat_g":     round(fat, 1),
        }
    except Exception:
        return empty


def fetch_nutrition_for_meal(meal: dict) -> dict:
    """Return accurate per-serving nutrition for a TheMealDB meal dict.

    Strategy:
      1. Spoonacular complexSearch by dish name (accurate, cached 24 h).
      2. Fallback: ingredient parser ÷ 4 (rough, also cached 24 h).
    """
    result = fetch_nutrition_by_title(meal.get("strMeal", ""))
    if result["kcal"] is not None:
        return result

    # Fallback — pass as tuple so the result is cacheable
    raw = fetch_nutrition_from_ingredients(
        tuple(extract_ingredients_from_meal(meal))
    )
    srv = 4
    return {
        "kcal":      int(round(raw["kcal"] / srv))      if raw["kcal"]      is not None else None,
        "protein_g": round(raw["protein_g"] / srv, 1)   if raw["protein_g"] is not None else None,
        "carbs_g":   round(raw["carbs_g"] / srv, 1)     if raw["carbs_g"]   is not None else None,
        "fat_g":     round(raw["fat_g"] / srv, 1)       if raw["fat_g"]     is not None else None,
    }


def fetch_kcal_for_title(title: str) -> int | None:
    """Convenience wrapper — returns just kcal for a dish title."""
    return fetch_nutrition_by_title(title)["kcal"]


@st.cache_data(ttl=60 * 60)
def search_spoonacular(query="", vegetarian=False, vegan=False,
                       gluten_free=False, dairy_free=False) -> list[dict]:
    """Search Spoonacular for recipes filtered by diet profile."""
    try:
        diet = "vegan" if vegan else ("vegetarian" if vegetarian else None)
        intolerances = []
        if gluten_free: intolerances.append("gluten")
        if dairy_free:  intolerances.append("dairy")

        params = {
            "apiKey": st.secrets["SPOONACULAR_API_KEY"],
            "query":  query, "number": 20,
            "addRecipeInformation": True,
            "fillIngredients": True,
            "addRecipeNutrition": True,
        }
        if diet:         params["diet"] = diet
        if intolerances: params["intolerances"] = ",".join(intolerances)

        resp = requests.get(
            "https://api.spoonacular.com/recipes/complexSearch",
            params=params, timeout=20,
        )
        resp.raise_for_status()

        import re
        results = []
        for r in resp.json().get("results", []):
            nutrients = r.get("nutrition", {}).get("nutrients", [])
            kcal = next(
                (int(n["amount"]) for n in nutrients if n.get("name") == "Calories"), None
            )
            results.append({
                "strMeal":         r.get("title", ""),
                "strMealThumb":    r.get("image", ""),
                "strArea":         "International",
                "strCategory":     r.get("dishTypes", [""])[0].title() if r.get("dishTypes") else "—",
                "strInstructions": re.sub(r"<[^>]+>", "", r.get("summary", "")),
                "_ingredients":    [i.get("name","").strip() for i in r.get("extendedIngredients",[]) if i.get("name","").strip()],
                "source":          "spoonacular",
                "kcal_per_serv":   kcal,
            })
        return results
    except Exception as exc:
        st.warning(f"Spoonacular unavailable: {exc}")
        return []
