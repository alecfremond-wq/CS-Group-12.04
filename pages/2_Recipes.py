
"""
Recipes — search and browse recipes (API + DB).
Owner: <assign on Apr 22>
Grading coverage:
    * Req. 2 (API — TheMealDB + Spoonacular)
    * Req. 4 (user interaction — search, filter, add-to-wishlist)
    * Req. 5 (ML — search results ranked by taste profile when available)
TODOs for the owner:
    - when a user clicks "Save recipe", persist to the `recipes` table
      so the Recommender has data to learn from.
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
    get_meal_by_id,
    list_cuisines,
    list_cuisines_with_recipes,
    search_recipes_by_name,
    search_spoonacular,
)
from src.data.database import query_df, execute
from src.models.recommender import Recommender
from src.utils.session import init_session_state, require_profile


# ── Planner helpers ───────────────────────────────────────────────────────────

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
        return df.to_dict("records")
    except Exception:
        return []


def show_my_planner_banner() -> None:
    """
    Show a summary banner at the top of the Recipes page listing all
    recipes already saved to the Meal Planner. Always visible — persists
    across navigation.
    """
    user_id = st.session_state.get("user_id")
    if not user_id:
        return

    saved_meals = get_my_planner_meals(user_id)
    count = len(saved_meals)
    label = "dish" if count == 1 else "dishes"

    with st.expander(
        f"🍽️ My Meal Planner  ·  **{count} {label} saved**",
        expanded=count > 0,
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
                        # Remove from the pool (dropdown options)
                        execute(
                            "DELETE FROM planner_pool WHERE user_id = ? AND recipe_id = ?",
                            (user_id, meal["recipe_id"]),
                        )
                        # Also remove any scheduled slots for this recipe
                        # so it disappears from the weekly grid too
                        execute(
                            "DELETE FROM meal_plan WHERE user_id = ? AND recipe_id = ?",
                            (user_id, meal["recipe_id"]),
                        )
                        st.toast(f"❌ '{meal['title']}' removed from Meal Planner", icon="🗑️")
                        st.rerun()

        st.caption("Go to the **Meal Planner** page to schedule them across the week.")


# ── App init ──────────────────────────────────────────────────────────────────

init_session_state()

profile = require_profile()

page_header("🍲 Recipes", "Search recipes or browse by cuisine.")

# Always show the Meal Planner summary at the top of the page
show_my_planner_banner()

local_title_to_id = {r["name"].lower(): r["id"] for r in LOCAL_RECIPES}


# ── World Map data ────────────────────────────────────────────────────────────

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
# Maps every known TheMealDB area name → ISO-3 country code.
# Used to build ISO_TO_CUISINE dynamically from the live API response.
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

# Build ISO_TO_CUISINE dynamically: only include countries that TheMealDB
# actually has recipes for (avoids colouring Peru, Indonesia etc. in the map
# when clicking them would show "No recipes found").
@st.cache_data(ttl=24 * 60 * 60)
def _build_iso_to_cuisine() -> dict[str, str]:
    valid_areas = list_cuisines_with_recipes()  # only areas with real recipes
    mapping: dict[str, str] = {}
    for area in valid_areas:
        iso = _AREA_TO_ISO.get(area)
        if iso:
            mapping[iso] = area
    return mapping

ISO_TO_CUISINE: dict[str, str] = _build_iso_to_cuisine()



def build_figure() -> go.Figure:
    """
    Build the Plotly choropleth world map.

    - Countries available on TheMealDB are coloured by continent and
      show a 'click to explore' prompt on hover.
    - All other countries are rendered in a neutral grey and show only
      the country name (no cuisine available).
    Two separate Choropleth traces are used so the two groups can have
    independent colours and hover templates without affecting the shared
    colour-scale logic.
    """
    all_locations = list(ISO_CONTINENT.keys())
    cuisine_isos  = set(ISO_TO_CUISINE.keys())

    # ── Coloured trace: countries with TheMealDB recipes ──────────────
    colored_locs  = [iso for iso in all_locations if iso in cuisine_isos]
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

    # ── Grey trace: countries without TheMealDB recipes ───────────────
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
    )

    fig = go.Figure(data=[trace_grey, trace_colored])
    fig.update_layout(
        geo=dict(
            showframe=False,
            showcoastlines=True,
            coastlinecolor="white",
            showland=True,
            landcolor="#D5D8DC",
            showocean=True,
            oceancolor="#AED6F1",
            showlakes=True,
            lakecolor="#AED6F1",
            showrivers=False,
            projection_type="natural earth",
            bgcolor="rgba(0,0,0,0)",
            lataxis_range=[-60, 85],
            lonaxis_range=[-180, 180],
            projection_scale=1,
            showsubunits=False,
            showcountries=False,
        ),
        paper_bgcolor="white",
        margin=dict(l=0, r=0, t=10, b=10),
        hoverlabel=dict(
            bgcolor="#2C3E50",
            font=dict(size=12, color="white", family="monospace"),
            bordercolor="#AAA",
            align="left",
        ),
        dragmode=False,
        annotations=[],
    )
    return fig


# ── Pantry helper ─────────────────────────────────────────────────────────────

def extract_ingredients(meal: dict) -> list[str]:
    """Pull the ingredient list out of a TheMealDB or Spoonacular result."""
    if meal.get("_ingredients"):
        return [i.strip() for i in meal["_ingredients"] if i.strip()]

    return [
        meal[f"strIngredient{i}"].strip()
        for i in range(1, 21)
        if (meal.get(f"strIngredient{i}") or "").strip()
    ]


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


# ── Wishlist / taste-profile setup ────────────────────────────────────────────

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


# ── Helper: render one recipe card ────────────────────────────────────────────

def render_meal_card(
    meal: dict,
    ml_score: float | None = None,
    pantry: float | None = None,
    card_key: str = "",  # unique prefix to avoid StreamlitDuplicateElementKey
) -> None:
    """Draw a single recipe card.

    card_key must be unique for every card rendered in a single Streamlit
    run (e.g. "search_0", "cuisine_3"). Without it, two cards with the
    same meal title produce duplicate widget keys and crash the app.
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

            if ml_score is not None and not pd.isna(ml_score):
                st.progress(float(ml_score), text=f"Match score: {ml_score:.0%}")

            if pantry is not None:
                if pantry > 0.6:
                    st.success("🟢 Pantry-friendly")
                elif pantry > 0.3:
                    st.warning("🟡 Partially available")

            with st.expander("🧾 Ingredients & Instructions"):
                col_ing, col_inst = st.columns([1, 2])
                with col_ing:
                    st.markdown("**Ingredients**")
                    for ing in extract_ingredients(meal):
                        st.markdown(f"- {ing}")
                with col_inst:
                    st.markdown("**Instructions**")
                    st.write(meal.get("strInstructions", "No instructions available."))

            # ── Wishlist ──────────────────────────────────────────────────
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
                    st.rerun()

            # ── Meal Planner ──────────────────────────────────────────────
            user_id = st.session_state.get("user_id")
            local_id = local_title_to_id.get(meal_title.lower())

            # If not in the local recipe list, check the DB
            if local_id is None:
                existing_recipe = query_df(
                    """
                    SELECT id
                    FROM recipes
                    WHERE LOWER(title) = LOWER(?)
                    LIMIT 1
                    """,
                    (meal_title,),
                )
                if not existing_recipe.empty:
                    local_id = int(existing_recipe.iloc[0]["id"])

            # Check whether this recipe is already in the planner
            already_in_planner = False
            if user_id and local_id:
                planner_check = query_df(
                    """
                    SELECT 1
                    FROM planner_pool
                    WHERE user_id = ? AND recipe_id = ?
                    LIMIT 1
                    """,
                    (user_id, local_id),
                )
                already_in_planner = not planner_check.empty

            if already_in_planner:
                # Green badge so the user can immediately see it's saved
                st.success("🍽️ Already in your Meal Planner!")

                if st.button(
                    "❌ Remove from Meal Planner",
                    key=f"{card_key}_remove_planner_{meal_title}",
                ):
                    # Remove from the pool (dropdown options)
                    execute(
                        "DELETE FROM planner_pool WHERE user_id = ? AND recipe_id = ?",
                        (user_id, local_id),
                    )
                    # Also remove any scheduled slots for this recipe
                    # so it disappears from the weekly grid too
                    execute(
                        "DELETE FROM meal_plan WHERE user_id = ? AND recipe_id = ?",
                        (user_id, local_id),
                    )
                    # Toast persists across the rerun so the user sees it
                    st.toast(f"'{meal_title}' removed from Meal Planner 🗑️", icon="❌")
                    st.rerun()

            else:
                if st.button(
                    "➕ Add to Meal Planner",
                    key=f"{card_key}_planner_{meal_title}",
                ):
                    # If the recipe doesn't exist in the DB yet, create it.
                    # Also save kcal_per_serv if available (Spoonacular provides
                    # this when addRecipeNutrition=True is set in api_client.py).
                    if local_id is None:
                        kcal      = meal.get("kcal_per_serv")
                        protein_g = meal.get("protein_g")
                        carbs_g   = meal.get("carbs_g")
                        fat_g     = meal.get("fat_g")

                        # TheMealDB recipes don't carry nutrition data.
                        # We extract their ingredients and send them to
                        # Spoonacular's nutrition parser to get real values.
                        if kcal is None:
                            nutrition = fetch_nutrition_for_meal(meal)
                            kcal      = nutrition["kcal"]
                            protein_g = nutrition["protein_g"]
                            carbs_g   = nutrition["carbs_g"]
                            fat_g     = nutrition["fat_g"]

                        execute(
                            """INSERT INTO recipes
                               (title, kcal_per_serv, protein_g, carbs_g, fat_g)
                               VALUES (?, ?, ?, ?, ?)""",
                            (meal_title, kcal, protein_g, carbs_g, fat_g),
                        )
                        new_row = query_df(
                            "SELECT id FROM recipes WHERE title = ? ORDER BY id DESC LIMIT 1",
                            (meal_title,),
                        )
                        if not new_row.empty:
                            local_id = int(new_row.iloc[0]["id"])
                    else:
                        # Recipe already exists — update nutrition if missing.
                        kcal      = meal.get("kcal_per_serv")
                        protein_g = meal.get("protein_g")
                        carbs_g   = meal.get("carbs_g")
                        fat_g     = meal.get("fat_g")

                        # If still missing (TheMealDB recipe), fetch via Spoonacular
                        if kcal is None:
                            nutrition = fetch_nutrition_for_meal(meal)
                            kcal      = nutrition["kcal"]
                            protein_g = nutrition["protein_g"]
                            carbs_g   = nutrition["carbs_g"]
                            fat_g     = nutrition["fat_g"]

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

                    # Toast persists across the rerun — much more visible than st.success
                    st.toast(f"✅ '{meal_title}' added to Meal Planner!", icon="🍽️")
                    if kcal is None:
                        st.toast(
                            "⚠️ Calorie non trovate per questa ricetta. "
                            "Inseriscile manualmente in Nutrition Analytics.",
                            icon="ℹ️",
                        )
                    st.rerun()


# ── Search tab ────────────────────────────────────────────────────────────────

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
        diet = profile.get("diet", "omnivore")
        allergies = profile.get("allergies", [])

        veg = diet in ("vegetarian", "vegan")
        vgn = diet == "vegan"
        gf = "gluten" in allergies
        df = "lactose" in allergies

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
            recipes_df = pd.DataFrame(LOCAL_RECIPES).rename(
                columns={"name": "title"}
            )

            rec = Recommender(recipes_df)
            top_results = results[:10]

            ingredient_lists = [
                extract_ingredients(m) for m in top_results
            ]

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

            scored_results = sorted(
                zip(top_results, raw_scores),
                key=lambda pair: (
                    (0, -(pair[1] or 0))
                    if pair[1] is not None
                    else (1, 0)
                ),
            )

            any_scored = any(s is not None for _, s in scored_results)

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

            user_pantry = get_pantry()

            # ── FIX: pass card_key with index so each card has unique widget keys
            for idx, (meal, score) in enumerate(scored_results):
                render_meal_card(
                    meal,
                    ml_score=score,
                    pantry=pantry_pct(meal, user_pantry),
                    card_key=f"search_{idx}",
                )


# ── Cuisine tab ───────────────────────────────────────────────────────────────


def fetch_cuisine_recipes(cuisine: str, limit: int = 10) -> list[dict]:
    """
    Fetch full recipe details for a given cuisine using TheMealDB.

    filter_by_cuisine() returns stubs (id + thumbnail only).
    We then call get_meal_by_id() for each to get instructions,
    ingredients, area, and category — everything render_meal_card() needs.
    Results are cached inside each called function so this is fast.
    """
    stubs = filter_by_cuisine(cuisine)[:limit]
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
        # ── World Map ──────────────────────────────────────────────────────
        st.subheader("🌍 Bites Across Borders")
        st.markdown("- Click on a country on the map to explore its traditional recipes")
        st.markdown("- Not sure where a country is? You can also use the selector below!")

        from streamlit_plotly_events import plotly_events

        # Render the map and capture clicks. plotly_events returns a list of
        # dicts — one per clicked point — each containing the customdata we
        # embedded (the ISO-3 code).
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
        legend_cols = st.columns(len(CONTINENT_DATA) - 1)  # skip Antarctica
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

        # plotly_events returns pointIndex relative to the clicked trace.
        # curveNumber tells us which trace was clicked:
        #   0 → grey trace (countries without TheMealDB recipes) — ignore
        #   1 → coloured trace (countries with TheMealDB recipes) — use it
        # The coloured trace contains only TheMealDB-linked ISOs in the same
        # order as colored_locs (built inside build_figure).
        all_locations = list(ISO_CONTINENT.keys())
        cuisine_isos  = set(ISO_TO_CUISINE.keys())
        colored_locs  = [iso for iso in all_locations if iso in cuisine_isos]

        if clicked_points:
            curve_number = clicked_points[0].get("curveNumber", 0)
            point_index  = clicked_points[0].get("pointIndex")
            # Only act on clicks on the coloured (TheMealDB) trace
            if curve_number == 1 and point_index is not None and point_index < len(colored_locs):
                iso = colored_locs[point_index]
                if iso in ISO_TO_CUISINE:
                    st.session_state["map_selected_iso"] = iso

        selected_iso = st.session_state.get("map_selected_iso")
        active_cuisine = ISO_TO_CUISINE.get(selected_iso) if selected_iso else None
        selected_country_name = ISO_NAME.get(selected_iso) if selected_iso else None

        # ── Also allow manual fallback via selectbox ──────────────────────
        CUISINE_TO_ISO = {v: k for k, v in ISO_TO_CUISINE.items()}
        cuisine_options = ["— click the map or choose here —"] + sorted(ISO_TO_CUISINE.values())
        default_idx = 0
        if active_cuisine and active_cuisine in cuisine_options:
            default_idx = cuisine_options.index(active_cuisine)

        manual_choice = st.selectbox(
            "Or pick a cuisine manually:",
            options=cuisine_options,
            index=default_idx,
            key="cuisine_selectbox",
        )

        if manual_choice != "— click the map or choose here —":
            active_cuisine = manual_choice
            selected_iso = CUISINE_TO_ISO.get(active_cuisine)
            selected_country_name = ISO_NAME.get(selected_iso, active_cuisine)
            st.session_state["map_selected_iso"] = selected_iso

        # ── Show results ──────────────────────────────────────────────────
        if active_cuisine:
            st.subheader(f"🍽️ Recipes from {selected_country_name}")

            with st.spinner(f"Loading {active_cuisine} recipes…"):
                cuisine_results = fetch_cuisine_recipes(active_cuisine)

            if not cuisine_results:
                empty_state(f"No recipes found for {active_cuisine} — try another country.")
            else:
                user_pantry = get_pantry()
                # ── FIX: pass card_key with index so each card has unique widget keys
                for idx, meal in enumerate(cuisine_results[:10]):
                    render_meal_card(
                        meal,
                        pantry=pantry_pct(meal, user_pantry),
                        card_key=f"cuisine_{idx}",
                    )
        else:
            st.info("👆 Click a country on the map to explore its recipes.")
