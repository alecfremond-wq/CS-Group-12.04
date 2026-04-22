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


--------------------------------------------------------------------------------------------------------------------------------------------
"""
Interactive World Map — Continent Tracker + API Integration
============================================================
Requirements:
    pip install folium requests
 
Usage:
    python continent_map.py
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  HOW TO CONNECT YOUR API
  Search for the tag  >>>  # 🔌 API INTEGRATION  <<<
  There are 3 places to edit (marked with TODO comments).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
 
import folium
import requests
import webbrowser
import os
 
# ===========================================================================
# 🔌 API INTEGRATION  —  STEP 1 OF 3
# ---------------------------------------------------------------------------
# Replace the values below with your real API credentials.
# ===========================================================================
 
API_BASE_URL = "https://your-api.com"   # TODO: replace with your API base URL
API_KEY      = "YOUR_API_KEY_HERE"      # TODO: replace with your API key
API_HEADERS  = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
 
# ===========================================================================
# 🔌 API INTEGRATION  —  STEP 2 OF 3
# ---------------------------------------------------------------------------
# This function fetches data FOR EACH CONTINENT from your API.
# Edit the endpoint path and the field names to match your API response.
#
# Expected return format (one dict per continent):
#   {
#     "value":    "1,200",        ← main metric shown in the popup
#     "subtitle": "active users", ← label under the metric
#     "extra":    "↑ 12% vs last month"  ← optional extra line
#   }
#
# If the API call fails, the map still loads with a fallback message.
# ===========================================================================
 
def fetch_continent_data(continent_name: str) -> dict:
    """
    Call your API and return data for the given continent.
 
    Args:
        continent_name: e.g. "Europe", "Asia", "Africa" …
 
    Returns:
        dict with keys: value, subtitle, extra
    """
    try:
        # TODO: change the endpoint path to match YOUR API
        endpoint = f"{API_BASE_URL}/continents/{continent_name.lower().replace(' ', '-')}"
 
        response = requests.get(endpoint, headers=API_HEADERS, timeout=5)
        response.raise_for_status()
 
        data = response.json()
 
        # TODO: map YOUR API response fields to the three display fields below
        return {
            "value":    data.get("value",    "N/A"),       # ← change "value"
            "subtitle": data.get("subtitle", ""),          # ← change "subtitle"
            "extra":    data.get("extra",    ""),          # ← change "extra"
        }
 
    except requests.exceptions.ConnectionError:
        return {"value": "Offline", "subtitle": "API unreachable", "extra": ""}
    except requests.exceptions.Timeout:
        return {"value": "Timeout", "subtitle": "Request timed out", "extra": ""}
    except Exception as e:
        return {"value": "Error", "subtitle": str(e)[:40], "extra": ""}
 
 
# ===========================================================================
# Continent definitions  (visual config — no need to edit these)
# ===========================================================================
 
CONTINENTS = {
    "Europe": {
        "color":    "#2e86c1",
        "center":   [54, 15],
        "emoji":    "🏛️",
        "geojson_names": [
            "Albania","Andorra","Austria","Belarus","Belgium","Bosnia and Herz.",
            "Bulgaria","Croatia","Cyprus","Czech Rep.","Denmark","Estonia",
            "Finland","France","Germany","Greece","Hungary","Iceland","Ireland",
            "Italy","Kosovo","Latvia","Liechtenstein","Lithuania","Luxembourg",
            "Malta","Moldova","Monaco","Montenegro","Netherlands","Norway",
            "Poland","Portugal","Romania","Russia","San Marino","Serbia",
            "Slovakia","Slovenia","Spain","Sweden","Switzerland","Ukraine",
            "United Kingdom","Vatican",
        ],
    },
    "Asia": {
        "color":    "#1a9a6e",
        "center":   [34, 100],
        "emoji":    "🗼",
        "geojson_names": [
            "Afghanistan","Armenia","Azerbaijan","Bahrain","Bangladesh","Bhutan",
            "Brunei","Cambodia","China","Georgia","India","Indonesia","Iran",
            "Iraq","Israel","Japan","Jordan","Kazakhstan","Kuwait","Kyrgyzstan",
            "Laos","Lebanon","Malaysia","Maldives","Mongolia","Myanmar","Nepal",
            "North Korea","Oman","Pakistan","Palestine","Philippines","Qatar",
            "Saudi Arabia","Singapore","South Korea","Sri Lanka","Syria",
            "Taiwan","Tajikistan","Thailand","Timor-Leste","Turkey",
            "Turkmenistan","United Arab Emirates","Uzbekistan","Vietnam","Yemen",
        ],
    },
    "Africa": {
        "color":    "#d4ac0d",
        "center":   [2, 20],
        "emoji":    "🦁",
        "geojson_names": [
            "Algeria","Angola","Benin","Botswana","Burkina Faso","Burundi",
            "Cameroon","Cape Verde","Central African Rep.","Chad","Comoros",
            "Congo","Côte d'Ivoire","Dem. Rep. Congo","Djibouti","Egypt",
            "Equatorial Guinea","Eritrea","Ethiopia","Gabon","Gambia","Ghana",
            "Guinea","Guinea-Bissau","Kenya","Lesotho","Liberia","Libya",
            "Madagascar","Malawi","Mali","Mauritania","Mauritius","Morocco",
            "Mozambique","Namibia","Niger","Nigeria","Rwanda","São Tomé and Pr.",
            "Senegal","Seychelles","Sierra Leone","Somalia","S. Sudan",
            "South Africa","Sudan","Swaziland","Tanzania","Togo","Tunisia",
            "Uganda","Zambia","Zimbabwe",
        ],
    },
    "North America": {
        "color":    "#27ae60",
        "center":   [48, -100],
        "emoji":    "🗽",
        "geojson_names": [
            "Antigua and Barb.","Bahamas","Barbados","Belize","Canada","Costa Rica",
            "Cuba","Dominica","Dominican Rep.","El Salvador","Grenada","Guatemala",
            "Haiti","Honduras","Jamaica","Mexico","Nicaragua","Panama",
            "Saint Kitts and Nevis","Saint Lucia","Saint Vincent and the Grenadines",
            "Trinidad and Tobago","United States of America",
        ],
    },
    "South America": {
        "color":    "#8e44ad",
        "center":   [-15, -60],
        "emoji":    "🌿",
        "geojson_names": [
            "Argentina","Bolivia","Brazil","Chile","Colombia","Ecuador",
            "Guyana","Paraguay","Peru","Suriname","Uruguay","Venezuela",
        ],
    },
    "Oceania": {
        "color":    "#e67e22",
        "center":   [-25, 140],
        "emoji":    "🦘",
        "geojson_names": [
            "Australia","Fiji","Kiribati","Marshall Is.","Micronesia","Nauru",
            "New Zealand","Palau","Papua New Guinea","Samoa","Solomon Is.",
            "Tonga","Tuvalu","Vanuatu",
        ],
    },
    "Antarctica": {
        "color":    "#95a5a6",
        "center":   [-80, 0],
        "emoji":    "🧊",
        "geojson_names": ["Antarctica"],
    },
}
 
# Build a lookup: country name → continent name (used for GeoJSON styling)
COUNTRY_TO_CONTINENT = {}
for cont_name, cont_data in CONTINENTS.items():
    for country in cont_data["geojson_names"]:
        COUNTRY_TO_CONTINENT[country] = cont_name
 
 
# ===========================================================================
# Map builder
# ===========================================================================
 
def build_map() -> folium.Map:
    """Build the interactive continent map, fetching API data for each popup."""
 
    m = folium.Map(
        location=[20, 10],
        zoom_start=2,
        tiles="CartoDB dark_matter",
        min_zoom=1,
        max_zoom=8,
        control_scale=True,
    )
 
    # -----------------------------------------------------------------------
    # GeoJSON world layer — countries coloured by continent
    # -----------------------------------------------------------------------
    geojson_url = (
        "https://raw.githubusercontent.com/datasets/geo-countries/"
        "master/data/countries.geojson"
    )
 
    def country_style(feature):
        name = feature["properties"].get("ADMIN", "")
        continent = COUNTRY_TO_CONTINENT.get(name, None)
        color = CONTINENTS[continent]["color"] if continent else "#1a2a3a"
        return {
            "fillColor": color,
            "color":       "#060e1a",
            "weight":      0.4,
            "fillOpacity": 0.72,
        }
 
    def country_highlight(feature):
        name = feature["properties"].get("ADMIN", "")
        continent = COUNTRY_TO_CONTINENT.get(name, None)
        color = CONTINENTS[continent]["color"] if continent else "#4fc3f7"
        return {
            "fillColor": color,
            "color":       "#ffffff",
            "weight":      1.5,
            "fillOpacity": 0.95,
        }
 
    folium.GeoJson(
        geojson_url,
        name="Countries",
        style_function=country_style,
        highlight_function=country_highlight,
        tooltip=folium.GeoJsonTooltip(
            fields=["ADMIN"],
            aliases=[""],
            style=(
                "background:rgba(6,16,32,0.92);"
                "color:#4fc3f7;"
                "font-family:monospace;"
                "font-size:12px;"
                "border:1px solid #4fc3f744;"
                "border-radius:4px;"
                "padding:5px 10px;"
            ),
        ),
    ).add_to(m)
 
    # -----------------------------------------------------------------------
    # Continent markers — each calls the API and shows a popup
    # -----------------------------------------------------------------------
    print("\nFetching API data for each continent...")
    for cont_name, info in CONTINENTS.items():
 
        # 🔌 API INTEGRATION — STEP 3 OF 3
        # This calls fetch_continent_data() (defined above) for every continent.
        # Once your API credentials and endpoint are set in STEP 1 and STEP 2,
        # this line will automatically pull live data into each popup.
        api_data = fetch_continent_data(cont_name)
 
        status_color = "#4fc3f7" if api_data["value"] not in ("Error", "Offline", "Timeout", "N/A") else "#e74c3c"
 
        popup_html = f"""
        <div style="
            font-family:monospace;
            background:rgba(6,16,32,0.98);
            color:#e8f4f8;
            padding:16px 20px;
            border-radius:8px;
            border:1px solid {info['color']};
            min-width:220px;
        ">
            <div style="font-size:2rem;margin-bottom:6px">{info['emoji']}</div>
            <div style="
                font-size:1.3rem;color:{info['color']};
                font-weight:bold;margin-bottom:12px
            ">{cont_name}</div>
 
            <div style="border-top:1px solid #1a3a5c;padding-top:10px;margin-top:4px">
                <div style="font-size:0.65rem;color:#6b9ab8;
                            letter-spacing:0.12em;text-transform:uppercase;
                            margin-bottom:4px">
                    API DATA
                </div>
                <div style="font-size:1.6rem;color:{status_color};font-weight:bold">
                    {api_data['value']}
                </div>
                <div style="font-size:0.78rem;color:#8bb8cc;margin-top:2px">
                    {api_data['subtitle']}
                </div>
                <div style="font-size:0.72rem;color:#4fc3f7;margin-top:6px">
                    {api_data['extra']}
                </div>
            </div>
        </div>
        """
 
        print(f"  {info['emoji']}  {cont_name:<15} → {api_data['value']}")
 
        folium.Marker(
            location=info["center"],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"<b style='color:{info['color']}'>{info['emoji']} {cont_name}</b>",
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    background:{info['color']};
                    color:#fff;
                    font-family:monospace;
                    font-size:11px;
                    font-weight:bold;
                    padding:4px 9px;
                    border-radius:4px;
                    white-space:nowrap;
                    box-shadow:0 2px 10px rgba(0,0,0,0.6);
                    letter-spacing:0.08em;
                    text-transform:uppercase;
                    cursor:pointer;
                ">{cont_name}</div>
                """,
                icon_size=(160, 26),
                icon_anchor=(80, 13),
            ),
        ).add_to(m)
 
    # -----------------------------------------------------------------------
    # Legend
    # -----------------------------------------------------------------------
    legend_html = """
    <div style="
        position:fixed; bottom:28px; left:14px; z-index:1000;
        background:rgba(6,16,32,0.95); border:1px solid #1a3a5c;
        border-radius:6px; padding:12px 16px;
        font-family:monospace; font-size:11px; color:#8bb8cc;
    ">
        <div style="color:#e8f4f8;font-size:11px;font-weight:bold;
                    margin-bottom:8px;letter-spacing:0.1em;text-transform:uppercase">
            Continents
        </div>
    """
    for name, info in CONTINENTS.items():
        legend_html += f"""
        <div style="display:flex;align-items:center;gap:7px;margin-bottom:5px">
            <div style="width:10px;height:10px;border-radius:2px;
                        background:{info['color']};flex-shrink:0"></div>
            <span>{info['emoji']} {name}</span>
        </div>"""
    legend_html += "</div>"
    m.get_root().html.add_child(folium.Element(legend_html))
 
    # Title
    title_html = """
    <div style="
        position:fixed; top:12px; left:50%; transform:translateX(-50%);
        z-index:1000; background:rgba(6,16,32,0.92);
        border:1px solid #4fc3f744; border-radius:6px;
        padding:8px 22px; font-family:Georgia,serif; font-style:italic;
        font-size:18px; color:#4fc3f7; letter-spacing:0.05em;
        box-shadow:0 4px 20px rgba(0,0,0,0.6); pointer-events:none;
    ">🌍 Interactive World Map — Continent Tracker</div>
    """
    m.get_root().html.add_child(folium.Element(title_html))
 
    return m
 
 
# ===========================================================================
# Entry point
# ===========================================================================
 
def main():
    print("=" * 55)
    print("  🌍  Interactive World Map — Continent Tracker")
    print("=" * 55)
 
    world_map = build_map()
 
    output_file = "continent_map.html"
    world_map.save(output_file)
    abs_path = os.path.abspath(output_file)
 
    print(f"\n✅  Map saved → {abs_path}")
    print("Opening in browser...")
    webbrowser.open(f"file://{abs_path}")
 
    print("\nControls:")
    print("  🖱️  Scroll        → zoom")
    print("  🖱️  Drag          → pan")
    print("  🖱️  Click label   → API data popup")
    print("  🖱️  Hover country → country name")
 
 
if __name__ == "__main__":
    main()
