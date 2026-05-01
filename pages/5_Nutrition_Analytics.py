"""
Nutrition Analytics — visualise what the user actually eats.

Owner: <assign on Apr 22>
Grading coverage:
    * Req. 3 (visualisation — multiple charts)
    * Req. 2 (data sourced from the `cooking_history` + `recipes` tables)

TODOs for the owner:
    - replace the random demo data with a join across cooking_history + recipes.
    - add a date-range filter (st.date_input(value=[...])).
"""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.components.ui import page_header
from src.utils.session import init_session_state, require_profile


init_session_state()
require_profile()
page_header("📊 Nutrition Analytics", "Track your calories, protein and more.")

# --- demo data (owner: replace with real history join) --------------------
rng = np.random.default_rng(42)
days = pd.date_range(end=pd.Timestamp.today(), periods=14).date
demo = pd.DataFrame(
    {
        "date": days,
        "kcal": rng.integers(1600, 2400, len(days)),
        "protein_g": rng.integers(40, 120, len(days)),
        "carbs_g": rng.integers(150, 320, len(days)),
        "fat_g": rng.integers(40, 100, len(days)),
    }
)

metric = st.selectbox("Metric", ["kcal", "protein_g", "carbs_g", "fat_g"])
fig = px.line(demo, x="date", y=metric, markers=True, title=f"{metric} over time")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Macro breakdown (last 7 days)")
last7 = demo.tail(7)[["protein_g", "carbs_g", "fat_g"]].sum().reset_index()
last7.columns = ["macro", "grams"]
st.plotly_chart(
    px.pie(last7, names="macro", values="grams", hole=0.4),
    use_container_width=True,
)

st.caption("⚠️  Demo data — owner: wire up real cooking_history in Sprint 2.")

--------------------------------
st.subheader ("Nutrition facts for the past 7 days")
import json
import requests
from datetime import datetime, timedelta
from collections import defaultdict
 
import dash
from dash import dcc, html, Input, Output, State, ctx
import plotly.graph_objects as go
 
# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# Replace with your real Spoonacular API key
# Get one free at: https://spoonacular.com/food-api
# ─────────────────────────────────────────────────────────────
SPOONACULAR_API_KEY = "YOUR_API_KEY_HERE"
SPOONACULAR_BASE    = "https://api.spoonacular.com"
CALORIE_GOAL        = 2000   # daily kcal goal
 
# ─────────────────────────────────────────────────────────────
# SPOONACULAR API HELPERS
# ─────────────────────────────────────────────────────────────
def search_recipes(query: str, number: int = 8) -> list[dict]:
    """Search recipes by name. Returns list of {id, title, image, calories}."""
    if not query.strip():
        return []
    try:
        r = requests.get(
            f"{SPOONACULAR_BASE}/recipes/complexSearch",
            params={
                "apiKey":          SPOONACULAR_API_KEY,
                "query":           query,
                "number":          number,
                "addRecipeNutrition": True,
            },
            timeout=8,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        recipes = []
        for item in results:
            kcal = 0
            nutrients = item.get("nutrition", {}).get("nutrients", [])
            for n in nutrients:
                if n.get("name") == "Calories":
                    kcal = round(n.get("amount", 0))
                    break
            recipes.append({
                "id":       item["id"],
                "title":    item["title"],
                "image":    item.get("image", ""),
                "calories": kcal,
            })
        return recipes
    except Exception as e:
        print(f"[Spoonacular] Search error: {e}")
        return []
 
 
def get_recipe_nutrition(recipe_id: int) -> dict:
    """Get full nutrition details for a recipe."""
    try:
        r = requests.get(
            f"{SPOONACULAR_BASE}/recipes/{recipe_id}/nutritionWidget.json",
            params={"apiKey": SPOONACULAR_API_KEY},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        def _val(key):
            for n in data.get("nutrients", []):
                if n.get("name") == key:
                    return round(float(n.get("amount", 0)))
            return 0
        return {
            "calories": _val("Calories"),
            "protein":  _val("Protein"),
            "carbs":    _val("Carbohydrates"),
            "fat":      _val("Fat"),
        }
    except Exception as e:
        print(f"[Spoonacular] Nutrition error: {e}")
        return {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
 
# ─────────────────────────────────────────────────────────────
# DATE HELPERS
# ─────────────────────────────────────────────────────────────
def last_7_days() -> list[str]:
    today = datetime.today()
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
 
def date_to_label(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%a")
 
DATES  = last_7_days()
LABELS = [date_to_label(d) for d in DATES]
 
# ─────────────────────────────────────────────────────────────
# COLOR HELPERS
# ─────────────────────────────────────────────────────────────
def bar_color(total: int) -> str:
    if total > CALORIE_GOAL + 150: return "#E24B4A"
    if total < CALORIE_GOAL - 150: return "#378ADD"
    return "#5AAF32"
 
MACRO_COLORS = {
    "calories": "#F4A522",
    "protein":  "#378ADD",
    "carbs":    "#9B6FD8",
    "fat":      "#E24B4A",
}
 
FONT = "'DM Sans', 'Segoe UI', sans-serif"
 
# ─────────────────────────────────────────────────────────────
# CHART BUILDERS
# ─────────────────────────────────────────────────────────────
def build_bar_chart(log: dict, selected_date: str | None = None) -> go.Figure:
    totals = [sum(r["calories"] for r in log.get(d, [])) for d in DATES]
    sel_idx = DATES.index(selected_date) if selected_date in DATES else None
 
    bar_colors = []
    for i, t in enumerate(totals):
        c = bar_color(t)
        if sel_idx is not None and i != sel_idx:
            bar_colors.append("rgba(255,255,255,0.07)")
        else:
            bar_colors.append(c)
 
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=LABELS, y=totals,
        marker=dict(color=bar_colors, cornerradius=8),
        hovertemplate="<b>%{x}</b><br>%{y:,} kcal<extra></extra>",
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=LABELS, y=[CALORIE_GOAL] * 7,
        mode="lines",
        line=dict(color="rgba(255,255,255,0.2)", width=1.5, dash="dot"),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_annotation(
        x=LABELS[-1], y=CALORIE_GOAL,
        text=f"Goal {CALORIE_GOAL:,}",
        showarrow=False, xanchor="right", yanchor="bottom",
        font=dict(size=11, color="rgba(255,255,255,0.25)", family=FONT),
        yshift=6,
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0), height=230,
        font=dict(family=FONT, color="#888780"),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=13, color="#888780")),
        yaxis=dict(
            range=[0, max(max(totals, default=0) + 400, CALORIE_GOAL + 600)],
            showgrid=True, gridcolor="rgba(255,255,255,0.05)",
            zeroline=False, tickfont=dict(size=11, color="#555"), tickformat=",",
        ),
        bargap=0.35,
        hoverlabel=dict(bgcolor="#1e1e1c", bordercolor="rgba(255,255,255,0.1)",
                        font=dict(family=FONT, color="#f0ede8", size=13)),
    )
    return fig
 
 
def build_macro_chart(log: dict, selected_date: str) -> go.Figure:
    recipes = log.get(selected_date, [])
    if not recipes:
        fig = go.Figure()
        fig.add_annotation(text="No meals logged for this day",
                           x=0.5, y=0.5, showarrow=False,
                           font=dict(size=14, color="#5f5e5a", family=FONT))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          height=200, margin=dict(l=0,r=0,t=0,b=0))
        return fig
 
    totals = {"protein": 0, "carbs": 0, "fat": 0}
    for r in recipes:
        totals["protein"] += r.get("protein", 0)
        totals["carbs"]   += r.get("carbs", 0)
        totals["fat"]     += r.get("fat", 0)
 
    fig = go.Figure(go.Pie(
        labels=["Protein", "Carbs", "Fat"],
        values=[totals["protein"], totals["carbs"], totals["fat"]],
        hole=0.6,
        marker=dict(
            colors=[MACRO_COLORS["protein"], MACRO_COLORS["carbs"], MACRO_COLORS["fat"]],
            line=dict(color="#0f0f0d", width=3),
        ),
        hovertemplate="<b>%{label}</b><br>%{value}g (%{percent})<extra></extra>",
        textinfo="none", direction="clockwise", sort=False,
    ))
    total_kcal = sum(r["calories"] for r in recipes)
    fig.add_annotation(
        text=f"<b>{total_kcal:,}</b><br>kcal",
        x=0.5, y=0.5, showarrow=False, align="center",
        font=dict(size=17, color="#f0ede8", family=FONT),
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0), height=200, showlegend=False,
        hoverlabel=dict(bgcolor="#1e1e1c", bordercolor="rgba(255,255,255,0.1)",
                        font=dict(family=FONT, color="#f0ede8", size=13)),
    )
    return fig
 
# ─────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────
app = dash.Dash(__name__, title="Student Meal Tracker")
 
app.index_string = """
<!DOCTYPE html>
<html>
<head>
  {%metas%}<title>{%title%}</title>{%favicon%}{%css%}
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f0f0d; min-height: 100vh; font-family: 'DM Sans', sans-serif; color: #f0ede8; }
 
    /* Search bar */
    .search-input {
      width: 100%; padding: 12px 16px; background: #1a1a17;
      border: 1px solid rgba(255,255,255,0.1); border-radius: 10px;
      color: #f0ede8; font-size: 14px; font-family: 'DM Sans', sans-serif;
      outline: none; transition: border-color 0.15s;
    }
    .search-input:focus { border-color: #378ADD; }
    .search-input::placeholder { color: #5f5e5a; }
 
    /* Recipe cards */
    .recipe-card {
      display: flex; align-items: center; gap: 12px;
      background: #1a1a17; border: 1px solid rgba(255,255,255,0.07);
      border-radius: 10px; padding: 10px 14px; cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
    }
    .recipe-card:hover { border-color: #378ADD; background: #1e2830; }
    .recipe-thumb {
      width: 48px; height: 48px; border-radius: 8px;
      object-fit: cover; flex-shrink: 0; background: #222;
    }
    .recipe-title { font-size: 13px; font-weight: 500; color: #f0ede8; margin-bottom: 2px; }
    .recipe-kcal  { font-size: 12px; color: #5f5e5a; }
    .recipe-add   {
      margin-left: auto; background: #378ADD22; border: 1px solid #378ADD55;
      color: #378ADD; border-radius: 6px; padding: 4px 12px;
      font-size: 12px; font-weight: 500; cursor: pointer; white-space: nowrap;
      transition: background 0.15s;
    }
    .recipe-add:hover { background: #378ADD44; }
 
    /* Day tabs */
    .day-tab {
      padding: 8px 16px; border-radius: 50px; cursor: pointer; font-size: 13px;
      font-weight: 500; border: 1px solid rgba(255,255,255,0.07);
      background: #1a1a17; color: #888780; transition: all 0.15s; white-space: nowrap;
    }
    .day-tab:hover { border-color: rgba(255,255,255,0.2); color: #f0ede8; }
    .day-tab.active { background: #378ADD22; border-color: #378ADD; color: #378ADD; }
 
    /* Logged meal chips */
    .meal-chip {
      display: flex; align-items: center; gap: 8px;
      background: #222220; border: 1px solid rgba(255,255,255,0.07);
      border-radius: 8px; padding: 8px 12px; font-size: 13px;
    }
    .meal-chip-remove {
      margin-left: auto; color: #E24B4A; cursor: pointer;
      font-size: 16px; line-height: 1; opacity: 0.6;
    }
    .meal-chip-remove:hover { opacity: 1; }
 
    /* Panels */
    .panel {
      background: #1a1a17; border: 1px solid rgba(255,255,255,0.07);
      border-radius: 16px; padding: 20px;
    }
    .section-label {
      font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase;
      color: #5f5e5a; margin-bottom: 14px;
    }
 
    /* Metric cards */
    .metric-card {
      background: #1a1a17; border: 1px solid rgba(255,255,255,0.07);
      border-radius: 14px; padding: 16px 20px; flex: 1; min-width: 140px;
    }
    .metric-label { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: #5f5e5a; margin-bottom: 4px; }
    .metric-value { font-size: 22px; font-weight: 600; }
    .metric-sub   { font-size: 11px; color: #5f5e5a; margin-top: 2px; }
 
    /* Spinner */
    .spinner { color: #5f5e5a; font-size: 13px; padding: 12px 0; text-align: center; }
 
    /* Status badge */
    .status-badge {
      display: inline-block; font-size: 11px; font-weight: 500;
      padding: 3px 10px; border-radius: 20px;
    }
    .status-over   { background: #E24B4A22; color: #E24B4A; border: 1px solid #E24B4A44; }
    .status-ok     { background: #5AAF3222; color: #5AAF32; border: 1px solid #5AAF3244; }
    .status-under  { background: #378ADD22; color: #378ADD; border: 1px solid #378ADD44; }
  </style>
</head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>
"""
 
app.layout = html.Div([
 
    # ── Stores ──
    dcc.Store(id="meal-log",        data={}),     # {date: [{title, calories, protein, carbs, fat}]}
    dcc.Store(id="selected-date",   data=DATES[-1]),
    dcc.Store(id="search-results",  data=[]),
 
    html.Div([
 
        # ══════════ HEADER ══════════
        html.Div([
            html.Div([
                html.P("🥗 Student Meal Tracker", style={"fontSize": "11px", "color": "#5f5e5a", "letterSpacing": "0.08em", "textTransform": "uppercase", "marginBottom": "4px"}),
                html.H1("Weekly Nutrition", style={"fontSize": "28px", "fontWeight": "600"}),
            ]),
            html.Div([
                html.Div([
                    html.Span(style={"width": "10px", "height": "10px", "borderRadius": "3px", "background": c, "display": "inline-block", "marginRight": "6px"}),
                    html.Span(label, style={"fontSize": "12px", "color": "#5f5e5a", "marginRight": "14px"}),
                ], style={"display": "inline-flex", "alignItems": "center"})
                for c, label in [("#378ADD", "Under"), ("#5AAF32", "On target"), ("#E24B4A", "Over")]
            ], style={"display": "flex", "flexWrap": "wrap", "alignItems": "center"}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-end",
                  "flexWrap": "wrap", "gap": "12px", "marginBottom": "28px"}),
 
        # ══════════ BAR CHART ══════════
        html.Div([
            dcc.Graph(id="bar-chart", figure=build_bar_chart({}),
                      config={"displayModeBar": False}),
        ], className="panel", style={"marginBottom": "20px"}),
 
        # ══════════ DAY SELECTOR ══════════
        html.Div([
            html.Button(
                [html.Span(lbl, style={"display": "block", "fontWeight": "500"}),
                 html.Span(d[5:], style={"fontSize": "10px", "color": "#5f5e5a"})],
                id={"type": "day-tab", "index": d},
                className="day-tab" + (" active" if d == DATES[-1] else ""),
                n_clicks=0,
            )
            for d, lbl in zip(DATES, LABELS)
        ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap", "marginBottom": "20px"}),
 
        # ══════════ MAIN ROW ══════════
        html.Div([
 
            # ── LEFT: Search + log ──
            html.Div([
 
                # Search
                html.Div([
                    html.P("Search recipes", className="section-label"),
                    dcc.Input(
                        id="search-input", type="text",
                        placeholder="e.g. pasta, chicken salad, oatmeal…",
                        debounce=True, debounce_wait=600,
                        className="search-input",
                    ),
                    html.Div(id="search-spinner"),
                    html.Div(id="search-results-list",
                             style={"marginTop": "12px", "display": "flex", "flexDirection": "column", "gap": "8px"}),
                ], className="panel", style={"marginBottom": "16px"}),
 
                # Logged meals
                html.Div([
                    html.Div([
                        html.P("Logged meals", className="section-label", style={"margin": "0"}),
                        html.Div(id="day-status-badge"),
                    ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "14px"}),
                    html.Div(id="logged-meals-list"),
                ], className="panel"),
 
            ], style={"flex": "1", "minWidth": "280px"}),
 
            # ── RIGHT: Macro donut + macro bars ──
            html.Div([
                html.Div([
                    html.P("Macro split", className="section-label"),
                    dcc.Graph(id="macro-chart", figure=build_macro_chart({}, DATES[-1]),
                              config={"displayModeBar": False}),
                    # Legend
                    html.Div([
                        html.Div([
                            html.Span(style={"width": "10px", "height": "10px", "borderRadius": "2px",
                                             "background": MACRO_COLORS[k], "display": "inline-block", "marginRight": "6px"}),
                            html.Span(k.capitalize(), style={"fontSize": "12px", "color": "#888780"}),
                        ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"})
                        for k in ["protein", "carbs", "fat"]
                    ], style={"marginTop": "12px"}),
                ], className="panel", style={"marginBottom": "16px"}),
 
                # Macro totals
                html.Div(id="macro-totals-panel", className="panel"),
 
            ], style={"flex": "0 0 240px", "minWidth": "200px"}),
 
        ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "marginBottom": "20px"}),
 
        # ══════════ WEEKLY METRICS ══════════
        html.Div([
            html.Div([
                html.P("Avg / day", className="metric-label"),
                html.P(id="metric-avg", children="—", className="metric-value"),
                html.P("kcal", className="metric-sub"),
            ], className="metric-card"),
            html.Div([
                html.P("Days on target", className="metric-label"),
                html.P(id="metric-on-target", children="—", className="metric-value"),
                html.P("out of 7", className="metric-sub"),
            ], className="metric-card"),
            html.Div([
                html.P("Weekly total", className="metric-label"),
                html.P(id="metric-weekly", children="—", className="metric-value"),
                html.P("kcal", className="metric-sub"),
            ], className="metric-card"),
            html.Div([
                html.P("Best day", className="metric-label"),
                html.P(id="metric-best", children="—", className="metric-value"),
                html.P("closest to goal", className="metric-sub"),
            ], className="metric-card"),
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}),
 
    ], style={"maxWidth": "900px", "margin": "0 auto", "padding": "40px 20px"}),
 
], style={"fontFamily": FONT})
 
 
# ─────────────────────────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────────────────────────
 
# 1. Update selected date when a day tab is clicked
@app.callback(
    Output("selected-date", "data"),
    Input({"type": "day-tab", "index": dash.ALL}, "n_clicks"),
    State("selected-date", "data"),
    prevent_initial_call=True,
)
def update_selected_date(_, current):
    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        return triggered["index"]
    return current
 
 
# 2. Style day tabs
@app.callback(
    Output({"type": "day-tab", "index": dash.ALL}, "className"),
    Input("selected-date", "data"),
)
def style_day_tabs(selected):
    return ["day-tab active" if d == selected else "day-tab" for d in DATES]
 
 
# 3. Search Spoonacular
@app.callback(
    Output("search-results",      "data"),
    Output("search-results-list", "children"),
    Output("search-spinner",      "children"),
    Input("search-input", "value"),
    prevent_initial_call=True,
)
def do_search(query):
    if not query or len(query.strip()) < 2:
        return [], [], ""
 
    results = search_recipes(query)
 
    if not results:
        return [], [html.P("No results found.", style={"color": "#5f5e5a", "fontSize": "13px", "marginTop": "8px"})], ""
 
    cards = []
    for r in results:
        cards.append(html.Div([
            html.Img(src=r["image"], className="recipe-thumb",
                     style={"display": "block" if r["image"] else "none"}),
            html.Div([
                html.P(r["title"], className="recipe-title",
                       style={"whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis", "maxWidth": "220px"}),
                html.P(f"{r['calories']} kcal", className="recipe-kcal"),
            ], style={"flex": "1", "minWidth": "0"}),
            html.Button("+ Add", id={"type": "add-recipe-btn", "index": r["id"]},
                        className="recipe-add", n_clicks=0),
        ], className="recipe-card"))
 
    return results, cards, ""
 
 
# 4. Add recipe to meal log
@app.callback(
    Output("meal-log", "data"),
    Input({"type": "add-recipe-btn", "index": dash.ALL}, "n_clicks"),
    State("meal-log",       "data"),
    State("selected-date",  "data"),
    State("search-results", "data"),
    prevent_initial_call=True,
)
def add_recipe_to_log(n_clicks_list, log, selected_date, search_results):
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return log
 
    # Only fire if the click count > 0
    recipe_id = triggered["index"]
    click_idx = next((i for i, r in enumerate(search_results) if r["id"] == recipe_id), None)
    if click_idx is None or n_clicks_list[click_idx] == 0:
        return log
 
    # Find recipe in search results
    recipe = next((r for r in search_results if r["id"] == recipe_id), None)
    if not recipe:
        return log
 
    # Fetch full nutrition from Spoonacular
    nutrition = get_recipe_nutrition(recipe_id)
 
    entry = {
        "id":       recipe_id,
        "title":    recipe["title"],
        "calories": nutrition["calories"] or recipe["calories"],
        "protein":  nutrition["protein"],
        "carbs":    nutrition["carbs"],
        "fat":      nutrition["fat"],
    }
 
    log = dict(log)
    if selected_date not in log:
        log[selected_date] = []
    log[selected_date] = list(log[selected_date]) + [entry]
    return log
 
 
# 5. Remove recipe from log
@app.callback(
    Output("meal-log", "data", allow_duplicate=True),
    Input({"type": "remove-meal-btn", "index": dash.ALL}, "n_clicks"),
    State("meal-log",      "data"),
    State("selected-date", "data"),
    prevent_initial_call=True,
)
def remove_meal(n_clicks_list, log, selected_date):
    triggered = ctx.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return log
    remove_idx = triggered["index"]
    if n_clicks_list[remove_idx] == 0:
        return log
    log = dict(log)
    meals = list(log.get(selected_date, []))
    if 0 <= remove_idx < len(meals):
        meals.pop(remove_idx)
    log[selected_date] = meals
    return log
 
 
# 6. Update all visuals when log or selected date changes
@app.callback(
    Output("bar-chart",          "figure"),
    Output("macro-chart",        "figure"),
    Output("logged-meals-list",  "children"),
    Output("macro-totals-panel", "children"),
    Output("day-status-badge",   "children"),
    Output("metric-avg",         "children"),
    Output("metric-on-target",   "children"),
    Output("metric-weekly",      "children"),
    Output("metric-best",        "children"),
    Input("meal-log",      "data"),
    Input("selected-date", "data"),
)
def update_all(log, selected_date):
    # Bar chart
    bar_fig = build_bar_chart(log, selected_date)
 
    # Macro donut
    macro_fig = build_macro_chart(log, selected_date)
 
    # Logged meals list
    day_meals = log.get(selected_date, [])
    if day_meals:
        chips = []
        for i, m in enumerate(day_meals):
            chips.append(html.Div([
                html.Span("🍽", style={"fontSize": "16px"}),
                html.Div([
                    html.P(m["title"], style={"fontSize": "13px", "fontWeight": "500",
                                              "whiteSpace": "nowrap", "overflow": "hidden",
                                              "textOverflow": "ellipsis", "maxWidth": "240px"}),
                    html.P(f"{m['calories']} kcal · {m.get('protein',0)}g protein · {m.get('carbs',0)}g carbs · {m.get('fat',0)}g fat",
                           style={"fontSize": "11px", "color": "#5f5e5a"}),
                ], style={"flex": "1", "minWidth": "0"}),
                html.Span("✕", id={"type": "remove-meal-btn", "index": i},
                          className="meal-chip-remove", n_clicks=0),
            ], className="meal-chip", style={"marginBottom": "8px"}))
        meal_list = chips
    else:
        meal_list = html.P("No meals logged yet. Search and add recipes above.",
                           style={"fontSize": "13px", "color": "#5f5e5a", "textAlign": "center", "padding": "16px 0"})
 
    # Macro totals panel
    totals_day = {"protein": 0, "carbs": 0, "fat": 0, "calories": 0}
    for m in day_meals:
        totals_day["protein"]  += m.get("protein", 0)
        totals_day["carbs"]    += m.get("carbs", 0)
        totals_day["fat"]      += m.get("fat", 0)
        totals_day["calories"] += m.get("calories", 0)
 
    macro_panel = [
        html.P("Daily totals", className="section-label"),
        *[
            html.Div([
                html.Div(style={"width": "10px", "height": "10px", "borderRadius": "2px",
                                "background": MACRO_COLORS[k], "flexShrink": "0"}),
                html.Span(k.capitalize(), style={"fontSize": "13px", "color": "#888780", "flex": "1"}),
                html.Span(f"{totals_day[k]}{'g' if k != 'calories' else ' kcal'}",
                          style={"fontSize": "13px", "fontWeight": "500"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "8px", "marginBottom": "10px"})
            for k in ["calories", "protein", "carbs", "fat"]
        ]
    ]
 
    # Day status badge
    day_total = totals_day["calories"]
    if day_total == 0:
        badge = html.Span("No data", className="status-badge", style={"background": "#22221f", "color": "#5f5e5a", "border": "1px solid #333"})
    elif day_total > CALORIE_GOAL + 150:
        badge = html.Span(f"Over by {day_total - CALORIE_GOAL:,} kcal", className="status-badge status-over")
    elif day_total < CALORIE_GOAL - 150:
        badge = html.Span(f"Under by {CALORIE_GOAL - day_total:,} kcal", className="status-badge status-under")
    else:
        badge = html.Span("On target ✓", className="status-badge status-ok")
 
    # Weekly metrics
    all_totals = [sum(m["calories"] for m in log.get(d, [])) for d in DATES]
    logged_totals = [t for t in all_totals if t > 0]
    avg_val     = f"{round(sum(logged_totals)/len(logged_totals)):,}" if logged_totals else "—"
    on_target   = sum(1 for t in all_totals if CALORIE_GOAL - 150 <= t <= CALORIE_GOAL + 150 and t > 0)
    weekly_val  = f"{sum(all_totals):,}" if any(t > 0 for t in all_totals) else "—"
    best_days   = [(abs(t - CALORIE_GOAL), lbl) for t, lbl in zip(all_totals, LABELS) if t > 0]
    best_val    = min(best_days)[1] if best_days else "—"
 
    return (bar_fig, macro_fig, meal_list, macro_panel, badge,
            avg_val, f"{on_target} / 7", weekly_val, best_val)
 
 
# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🥗 Student Meal Tracker")
    print("─────────────────────────────")
    print("1. Add your Spoonacular API key to SPOONACULAR_API_KEY at the top of this file")
    print("   → Get a free key at: https://spoonacular.com/food-api")
    print("2. Run:  pip install dash plotly requests")
    print("3. Open: http://localhost:8050\n")
    app.run(debug=True, port=8050)


   
