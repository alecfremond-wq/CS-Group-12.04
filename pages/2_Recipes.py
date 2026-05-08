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
    list_cuisines,
    search_recipes_by_name,
    search_spoonacular,
)
from src.data.database import query_df, execute
from src.models.recommender import Recommender
from src.utils.session import init_session_state, require_profile

init_session_state()

profile = require_profile()

page_header("🍲 Recipes", "Search recipes or browse by cuisine.")

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


def build_figure() -> go.Figure:
    """Build the Plotly choropleth world map coloured by continent."""
    locations = list(ISO_CONTINENT.keys())
    continents = [ISO_CONTINENT[c] for c in locations]
    continent_list = list(CONTINENT_DATA.keys())
    colors_list = [CONTINENT_DATA[c]["color"] for c in continent_list]

    z_values = [continent_list.index(c) for c in continents]

    n = len(continent_list)
    colorscale = []
    for i, col in enumerate(colors_list):
        colorscale.append([i / n, col])
        colorscale.append([(i + 1) / n, col])

    hover_texts = []
    for iso in locations:
        cont = ISO_CONTINENT.get(iso, "")
        name = ISO_NAME.get(iso, iso)
        color = CONTINENT_DATA.get(cont, {}).get("color", "#999")
        hover_texts.append(
            f"<b style='font-size:14px'>{name}</b><br>"
            f"<span style='color:{color}'>&#9632;</span> {cont}"
        )

    trace = go.Choropleth(
        locations=locations,
        locationmode="ISO-3",
        z=z_values,
        text=hover_texts,
        hovertemplate="%{text}<extra></extra>",
        colorscale=colorscale,
        zmin=0,
        zmax=n,
        showscale=False,
        marker_line_color="white",
        marker_line_width=0.8,
    )

    fig = go.Figure(data=[trace])
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
) -> None:
    """Draw a single recipe card."""
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

            with st.expander("Instructions"):
                st.write(meal.get("strInstructions", ""))

            already_saved = any(
                isinstance(w, dict) and w.get("title") == meal_title
                for w in st.session_state.get("wishlist", [])
            )

            if already_saved:
                st.caption("❤️ Saved to wishlist")
            else:
                if st.button("❤️ Save to wishlist", key=f"wish_{meal_title}"):
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

            user_id = st.session_state.get("user_id")
            local_id = local_title_to_id.get(meal_title.lower())
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
                st.caption("🍽️ Added to Meal Planner")

                if st.button(
                    "❌ Remove from Meal Planner",
                    key=f"remove_planner_{meal_title}",
                ):
                    execute(
                        """
                        DELETE FROM planner_pool
                        WHERE user_id = ? AND recipe_id = ?
                        """,
                        (user_id, local_id),
                    )

                    st.rerun()

            else:
                if st.button(
                    "➕ Add to Meal Planner",
                    key=f"planner_{meal_title}",
                ):

                    if local_id is None:
                        execute(
                            """
                            INSERT INTO recipes (title)
                            VALUES (?)
                            """,
                            (meal_title,),
                        )

                        new_row = query_df(
                            """
                            SELECT id FROM recipes
                            WHERE title = ?
                            ORDER BY id DESC LIMIT 1
                            """,
                            (meal_title,),
                        )

                        if not new_row.empty:
                            local_id = int(new_row.iloc[0]["id"])

                    if local_id:
                        execute(
                            """
                            INSERT OR IGNORE INTO planner_pool (user_id, recipe_id)
                            VALUES (?, ?)
                            """,
                            (user_id, local_id),
                        )

                    st.success("Added to Meal Planner 🍽️")
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

            for meal, score in scored_results:
                render_meal_card(
                    meal,
                    ml_score=score,
                    pantry=pantry_pct(meal, user_pantry),
                )


# ── Cuisine tab ───────────────────────────────────────────────────────────────

with tab_cuisine:
    cuisines = list_cuisines()

    if not cuisines:
        empty_state("Cuisine list couldn't be loaded — check your internet.")
    else:
        # ── World Map ──────────────────────────────────────────────────────
        st.subheader("🌍 Bites Across Borders")
        st.caption("A journey through international food traditions")
        st.markdown("- Click on a country on the map to explore its traditional recipes")
        st.markdown("- Not sure where a country is? You can also search it manuelly using the selector below!")
        st.plotly_chart(
            build_figure(),
            use_container_width=True,
            config={
                "scrollZoom": False,
                "displayModeBar": False,
                "staticPlot": False,
            },
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
        choice = st.selectbox("Cuisine", cuisines)
        st.caption(f"(Owner: render recipes for cuisine = **{choice}**)")



