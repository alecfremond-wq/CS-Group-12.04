"""
Recipes — search and browse recipes (API + DB).
Owner: <assign on Apr 22>
Grading coverage:
    * Req. 2 (API — TheMealDB + Spoonacular)
    * Req. 4 (user interaction — search, filter, add-to-wishlist)
    * Req. 5 (ML — search results ranked by taste profile when available)
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from recipes_data import RECIPES as LOCAL_RECIPES
from src.components.ui import empty_state, page_header
from src.data.api_client import (
    fetch_cuisine_meals,
    fetch_nutrition_for_meal,
    fetch_kcal_for_title,
    list_cuisines,
    search_recipes_by_name,
)
from src.data.database import query_df, execute
from src.models.recommender import Recommender
from src.utils.session import init_session_state, require_profile


# ── Init (no DB calls here) ───────────────────────────────────────────────────

init_session_state()
profile = require_profile()

# ── Deferred rerun + toast ────────────────────────────────────────────────────
# NEVER call st.rerun() or st.toast() inside a button callback — it corrupts
# the WebSocket frame mid-render ("Cached ForwardMsg MISS" crash).
# Instead, buttons write to session state; we act on them here at the very
# top of the next clean render cycle.
_pending_toast = st.session_state.pop("_toast", None)
if _pending_toast:
    st.toast(_pending_toast[0], icon=_pending_toast[1])

if st.session_state.pop("_needs_rerun", False):
    st.rerun()

page_header("🍲 Recipes", "Search recipes or browse by cuisine.")

local_title_to_id: dict[str, int] = {r["name"].lower(): r["id"] for r in LOCAL_RECIPES}


# ── Single DB read per render: load planner + pantry once ────────────────────
# Previously render_meal_card() ran 3 separate query_df() calls per card
# (×10 cards = 30 DB round-trips per render). Now we load everything we
# need in two queries up front and pass it down as plain Python sets/dicts.

_user_id: int | None = st.session_state.get("user_id")


@st.cache_data(ttl=0)   # no TTL — always fresh, but only called once per render
def _load_planner_ids(user_id: int) -> set[int]:
    """Return the set of recipe_ids currently in this user's planner pool."""
    if not user_id:
        return set()
    try:
        df = query_df(
            "SELECT recipe_id FROM planner_pool WHERE user_id = ?", (user_id,)
        )
        return set(df["recipe_id"].tolist()) if not df.empty else set()
    except Exception:
        return set()


@st.cache_data(ttl=0)
def _load_pantry_names(user_id: int) -> set[str]:
    """Return ingredient names (lowercase) in this user's pantry."""
    if not user_id:
        return set()
    try:
        df = query_df(
            """
            SELECT i.name FROM pantry p
            JOIN ingredients i ON p.ingredient_id = i.id
            WHERE p.user_id = ? AND p.quantity > 0
            """,
            (user_id,),
        )
        return set(df["name"].str.lower().tolist()) if not df.empty else set()
    except Exception:
        return set()


@st.cache_data(ttl=0)
def _load_planner_meals(user_id: int) -> list[dict]:
    """Return title+id rows for the planner banner."""
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
        return df.to_dict("records") if not df.empty else []
    except Exception:
        return []


# We deliberately use ttl=0 so values are always current, but because
# Streamlit only executes each cached function once per script run (same
# args → same cached result within that run), there's no extra DB hit.
_planner_ids: set[int]    = _load_planner_ids(_user_id)   if _user_id else set()
_pantry_names: set[str]   = _load_pantry_names(_user_id)  if _user_id else set()
_planner_meals: list[dict] = _load_planner_meals(_user_id) if _user_id else []


# ── Planner banner ────────────────────────────────────────────────────────────

def show_my_planner_banner() -> None:
    if not _user_id:
        return
    count = len(_planner_meals)
    label = "dish" if count == 1 else "dishes"

    with st.expander(
        f"🍽️ My Meal Planner  ·  **{count} {label} saved**",
        expanded=count > 0,
    ):
        if not _planner_meals:
            st.info("You haven't saved any dishes to the Meal Planner yet.")
            return

        cols = st.columns(3)
        for idx, meal in enumerate(_planner_meals):
            with cols[idx % 3]:
                col_text, col_btn = st.columns([3, 1])
                with col_text:
                    st.markdown(f"✅ **{meal['title']}**")
                with col_btn:
                    if st.button("✕", key=f"banner_remove_{meal['recipe_id']}",
                                 help="Remove from Meal Planner"):
                        execute(
                            "DELETE FROM planner_pool WHERE user_id = ? AND recipe_id = ?",
                            (_user_id, meal["recipe_id"]),
                        )
                        execute(
                            "DELETE FROM meal_plan WHERE user_id = ? AND recipe_id = ?",
                            (_user_id, meal["recipe_id"]),
                        )
                        st.session_state["_toast"] = (
                            f"❌ '{meal['title']}' removed from Meal Planner", "🗑️"
                        )
                        st.session_state["_needs_rerun"] = True

        st.caption("Go to the **Meal Planner** page to schedule them across the week.")


show_my_planner_banner()


# ── Map data ──────────────────────────────────────────────────────────────────

CONTINENT_DATA = {
    "Africa":        {"color": "#E07B39", "countries": ["Algeria","Angola","Benin","Botswana","Burkina Faso","Burundi","Cameroon","Cape Verde","Central African Rep.","Chad","Comoros","DR Congo","Rep. Congo","Djibouti","Egypt","Equatorial Guinea","Eritrea","Eswatini","Ethiopia","Gabon","Gambia","Ghana","Guinea","Guinea-Bissau","Ivory Coast","Kenya","Lesotho","Liberia","Libya","Madagascar","Malawi","Mali","Mauritania","Mauritius","Morocco","Mozambique","Namibia","Niger","Nigeria","Rwanda","São Tomé & Príncipe","Senegal","Sierra Leone","Somalia","South Africa","South Sudan","Sudan","Tanzania","Togo","Tunisia","Uganda","Zambia","Zimbabwe"]},
    "Asia":          {"color": "#4A90D9", "countries": ["Afghanistan","Armenia","Azerbaijan","Bahrain","Bangladesh","Bhutan","Brunei","Cambodia","China","Cyprus","Georgia","India","Indonesia","Iran","Iraq","Israel","Japan","Jordan","Kazakhstan","Kuwait","Kyrgyzstan","Laos","Lebanon","Malaysia","Maldives","Mongolia","Myanmar","Nepal","North Korea","Oman","Pakistan","Palestine","Philippines","Qatar","Saudi Arabia","Singapore","South Korea","Sri Lanka","Syria","Taiwan","Tajikistan","Thailand","Timor-Leste","Turkey","Turkmenistan","UAE","Uzbekistan","Vietnam","Yemen"]},
    "Europe":        {"color": "#5BAD6F", "countries": ["Albania","Andorra","Austria","Belarus","Belgium","Bosnia & Herz.","Bulgaria","Croatia","Czech Republic","Denmark","Estonia","Finland","France","Germany","Greece","Hungary","Iceland","Ireland","Italy","Kosovo","Latvia","Liechtenstein","Lithuania","Luxembourg","Malta","Moldova","Monaco","Montenegro","Netherlands","North Macedonia","Norway","Poland","Portugal","Romania","Russia","San Marino","Serbia","Slovakia","Slovenia","Spain","Sweden","Switzerland","Ukraine","United Kingdom","Vatican City"]},
    "North America": {"color": "#9B59B6", "countries": ["Antigua & Barbuda","Bahamas","Barbados","Belize","Canada","Costa Rica","Cuba","Dominica","Dominican Republic","El Salvador","Grenada","Guatemala","Haiti","Honduras","Jamaica","Mexico","Nicaragua","Panama","St Kitts & Nevis","St Lucia","St Vincent & the Grenadines","Trinidad & Tobago","United States"]},
    "South America": {"color": "#E74C3C", "countries": ["Argentina","Bolivia","Brazil","Chile","Colombia","Ecuador","Guyana","Paraguay","Peru","Suriname","Uruguay","Venezuela"]},
    "Oceania":       {"color": "#F1C40F", "countries": ["Australia","Fiji","Kiribati","Marshall Islands","Micronesia","Nauru","New Zealand","Palau","Papua New Guinea","Samoa","Solomon Islands","Tonga","Tuvalu","Vanuatu"]},
    "Antarctica":    {"color": "#BDC3C7", "countries": ["Antarctica (no sovereign countries)"]},
}

ISO_CONTINENT = {
    "DZA":"Africa","AGO":"Africa","BEN":"Africa","BWA":"Africa","BFA":"Africa","BDI":"Africa","CPV":"Africa","CMR":"Africa","CAF":"Africa","TCD":"Africa","COM":"Africa","COD":"Africa","COG":"Africa","DJI":"Africa","EGY":"Africa","GNQ":"Africa","ERI":"Africa","SWZ":"Africa","ETH":"Africa","GAB":"Africa","GMB":"Africa","GHA":"Africa","GIN":"Africa","GNB":"Africa","CIV":"Africa","KEN":"Africa","LSO":"Africa","LBR":"Africa","LBY":"Africa","MDG":"Africa","MWI":"Africa","MLI":"Africa","MRT":"Africa","MUS":"Africa","MAR":"Africa","MOZ":"Africa","NAM":"Africa","NER":"Africa","NGA":"Africa","RWA":"Africa","STP":"Africa","SEN":"Africa","SLE":"Africa","SOM":"Africa","ZAF":"Africa","SSD":"Africa","SDN":"Africa","TZA":"Africa","TGO":"Africa","TUN":"Africa","UGA":"Africa","ZMB":"Africa","ZWE":"Africa",
    "AFG":"Asia","ARM":"Asia","AZE":"Asia","BHR":"Asia","BGD":"Asia","BTN":"Asia","BRN":"Asia","KHM":"Asia","CHN":"Asia","CYP":"Asia","GEO":"Asia","IND":"Asia","IDN":"Asia","IRN":"Asia","IRQ":"Asia","ISR":"Asia","JPN":"Asia","JOR":"Asia","KAZ":"Asia","KWT":"Asia","KGZ":"Asia","LAO":"Asia","LBN":"Asia","MYS":"Asia","MDV":"Asia","MNG":"Asia","MMR":"Asia","NPL":"Asia","PRK":"Asia","OMN":"Asia","PAK":"Asia","PSE":"Asia","PHL":"Asia","QAT":"Asia","SAU":"Asia","SGP":"Asia","KOR":"Asia","LKA":"Asia","SYR":"Asia","TWN":"Asia","TJK":"Asia","THA":"Asia","TLS":"Asia","TUR":"Asia","TKM":"Asia","ARE":"Asia","UZB":"Asia","VNM":"Asia","YEM":"Asia",
    "ALB":"Europe","AND":"Europe","AUT":"Europe","BLR":"Europe","BEL":"Europe","BIH":"Europe","BGR":"Europe","HRV":"Europe","CZE":"Europe","DNK":"Europe","EST":"Europe","FIN":"Europe","FRA":"Europe","DEU":"Europe","GRC":"Europe","HUN":"Europe","ISL":"Europe","IRL":"Europe","ITA":"Europe","XKX":"Europe","LVA":"Europe","LIE":"Europe","LTU":"Europe","LUX":"Europe","MLT":"Europe","MDA":"Europe","MCO":"Europe","MNE":"Europe","NLD":"Europe","MKD":"Europe","NOR":"Europe","POL":"Europe","PRT":"Europe","ROU":"Europe","RUS":"Europe","SMR":"Europe","SRB":"Europe","SVK":"Europe","SVN":"Europe","ESP":"Europe","SWE":"Europe","CHE":"Europe","UKR":"Europe","GBR":"Europe","VAT":"Europe",
    "ATG":"North America","BHS":"North America","BRB":"North America","BLZ":"North America","CAN":"North America","CRI":"North America","CUB":"North America","DMA":"North America","DOM":"North America","SLV":"North America","GRD":"North America","GTM":"North America","HTI":"North America","HND":"North America","JAM":"North America","MEX":"North America","NIC":"North America","PAN":"North America","KNA":"North America","LCA":"North America","VCT":"North America","TTO":"North America","USA":"North America",
    "ARG":"South America","BOL":"South America","BRA":"South America","CHL":"South America","COL":"South America","ECU":"South America","GUY":"South America","PRY":"South America","PER":"South America","SUR":"South America","URY":"South America","VEN":"South America",
    "AUS":"Oceania","FJI":"Oceania","KIR":"Oceania","MHL":"Oceania","FSM":"Oceania","NRU":"Oceania","NZL":"Oceania","PLW":"Oceania","PNG":"Oceania","WSM":"Oceania","SLB":"Oceania","TON":"Oceania","TUV":"Oceania","VUT":"Oceania",
    "ATA":"Antarctica",
}

ISO_NAME = {
    "DZA":"Algeria","AGO":"Angola","BEN":"Benin","BWA":"Botswana","BFA":"Burkina Faso","BDI":"Burundi","CPV":"Cape Verde","CMR":"Cameroon","CAF":"Central African Rep.","TCD":"Chad","COM":"Comoros","COD":"DR Congo","COG":"Rep. Congo","DJI":"Djibouti","EGY":"Egypt","GNQ":"Equatorial Guinea","ERI":"Eritrea","SWZ":"Eswatini","ETH":"Ethiopia","GAB":"Gabon","GMB":"Gambia","GHA":"Ghana","GIN":"Guinea","GNB":"Guinea-Bissau","CIV":"Ivory Coast","KEN":"Kenya","LSO":"Lesotho","LBR":"Liberia","LBY":"Libya","MDG":"Madagascar","MWI":"Malawi","MLI":"Mali","MRT":"Mauritania","MUS":"Mauritius","MAR":"Morocco","MOZ":"Mozambique","NAM":"Namibia","NER":"Niger","NGA":"Nigeria","RWA":"Rwanda","STP":"Sao Tome & Principe","SEN":"Senegal","SLE":"Sierra Leone","SOM":"Somalia","ZAF":"South Africa","SSD":"South Sudan","SDN":"Sudan","TZA":"Tanzania","TGO":"Togo","TUN":"Tunisia","UGA":"Uganda","ZMB":"Zambia","ZWE":"Zimbabwe",
    "AFG":"Afghanistan","ARM":"Armenia","AZE":"Azerbaijan","BHR":"Bahrain","BGD":"Bangladesh","BTN":"Bhutan","BRN":"Brunei","KHM":"Cambodia","CHN":"China","CYP":"Cyprus","GEO":"Georgia","IND":"India","IDN":"Indonesia","IRN":"Iran","IRQ":"Iraq","ISR":"Israel","JPN":"Japan","JOR":"Jordan","KAZ":"Kazakhstan","KWT":"Kuwait","KGZ":"Kyrgyzstan","LAO":"Laos","LBN":"Lebanon","MYS":"Malaysia","MDV":"Maldives","MNG":"Mongolia","MMR":"Myanmar","NPL":"Nepal","PRK":"North Korea","OMN":"Oman","PAK":"Pakistan","PSE":"Palestine","PHL":"Philippines","QAT":"Qatar","SAU":"Saudi Arabia","SGP":"Singapore","KOR":"South Korea","LKA":"Sri Lanka","SYR":"Syria","TWN":"Taiwan","TJK":"Tajikistan","THA":"Thailand","TLS":"Timor-Leste","TUR":"Turkey","TKM":"Turkmenistan","ARE":"UAE","UZB":"Uzbekistan","VNM":"Vietnam","YEM":"Yemen",
    "ALB":"Albania","AND":"Andorra","AUT":"Austria","BLR":"Belarus","BEL":"Belgium","BIH":"Bosnia & Herz.","BGR":"Bulgaria","HRV":"Croatia","CZE":"Czech Republic","DNK":"Denmark","EST":"Estonia","FIN":"Finland","FRA":"France","DEU":"Germany","GRC":"Greece","HUN":"Hungary","ISL":"Iceland","IRL":"Ireland","ITA":"Italy","XKX":"Kosovo","LVA":"Latvia","LIE":"Liechtenstein","LTU":"Lithuania","LUX":"Luxembourg","MLT":"Malta","MDA":"Moldova","MCO":"Monaco","MNE":"Montenegro","NLD":"Netherlands","MKD":"North Macedonia","NOR":"Norway","POL":"Poland","PRT":"Portugal","ROU":"Romania","RUS":"Russia","SMR":"San Marino","SRB":"Serbia","SVK":"Slovakia","SVN":"Slovenia","ESP":"Spain","SWE":"Sweden","CHE":"Switzerland","UKR":"Ukraine","GBR":"United Kingdom","VAT":"Vatican City",
    "ATG":"Antigua & Barbuda","BHS":"Bahamas","BRB":"Barbados","BLZ":"Belize","CAN":"Canada","CRI":"Costa Rica","CUB":"Cuba","DMA":"Dominica","DOM":"Dominican Republic","SLV":"El Salvador","GRD":"Grenada","GTM":"Guatemala","HTI":"Haiti","HND":"Honduras","JAM":"Jamaica","MEX":"Mexico","NIC":"Nicaragua","PAN":"Panama","KNA":"St Kitts & Nevis","LCA":"St Lucia","VCT":"St Vincent & Gren.","TTO":"Trinidad & Tobago","USA":"United States",
    "ARG":"Argentina","BOL":"Bolivia","BRA":"Brazil","CHL":"Chile","COL":"Colombia","ECU":"Ecuador","GUY":"Guyana","PRY":"Paraguay","PER":"Peru","SUR":"Suriname","URY":"Uruguay","VEN":"Venezuela",
    "AUS":"Australia","FJI":"Fiji","KIR":"Kiribati","MHL":"Marshall Islands","FSM":"Micronesia","NRU":"Nauru","NZL":"New Zealand","PLW":"Palau","PNG":"Papua New Guinea","WSM":"Samoa","SLB":"Solomon Islands","TON":"Tonga","TUV":"Tuvalu","VUT":"Vanuatu",
    "ATA":"Antarctica",
}

ISO_TO_CUISINE = {
    "CAN":"Canadian",  "CHN":"Chinese",    "EGY":"Egyptian",  "FRA":"French",
    "GRC":"Greek",     "IND":"Indian",     "IRL":"Irish",     "ITA":"Italian",
    "JAM":"Jamaican",  "JPN":"Japanese",   "KEN":"Kenyan",    "MYS":"Malaysian",
    "MEX":"Mexican",   "MAR":"Moroccan",   "NLD":"Dutch",     "POL":"Polish",
    "PRT":"Portuguese","RUS":"Russian",    "ESP":"Spanish",   "THA":"Thai",
    "TUN":"Tunisian",  "TUR":"Turkish",    "GBR":"British",   "USA":"American",
    "VNM":"Vietnamese","PHL":"Filipino",   "HRV":"Croatian",  "URY":"Uruguayan",
}


@st.cache_data(ttl=24 * 60 * 60)
def build_figure() -> go.Figure:
    """Build the world-map choropleth. Cached for 24 h — it never changes."""
    all_locations  = list(ISO_CONTINENT.keys())
    cuisine_isos   = set(ISO_TO_CUISINE.keys())
    colored_locs   = [iso for iso in all_locations if iso in cuisine_isos]
    continent_list = list(CONTINENT_DATA.keys())
    colors_list    = [CONTINENT_DATA[c]["color"] for c in continent_list]
    n = len(continent_list)

    colorscale = []
    for i, col in enumerate(colors_list):
        colorscale += [[i / n, col], [(i + 1) / n, col]]

    colored_hover = []
    for iso in colored_locs:
        cont  = ISO_CONTINENT.get(iso, "")
        color = CONTINENT_DATA.get(cont, {}).get("color", "#999")
        colored_hover.append(
            f"<b style='font-size:14px'>{ISO_NAME.get(iso,iso)}</b><br>"
            f"<span style='color:{color}'>&#9632;</span> {cont}<br>"
            f"<i style='color:#F1C40F'>🍽️ {ISO_TO_CUISINE.get(iso,'')} cuisine — click to explore!</i>"
        )

    grey_locs = [iso for iso in all_locations if iso not in cuisine_isos]

    fig = go.Figure(data=[
        go.Choropleth(
            locations=grey_locs, locationmode="ISO-3",
            z=[0]*len(grey_locs),
            text=[f"<b>{ISO_NAME.get(i,i)}</b><br><span style='color:#999'>No recipes available</span>" for i in grey_locs],
            customdata=grey_locs, hovertemplate="%{text}<extra></extra>",
            colorscale=[[0,"#C8C8C8"],[1,"#C8C8C8"]], zmin=0, zmax=1,
            showscale=False, marker_line_color="white", marker_line_width=0.5, name="",
        ),
        go.Choropleth(
            locations=colored_locs, locationmode="ISO-3",
            z=[continent_list.index(ISO_CONTINENT[iso]) for iso in colored_locs],
            text=colored_hover, customdata=colored_locs,
            hovertemplate="%{text}<extra></extra>",
            colorscale=colorscale, zmin=0, zmax=n,
            showscale=False, marker_line_color="white", marker_line_width=0.8, name="",
        ),
    ])
    fig.update_layout(
        geo=dict(
            showframe=False, showcoastlines=True, coastlinecolor="white",
            showland=True, landcolor="#D5D8DC",
            showocean=True, oceancolor="#AED6F1",
            showlakes=True, lakecolor="#AED6F1", showrivers=False,
            projection_type="natural earth", bgcolor="rgba(0,0,0,0)",
            lataxis_range=[-60, 85], lonaxis_range=[-180, 180],
            showsubunits=False, showcountries=False,
        ),
        paper_bgcolor="white",
        margin=dict(l=0, r=0, t=10, b=10),
        hoverlabel=dict(bgcolor="#2C3E50", font=dict(size=12, color="white", family="monospace"), bordercolor="#AAA", align="left"),
        dragmode=False, annotations=[],
    )
    return fig


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_ingredients(meal: dict) -> list[str]:
    if meal.get("_ingredients"):
        return [i.strip() for i in meal["_ingredients"] if i.strip()]
    return [
        meal[f"strIngredient{i}"].strip()
        for i in range(1, 21)
        if (meal.get(f"strIngredient{i}") or "").strip()
    ]


def pantry_pct(meal: dict) -> float | None:
    if not _pantry_names:
        return None
    names = [i.lower() for i in extract_ingredients(meal)]
    return (sum(1 for n in names if n in _pantry_names) / len(names)) if names else None


def resolve_local_id(meal_title: str) -> int | None:
    """Look up recipe id in local data first, then DB — no per-card query."""
    lid = local_title_to_id.get(meal_title.lower())
    if lid is not None:
        return lid
    try:
        df = query_df(
            "SELECT id FROM recipes WHERE LOWER(title) = LOWER(?) LIMIT 1",
            (meal_title,),
        )
        return int(df.iloc[0]["id"]) if not df.empty else None
    except Exception:
        return None


# ── Taste profile ─────────────────────────────────────────────────────────────

wishlist = st.session_state.get("wishlist", [])
wishlist_ids = [w["local_id"] for w in wishlist if isinstance(w, dict) and w.get("local_id") is not None]
liked_ingredients = [w["ingredients"] for w in wishlist if isinstance(w, dict) and w.get("ingredients")]
history_df = pd.DataFrame(st.session_state.get("cooking_history", []))
has_taste_profile = (
    bool(wishlist_ids) or bool(liked_ingredients)
    or (not history_df.empty and "rating" in history_df.columns and (history_df["rating"] >= 4).any())
)


# ── Recipe card ───────────────────────────────────────────────────────────────

def render_meal_card(meal: dict, ml_score: float | None = None, card_key: str = "") -> None:
    meal_title   = meal["strMeal"]
    local_id     = resolve_local_id(meal_title)
    in_planner   = local_id in _planner_ids if local_id else False

    with st.container(border=True):
        col_img, col_meta = st.columns([1, 3])

        with col_img:
            st.image(meal.get("strMealThumb"), use_container_width=True)

        with col_meta:
            st.subheader(meal_title)
            st.caption(f"{meal.get('strArea','—')} · {meal.get('strCategory','—')}")

            if ml_score is not None and not pd.isna(ml_score):
                st.progress(float(ml_score), text=f"Match score: {ml_score:.0%}")

            pct = pantry_pct(meal)
            if pct is not None:
                if pct > 0.6:
                    st.success("🟢 Pantry-friendly")
                elif pct > 0.3:
                    st.warning("🟡 Partially available")

            with st.expander("Instructions"):
                st.write(meal.get("strInstructions", ""))

            # ── Wishlist ──────────────────────────────────────────────────
            already_saved = any(
                isinstance(w, dict) and w.get("title") == meal_title
                for w in st.session_state.get("wishlist", [])
            )
            if already_saved:
                st.caption("❤️ Saved to wishlist")
            else:
                if st.button("❤️ Save to wishlist", key=f"{card_key}_wish_{meal_title}"):
                    st.session_state["wishlist"].append({
                        "title": meal_title, "image": meal.get("strMealThumb"),
                        "area": meal.get("strArea", ""), "local_id": local_id,
                        "ingredients": extract_ingredients(meal),
                    })
                    st.session_state["_needs_rerun"] = True

            # ── Meal Planner ──────────────────────────────────────────────
            if in_planner:
                st.success("🍽️ Already in your Meal Planner!")
                if st.button("❌ Remove from Meal Planner", key=f"{card_key}_rm_{meal_title}"):
                    execute("DELETE FROM planner_pool WHERE user_id=? AND recipe_id=?", (_user_id, local_id))
                    execute("DELETE FROM meal_plan WHERE user_id=? AND recipe_id=?",    (_user_id, local_id))
                    st.session_state["_toast"]       = (f"'{meal_title}' removed 🗑️", "❌")
                    st.session_state["_needs_rerun"] = True
            else:
                if st.button("➕ Add to Meal Planner", key=f"{card_key}_add_{meal_title}"):
                    resolved_id = local_id

                    if resolved_id is None:
                        # Recipe not in DB — fetch nutrition then insert
                        n = fetch_nutrition_for_meal(meal)
                        execute(
                            "INSERT INTO recipes (title, kcal_per_serv, protein_g, carbs_g, fat_g) VALUES (?,?,?,?,?)",
                            (meal_title, n["kcal"], n["protein_g"], n["carbs_g"], n["fat_g"]),
                        )
                        row = query_df("SELECT id FROM recipes WHERE title=? ORDER BY id DESC LIMIT 1", (meal_title,))
                        if not row.empty:
                            resolved_id = int(row.iloc[0]["id"])
                        kcal = n["kcal"]
                    else:
                        kcal = meal.get("kcal_per_serv")
                        if kcal is None:
                            n    = fetch_nutrition_for_meal(meal)
                            kcal = n["kcal"]
                            if kcal is not None:
                                execute(
                                    "UPDATE recipes SET kcal_per_serv=?, protein_g=?, carbs_g=?, fat_g=? WHERE id=?",
                                    (kcal, n["protein_g"], n["carbs_g"], n["fat_g"], resolved_id),
                                )

                    if resolved_id:
                        execute(
                            "INSERT OR IGNORE INTO planner_pool (user_id, recipe_id) VALUES (?,?)",
                            (_user_id, resolved_id),
                        )

                    if kcal is None:
                        st.session_state["_toast"] = (
                            "⚠️ Calories not found — enter them manually in Nutrition Analytics.", "ℹ️"
                        )
                    else:
                        st.session_state["_toast"] = (f"✅ '{meal_title}' added to Meal Planner!", "🍽️")
                    st.session_state["_needs_rerun"] = True


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_search, tab_cuisine = st.tabs(["🔎 Search", "🌍 Browse by cuisine"])


# ── Search tab ────────────────────────────────────────────────────────────────

with tab_search:
    st.subheader("🔎 Hungry? Let's find something delicious!")
    st.markdown("- Search for any dish by name")
    st.markdown("- Get info on the dish and how to make it")
    st.markdown("- Add it to your Meal Planner or Wishlist for later")

    query = st.text_input("What would you like to cook?", placeholder="e.g. pasta, curry…")

    if query:
        results = search_recipes_by_name(query)   # cached 1 h

        if not results:
            empty_state("No recipes found — try another word.")
        else:
            recipes_df  = pd.DataFrame(LOCAL_RECIPES).rename(columns={"name": "title"})
            rec         = Recommender(recipes_df)
            top_results = results[:10]
            ing_lists   = [extract_ingredients(m) for m in top_results]

            raw_scores = (
                rec.score_external(ing_lists, history_df, wishlist_ids, liked_ingredients)
                if has_taste_profile else [None] * len(top_results)
            )

            scored = sorted(
                zip(top_results, raw_scores),
                key=lambda p: (0, -(p[1] or 0)) if p[1] is not None else (1, 0),
            )

            if any(s is not None for _, s in scored):
                st.caption("🎯 Results ranked by ingredient similarity to your taste profile.")
            elif has_taste_profile:
                st.caption("ℹ️ No ingredient data — ML ranking unavailable for these results.")

            for idx, (meal, score) in enumerate(scored):
                render_meal_card(meal, ml_score=score, card_key=f"s{idx}")


# ── Cuisine tab ───────────────────────────────────────────────────────────────

with tab_cuisine:
    cuisines = list_cuisines()   # cached 24 h

    if not cuisines:
        empty_state("Cuisine list couldn't be loaded — check your internet.")
    else:
        st.subheader("🌍 Bites Across Borders")
        st.markdown("- Click on a country on the map to explore its traditional recipes")
        st.markdown("- Not sure where a country is? You can also use the selector below!")

        from streamlit_plotly_events import plotly_events

        all_locations = list(ISO_CONTINENT.keys())
        cuisine_isos  = set(ISO_TO_CUISINE.keys())
        colored_locs  = [iso for iso in all_locations if iso in cuisine_isos]

        clicked_points = plotly_events(
            build_figure(),   # cached 24 h — no rebuild on every render
            click_event=True, hover_event=False, select_event=False,
            override_width="100%", override_height=450, key="world_map",
        )

        legend_cols = st.columns(len(CONTINENT_DATA) - 1)
        for col_idx, (cont, info) in enumerate(
            (c, i) for c, i in CONTINENT_DATA.items() if c != "Antarctica"
        ):
            with legend_cols[col_idx]:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:6px;font-size:12px;color:#2C3E50;">'
                    f'<span style="width:12px;height:12px;border-radius:50%;background:{info["color"]};display:inline-block;flex-shrink:0;"></span>'
                    f'{cont} <span style="color:#999;font-size:11px;">({len(info["countries"])})</span></div>',
                    unsafe_allow_html=True,
                )

        st.divider()

        if clicked_points:
            ci = clicked_points[0].get("curveNumber", 0)
            pi = clicked_points[0].get("pointIndex")
            if ci == 1 and pi is not None and pi < len(colored_locs):
                iso = colored_locs[pi]
                if iso in ISO_TO_CUISINE:
                    st.session_state["map_selected_iso"] = iso
                    st.session_state["_needs_rerun"] = True

        selected_iso          = st.session_state.get("map_selected_iso")
        active_cuisine        = ISO_TO_CUISINE.get(selected_iso) if selected_iso else None
        selected_country_name = ISO_NAME.get(selected_iso) if selected_iso else None

        CUISINE_TO_ISO  = {v: k for k, v in ISO_TO_CUISINE.items()}
        cuisine_options = ["— click the map or choose here —"] + sorted(ISO_TO_CUISINE.values())
        default_idx     = cuisine_options.index(active_cuisine) if active_cuisine in cuisine_options else 0

        manual_choice = st.selectbox(
            "Or pick a cuisine manually:",
            options=cuisine_options, index=default_idx, key="cuisine_selectbox",
        )
        if manual_choice != "— click the map or choose here —":
            active_cuisine        = manual_choice
            selected_iso          = CUISINE_TO_ISO.get(active_cuisine)
            selected_country_name = ISO_NAME.get(selected_iso, active_cuisine)
            st.session_state["map_selected_iso"] = selected_iso

        if active_cuisine:
            st.subheader(f"🍽️ Recipes from {selected_country_name}")
            with st.spinner(f"Loading {active_cuisine} recipes…"):
                cuisine_results = fetch_cuisine_meals(active_cuisine)   # cached 1 h

            if not cuisine_results:
                empty_state(f"No recipes found for {active_cuisine} — try another country.")
            else:
                for idx, meal in enumerate(cuisine_results):
                    render_meal_card(meal, card_key=f"c{idx}")
        else:
            st.info("👆 Click a country on the map to explore its recipes.")
