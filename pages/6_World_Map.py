"""
World Map — explore recipes by geographical origin.

Owner: <assign on Apr 22>
Grading coverage:
    * Req. 3 (visualisation — choropleth / scatter map)
    * Req. 2 (cuisine counts come from the API or DB)

TODOs for the owner:
    - replace the hand-coded demo counts with `query_df(...)` against
      the `recipes` table, grouped by `country_iso`.
    - when a country is clicked, show its recipes in a side panel.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from src.components.ui import page_header
from src.utils.session import init_session_state, require_profile


init_session_state()
require_profile()
page_header("🗺️ World of Recipes", "Explore what the world cooks.")

# Demo data — owner: replace with real DB query.
demo = pd.DataFrame(
    [
        {"country_iso": "ITA", "country": "Italy",   "recipes": 42},
        {"country_iso": "CHE", "country": "Switzerland", "recipes": 17},
        {"country_iso": "JPN", "country": "Japan",   "recipes": 23},
        {"country_iso": "IND", "country": "India",   "recipes": 31},
        {"country_iso": "MEX", "country": "Mexico",  "recipes": 19},
        {"country_iso": "FRA", "country": "France",  "recipes": 28},
        {"country_iso": "THA", "country": "Thailand","recipes": 15},
    ]
)

fig = px.choropleth(
    demo,
    locations="country_iso",
    color="recipes",
    hover_name="country",
    color_continuous_scale="Oranges",
)
fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
st.plotly_chart(fig, use_container_width=True)
