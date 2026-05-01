"""
World Map — explore recipes by country of origin.
Owner: <assign on Apr 22>
Grading coverage:
    * Req. 3 (visualisation — interactive choropleth/scatter-geo)
    * Req. 4 (interactivity — country picker drives a recipe list)
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from src.components.ui import page_header
from src.utils.session import init_session_state, require_profile

try:
    from src.data.database import query_df  # type: ignore
except Exception:
    query_df = None  # type: ignore


init_session_state()
require_profile()

page_header("🌍 World Map", "Discover recipes from around the world.")


# ---------------------------------------------------------------------------
# TheMealDB uses "area" labels (Italian, Japanese, …). Map them to a country
# name + lat/lon so we can plot them on the globe. Easy to extend.
# ---------------------------------------------------------------------------
AREA_TO_COUNTRY = {
    "American":   {"country": "United States",  "lat": 37.09,  "lon": -95.71},
    "British":    {"country": "United Kingdom", "lat": 55.38,  "lon": -3.44},
    "Canadian":   {"country": "Canada",         "lat": 56.13,  "lon": -106.35},
    "Chinese":    {"country": "China",          "lat": 35.86,  "lon": 104.19},
    "Croatian":   {"country": "Croatia",        "lat": 45.10,  "lon": 15.20},
    "Dutch":      {"country": "Netherlands",    "lat": 52.13,  "lon": 5.29},
    "Egyptian":   {"country": "Egypt",          "lat": 26.82,  "lon": 30.80},
    "Filipino":   {"country": "Philippines",    "lat": 12.88,  "lon": 121.77},
    "French":     {"country": "France",         "lat": 46.23,  "lon": 2.21},
    "Greek":      {"country": "Greece",         "lat": 39.07,  "lon": 21.82},
    "Indian":     {"country": "India",          "lat": 20.59,  "lon": 78.96},
    "Irish":      {"country": "Ireland",        "lat": 53.41,  "lon": -8.24},
    "Italian":    {"country": "Italy",          "lat": 41.87,  "lon": 12.56},
    "Jamaican":   {"country": "Jamaica",        "lat": 18.11,  "lon": -77.30},
    "Japanese":   {"country": "Japan",          "lat": 36.20,  "lon": 138.25},
    "Kenyan":     {"country": "Kenya",          "lat": -0.02,  "lon": 37.91},
    "Malaysian":  {"country": "Malaysia",       "lat": 4.21,   "lon": 101.98},
    "Mexican":    {"country": "Mexico",         "lat": 23.63,  "lon": -102.55},
    "Moroccan":   {"country": "Morocco",        "lat": 31.79,  "lon": -7.09},
    "Polish":     {"country": "Poland",         "lat": 51.92,  "lon": 19.13},
    "Portuguese": {"country": "Portugal",       "lat": 39.40,  "lon": -8.22},
    "Russian":    {"country": "Russia",         "lat": 61.52,  "lon": 105.32},
    "Spanish":    {"country": "Spain",          "lat": 40.46,  "lon": -3.74},
    "Thai":       {"country": "Thailand",       "lat": 15.87,  "lon": 100.99},
    "Tunisian":   {"country": "Tunisia",        "lat": 33.89,  "lon": 9.54},
    "Turkish":    {"country": "Turkey",         "lat": 38.96,  "lon": 35.24},
    "Ukrainian":  {"country": "Ukraine",        "lat": 48.38,  "lon": 31.17},
    "Vietnamese": {"country": "Vietnam",        "lat": 14.06,  "lon": 108.28},
}


# ---------------------------------------------------------------------------
# Load recipes — DB first, demo fallback otherwise (same pattern as page 7).
# ---------------------------------------------------------------------------
def load_recipes() -> pd.DataFrame:
    if query_df is not None:
        try:
            df = query_df("SELECT id, title, area FROM recipes WHERE area IS NOT NULL")
            if df is not None and len(df) > 0:
                return df
        except Exception:
            pass
    # demo fallback — varied areas so the map shows several bubbles
    return pd.DataFrame(
        [
            {"id": 1, "title": "Pasta Pesto",      "area": "Italian"},
            {"id": 2, "title": "Thai Green Curry", "area": "Thai"},
            {"id": 3, "title": "Rösti",            "area": "British"},  # closest in TheMealDB taxonomy
            {"id": 4, "title": "Dal Tadka",        "area": "Indian"},
            {"id": 5, "title": "Tacos al Pastor",  "area": "Mexican"},
            {"id": 6, "title": "Tomato Risotto",   "area": "Italian"},
            {"id": 7, "title": "Sushi Rolls",      "area": "Japanese"},
            {"id": 8, "title": "Beef Bourguignon", "area": "French"},
            {"id": 9, "title": "Greek Salad",      "area": "Greek"},
            {"id": 10, "title": "Paella",          "area": "Spanish"},
        ]
    )


recipes = load_recipes()

# Attach country / lat / lon
recipes = recipes.copy()
recipes["country"] = recipes["area"].map(lambda a: AREA_TO_COUNTRY.get(a, {}).get("country"))
recipes["lat"]     = recipes["area"].map(lambda a: AREA_TO_COUNTRY.get(a, {}).get("lat"))
recipes["lon"]     = recipes["area"].map(lambda a: AREA_TO_COUNTRY.get(a, {}).get("lon"))

mappable = recipes.dropna(subset=["lat", "lon"])

if mappable.empty:
    st.info(
        "No recipes with a recognised area yet — sync the DB or add entries to "
        "`AREA_TO_COUNTRY` in this file."
    )
    st.stop()


# ---------------------------------------------------------------------------
# Plot — bubble per country, sized by recipe count
# ---------------------------------------------------------------------------
grouped = (
    mappable.groupby(["country", "lat", "lon"])
    .agg(
        recipe_count=("title", "count"),
        recipes=("title", lambda names: "<br>• " + "<br>• ".join(sorted(set(names))[:15])),
    )
    .reset_index()
)

fig = px.scatter_geo(
    grouped,
    lat="lat", lon="lon",
    size="recipe_count",
    hover_name="country",
    hover_data={"recipes": True, "recipe_count": True, "lat": False, "lon": False},
    projection="natural earth",
    size_max=35,
    color="recipe_count",
    color_continuous_scale="Sunsetdark",
)
fig.update_layout(
    margin=dict(l=0, r=0, t=10, b=0),
    height=520,
    geo=dict(showland=True, landcolor="#2b2b2b", bgcolor="rgba(0,0,0,0)"),
    paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Country picker — drives a recipe list under the map
# ---------------------------------------------------------------------------
st.divider()
countries = sorted(mappable["country"].unique())
country = st.selectbox("Pick a country to browse:", countries)

country_recipes = mappable[mappable["country"] == country].drop_duplicates(subset=["title"])
st.caption(f"{len(country_recipes)} recipe(s) from {country}")

cols = st.columns(2)
for i, (_, row) in enumerate(country_recipes.iterrows()):
    with cols[i % 2]:
        with st.container(border=True):
            st.subheader(row["title"])
            st.caption(f"📍 {row['country']}  •  Area: {row['area']}")
            if st.button("View recipe", key=f"view_{row['id']}"):
                st.session_state["selected_recipe_id"] = int(row["id"])
                try:
                    st.switch_page("pages/2_Recipes.py")
                except Exception:
                    st.toast(f"Opening {row['title']} on the Recipes page…")
