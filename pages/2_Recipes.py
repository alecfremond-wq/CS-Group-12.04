"""
Recipes: Search and browse recipes (API + DB)

This is the main recipe-browsing page of the CookMate application.
It gives users two ways to discover recipes:
  1. Free-text search (tab "🔎 Search") : queries both TheMealDB and Spoonacular,
  optionally ranks results with an ML Recommender, and shows pantry-match indicators.
  2. World-map browser (tab "🌍 Browse by cuisine"): An interactive
     Plotly choropleth coloured by continent; clicking a country loads its traditional recipes 
     ONLY from TheMealDB.

Dependencies: 
  recipes_data        — Static list of local recipes (RECIPES constant); used as the
                        baseline catalogue for the ML Recommender and for mapping
                        recipe titles to their internal database IDs.

  src.components.ui   — Shared UI helpers:
                          empty_state()  → renders a friendly "nothing found" message
                          page_header()  → renders the page title + subtitle

  src.data.api_client — All outbound API calls, each decorated with @st.cache_data:
                          filter_by_cuisine()         → TheMealDB: stubs for one cuisine
                          fetch_kcal_for_title()      → Spoonacular: kcal by dish name
                          fetch_nutrition_for_meal()  → Spoonacular: full nutrition by meal
                          fetch_nutrition_by_title()  → Spoonacular: nutrition by title
                          fetch_nutrition_from_ingredients() → Spoonacular: parse ingredients
                          get_meal_by_id()            → TheMealDB: full recipe by ID
                          list_cuisines()             → TheMealDB: all cuisine area names
                          list_cuisines_with_recipes() → TheMealDB: areas that have ≥1 recipe
                          search_recipes_by_name()    → TheMealDB: free-text search
                          search_spoonacular()        → Spoonacular: filtered search

  src.data.database   — SQLite helpers:
                          query_df()  → SELECT → pandas DataFrame
                          execute()   → INSERT / UPDATE / DELETE

  src.models.recommender — Recommender class: content-based ML scorer that ranks
                           external recipes by ingredient similarity to the user's
                           taste profile.

  src.utils.session   — Session management:
                          init_session_state()  → sets up all required st.session_state keys
                          require_profile()     → redirects to onboarding if no profile exists;
                                                  returns the user profile dict on success

Database table used:
- recipes     : Master recipe catalogue (id, title, kcal_per_serv, protein_g, carbs_g, fat_g)
- planner_pool: Junction table linking users to recipes saved for meal planning
                  (user_id, recipe_id)
- meal_plan   : Scheduled meal plan entries (user_id, recipe_id, day, meal_slot)
- pantry      : User's on-hand ingredients (user_id, ingredient_id, quantity)
- ingredients : Ingredient master list (id, name)
 
Authors: 
Alec, 
Camilla Piano,        -> World map section
Giulia De Angelis,    -> Section 3, 
Ines

Sources: Claude Sonnet 4.6 (see comments below)

"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from recipes_data import RECIPES as LOCAL_RECIPES
from src.components.ui import empty_state, page_header
from src.data.api_client import (
    filter_by_cuisine,
    fetch_kcal_for_title,
    fetch_nutrition_for_meal,
    fetch_nutrition_by_title,
    fetch_nutrition_from_ingredients,
    get_meal_by_id,
    list_cuisines,
    list_cuisines_with_recipes,
    search_recipes_by_name,
    search_spoonacular,
)
from src.data.database import query_df, execute
from src.models.recommender import Recommender
from src.utils.session import init_session_state, require_profile


## SECTION 1: Ingredient extractor

def extract_ingredients(meal: dict) -> list[str]:
    """Pull the ingredient list out of a TheMealDB or Spoonacular result.

    Spoonacular already gives us full strings like "2 cups flour" in _ingredients.
    TheMealDB splits the name and amount into separate fields:
        strIngredient1 = "Flour",  strMeasure1 = "2 cups"
    We combine them so the result looks like "2 cups Flour", "1 Egg", etc.
    """
    if meal.get("_ingredients"):
        return [i.strip() for i in meal["_ingredients"] if i.strip()]

    ingredients = []
    for i in range(1, 21):
        name    = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}")    or "").strip()
        if not name:
            continue
        ingredients.append(f"{measure} {name}" if measure else name)
    return ingredients


## Section 2: Nutrition helper
#  Begin code generated with Claude Sonnet 4.6
def _fetch_nutrition_robust(meal: dict) -> dict:
    """Fetch per-serving nutrition for any recipe, regardless of source.

    Works for BOTH Spoonacular and MealDB recipes:

    Spoonacular recipes already carry kcal_per_serv / protein_g / carbs_g /
    fat_g in the meal dict — return immediately, no API call needed.

    MealDB recipes have none of those fields, so we try two strategies:
      1. complexSearch by dish title (fast; accurate when Spoonacular knows
         the dish name — e.g. "Spaghetti Bolognese").
      2. parseIngredients fallback (slower; works for any MealDB recipe by
         parsing its ingredient list and dividing totals by 4 servings).

    Both Spoonacular calls are @st.cache_data(ttl=24h) in api_client.py,
    so each unique dish is only fetched once per day.

    Returns dict with keys: kcal, protein_g, carbs_g, fat_g
    (all may be None if every strategy fails).
    """
    empty = {"kcal": None, "protein_g": None, "carbs_g": None, "fat_g": None}

    # ── Spoonacular recipes already have nutrition attached ───────────
    if meal.get("kcal_per_serv") is not None:
        return {
            "kcal":      meal["kcal_per_serv"],
            "protein_g": meal.get("protein_g"),
            "carbs_g":   meal.get("carbs_g"),
            "fat_g":     meal.get("fat_g"),
        }

    # ── Strategy 1: title-based Spoonacular lookup ────────────────────
    title = meal.get("strMeal") or meal.get("title") or ""
    if title:
        try:
            nutrition = fetch_nutrition_by_title(title)
            if nutrition.get("kcal") is not None:
                return nutrition
        except Exception:
            pass

    # ── Strategy 2: ingredient-parser fallback ────────────────────────
    # extract_ingredients() is defined just above — safe to call here.
    try:
        ingredients = extract_ingredients(meal)
        if ingredients:
            raw = fetch_nutrition_from_ingredients(ingredients)
            if raw.get("kcal") is not None:
                # parseIngredients returns whole-recipe totals → divide by ~4 servings
                return {
                    "kcal":      int(raw["kcal"] / 4),
                    "protein_g": round(raw["protein_g"] / 4, 1) if raw.get("protein_g") else None,
                    "carbs_g":   round(raw["carbs_g"]   / 4, 1) if raw.get("carbs_g")   else None,
                    "fat_g":     round(raw["fat_g"]     / 4, 1) if raw.get("fat_g")     else None,
                }
    except Exception:
        pass

    return empty

#  end code generated by Claude Sonnet 4.6


# Section 3: Meal Planner helpers
# Load/display/remove recipes saved to the weekly Meal Planner.

def get_my_planner_meals(user_id: int) -> list[dict]:
    """
    Load all recipes saved in the Meal Planner for the given user.
    Returns a list of dicts with 'title' and 'recipe_id'.
    """
    if not user_id:
        return []
    try:
        df = query_df(
            """
            SELECT r.id AS recipe_id, r.title
            FROM planner_pool pp
            JOIN recipes r ON pp.recipe_id = r.id
            WHERE pp.user_id = ?
            ORDER BY r.title
            """,
            (user_id,),
        )
        if df.empty:
            return []
        return df.to_dict("records")  # Convert each DataFrame row to a plain dict
    except Exception:
        return []                     # return empty list on any DB error


def show_my_planner_banner() -> None:
    """
    Show a summary banner at the top of the Recipes page listing all
    recipes already saved to the Meal Planner. Always visible

    Recipes are displayed in a compact 3-column grid
    The expander is open by default when the user has saved at least one dish.

    note: 
    - Calls execute() to DELETE from planner_pool and meal_plan on removal.
    - Calls st.rerun() after a removal so the banner reflects the updated state.
    """
    user_id = st.session_state.get("user_id")
    if not user_id:
        return

    saved_meals = get_my_planner_meals(user_id)
    count = len(saved_meals)
    label = "dish" if count == 1 else "dishes"    # Correct singular/plural

    with st.expander(
        f"🍽️ My Meal Planner  ·  **{count} {label} saved**",
        expanded=count > 0, # Auto-expand only when there are saved dishes
    ):
        if not saved_meals:
            st.info("You haven't saved any dishes to the Meal Planner yet.")
            return

        # Show saved dishes in a compact 3-column grid
        cols = st.columns(3)
        for idx, meal in enumerate(saved_meals):
            with cols[idx % 3]:
                col_text, col_btn = st.columns([3, 1])
                with col_text:
                    st.markdown(f"✅ **{meal['title']}**")
                with col_btn:
                    if st.button(
                        "✕",
                        key=f"banner_remove_{meal['recipe_id']}",
                        help="Remove from Meal Planner",
                    ):
                        # Remove from the saved pool
                        execute(
                            "DELETE FROM planner_pool WHERE user_id = ? AND recipe_id = ?",
                            (user_id, meal["recipe_id"]),
                        )
                        # Also remove any scheduled slots to avoid orphaned entries
                        execute(
                            "DELETE FROM meal_plan WHERE user_id = ? AND recipe_id = ?",
                            (user_id, meal["recipe_id"]),
                        )
                        st.toast(f"❌ '{meal['title']}' removed from Meal Planner", icon="🗑️")
                        st.rerun()

        st.caption("Go to the **Meal Planner** page to schedule them across the week.")


## Section 4: Page
# Initialise session state, enforce login, render header and top-of-page widgets.

# Set up all required st.session_state keys with their default values
init_session_state()

profile = require_profile()

page_header("🍲 Recipes", "Search recipes or browse by cuisine.")

# Always show the Meal Planner summary at the top of the page
show_my_planner_banner()

# The workaround: store the title in session_state before rerun, then pop and display it 
# here at the start of the next render cycle
if "planner_added_title" in st.session_state:
    added_title = st.session_state.pop("planner_added_title")
    st.toast(f"✅ '{added_title}' added to Meal Planner!", icon="🍽️")

# API quota notice
# Spoonacular's free tier is limited to 50 points/day across all users.
# This info banner lets users know why calorie data may sometimes be missing.
st.info(
    "**Calorie & nutrition data** for TheMealDB recipes is estimated via the "
    "[Spoonacular API](https://spoonacular.com/food-api) (free tier: 50 points/day). "
    "If calorie data is missing on a recipe, the daily quota may be exhausted — "
    "you can always enter calories manually in **Nutrition Analytics**.",
    icon="ℹ️",
)

local_title_to_id = {r["name"].lower(): r["id"] for r in LOCAL_RECIPES}


## Section 4b: Allergy filter toggle
# ── Allergy filter toggle ─────────────────────────────────────────────────────
user_allergies: list[str] = profile.get("allergies") or []
if user_allergies:
    _labels = ", ".join(user_allergies)
    hide_unsafe = st.toggle(
        f"🛡️ Hide recipes that contain my allergens ({_labels})",
        value=True,
        key="hide_unsafe_recipes",
        help="Turn off to see all recipes — unsafe ones will still show a warning badge.",
    )
else:
    hide_unsafe = False


## Section 4c: Allergy conflict checker

def check_allergy_conflicts(meal: dict, allergies: list[str]) -> list[str]:
    """Return a list of allergens found in the meal's ingredients.

    Checks each user allergen string (case-insensitive) against the full
    ingredient list of the recipe. Returns only those allergens that appear
    in at least one ingredient string.

    Args:
        meal:      A recipe dict from TheMealDB or Spoonacular.
        allergies: List of allergen strings from the user profile
                   (e.g. ["gluten", "lactose", "nuts"]).

    Returns:
        A (possibly empty) list of conflicting allergen strings.
    """
    if not allergies:
        return []
    ingredients = extract_ingredients(meal)
    ingredient_text = " ".join(ingredients).lower()
    return [allergen for allergen in allergies if allergen.lower() in ingredient_text]


## Section 5: World map data structure
#Author: Camilla Piano 
#The world map on the Recipes page is colored by continent, with each country colored if we have at least one recipe from that country in TheMealDB. 
#The following data structures support that visualization and the hover tooltips:

#CONTINENT_DATA is a dictionary which link the continents to their respective colors and 
#the countries that belong to them (from A to Z).
CONTINENT_DATA = {
    "Africa": {
        "color": "#E07B39",
        "countries": [
            "Algeria","Angola","Benin","Botswana","Burkina Faso","Burundi",
            "Cameroon","Cape Verde","Central African Rep.","Chad","Comoros",
            "DR Congo","Rep. Congo","Djibouti","Egypt","Equatorial Guinea",
            "Eritrea","Eswatini","Ethiopia","Gabon","Gambia","Ghana","Guinea",
            "Guinea-Bissau","Ivory Coast","Kenya","Lesotho","Liberia","Libya",
            "Madagascar","Malawi","Mali","Mauritania","Mauritius","Morocco",
            "Mozambique","Namibia","Niger","Nigeria","Rwanda","São Tomé & Príncipe",
            "Senegal","Sierra Leone","Somalia","South Africa","South Sudan",
            "Sudan","Tanzania","Togo","Tunisia","Uganda","Zambia","Zimbabwe",
        ],
    },
    "Asia": {
        "color": "#4A90D9",
        "countries": [
            "Afghanistan","Armenia","Azerbaijan","Bahrain","Bangladesh","Bhutan",
            "Brunei","Cambodia","China","Cyprus","Georgia","India","Indonesia",
            "Iran","Iraq","Israel","Japan","Jordan","Kazakhstan","Kuwait",
            "Kyrgyzstan","Laos","Lebanon","Malaysia","Maldives","Mongolia",
            "Myanmar","Nepal","North Korea","Oman","Pakistan","Palestine",
            "Philippines","Qatar","Saudi Arabia","Singapore","South Korea",
            "Sri Lanka","Syria","Taiwan","Tajikistan","Thailand","Timor-Leste",
            "Turkey","Turkmenistan","UAE","Uzbekistan","Vietnam","Yemen",
        ],
    },
    "Europe": {
        "color": "#5BAD6F",
        "countries": [
            "Albania","Andorra","Austria","Belarus","Belgium","Bosnia & Herz.",
            "Bulgaria","Croatia","Czech Republic","Denmark","Estonia","Finland",
            "France","Germany","Greece","Hungary","Iceland","Ireland","Italy",
            "Kosovo","Latvia","Liechtenstein","Lithuania","Luxembourg","Malta",
            "Moldova","Monaco","Montenegro","Netherlands","North Macedonia",
            "Norway","Poland","Portugal","Romania","Russia","San Marino",
            "Serbia","Slovakia","Slovenia","Spain","Sweden","Switzerland",
            "Ukraine","United Kingdom","Vatican City",
        ],
    },
    "North America": {
        "color": "#9B59B6",
        "countries": [
            "Antigua & Barbuda","Bahamas","Barbados","Belize","Canada",
            "Costa Rica","Cuba","Dominica","Dominican Republic","El Salvador",
            "Grenada","Guatemala","Haiti","Honduras","Jamaica","Mexico",
            "Nicaragua","Panama","St Kitts & Nevis","St Lucia",
            "St Vincent & the Grenadines","Trinidad & Tobago","United States",
        ],
    },
    "South America": {
        "color": "#E74C3C",
        "countries": [
            "Argentina","Bolivia","Brazil","Chile","Colombia","Ecuador",
            "Guyana","Paraguay","Peru","Suriname","Uruguay","Venezuela",
        ],
    },
    "Oceania": {
        "color": "#F1C40F",
        "countries": [
            "Australia","Fiji","Kiribati","Marshall Islands","Micronesia",
            "Nauru","New Zealand","Palau","Papua New Guinea","Samoa",
            "Solomon Islands","Tonga","Tuvalu","Vanuatu",
        ],
    },
    "Antarctica": {
        "color": "#BDC3C7",
        "countries": ["Antarctica (no sovereign countries)"],
    },
}

#ISO_CONTINENT is a dictionary which maps each country (by ISO code) to its continent,
#used for coloring the world map and showing continent names in hover tooltips.
ISO_CONTINENT = {
    # Africa
    "DZA":"Africa","AGO":"Africa","BEN":"Africa","BWA":"Africa","BFA":"Africa",
    "BDI":"Africa","CPV":"Africa","CMR":"Africa","CAF":"Africa","TCD":"Africa",
    "COM":"Africa","COD":"Africa","COG":"Africa","DJI":"Africa","EGY":"Africa",
    "GNQ":"Africa","ERI":"Africa","SWZ":"Africa","ETH":"Africa","GAB":"Africa",
    "GMB":"Africa","GHA":"Africa","GIN":"Africa","GNB":"Africa","CIV":"Africa",
    "KEN":"Africa","LSO":"Africa","LBR":"Africa","LBY":"Africa","MDG":"Africa",
    "MWI":"Africa","MLI":"Africa","MRT":"Africa","MUS":"Africa","MAR":"Africa",
    "MOZ":"Africa","NAM":"Africa","NER":"Africa","NGA":"Africa","RWA":"Africa",
    "STP":"Africa","SEN":"Africa","SLE":"Africa","SOM":"Africa","ZAF":"Africa",
    "SSD":"Africa","SDN":"Africa","TZA":"Africa","TGO":"Africa","TUN":"Africa",
    "UGA":"Africa","ZMB":"Africa","ZWE":"Africa",
    # Asia
    "AFG":"Asia","ARM":"Asia","AZE":"Asia","BHR":"Asia","BGD":"Asia",
    "BTN":"Asia","BRN":"Asia","KHM":"Asia","CHN":"Asia","CYP":"Asia",
    "GEO":"Asia","IND":"Asia","IDN":"Asia","IRN":"Asia","IRQ":"Asia",
    "ISR":"Asia","JPN":"Asia","JOR":"Asia","KAZ":"Asia","KWT":"Asia",
    "KGZ":"Asia","LAO":"Asia","LBN":"Asia","MYS":"Asia","MDV":"Asia",
    "MNG":"Asia","MMR":"Asia","NPL":"Asia","PRK":"Asia","OMN":"Asia",
    "PAK":"Asia","PSE":"Asia","PHL":"Asia","QAT":"Asia","SAU":"Asia",
    "SGP":"Asia","KOR":"Asia","LKA":"Asia","SYR":"Asia","TWN":"Asia",
    "TJK":"Asia","THA":"Asia","TLS":"Asia","TUR":"Asia","TKM":"Asia",
    "ARE":"Asia","UZB":"Asia","VNM":"Asia","YEM":"Asia",
    # Europe
    "ALB":"Europe","AND":"Europe","AUT":"Europe","BLR":"Europe","BEL":"Europe",
    "BIH":"Europe","BGR":"Europe","HRV":"Europe","CZE":"Europe","DNK":"Europe",
    "EST":"Europe","FIN":"Europe","FRA":"Europe","DEU":"Europe","GRC":"Europe",
    "HUN":"Europe","ISL":"Europe","IRL":"Europe","ITA":"Europe","XKX":"Europe",
    "LVA":"Europe","LIE":"Europe","LTU":"Europe","LUX":"Europe","MLT":"Europe",
    "MDA":"Europe","MCO":"Europe","MNE":"Europe","NLD":"Europe","MKD":"Europe",
    "NOR":"Europe","POL":"Europe","PRT":"Europe","ROU":"Europe","RUS":"Europe",
    "SMR":"Europe","SRB":"Europe","SVK":"Europe","SVN":"Europe","ESP":"Europe",
    "SWE":"Europe","CHE":"Europe","UKR":"Europe","GBR":"Europe","VAT":"Europe",
    # North America
    "ATG":"North America","BHS":"North America","BRB":"North America",
    "BLZ":"North America","CAN":"North America","CRI":"North America",
    "CUB":"North America","DMA":"North America","DOM":"North America",
    "SLV":"North America","GRD":"North America","GTM":"North America",
    "HTI":"North America","HND":"North America","JAM":"North America",
    "MEX":"North America","NIC":"North America","PAN":"North America",
    "KNA":"North America","LCA":"North America","VCT":"North America",
    "TTO":"North America","USA":"North America",
    # South America
    "ARG":"South America","BOL":"South America","BRA":"South America",
    "CHL":"South America","COL":"South America","ECU":"South America",
    "GUY":"South America","PRY":"South America","PER":"South America",
    "SUR":"South America","URY":"South America","VEN":"South America",
    # Oceania
    "AUS":"Oceania","FJI":"Oceania","KIR":"Oceania","MHL":"Oceania",
    "FSM":"Oceania","NRU":"Oceania","NZL":"Oceania","PLW":"Oceania",
    "PNG":"Oceania","WSM":"Oceania","SLB":"Oceania","TON":"Oceania",
    "TUV":"Oceania","VUT":"Oceania",
    # Antarctica
    "ATA":"Antarctica",
}

#ISO_NAME is a dictionary mapping ISO country codes to their full country names, 
#used for display in hover tooltips on the world map.
ISO_NAME = {
    "DZA":"Algeria","AGO":"Angola","BEN":"Benin","BWA":"Botswana","BFA":"Burkina Faso",
    "BDI":"Burundi","CPV":"Cape Verde","CMR":"Cameroon","CAF":"Central African Rep.",
    "TCD":"Chad","COM":"Comoros","COD":"DR Congo","COG":"Rep. Congo","DJI":"Djibouti",
    "EGY":"Egypt","GNQ":"Equatorial Guinea","ERI":"Eritrea","SWZ":"Eswatini",
    "ETH":"Ethiopia","GAB":"Gabon","GMB":"Gambia","GHA":"Ghana","GIN":"Guinea",
    "GNB":"Guinea-Bissau","CIV":"Ivory Coast","KEN":"Kenya","LSO":"Lesotho",
    "LBR":"Liberia","LBY":"Libya","MDG":"Madagascar","MWI":"Malawi","MLI":"Mali",
    "MRT":"Mauritania","MUS":"Mauritius","MAR":"Morocco","MOZ":"Mozambique",
    "NAM":"Namibia","NER":"Niger","NGA":"Nigeria","RWA":"Rwanda",
    "STP":"Sao Tome & Principe","SEN":"Senegal","SLE":"Sierra Leone","SOM":"Somalia",
    "ZAF":"South Africa","SSD":"South Sudan","SDN":"Sudan","TZA":"Tanzania",
    "TGO":"Togo","TUN":"Tunisia","UGA":"Uganda","ZMB":"Zambia","ZWE":"Zimbabwe",
    "AFG":"Afghanistan","ARM":"Armenia","AZE":"Azerbaijan","BHR":"Bahrain",
    "BGD":"Bangladesh","BTN":"Bhutan","BRN":"Brunei","KHM":"Cambodia","CHN":"China",
    "CYP":"Cyprus","GEO":"Georgia","IND":"India","IDN":"Indonesia","IRN":"Iran",
    "IRQ":"Iraq","ISR":"Israel","JPN":"Japan","JOR":"Jordan","KAZ":"Kazakhstan",
    "KWT":"Kuwait","KGZ":"Kyrgyzstan","LAO":"Laos","LBN":"Lebanon","MYS":"Malaysia",
    "MDV":"Maldives","MNG":"Mongolia","MMR":"Myanmar","NPL":"Nepal",
    "PRK":"North Korea","OMN":"Oman","PAK":"Pakistan","PSE":"Palestine",
    "PHL":"Philippines","QAT":"Qatar","SAU":"Saudi Arabia","SGP":"Singapore",
    "KOR":"South Korea","LKA":"Sri Lanka","SYR":"Syria","TWN":"Taiwan",
    "TJK":"Tajikistan","THA":"Thailand","TLS":"Timor-Leste","TUR":"Turkey",
    "TKM":"Turkmenistan","ARE":"UAE","UZB":"Uzbekistan","VNM":"Vietnam","YEM":"Yemen",
    "ALB":"Albania","AND":"Andorra","AUT":"Austria","BLR":"Belarus","BEL":"Belgium",
    "BIH":"Bosnia & Herz.","BGR":"Bulgaria","HRV":"Croatia","CZE":"Czech Republic",
    "DNK":"Denmark","EST":"Estonia","FIN":"Finland","FRA":"France","DEU":"Germany",
    "GRC":"Greece","HUN":"Hungary","ISL":"Iceland","IRL":"Ireland","ITA":"Italy",
    "XKX":"Kosovo","LVA":"Latvia","LIE":"Liechtenstein","LTU":"Lithuania",
    "LUX":"Luxembourg","MLT":"Malta","MDA":"Moldova","MCO":"Monaco","MNE":"Montenegro",
    "NLD":"Netherlands","MKD":"North Macedonia","NOR":"Norway","POL":"Poland",
    "PRT":"Portugal","ROU":"Romania","RUS":"Russia","SMR":"San Marino","SRB":"Serbia",
    "SVK":"Slovakia","SVN":"Slovenia","ESP":"Spain","SWE":"Sweden","CHE":"Switzerland",
    "UKR":"Ukraine","GBR":"United Kingdom","VAT":"Vatican City",
    "ATG":"Antigua & Barbuda","BHS":"Bahamas","BRB":"Barbados","BLZ":"Belize",
    "CAN":"Canada","CRI":"Costa Rica","CUB":"Cuba","DMA":"Dominica",
    "DOM":"Dominican Republic","SLV":"El Salvador","GRD":"Grenada","GTM":"Guatemala",
    "HTI":"Haiti","HND":"Honduras","JAM":"Jamaica","MEX":"Mexico","NIC":"Nicaragua",
    "PAN":"Panama","KNA":"St Kitts & Nevis","LCA":"St Lucia","VCT":"St Vincent & Gren.",
    "TTO":"Trinidad & Tobago","USA":"United States",
    "ARG":"Argentina","BOL":"Bolivia","BRA":"Brazil","CHL":"Chile","COL":"Colombia",
    "ECU":"Ecuador","GUY":"Guyana","PRY":"Paraguay","PER":"Peru","SUR":"Suriname",
    "URY":"Uruguay","VEN":"Venezuela",
    "AUS":"Australia","FJI":"Fiji","KIR":"Kiribati","MHL":"Marshall Islands",
    "FSM":"Micronesia","NRU":"Nauru","NZL":"New Zealand","PLW":"Palau",
    "PNG":"Papua New Guinea","WSM":"Samoa","SLB":"Solomon Islands","TON":"Tonga",
    "TUV":"Tuvalu","VUT":"Vanuatu",
    "ATA":"Antarctica",
}

#_AREA_TO_ISO is a dictionary mapping cuisine area names from TheMealDB to their 
# corresponding ISO country codes, used to link TheMealDB cuisines to countries on the world map. 
# Some areas may not have a direct ISO match (e.g. "American" → "USA"), and some may be missing 
# if they don't correspond to a specific country (e.g. "European" or "Unknown").
_AREA_TO_ISO: dict[str, str] = {
    "American":        "USA",
    "Argentine":       "ARG",
    "Argentinian":     "ARG",
    "Argentina":       "ARG",
    "Australian":      "AUS",
    "British":         "GBR",
    "Burundian":       "BDI",
    "Cambodian":       "KHM",
    "Cameroonian":     "CMR",
    "Canadian":        "CAN",
    "Chilean":         "CHL",
    "Chinese":         "CHN",
    "Colombian":       "COL",
    "Congolese":       "COD",
    "Costa Rican":     "CRI",
    "Croatian":        "HRV",
    "Cuban":           "CUB",
    "Cypriot":         "CYP",
    "Czech":           "CZE",
    "Danish":          "DNK",
    "Dominican":       "DOM",
    "Dutch":           "NLD",
    "Ecuadoran":       "ECU",
    "Egyptian":        "EGY",
    "Emirati":         "ARE",
    "Estonian":        "EST",
    "Ethiopian":       "ETH",
    "Filipino":        "PHL",
    "Finnish":         "FIN",
    "French":          "FRA",
    "Georgian":        "GEO",
    "German":          "DEU",
    "Ghanaian":        "GHA",
    "Greek":           "GRC",
    "Guatemalan":      "GTM",
    "Guyanese":        "GUY",
    "Haitian":         "HTI",
    "Honduran":        "HND",
    "Hungarian":       "HUN",
    "Icelander":       "ISL",
    "Indian":          "IND",
    "Indonesian":      "IDN",
    "Indonesia":       "IDN",
    "Iranian":         "IRN",
    "Iraqi":           "IRQ",
    "Irish":           "IRL",
    "Israeli":         "ISR",
    "Italian":         "ITA",
    "Ivorian":         "CIV",
    "Jamaican":        "JAM",
    "Japanese":        "JPN",
    "Jordanian":       "JOR",
    "Kazakhstani":     "KAZ",
    "Kenyan":          "KEN",
    "Kirghiz":         "KGZ",
    "Kosovar":         "XKX",
    "Kuwaiti":         "KWT",
    "Laotian":         "LAO",
    "Latvian":         "LVA",
    "Lebanese":        "LBN",
    "Libyan":          "LBY",
    "Lithuanian":      "LTU",
    "Luxembourger":    "LUX",
    "Macedonian":      "MKD",
    "Malagasy":        "MDG",
    "Malawian":        "MWI",
    "Malaysian":       "MYS",
    "Malian":          "MLI",
    "Maltese":         "MLT",
    "Mauritanian":     "MRT",
    "Mauritian":       "MUS",
    "Mexican":         "MEX",
    "Moldovan":        "MDA",
    "Mongolian":       "MNG",
    "Montenegrin":     "MNE",
    "Moroccan":        "MAR",
    "Mozambican":      "MOZ",
    "Namibian":        "NAM",
    "Nepalese":        "NPL",
    "New Zealander":   "NZL",
    "Nicaraguan":      "NIC",
    "Nigerian":        "NGA",
    "Nigerien":        "NER",
    "North Korean":    "PRK",
    "Norwegian":       "NOR",
    "Omani":           "OMN",
    "Pakistani":       "PAK",
    "Palestinian":     "PSE",
    "Panamanian":      "PAN",
    "Paraguayan":      "PRY",
    "Peruvian":        "PER",
    "Polish":          "POL",
    "Portuguese":      "PRT",
    "Puerto Rican":    "PRI",
    "Qatari":          "QAT",
    "Romanian":        "ROU",
    "Russian":         "RUS",
    "Rwandan":         "RWA",
    "Salvadoran":      "SLV",
    "Samoan":          "WSM",
    "Saudi Arabian":   "SAU",
    "Senegalese":      "SEN",
    "Serbian":         "SRB",
    "Seychellois":     "SYC",
    "Sierra Leonean":  "SLE",
    "Singaporean":     "SGP",
    "Slovak":          "SVK",
    "Slovene":         "SVN",
    "Somali":          "SOM",
    "South African":   "ZAF",
    "South Korean":    "KOR",
    "South Sudanese":  "SSD",
    "Spanish":         "ESP",
    "Sri Lankan":      "LKA",
    "Sudanese":        "SDN",
    "Surinamer":       "SUR",
    "Swedish":         "SWE",
    "Swiss":           "CHE",
    "Syrian":          "SYR",
    "Tadhzik":         "TJK",
    "Taiwanese":       "TWN",
    "Tanzanian":       "TZA",
    "Thai":            "THA",
    "Togolese":        "TGO",
    "Tongan":          "TON",
    "Trinidadian":     "TTO",
    "Tunisian":        "TUN",
    "Turkish":         "TUR",
    "Ugandan":         "UGA",
    "Ukrainian":       "UKR",
    "Uruguayan":       "URY",
    "Uzbekistani":     "UZB",
    "Venezuelan":      "VEN",
    "Venezuela":       "VEN",
    "Vietnamese":      "VNM",
    "Yemeni":          "YEM",
    "Zambian":         "ZMB",
    "Zimbabwean":      "ZWE",
    "Burmese":         "MMR",
    "Channel Islander":"GGY",
    "Sammarinese":     "SMR",
    "Guamanian":       "GUM",
    "Bolivian":        "BOL",
    "Brazilian":       "BRA",
}


@st.cache_data(ttl=24 * 60 * 60)
def _build_iso_to_cuisine() -> dict[str, str]:
    """ 
    It fetches from TheMealDB all cuisines that have at least one recipes, 
    then for each one looks up its corresponding ISo country code via the _AREA_TO_ISO dictionary.
    If a match is found, it adds an entry to the mapping from ISO code to cuisine area name. 
    It returns a map that allows the app to know which countries on the map have recipes in TheMealDB. 
    the result is cached for 24 hours to avoid unnecessary API calls. 
    """
    valid_areas = list_cuisines_with_recipes()
    mapping: dict[str, str] = {}
    for area in valid_areas:
        iso = _AREA_TO_ISO.get(area)
        if iso:
            mapping[iso] = area
    return mapping


ISO_TO_CUISINE: dict[str, str] = _build_iso_to_cuisine()


def build_figure() -> go.Figure: #begin code generated by Claude Sonnet 4.6
    """ 
    Builds and returns an interactive Plotly world map by splitting countries into two groups: 
    those with recipes on TheMealDB, colored by continent using a custom colorscale, and those without, shown in grey. 
    For each country with available cuisine it also builds an HTML hover tooltip showing the country name, continent, and cuisine name.
    """
    all_locations = list(ISO_CONTINENT.keys())
    cuisine_isos  = set(ISO_TO_CUISINE.keys())

    colored_locs   = [iso for iso in all_locations if iso in cuisine_isos]
    continent_list = list(CONTINENT_DATA.keys())
    colors_list    = [CONTINENT_DATA[c]["color"] for c in continent_list]
    n = len(continent_list)

    colorscale = []
    for i, col in enumerate(colors_list):
        colorscale.append([i / n, col])
        colorscale.append([(i + 1) / n, col])

    colored_z     = [continent_list.index(ISO_CONTINENT[iso]) for iso in colored_locs]
    colored_hover = []
    for iso in colored_locs:
        cont    = ISO_CONTINENT.get(iso, "")
        name    = ISO_NAME.get(iso, iso)
        cuisine = ISO_TO_CUISINE.get(iso, "")
        color   = CONTINENT_DATA.get(cont, {}).get("color", "#999")
        colored_hover.append(
            f"<b style='font-size:14px'>{name}</b><br>"
            f"<span style='color:{color}'>&#9632;</span> {cont}<br>"
            f"<i style='color:#F1C40F'>🍽️ {cuisine} cuisine — click to explore!</i>"
        )

    trace_colored = go.Choropleth(
        locations=colored_locs,
        locationmode="ISO-3",
        z=colored_z,
        text=colored_hover,
        customdata=colored_locs,
        hovertemplate="%{text}<extra></extra>",
        colorscale=colorscale,
        zmin=0,
        zmax=n,
        showscale=False,
        marker_line_color="white",
        marker_line_width=0.8,
        name="",
    )

    grey_locs  = [iso for iso in all_locations if iso not in cuisine_isos]
    grey_hover = []
    for iso in grey_locs:
        name = ISO_NAME.get(iso, iso)
        grey_hover.append(
            f"<b style='font-size:14px'>{name}</b><br>"
            f"<span style='color:#999'>No recipes available in TheMealDB</span>"
        )

    trace_grey = go.Choropleth(
        locations=grey_locs,
        locationmode="ISO-3",
        z=[0] * len(grey_locs),
        text=grey_hover,
        customdata=grey_locs,
        hovertemplate="%{text}<extra></extra>",
        colorscale=[[0, "#C8C8C8"], [1, "#C8C8C8"]],
        zmin=0,
        zmax=1,
        showscale=False,
        marker_line_color="white",
        marker_line_width=0.5,
        name="",
    ) #end code generated by Claude Sonnet 4.6
   
#It assembles the final figure combining the grey trace bottom and he coloured trace
    fig = go.Figure(data=[trace_grey, trace_colored])
#It applies all visual geographic settings to the map  
    fig.update_layout(
        geo=dict(
            showframe=False, #no border around the map
            showcoastlines=True, #show coastlines in white
            coastlinecolor="white", #coastline color (white)
            showland=True, #show land in light grey
            landcolor="#D5D8DC", #land color (light grey)
            showocean=True, #show ocean in light blue
            oceancolor="#AED6F1", #ocean color (light blue)
            showlakes=True, #show lakes in light blue
            lakecolor="#AED6F1", #lake color (same as ocean)
            showrivers=False, #don't show rivers to reduce clutter
            projection_type="natural earth", #use natural earth projection for a balanced view of all continents
            bgcolor="rgba(0,0,0,0)", #transparent background for the geo component
            lataxis_range=[-60, 85], #limit latitude to exclude Antarctica and focus on inhabited areas
            lonaxis_range=[-180, 180], #full longitude range
            projection_scale=1, #default scale for natural earth projection
            showsubunits=False, #don't show subunits (states/provinces) to keep the map clean
            showcountries=False, #countries are colored by the choropleth traces, so we don't need default country borders
        ),
        paper_bgcolor="white", #white background for the whole figure
        margin=dict(l=0, r=0, t=10, b=10), #tight margins to maximize map area
        hoverlabel=dict(
            bgcolor="#2C3E50", #dark blue background for hover labels
            font=dict(size=12, color="white", family="monospace"), #white monospace font for better readability
            bordercolor="#AAA", #light grey border around hover labels
            align="left", #left-align text in hover labels
        ),
        dragmode=False, #disable dragging to prevent accidental map movement
        annotations=[], #no annotations needed for this map
    )
    return fig #return the final figure object to be rendered in Streamlit


## Section 6: Pantry helpers

def get_pantry() -> set[str]:
    """Load the user's pantry from the database."""
    user_id = st.session_state.get("user_id")
    if not user_id:
        return set()
    try:
        df = query_df(
            """
            SELECT i.name
            FROM pantry p
            JOIN ingredients i ON p.ingredient_id = i.id
            WHERE p.user_id = ? AND p.quantity > 0
            """,
            (user_id,),
        )
        if df.empty:
            return set()
        return set(df["name"].str.lower())
    except Exception:
        return set()


def pantry_pct(meal: dict, pantry: set[str]) -> float | None:
    """Return fraction of ingredients already in pantry."""
    if not pantry:
        return None
    ingredients = extract_ingredients(meal)
    if not ingredients:
        return None
    names = [i.lower() for i in ingredients]
    return sum(1 for n in names if n in pantry) / len(names)


## Section 7: Taste Profile setup

wishlist = st.session_state.get("wishlist", [])

wishlist_ids = [
    w["local_id"]
    for w in wishlist
    if isinstance(w, dict) and w.get("local_id") is not None
]

liked_ingredients = [
    w["ingredients"]
    for w in wishlist
    if isinstance(w, dict) and w.get("ingredients")
]

history_df = pd.DataFrame(st.session_state.get("cooking_history", []))

has_taste_profile = (
    bool(wishlist_ids)
    or bool(liked_ingredients)
    or (
        not history_df.empty
        and "rating" in history_df.columns
        and (history_df["rating"] >= 4).any()
    )
)

tab_search, tab_cuisine = st.tabs(["🔎 Search", "🌍 Browse by cuisine"])


## Section 8: Recipe Card Renderer
# Draws a single recipe card: image, metadata, ingredients, instructions,
# wishlist button, and meal planner button.

def render_meal_card(
   """Render one recipe card inside a Streamlit bordered container.

    Each card contains:
      - Thumbnail image (left column)
      - Title, area/category caption (right column)
      - ML match score progress bar (if available)
      - Pantry-match badge (green/yellow, if available)
      - Expandable ingredients + instructions section
      - ❤️ Save to Wishlist button (or "already saved" caption)
      - ➕ Add to Meal Planner button (or ❌ Remove if already saved)

   Note
      - Reads/writes st.session_state["wishlist"]
      - Reads/writes DB tables: recipes, planner_pool, meal_plan
      - Calls st.rerun() after wishlist/planner changes
    """
    meal: dict,
    ml_score: float | None = None,
    pantry: float | None = None,
    card_key: str = "",
) -> None:
    """Draw a single recipe card.

    card_key must be unique for every card rendered in a single Streamlit
    run (e.g. "search_0", "cuisine_3").
    """
    meal_title = meal["strMeal"]

    with st.container(border=True):
        col_img, col_meta = st.columns([1, 3])

        with col_img:
            st.image(meal.get("strMealThumb"), use_container_width=True)

        with col_meta:
            st.subheader(meal_title)
            st.caption(
                f"{meal.get('strArea', '—')} · {meal.get('strCategory', '—')}"
            )
            # ML Recommender score: shown as a labelled progress bar (0% – 100%)
            if ml_score is not None and not pd.isna(ml_score):
                st.progress(float(ml_score), text=f"Match score: {ml_score:.0%}")
              
            # Pantry badge: only shown if ≥30% of ingredients are on-hand
            if pantry is not None:
                if pantry > 0.6:
                    st.success("🟢 Pantry-friendly")
                elif pantry > 0.3:
                    st.warning("🟡 Partially available")
            # Ingredients & Instructions expandable section
            with st.expander("🧾 Ingredients & Instructions"):
                col_ing, col_inst = st.columns([1, 2])
                with col_ing:
                    st.markdown("**Ingredients**")
                    for ing in extract_ingredients(meal):
                        st.markdown(f"- {ing}")
                with col_inst:
                    st.markdown("**Instructions**")
                    st.write(meal.get("strInstructions", "No instructions available."))

            # Wishlist  button
            # Check if this recipe title is already in the wishlist
            already_saved = any(
                isinstance(w, dict) and w.get("title") == meal_title
                for w in st.session_state.get("wishlist", [])
            )

            if already_saved:
                st.caption("❤️ Saved to wishlist")
            else:
                if st.button("❤️ Save to wishlist", key=f"{card_key}_wish_{meal_title}"):
                    local_id = local_title_to_id.get(meal_title.lower())
                    st.session_state["wishlist"].append(
                        {
                            "title": meal_title,
                            "image": meal.get("strMealThumb"),
                            "area": meal.get("strArea", ""),
                            "local_id": local_id,
                            "ingredients": extract_ingredients(meal),
                        }
                    )
                    st.rerun()  # Refresh so the button changes to "❤️ Saved to wishlist"

            #  Meal Planner button
            user_id  = st.session_state.get("user_id")
            local_id = local_title_to_id.get(meal_title.lower()) # Check local recipe list first

            # If not in the local recipe list, check the DB
            if local_id is None:
                existing_recipe = query_df(
                    """
                    SELECT id FROM recipes
                    WHERE LOWER(title) = LOWER(?)
                    LIMIT 1
                    """,
                    (meal_title,),
                )
                if not existing_recipe.empty:
                    local_id = int(existing_recipe.iloc[0]["id"])

            # Check whether this recipe is already in the planner pool
            already_in_planner = False
            if user_id and local_id:
                planner_check = query_df(
                    """
                    SELECT 1 FROM planner_pool
                    WHERE user_id = ? AND recipe_id = ?
                    LIMIT 1
                    """,
                    (user_id, local_id),
                )
                already_in_planner = not planner_check.empty

            if already_in_planner:
                st.success("🍽️ Already in your Meal Planner!")
                if st.button(
                    "❌ Remove from Meal Planner",
                    key=f"{card_key}_remove_planner_{meal_title}",
                ):
                    # Remove from the pool and also from any scheduled slots
                    execute(
                        "DELETE FROM planner_pool WHERE user_id = ? AND recipe_id = ?",
                        (user_id, local_id),
                    )
                    execute(
                        "DELETE FROM meal_plan WHERE user_id = ? AND recipe_id = ?",
                        (user_id, local_id),
                    )
                    st.toast(f"'{meal_title}' removed from Meal Planner 🗑️", icon="❌")
                    st.rerun()

            else:
                if st.button(
                    "➕ Add to Meal Planner",
                    key=f"{card_key}_planner_{meal_title}",
                ):
                    # Fetch nutrition before saving so the planner has macro data to display.
                    # _fetch_nutrition_robust() handles both Spoonacular (already has nutrition)
                    # and TheMealDB (needs Spoonacular lookup).
                    nutrition = _fetch_nutrition_robust(meal)
                    kcal      = nutrition["kcal"]
                    protein_g = nutrition["protein_g"]
                    carbs_g   = nutrition["carbs_g"]
                    fat_g     = nutrition["fat_g"]

                    if local_id is None:
                        # New recipe not yet in the DB insert it into DB with full nutrition
                        execute(
                            """INSERT INTO recipes
                               (title, kcal_per_serv, protein_g, carbs_g, fat_g)
                               VALUES (?, ?, ?, ?, ?)""",
                            (meal_title, kcal, protein_g, carbs_g, fat_g),
                        )
                        # Retrieve the auto-generated primary key for the new row
                        new_row = query_df(
                            "SELECT id FROM recipes WHERE title = ? ORDER BY id DESC LIMIT 1",
                            (meal_title,),
                        )
                        if not new_row.empty:
                            local_id = int(new_row.iloc[0]["id"])
                    else:
                        # Existing recipe — update nutrition if we got values
                        if kcal is not None:
                            execute(
                                """UPDATE recipes
                                   SET kcal_per_serv = ?, protein_g = ?,
                                       carbs_g = ?, fat_g = ?
                                   WHERE id = ?""",
                                (kcal, protein_g, carbs_g, fat_g, local_id),
                            )

                    if local_id:
                        execute(
                            "INSERT OR IGNORE INTO planner_pool (user_id, recipe_id) VALUES (?, ?)",
                            (user_id, local_id),
                        )
                    # Store the message in session_state and show it on the 
                    # next execution cycle instead
                    st.session_state["planner_added_title"] = meal_title
                    st.rerun()


## Section 9: Search Tab
# Free-text recipe search across TheMealDB + Spoonacular, with optional
# ML ranking based on the user's taste profile.

with tab_search:
    st.subheader("🔎 Hungry? Let's find something delicious!")
    st.markdown("- Search for any dish by name")
    st.markdown("- Get info on the dish and how to make it")
    st.markdown("- Add it to your Meal Planner or Wishlist for later")
    query = st.text_input(
        "What would you like to cook?",
        placeholder="e.g. pasta, curry…",
    )

    if query:
        diet      = profile.get("diet", "omnivore")
        allergies = profile.get("allergies", [])

        veg = diet in ("vegetarian", "vegan") # Both vegetarian and vegan exclude meat
        vgn = diet == "vegan"                 # Vegan additionally excludes dairy/eggs
        gf  = "gluten" in allergies           # Gluten-free filter
        df  = "lactose" in allergies          # Dairy-free filter

        # Search both APIs and combine results (TheMealDB first, then Spoonacular)
        results = search_recipes_by_name(query) + search_spoonacular(
            query=query,
            vegetarian=veg,
            vegan=vgn,
            gluten_free=gf,
            dairy_free=df,
        )

        if not results:
            empty_state("No recipes found — try another word.")
        else:
            # Set up the ML Recommender using the local recipe catalogue as the baseline
            recipes_df = pd.DataFrame(LOCAL_RECIPES).rename(columns={"name": "title"})
            rec        = Recommender(recipes_df)
          
            # Only score the top 10 results (Recommender is O(n) but API results can be large)
            top_results = results[:10]

            # Extract ingredient lists for all top results (needed by the Recommender)
            ingredient_lists = [extract_ingredients(m) for m in top_results]

            # Score results IF the user has a taste profile; otherwise use None placeholders
            raw_scores = (
                rec.score_external(
                    ingredient_lists,
                    history_df,
                    wishlist_ids,
                    liked_ingredients,
                )
                if has_taste_profile
                else [None] * len(top_results)
            )
            # begin code generated with the help of Claude Sonnet 4.6
            # Sort results: scored recipes first (highest score → top), then unscored
            scored_results = sorted(
                zip(top_results, raw_scores),
                key=lambda pair: (
                    (0, -(pair[1] or 0))   # Scored: sort group 0, descending by score
                    if pair[1] is not None
                    else (1, 0)            # Unscored: sort group 1, any order
                ),
            )

            any_scored = any(s is not None for _, s in scored_results)

            # Show the user why results appear in this order
            if any_scored:
                st.caption(
                    "🎯 Results ranked by ingredient similarity to your taste profile. "
                    "Save more recipes to improve the ranking."
                )
            elif has_taste_profile:
                st.caption(
                    "ℹ️ These results don't have ingredient data, "
                    "so ML ranking isn't available here."
                )
            # Load pantry once for all cards (avoids N separate DB calls)
            user_pantry = get_pantry()

            # Per-tab allergy toggle for the search results
            hide_unsafe = (
                st.toggle(
                    "🛡️ Hide recipes that contain my allergies",
                    value=True,
                    key="hide_unsafe_search",
                    help="Turn off to see all recipes — unsafe ones will still show a warning badge.",
                )
                if user_allergies
                else False
            )

            # Render one card per result
            for idx, (meal, score) in enumerate(scored_results):
                conflicts = check_allergy_conflicts(meal, user_allergies)
                if hide_unsafe and conflicts:
                    continue  # Skip unsafe recipes when the filter is on
                render_meal_card(
                    meal,
                    ml_score=score,
                    pantry=pantry_pct(meal, user_pantry),
                    card_key=f"search_{idx}",
                )
              # end code generated with the help of Claude Sonnet 4.6

## Section 10: Cuisine Tab

def fetch_cuisine_recipes(cuisine: str, limit: int = 10) -> list[dict]:
    """Fetch full recipe details for a given cuisine using TheMealDB."""
    stubs      = filter_by_cuisine(cuisine)[:limit]
    full_meals = []
    for stub in stubs:
        meal = get_meal_by_id(stub["idMeal"])
        if meal:
            full_meals.append(meal)
    return full_meals


with tab_cuisine:
    cuisines = list_cuisines()

    if not cuisines:
        empty_state("Cuisine list couldn't be loaded — check your internet.")
    else:
        st.subheader("🌍 Bites Across Borders")
        st.markdown("- Click on a country on the map to explore its traditional recipes")
        st.markdown("- Not sure where a country is? You can also use the selector below!")

        from streamlit_plotly_events import plotly_events

        clicked_points = plotly_events(
            build_figure(),
            click_event=True,
            hover_event=False,
            select_event=False,
            override_width="100%",
            override_height=450,
            key="world_map",
        )

        # Legend
        legend_cols = st.columns(len(CONTINENT_DATA) - 1)
        col_idx = 0
        for cont, info in CONTINENT_DATA.items():
            if cont == "Antarctica":
                continue
            with legend_cols[col_idx]:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:6px;font-size:12px;color:#2C3E50;">'
                    f'<span style="width:12px;height:12px;border-radius:50%;background:{info["color"]};'
                    f'display:inline-block;flex-shrink:0;"></span>'
                    f'{cont} <span style="color:#999;font-size:11px;">({len(info["countries"])})</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            col_idx += 1

        st.divider()

        all_locations = list(ISO_CONTINENT.keys())
        cuisine_isos  = set(ISO_TO_CUISINE.keys())
        colored_locs  = [iso for iso in all_locations if iso in cuisine_isos]

        if clicked_points:
            curve_number = clicked_points[0].get("curveNumber", 0)
            point_index  = clicked_points[0].get("pointIndex")
            if curve_number == 1 and point_index is not None and point_index < len(colored_locs):
                iso = colored_locs[point_index]
                if iso in ISO_TO_CUISINE:
                    st.session_state["map_selected_iso"] = iso

        selected_iso         = st.session_state.get("map_selected_iso")
        active_cuisine       = ISO_TO_CUISINE.get(selected_iso) if selected_iso else None
        selected_country_name = ISO_NAME.get(selected_iso) if selected_iso else None

        CUISINE_TO_ISO  = {v: k for k, v in ISO_TO_CUISINE.items()}
        cuisine_options = ["— click the map or choose here —"] + sorted(ISO_TO_CUISINE.values())
        default_idx     = 0
        if active_cuisine and active_cuisine in cuisine_options:
            default_idx = cuisine_options.index(active_cuisine)

        manual_choice = st.selectbox(
            "Or pick a cuisine manually:",
            options=cuisine_options,
            index=default_idx,
            key="cuisine_selectbox",
        )

        if manual_choice != "— click the map or choose here —":
            active_cuisine        = manual_choice
            selected_iso          = CUISINE_TO_ISO.get(active_cuisine)
            selected_country_name = ISO_NAME.get(selected_iso, active_cuisine)
            st.session_state["map_selected_iso"] = selected_iso

        if active_cuisine:
            st.subheader(f"🍽️ Recipes from {selected_country_name}")

            with st.spinner(f"Loading {active_cuisine} recipes…"):
                cuisine_results = fetch_cuisine_recipes(active_cuisine)

            if not cuisine_results:
                empty_state(f"No recipes found for {active_cuisine} — try another country.")
            else:
                user_pantry = get_pantry()

                # Per-tab allergy toggle for the cuisine results
                hide_unsafe = (
                    st.toggle(
                        "🛡️ Hide recipes that contain my allergies",
                        value=True,
                        key="hide_unsafe_cuisine",
                        help="Turn off to see all recipes — unsafe ones will still show a warning badge.",
                    )
                    if user_allergies
                    else False
                )

                for idx, meal in enumerate(cuisine_results[:10]):
                    conflicts = check_allergy_conflicts(meal, user_allergies)
                    if hide_unsafe and conflicts:
                        continue  # Skip unsafe recipes when the filter is on
                    render_meal_card(
                        meal,
                        pantry=pantry_pct(meal, user_pantry),
                        card_key=f"cuisine_{idx}",
                    )
        else:
            st.info("👆 Click a country on the map to explore its recipes.")
