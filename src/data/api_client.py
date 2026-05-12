
# ============================================================================
#  api_client.py  —  wrapper around TheMealDB (a free public recipe API)
# ----------------------------------------------------------------------------
#  Docs: https://www.themealdb.com/api.php
#

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


@st.cache_data(ttl=24 * 60 * 60)
def list_cuisines_with_recipes() -> list[str]:
    """Return only the areas that actually have at least one recipe.

    TheMealDB's /list endpoint returns ~200 areas but many have zero meals
    in the /filter endpoint (e.g. 'Peruvian', 'Indonesian').  This function
    filters down to only the areas that return real results, so the map
    only colours countries where clicking will actually show recipes.
    """
    all_areas = list_cuisines()
    valid = []
    for area in all_areas:
        meals = filter_by_cuisine(area)
        if meals:
            valid.append(area)
    return valid


def _area_name_variants(area: str) -> list[str]:
    """
    Generate candidate area names to try with TheMealDB's filter endpoint.

    TheMealDB's /list endpoint returns adjective forms ("Indonesian",
    "Argentine") but /filter sometimes only accepts the plain country name
    ("Indonesia", "Argentina") — or vice versa.  Rather than maintaining a
    hardcoded alias table that breaks every time TheMealDB adds a new area,
    we generate plausible variants automatically and try them in order.
    """
    candidates: list[str] = [area]

    # adjective → country name (strip common English suffixes)
    suffixes = [
        ("inian", "inia"),   # Argentinian → Argentina... actually wrong
        ("nian",  "na"),     # Indonesian → Indonesia ... no
        ("ian",   "ia"),     # Indonesian → Indonesía, Iranian → Irani
        ("an",    "a"),      # Mexican → Mexica ... not ideal but harmless
        ("ese",   ""),       # Vietnamese → Vietnam... nope
        ("ish",   ""),       # British → Brit
        ("i",     ""),       # Emirati → Emirat
        ("er",    ""),       # New Zealander → New Zealand
    ]
    # Better: use the strCountry map from TheMealDB itself
    # The /list endpoint with ?a=list also returns strCountry — but we only
    # get strArea here.  So we use a curated map for the known tricky cases.
    _AREA_TO_COUNTRY: dict[str, str] = {
        "Afghan":          "Afghanistan",
        "Albanian":        "Albania",
        "Algerian":        "Algeria",
        "American":        "United States",
        "Argentine":       "Argentina",
        "Argentinian":     "Argentina",
        "Armenian":        "Armenia",
        "Australian":      "Australia",
        "Austrian":        "Austria",
        "Azerbaijani":     "Azerbaijan",
        "Bahraini":        "Bahrain",
        "Bangladeshi":     "Bangladesh",
        "Belgian":         "Belgium",
        "Bolivian":        "Bolivia",
        "Bosnian":         "Bosnia and Herzegovina",
        "Brazilian":       "Brazil",
        "British":         "United Kingdom",
        "Bulgarian":       "Bulgaria",
        "Burmese":         "Myanmar",
        "Burundian":       "Burundi",
        "Cambodian":       "Cambodia",
        "Cameroonian":     "Cameroon",
        "Canadian":        "Canada",
        "Chilean":         "Chile",
        "Chinese":         "China",
        "Colombian":       "Colombia",
        "Costa Rican":     "Costa Rica",
        "Croatian":        "Croatia",
        "Cuban":           "Cuba",
        "Cypriot":         "Cyprus",
        "Czech":           "Czechia",
        "Danish":          "Denmark",
        "Dominican":       "Dominican Republic",
        "Dutch":           "Netherlands",
        "Ecuadoran":       "Ecuador",
        "Egyptian":        "Egypt",
        "Emirati":         "United Arab Emirates",
        "Estonian":        "Estonia",
        "Ethiopian":       "Ethiopia",
        "Filipino":        "Philippines",
        "Finnish":         "Finland",
        "French":          "France",
        "Georgian":        "Georgia",
        "German":          "Germany",
        "Ghanaian":        "Ghana",
        "Greek":           "Greece",
        "Guatemalan":      "Guatemala",
        "Guyanese":        "Guyana",
        "Haitian":         "Haiti",
        "Honduran":        "Honduras",
        "Hungarian":       "Hungary",
        "Icelander":       "Iceland",
        "Indian":          "India",
        "Indonesian":      "Indonesia",
        "Iranian":         "Iran",
        "Iraqi":           "Iraq",
        "Irish":           "Ireland",
        "Israeli":         "Israel",
        "Italian":         "Italy",
        "Ivorian":         "Ivory Coast",
        "Jamaican":        "Jamaica",
        "Japanese":        "Japan",
        "Jordanian":       "Jordan",
        "Kazakhstani":     "Kazakhstan",
        "Kenyan":          "Kenya",
        "Kirghiz":         "Kyrgyzstan",
        "Kosovar":         "Kosovo",
        "Kuwaiti":         "Kuwait",
        "Laotian":         "Laos",
        "Latvian":         "Latvia",
        "Lebanese":        "Lebanon",
        "Libyan":          "Libya",
        "Lithuanian":      "Lithuania",
        "Luxembourger":    "Luxembourg",
        "Macedonian":      "North Macedonia",
        "Malagasy":        "Madagascar",
        "Malawian":        "Malawi",
        "Malaysian":       "Malaysia",
        "Malian":          "Mali",
        "Maltese":         "Malta",
        "Mauritanian":     "Mauritania",
        "Mauritian":       "Mauritius",
        "Mexican":         "Mexico",
        "Moldovan":        "Moldova",
        "Mongolian":       "Mongolia",
        "Montenegrin":     "Montenegro",
        "Moroccan":        "Morocco",
        "Mozambican":      "Mozambique",
        "Namibian":        "Namibia",
        "Nepalese":        "Nepal",
        "New Zealander":   "New Zealand",
        "Nicaraguan":      "Nicaragua",
        "Nigerian":        "Nigeria",
        "Nigerien":        "Niger",
        "North Korean":    "North Korea",
        "Norwegian":       "Norway",
        "Omani":           "Oman",
        "Pakistani":       "Pakistan",
        "Palestinian":     "Palestine",
        "Panamanian":      "Panama",
        "Paraguayan":      "Paraguay",
        "Peruvian":        "Peru",
        "Polish":          "Poland",
        "Portuguese":      "Portugal",
        "Puerto Rican":    "Puerto Rico",
        "Qatari":          "Qatar",
        "Romanian":        "Romania",
        "Russian":         "Russia",
        "Rwandan":         "Rwanda",
        "Salvadoran":      "El Salvador",
        "Samoan":          "Samoa",
        "Saudi Arabian":   "Saudi Arabia",
        "Senegalese":      "Senegal",
        "Serbian":         "Serbia",
        "Seychellois":     "Seychelles",
        "Sierra Leonean":  "Sierra Leone",
        "Singaporean":     "Singapore",
        "Slovak":          "Slovakia",
        "Slovene":         "Slovenia",
        "Somali":          "Somalia",
        "South African":   "South Africa",
        "South Korean":    "South Korea",
        "South Sudanese":  "South Sudan",
        "Spanish":         "Spain",
        "Sri Lankan":      "Sri Lanka",
        "Sudanese":        "Sudan",
        "Surinamer":       "Suriname",
        "Swedish":         "Sweden",
        "Swiss":           "Switzerland",
        "Syrian":          "Syria",
        "Tadhzik":         "Tajikistan",
        "Taiwanese":       "Taiwan",
        "Tanzanian":       "Tanzania",
        "Thai":            "Thailand",
        "Togolese":        "Togo",
        "Tongan":          "Tonga",
        "Trinidadian":     "Trinidad and Tobago",
        "Tunisian":        "Tunisia",
        "Turkish":         "Turkey",
        "Ugandan":         "Uganda",
        "Ukrainian":       "Ukraine",
        "Uruguayan":       "Uruguay",
        "Uzbekistani":     "Uzbekistan",
        "Venezuelan":      "Venezuela",
        "Vietnamese":      "Vietnam",
        "Yemeni":          "Yemen",
        "Zambian":         "Zambia",
        "Zimbabwean":      "Zimbabwe",
        # reverse (country → adjective) for cases TheMealDB uses country name
        "Argentina":       "Argentinian",
        "Venezuela":       "Venezuelan",
        "Indonesia":       "Indonesian",
    }

    alt = _AREA_TO_COUNTRY.get(area)
    if alt and alt not in candidates:
        candidates.append(alt)

    # Also try the reverse: if we have the country name, try the adjective
    reverse = {v: k for k, v in _AREA_TO_COUNTRY.items()}
    alt2 = reverse.get(area)
    if alt2 and alt2 not in candidates:
        candidates.append(alt2)

    return candidates


@st.cache_data(ttl=60 * 60)
def filter_by_cuisine(cuisine: str) -> list[dict]:
    """Return recipe stubs (id, name, thumbnail) for a cuisine.

    Tries the given name first; if TheMealDB returns nothing it automatically
    attempts alternate spellings (adjective ↔ country name) so that e.g.
    "Indonesian" and "Argentina" both resolve correctly.
    """
    for candidate in _area_name_variants(cuisine):
        try:
            resp = requests.get(
                f"{THEMEALDB_BASE}/filter.php", params={"a": candidate}, timeout=20
            )
            resp.raise_for_status()
            meals = resp.json().get("meals") or []
            if meals:
                return meals
        except requests.RequestException:
            return []
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


@st.cache_data(ttl=24 * 60 * 60)
def get_themealdb_ingredients() -> list[str]:
    # Fetch the full list of ingredients from TheMealDB and return them sorted
    # We use TheMealDB (free, no quota) instead of Spoonacular (paid, limited)
    # so that ingredient names in the pantry exactly match those used in recipes
    # The result is cached for 24 hours — the list almost never changes
    try:
        resp = requests.get(
            f"{THEMEALDB_BASE}/list.php",
            params={"i": "list"},
            timeout=20,
        )
        resp.raise_for_status()
        meals = resp.json().get("meals") or []
        # Extract the ingredient name from each entry, lowercase and sort alphabetically
        return sorted(
            m["strIngredient"].strip().lower()
            for m in meals
            if (m.get("strIngredient") or "").strip()
        )
    except requests.RequestException:
        # If the API is unavailable, return an empty list — the pantry still works
        return []


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
                # WHY TWO INGREDIENT FIELDS?
                # Spoonacular gives us two useful fields per ingredient:
                #   "name"     → just the ingredient name,  e.g. "flour"
                #   "original" → the full cooking string,   e.g. "2 cups all-purpose flour, sifted"
                #
                # We need BOTH for different purposes:
                #
                # _ingredients (plain names) → used by the ML model and the
                #   wishlist. The ML model compares ingredient names across
                #   recipes to find similarities. If we give it "2 cups
                #   all-purpose flour, sifted" it can't match that against
                #   "flour" in our TheMealDB catalogue — so scores drop to zero.
                #   Plain names like "flour" match perfectly.
                #
                # _ingredients_display (full strings) → used only for showing
                #   the ingredient list to the user in the recipe card expander.
                #   Here we WANT the full string so the user sees "2 cups flour"
                #   instead of just "flour".
                "_ingredients":         [i.get("name","").strip() for i in r.get("extendedIngredients",[]) if i.get("name","").strip()],
                "_ingredients_display": [i.get("original","").strip() for i in r.get("extendedIngredients",[]) if i.get("original","").strip()],
                "source":          "spoonacular",
                "kcal_per_serv":   kcal,
            })
        return results
    except Exception as exc:
        st.warning(f"Spoonacular unavailable: {exc}")
        return []
