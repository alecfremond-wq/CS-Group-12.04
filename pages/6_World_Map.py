"""
Interactive World Map — Student Meal Planner App
=================================================
Run this script to launch the interactive world map in your browser.
Hover over a continent to see its countries listed in a tooltip.

Requirements:
    pip install plotly

How to run:
    python world_map_app.py
"""

import json
import webbrowser
import os

# ── 1. Continent → Countries ──────────────────────────────────────────────────
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

# ── 2. ISO-3 code → Continent (for the choropleth) ───────────────────────────
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

# ── 3. Build hover text ────────────────────────────────────────────────────────
# ISO-3 → country name
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

def get_hover(iso):
    cont = ISO_CONTINENT.get(iso, "")
    name = ISO_NAME.get(iso, iso)
    color = CONTINENT_DATA.get(cont, {}).get("color", "#999")
    return (
        f"<b style='font-size:14px'>{name}</b><br>"
        f"<span style='color:{color}'>&#9632;</span> {cont}"
    )

# ── 4. Build HTML with embedded Plotly ────────────────────────────────────────
def build_html():
    locations = list(ISO_CONTINENT.keys())
    continents = [ISO_CONTINENT[c] for c in locations]
    continent_list = list(CONTINENT_DATA.keys())
    colors_list = [CONTINENT_DATA[c]["color"] for c in continent_list]

    z_values = [continent_list.index(c) for c in continents]

    # Build discrete colorscale
    n = len(continent_list)
    colorscale = []
    for i, col in enumerate(colors_list):
        colorscale.append([i / n, col])
        colorscale.append([(i + 1) / n, col])

    hover_texts = [get_hover(iso) for iso in locations]

    trace = {
        "type": "choropleth",
        "locations": locations,
        "locationmode": "ISO-3",
        "z": z_values,
        "text": hover_texts,
        "hovertemplate": "%{text}<extra></extra>",
        "colorscale": colorscale,
        "zmin": 0,
        "zmax": n,
        "showscale": False,
        "marker": {"line": {"color": "white", "width": 0.8}},
    }

    # Continent name annotations (approximate centres)
    continent_centres = {
        "Africa":        (20,  5),
        "Asia":          (90, 45),
        "Europe":        (15, 55),
        "North America": (-95, 45),
        "South America": (-60,-20),
        "Oceania":       (135,-25),
        "Antarctica":    (0,  -80),
    }

    annotations = []
    for cont, (lon, lat) in continent_centres.items():
        annotations.append({
            "x": lon, "y": lat,
            "xref": "x", "yref": "y",
            "text": f"<b>{cont}</b>",
            "showarrow": False,
            "font": {"size": 11, "color": "white",
                     "family": "Georgia, serif"},
            "bgcolor": "rgba(0,0,0,0.35)",
            "borderpad": 3,
        })

    layout = {
        "title": {
            "text": "Bites Across Borders",
            "x": 0.5,
            "font": {"size": 20, "family": "Georgia, serif", "color": "#2C3E50"},
        },
        "geo": {
            "showframe": False,
            "showcoastlines": True,
            "coastlinecolor": "white",
            "showland": True,
            "landcolor": "#D5D8DC",
            "showocean": True,
            "oceancolor": "#AED6F1",
            "showlakes": True,
            "lakecolor": "#AED6F1",
            "showrivers": False,
            "projection": {"type": "natural earth"},
            "bgcolor": "rgba(0,0,0,0)",
            "lataxis": {"range": [-60, 85]},
        },
        "paper_bgcolor": "#F4F6F8",
        "margin": {"l": 0, "r": 0, "t": 55, "b": 10},
        "annotations": annotations,
        "hoverlabel": {
            "bgcolor": "#2C3E50",
            "font": {"size": 12, "color": "white", "family": "monospace"},
            "bordercolor": "#AAA",
            "align": "left",
        },
    }

    data_json   = json.dumps([trace])
    layout_json = json.dumps(layout)

    # Legend HTML
    legend_html = ""
    for cont, info in CONTINENT_DATA.items():
        if cont == "Antarctica":
            continue
        legend_html += (
            f'<div class="legend-item">'
            f'<span class="dot" style="background:{info["color"]}"></span>'
            f'{cont} <span class="cnt">({len(info["countries"])})</span>'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>World Map — Student Meal Planner</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: Georgia, serif;
      background: #F4F6F8;
      display: flex;
      flex-direction: column;
      height: 100vh;
    }}
    #header {{
      background: #2C3E50;
      color: white;
      padding: 10px 24px;
      display: flex;
      align-items: center;
      gap: 14px;
    }}
    #header .logo {{
      font-size: 28px;
    }}
    #header h1 {{
      font-size: 18px;
      font-weight: normal;
      letter-spacing: 0.5px;
    }}
    #header p {{
      font-size: 12px;
      color: #BDC3C7;
      margin-top: 2px;
    }}
    #map {{
      flex: 1;
    }}
    #legend {{
      background: white;
      border-top: 1px solid #DDD;
      padding: 8px 20px;
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      align-items: center;
    }}
    .legend-label {{
      font-size: 12px;
      font-weight: bold;
      color: #555;
      margin-right: 4px;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: #2C3E50;
    }}
    .dot {{
      width: 12px; height: 12px;
      border-radius: 50%;
      display: inline-block;
      flex-shrink: 0;
    }}
    .cnt {{ color: #999; font-size: 11px; }}
    #tip {{
      position: fixed;
      bottom: 60px; right: 18px;
      background: rgba(44,62,80,0.75);
      color: white;
      font-size: 11px;
      padding: 6px 12px;
      border-radius: 20px;
      pointer-events: none;
    }}
  </style>
</head>
<body>
  <div id="header">
    <div class="logo">🍽️</div>
    <div>
      <h1>Bites Across Borders</h1>
      <p>A journey through international food traditions</p>
    </div>
  </div>

  <div id="map"></div>

  <div id="legend">
    <span class="legend-label">Continents:</span>
    {legend_html}
  </div>

  <div id="tip">🖱 Hover · Scroll to zoom · Drag to pan</div>

  <script>
    Plotly.newPlot('map', {data_json}, {layout_json}, {{
      responsive: true,
      displayModeBar: true,
      modeBarButtonsToRemove: ['toImage','sendDataToCloud'],
      displaylogo: false
    }});

    // Hide tip after 5 seconds
    setTimeout(() => {{
      document.getElementById('tip').style.opacity = '0';
      document.getElementById('tip').style.transition = 'opacity 1s';
    }}, 5000);
  </script>
</body>
</html>"""
    return html


# ── 5. Save & open ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    output_file = "world_map.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(build_html())

    abs_path = os.path.abspath(output_file)
    url = "file://" + abs_path

    print("=" * 55)
    print("  ✅  World Map generated successfully!")
    print("=" * 55)
    print(f"\n  📄  File : {abs_path}")
    print(f"\n  🌐  URL  : {url}")
    print("\n  ➡️   Opening in your browser automatically...")
    print("  (Or copy the URL above and paste it in your browser)")
    print("=" * 55)

    webbrowser.open(url)
