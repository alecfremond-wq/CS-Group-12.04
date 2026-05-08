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
    # `try`/`except` lets us handle network errors gracefully.
    try:
        # GET request to the search endpoint. The 's' parameter is the search term.
        # timeout=10 means: give up after 10 seconds (no frozen UI).
        resp = requests.get(
            f"{THEMEALDB_BASE}/search.php",       # full URL e.g. https://.../search.php
            params={"s": query},                  # TheMealDB expects the query under the key 's'
            timeout=20,                           # seconds before we give up
        )
        # raise_for_status() raises an exception if the HTTP status is 4xx or 5xx.
        resp.raise_for_status()

        # resp.json() parses the JSON response body into a Python dict.
        # TheMealDB returns {"meals": [...]} or {"meals": null} if empty.
        # The `or []` makes sure we always return a list (never None).
        return resp.json().get("meals") or []

    except requests.RequestException as exc:      # any network / HTTP error lands here
        # Show a yellow warning in the UI so users know what happened.
        st.warning(f"Recipe search unavailable: {exc}")
        return []                                 # degrade gracefully


# Cached for a whole day — the list of cuisines barely changes.
@st.cache_data(ttl=24 * 60 * 60)
def list_cuisines():
    """Return the list of cuisines (TheMealDB calls them 'areas')."""
    try:
        # The 'a=list' parameter tells TheMealDB "give me all available areas".
        resp = requests.get(
            f"{THEMEALDB_BASE}/list.php",
            params={"a": "list"},
            timeout=20,
        )
        resp.raise_for_status()

        # The response shape is {"meals": [{"strArea": "Italian"}, ...]}
        # We use a LIST COMPREHENSION to extract just the "strArea" strings.
        return [m["strArea"] for m in (resp.json().get("meals") or [])]

    except requests.RequestException:
        return []                                 # empty list = no cuisines loaded


@st.cache_data(ttl=60 * 60)
def filter_by_cuisine(cuisine):
    """Return a list of recipe stubs (id, name, thumbnail) for a cuisine."""
    try:
        # The 'a=<cuisine>' parameter filters meals by area.
        resp = requests.get(
            f"{THEMEALDB_BASE}/filter.php",
            params={"a": cuisine},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("meals") or []     # list of {"idMeal", "strMeal", "strMealThumb"}

    except requests.RequestException:
        return []


@st.cache_data(ttl=60 * 60)
def search_spoonacular(query="", vegetarian=False, vegan=False,
                       gluten_free=False, dairy_free=False):
    """Search Spoonacular for recipes, filtered by the user diet profile."""
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
            # fillIngredients makes Spoonacular include extendedIngredients in
            # the response — without this, ingredient lists come back empty.
            "fillIngredients": True,
        }
        if diet:
            params["diet"] = diet
        if intolerances:
            params["intolerances"] = ",".join(intolerances)
        resp = requests.get("https://api.spoonacular.com/recipes/complexSearch", params=params, timeout=20)
        resp.raise_for_status()
        results = []
        for r in resp.json().get("results", []):
            # Spoonacular returns the summary as HTML — strip tags for clean display.
            import re
            raw_summary = r.get("summary", "")
            clean_summary = re.sub(r"<[^>]+>", "", raw_summary)
            # Extract ingredient names from extendedIngredients (available when
            # addRecipeInformation=True). We store them under "_ingredients" so
            # extract_ingredients() in the Recipes page can find them — without
            # this, Spoonacular saves would always have an empty ingredient list
            # and would never feed the ML model.
            ing = [
                i.get("name", "").strip()
                for i in r.get("extendedIngredients", [])
                if i.get("name", "").strip()
            ]
            results.append({
                "strMeal": r.get("title", ""),
                "strMealThumb": r.get("image", ""),
                "strArea": "International",
                "strCategory": r.get("dishTypes", [""])[0].title() if r.get("dishTypes") else "—",
                "strInstructions": clean_summary,
                "_ingredients": ing,
                "source": "spoonacular",
            })
        return results
    except Exception as exc:
        st.warning(f"Spoonacular unavailable: {exc}")
        return []


@st.cache_data(ttl=24 * 60 * 60)
def get_spoonacular_ingredients():
    """Return a sorted list of ingredient names pulled from Spoonacular.

    We run a handful of common searches so the pantry dropdown is populated
    with real Spoonacular names — the same strings that appear in recipe
    results, so pantry matching is exact instead of fuzzy.
    Cached for 24 h so we only spend API quota once per day.
    """
    ingredients = set()
    for query in ["chicken", "pasta", "salad", "soup", "fish", "beef", "rice"]:
        for meal in search_spoonacular(query=query):
            for ing in meal.get("_ingredients", []):
                if ing.strip():
                    ingredients.add(ing.strip().lower())
    return sorted(ingredients)
