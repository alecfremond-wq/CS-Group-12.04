"""
This module is the single point of contact between the Streamlit UI and the two external 
recipe/nutrition APIs the app relies on:

 1. TheMealDB  (https://www.themealdb.com/api.php)
      A free, public recipe database.  No API key required.
      Used for: recipe search, cuisine (area) listing, meal detail lookup,  ingredient catalogue, 
      and cuisine-filtered browsing.

 2. Spoonacular  (https://spoonacular.com/food-api)
     A freemium recipe + nutrition API.  Requires an API key stored in
     Streamlit's secrets manager under the key "SPOONACULAR_API_KEY".
     Used for: per-serving nutrition data and diet-filtered recipe search.
     
 Notes:
-  Every public function is decorated with @st.cache_data so that repeated calls don't fire 
    new HTTP requests.

- All network calls use a 20-second timeout and are wrapped in try/except so that API failures 
show empty list / None and don't crash.

- The _area_name_variants() helper was written with AI assistance to handle
   the linguistic mismatch between TheMealDB's /list endpoint (which uses
   adjectival demonyms like "Indonesian") and its /filter endpoint (which
   sometimes only accepts plain country names like "Indonesia").  The curated
   mapping dictionary inside it was generated and reviewed with AI help.

  Dependecies:
    - requests      HTTP client used for all API calls
    - streamlit     Web-app framework; also provides caching (@st.cache_data)
                   and secrets management (st.secrets)

   - TheMealDB API  (free, no auth)  https://www.themealdb.com/api/json/v1/1
    - Spoonacular API (needs key)     https://api.spoonacular.com

Authors: Ines, Alec, Giulia

Sources: Claude Sonnet 4.6 (see comments below)
"""


import requests
import streamlit as st

# Base URL for all TheMealDB v1 endpoints.
THEMEALDB_BASE = "https://www.themealdb.com/api/json/v1/1"


## TheMealDB helpers

@st.cache_data(ttl=60 * 60)
def search_recipes_by_name(query: str) -> list[dict]:
    """Search TheMealDB for recipes whose name contains `query`.
     Returns a list of full meal dicts (each containing name, ingredients,
    instructions, thumbnail URL, etc.).  Returns an empty list if the
    network call fails or no results are found.

    """
    try:
        resp = requests.get(
            f"{THEMEALDB_BASE}/search.php", params={"s": query}, timeout=20
        )
        resp.raise_for_status()
        return resp.json().get("meals") or []
    except requests.RequestException as exc:
        # Shows q warning in the Streamlit sidebar; don't crash the app
        st.warning(f"Recipe search unavailable: {exc}")
        return []


@st.cache_data(ttl=24 * 60 * 60)   # Cache for 24 hours; cuisine list rarely changes
def list_cuisines() -> list[str]:
    """Return the list of cuisines (TheMealDB calls them 'areas')

    TheMealDB uses the word "area" internally for what most users call a
    "cuisine" or "country".  This function returns all ~200 area names that
    TheMealDB knows about, regardless of whether they actually have recipes.
    See list_cuisines_with_recipes() for a filtered version."""

    try:
        resp = requests.get(
            f"{THEMEALDB_BASE}/list.php", params={"a": "list"}, timeout=20
        )
        resp.raise_for_status()
        return [m["strArea"] for m in (resp.json().get("meals") or [])]
    except requests.RequestException:
        return []


@st.cache_data(ttl=24 * 60 * 60)    # Expensive (makes many sub-requests); cache 24 h
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

# \ begin code generated with Claude Sonnet 4.6
def _area_name_variants(area: str) -> list[str]:
    """
    This function has no @st.cache_data because it is pure string
    manipulation with no I/O.  It is called inside the cached filter_by_cuisine().

    TheMealDB's /list endpoint returns adjectival demonyms ("Indonesian",
    "Argentine") but its /filter endpoint sometimes only accepts the plain
    country name ("Indonesia", "Argentina") — or vice versa.  Rather than
    maintaining a static alias table that breaks whenever TheMealDB adds new
    areas, this function generates plausible name variants automatically and
    lets filter_by_cuisine() try each one in turn, stopping at the first hit.
    The large _AREA_TO_COUNTRY mapping below was generated with AI assistance
    and then manually reviewed for accuracy.
    """
    candidates: list[str] = [area]
    
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
    
    # Forward lookup: adjective (e.g. "Indonesian") to country ("Indonesia")
    alt = _AREA_TO_COUNTRY.get(area)
    if alt and alt not in candidates:
        candidates.append(alt)

    # Also try the reverse: if we have the country name, try the adjective
    reverse = {v: k for k, v in _AREA_TO_COUNTRY.items()}
    alt2 = reverse.get(area)
    if alt2 and alt2 not in candidates:
        candidates.append(alt2)

    return candidates
    
# \ end code generated with the help of Claude Sonnet 4.6


@st.cache_data(ttl=60 * 60)  # Cache 1 hour; recipe lists change occasionally
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
            # Network error: bail out immediately rather than retrying other variants
            return []
    return []

@st.cache_data(ttl=60 * 60) # Cache 1 hour; individual meal data is stable
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


# \ begin code generated with the help of Claude Sonnet 4.6
@st.cache_data(ttl=60 * 60) # Cache 1 hour — the combined fetch can be slow
def fetch_cuisine_meals(cuisine: str, limit: int = 10) -> list[dict]:
    """Return full meal dicts for a cuisine in ONE cached batch.

    Previously this was called uncached from 2_Recipes.py, firing up to 10 sequential HTTP 
    requests on every render. Now it's cached for 1 hour so subsequent renders cost zero network calls.

    This function combines filter_by_cuisine() (which returns stubs) and
    get_meal_by_id() (which hydrates each stub) so callers get full meal
    dicts in a single cached operation.
    """
    stubs = filter_by_cuisine(cuisine)[:limit]
    return [m for stub in stubs if (m := get_meal_by_id(stub["idMeal"]))]
# \ end code generated with the help of Claude Sonnet 4.6


## Ingredient extraction

def extract_ingredients_from_meal(meal: dict) -> list[str]:
    """Extract 'measure ingredient' strings from a TheMealDB meal dict.
     TheMealDB stores ingredients in 20 parallel numbered fields:
      strIngredient1 … strIngredient20
      strMeasure1    … strMeasure20
    Fields beyond the last ingredient are empty strings or None.
    """
    ingredients = []
    for i in range(1, 21):
        name    = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}")    or "").strip()
        if name:
            # Combine measure + name when a measure is present (e.g. "2 cups flour")
            # or use just the name when it isn't (e.g. "salt")
            ingredients.append(f"{measure} {name}".strip() if measure else name)
    return ingredients


@st.cache_data(ttl=24 * 60 * 60)  # Cache 24 h; ingredient catalogue rarely changes
def get_themealdb_ingredients() -> list[str]:
    """ Fetch the full list of ingredients from TheMealDB and return them sorted
        We use TheMealDB (free, no quota) instead of Spoonacular (paid, limited) so that ingredient
        names in the pantry exactly match those used in recipes
     The result is cached for 24 hours — the list almost never changes
    
    This returns alphabetically sorted list of lowercase ingredient name strings.
    """
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



## Nutrition — Spoonacular

@st.cache_data(ttl=24 * 60 * 60)
def fetch_nutrition_by_title(title: str) -> dict:
    
    """Look up per-serving nutrition for a dish by its name via Spoonacular.

    Uses Spoonacular's complexSearch endpoint with addRecipeNutrition=True.
    Returns the first result's nutrition data already normalised per serving —callers 
    don't need to divide by serving count.

    This requires st.secrets["SPOONACULAR_API_KEY"] to work. 
    """
    
     # Define the "empty" return value used for early exits and error cases
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

        # Helper to find a named nutrient's amount in the nested list
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


@st.cache_data(ttl=24 * 60 * 60) # Cache 24 h; ingredient nutrition is stable
def fetch_nutrition_from_ingredients(ingredients: tuple[str, ...]) -> dict:
    """Estimate whole-recipe nutrition by parsing raw ingredient strings.

    Uses Spoonacular's parseIngredients endpoint which understands human-language strings like 
    "2 cups all-purpose flour, sifted" and returns per-ingredient nutrition that this function 
    sums into recipe totals.

    @st.cache_data requires all arguments to be hashable. Lists are not hashable; tuples are.  
    Callers must pass the ingredients as a tuple.

    This returns WHOLE-RECIPE totals, not per-serving values.
    Callers must divide by the appropriate serving count (default assumed to be 4 in 
    fetch_nutrition_for_meal()).
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
        # Accumulate totals across all parsed ingredient items
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
    
    This function itself is NOT cached because its two sub-functions are already cached
    Adding another cache layer here would be redundant.
    """
    result = fetch_nutrition_by_title(meal.get("strMeal", ""))
    if result["kcal"] is not None:
        return result

    # Fallback — pass as tuple so the result is cacheable
    raw = fetch_nutrition_from_ingredients(
        tuple(extract_ingredients_from_meal(meal))
    )
    srv = 4  # Assumed serving count when none is known. TheMealDB doesn't provide this
    return {
        "kcal":      int(round(raw["kcal"] / srv))      if raw["kcal"]      is not None else None,
        "protein_g": round(raw["protein_g"] / srv, 1)   if raw["protein_g"] is not None else None,
        "carbs_g":   round(raw["carbs_g"] / srv, 1)     if raw["carbs_g"]   is not None else None,
        "fat_g":     round(raw["fat_g"] / srv, 1)       if raw["fat_g"]     is not None else None,
    }


def fetch_kcal_for_title(title: str) -> int | None:
    """Convenience wrapper. This returns just kcal for a dish title."""
    return fetch_nutrition_by_title(title)["kcal"]

# \ begin code generated with the help of Claude Sonnet 4.6
@st.cache_data(ttl=60 * 60)  # Cache 1 hour; search results can change but are stable
def search_spoonacular(query="", vegetarian=False, vegan=False,
                       gluten_free=False, dairy_free=False) -> list[dict]:
    """
    Search Spoonacular for recipes, optionally filtered by dietary requirements.
    Returns results normalised into a dict shape that is compatible with the
    TheMealDB meal dicts used everywhere else in the app, so that UI components
    can render both sources identically.
    
Two ingredient fields:
    Spoonacular provides two useful strings per ingredient:
      "name"     → plain ingredient name, e.g. "flour"
      "original" → full cooking string, e.g. "2 cups all-purpose flour, sifted"

    Both are stored under different keys for different consumers:
      _ingredients         (plain names)   → used by the ML similarity model
                                             and the wishlist feature.  The ML
                                             model compares ingredient sets; if
                                             it receives "2 cups all-purpose
                                             flour, sifted" it cannot match that
                                             against "flour" from a TheMealDB
                                             recipe, so similarity scores drop
                                             to zero.  Plain names match reliably.
      _ingredients_display (full strings)  → used only for rendering the
                                             ingredient list in recipe-card
                                             expanders so the user sees useful
                                             quantities, not just bare names

        This returns a list of normalised meal dicts with the same keys as TheMealDB meals
        (strMeal, strMealThumb, strArea, strCategory, strInstructions) plus
        Spoonacular-specific keys (_ingredients, _ingredients_display,
        source="spoonacular", kcal_per_serv).
        Returns [] if the API is unreachable.
    """ 
    try:
        # Build the diet string: Spoonacular uses a single "diet" param
        # and treats vegan as a superset of vegetarian

        diet = "vegan" if vegan else ("vegetarian" if vegetarian else None)

        # Build the intolerances list for gluten/dairy exclusions
        intolerances = []
        if gluten_free: intolerances.append("gluten")
        if dairy_free:  intolerances.append("dairy")

        params = {
            "apiKey": st.secrets["SPOONACULAR_API_KEY"],
            "query":  query, "number": 20,
            "addRecipeInformation": True, # Include dish type, summary, etc.
            "fillIngredients": True,     # Include extendedIngredients list
            "addRecipeNutrition": True,
        }
        if diet:         params["diet"] = diet
        if intolerances: params["intolerances"] = ",".join(intolerances)

        resp = requests.get(
            "https://api.spoonacular.com/recipes/complexSearch",
            params=params, timeout=20,
        )
        resp.raise_for_status()
        
        # re is imported here (not at module top) because it's only needed in
        # this function — avoids polluting the module namespace for the common
        # case where search_spoonacular() is never called.
        import re
        results = []
        for r in resp.json().get("results", []):
            nutrients = r.get("nutrition", {}).get("nutrients", [])
             # Extract just the calorie value from the nutrients list for the card summary
            kcal = next(
                (int(n["amount"]) for n in nutrients if n.get("name") == "Calories"), None
            )
            results.append({
                "strMeal":         r.get("title", ""),
                "strMealThumb":    r.get("image", ""),
                "strArea":         "International",         # Spoonacular doesn't provide a country/area
                "strCategory":     r.get("dishTypes", [""])[0].title() if r.get("dishTypes") else "—",
                "strInstructions": re.sub(r"<[^>]+>", "", r.get("summary", "")),
                # Plain ingredient names for ML model and wishlist matching
                "_ingredients":         [i.get("name","").strip() for i in r.get("extendedIngredients",[]) if i.get("name","").strip()],
                "_ingredients_display": [i.get("original","").strip() for i in r.get("extendedIngredients",[]) if i.get("original","").strip()],
                "source":          "spoonacular",
                "kcal_per_serv":   kcal,
            })
        return results
    except Exception as exc:
        st.warning(f"Spoonacular unavailable: {exc}")
        return []
# \ end code generated with the help of Claude Sonnet 4.6
