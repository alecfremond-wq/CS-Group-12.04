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
import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─────────────────────────────────────────────────────────────
# DATA — replace with your real backend data
# ─────────────────────────────────────────────────────────────
GOAL = 2000  # daily calorie goal (kcal)

days = [
    {"label": "Mon", "total": 1840, "meals": [{"name": "Breakfast", "kcal": 420}, {"name": "Lunch", "kcal": 680}, {"name": "Snacks", "kcal": 210}, {"name": "Dinner", "kcal": 530}]},
    {"label": "Tue", "total": 2210, "meals": [{"name": "Breakfast", "kcal": 510}, {"name": "Lunch", "kcal": 750}, {"name": "Snacks", "kcal": 380}, {"name": "Dinner", "kcal": 570}]},
    {"label": "Wed", "total": 1760, "meals": [{"name": "Breakfast", "kcal": 390}, {"name": "Lunch", "kcal": 620}, {"name": "Snacks", "kcal": 150}, {"name": "Dinner", "kcal": 600}]},
    {"label": "Thu", "total": 2450, "meals": [{"name": "Breakfast", "kcal": 640}, {"name": "Lunch", "kcal": 820}, {"name": "Snacks", "kcal": 430}, {"name": "Dinner", "kcal": 560}]},
    {"label": "Fri", "total": 1980, "meals": [{"name": "Breakfast", "kcal": 470}, {"name": "Lunch", "kcal": 700}, {"name": "Snacks", "kcal": 280}, {"name": "Dinner", "kcal": 530}]},
    {"label": "Sat", "total": 2330, "meals": [{"name": "Breakfast", "kcal": 590}, {"name": "Lunch", "kcal": 780}, {"name": "Snacks", "kcal": 410}, {"name": "Dinner", "kcal": 550}]},
    {"label": "Sun", "total": 1650, "meals": [{"name": "Breakfast", "kcal": 350}, {"name": "Lunch", "kcal": 580}, {"name": "Snacks", "kcal": 190}, {"name": "Dinner", "kcal": 530}]},
]

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def bar_color(total):
    if total > GOAL + 150:  return "#E24B4A"   # over
    if total < GOAL - 150:  return "#378ADD"   # under
    return "#5AAF32"                            # on target

MEAL_COLORS = {
    "Breakfast": "#F4A522",
    "Lunch":     "#378ADD",
    "Snacks":    "#9B6FD8",
    "Dinner":    "#5AAF32",
}

totals = [d["total"] for d in days]
labels = [d["label"] for d in days]
colors = [bar_color(t) for t in totals]
avg    = round(sum(totals) / len(totals))
best   = min(days, key=lambda d: abs(d["total"] - GOAL))
on_goal_count = sum(1 for t in totals if GOAL - 150 <= t <= GOAL + 150)
weekly_total  = sum(totals)

# ─────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────
app = dash.Dash(__name__, title="Weekly Calorie Tracker")

FONT = "'DM Sans', 'Segoe UI', sans-serif"

# Google Fonts import via index_string
app.index_string = """
<!DOCTYPE html>
<html>
<head>
  {%metas%}
  <title>{%title%}</title>
  {%favicon%}
  {%css%}
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f0f0d;
      min-height: 100vh;
      font-family: 'DM Sans', 'Segoe UI', sans-serif;
      color: #f0ede8;
    }
    .metric-card {
      background: #1a1a17;
      border: 1px solid rgba(255,255,255,0.07);
      border-radius: 14px;
      padding: 18px 22px;
      flex: 1;
      min-width: 160px;
    }
    .metric-label {
      font-size: 12px;
      color: #888780;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }
    .metric-value {
      font-size: 22px;
      font-weight: 600;
      color: #f0ede8;
    }
    .metric-sub {
      font-size: 12px;
      color: #5f5e5a;
      margin-top: 2px;
    }
    .day-pill {
      background: #1a1a17;
      border: 1px solid rgba(255,255,255,0.07);
      border-radius: 50px;
      padding: 8px 18px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 500;
      color: #888780;
      transition: all 0.15s;
      white-space: nowrap;
    }
    .day-pill:hover { border-color: rgba(255,255,255,0.2); color: #f0ede8; }
    .day-pill.selected {
      background: #378ADD22;
      border-color: #378ADD;
      color: #378ADD;
    }
    .section-title {
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #5f5e5a;
      margin-bottom: 14px;
    }
    .panel {
      background: #1a1a17;
      border: 1px solid rgba(255,255,255,0.07);
      border-radius: 16px;
      padding: 24px;
    }
  </style>
</head>
<body>
  {%app_entry%}
  <footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>
"""

def build_bar_chart(selected_idx=None):
    fig = go.Figure()

    bar_colors_highlight = []
    for i, c in enumerate(colors):
        if selected_idx is None or i == selected_idx:
            bar_colors_highlight.append(c)
        else:
            bar_colors_highlight.append("rgba(255,255,255,0.08)")

    # Bars
    fig.add_trace(go.Bar(
        x=labels,
        y=totals,
        marker=dict(
            color=bar_colors_highlight,
            cornerradius=8,
        ),
        hovertemplate="<b>%{x}</b><br>%{y:,} kcal<extra></extra>",
        showlegend=False,
    ))

    # Goal line
    fig.add_trace(go.Scatter(
        x=labels,
        y=[GOAL] * len(labels),
        mode="lines",
        line=dict(color="rgba(255,255,255,0.25)", width=1.5, dash="dot"),
        hoverinfo="skip",
        showlegend=False,
    ))

    # Goal annotation
    fig.add_annotation(
        x=labels[-1], y=GOAL,
        text=f"Goal {GOAL:,}",
        showarrow=False,
        xanchor="right",
        yanchor="bottom",
        font=dict(size=11, color="rgba(255,255,255,0.3)", family=FONT),
        yshift=6,
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
        height=260,
        font=dict(family=FONT, color="#888780"),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            tickfont=dict(size=13, color="#888780"),
        ),
        yaxis=dict(
            range=[1000, 2900],
            showgrid=True,
            gridcolor="rgba(255,255,255,0.05)",
            zeroline=False,
            tickfont=dict(size=11, color="#555"),
            tickformat=",",
        ),
        bargap=0.35,
        hoverlabel=dict(
            bgcolor="#1e1e1c",
            bordercolor="rgba(255,255,255,0.1)",
            font=dict(family=FONT, color="#f0ede8", size=13),
        ),
    )
    return fig


def build_donut(day_idx):
    d = days[day_idx]
    meal_names = [m["name"] for m in d["meals"]]
    meal_kcals = [m["kcal"] for m in d["meals"]]
    meal_cols  = [MEAL_COLORS.get(m, "#888") for m in meal_names]

    fig = go.Figure(go.Pie(
        labels=meal_names,
        values=meal_kcals,
        hole=0.65,
        marker=dict(colors=meal_cols, line=dict(color="#0f0f0d", width=3)),
        hovertemplate="<b>%{label}</b><br>%{value} kcal (%{percent})<extra></extra>",
        textinfo="none",
        direction="clockwise",
        sort=False,
    ))

    fig.add_annotation(
        text=f"<b>{d['total']:,}</b><br><span style='font-size:11px;color:#888'>kcal</span>",
        x=0.5, y=0.5,
        font=dict(size=18, color="#f0ede8", family=FONT),
        showarrow=False,
        align="center",
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=220,
        showlegend=False,
        hoverlabel=dict(
            bgcolor="#1e1e1c",
            bordercolor="rgba(255,255,255,0.1)",
            font=dict(family=FONT, color="#f0ede8", size=13),
        ),
    )
    return fig


def meal_breakdown_rows(day_idx):
    d = days[day_idx]
    rows = []
    for m in d["meals"]:
        pct = round(m["kcal"] / d["total"] * 100)
        col = MEAL_COLORS.get(m["name"], "#888")
        rows.append(
            html.Div([
                html.Div([
                    html.Span(m["name"], style={"fontSize": "13px", "color": "#888780", "minWidth": "80px", "display": "inline-block"}),
                    html.Div([
                        html.Div(style={
                            "width": f"{pct}%",
                            "height": "100%",
                            "background": col,
                            "borderRadius": "4px",
                            "transition": "width 0.4s ease",
                        })
                    ], style={
                        "flex": "1",
                        "height": "6px",
                        "background": "rgba(255,255,255,0.06)",
                        "borderRadius": "4px",
                        "margin": "0 12px",
                        "overflow": "hidden",
                    }),
                    html.Span(f"{m['kcal']} kcal", style={"fontSize": "13px", "fontWeight": "500", "minWidth": "64px", "textAlign": "right"}),
                ], style={"display": "flex", "alignItems": "center", "padding": "8px 0"}),
            ], style={"borderBottom": "1px solid rgba(255,255,255,0.05)"})
        )
    return rows


# ─────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────
app.layout = html.Div([
    html.Div([

        # ── Top header ──
        html.Div([
            html.Div([
                html.P("Past 7 days", style={"fontSize": "12px", "color": "#5f5e5a", "letterSpacing": "0.06em", "textTransform": "uppercase", "marginBottom": "4px"}),
                html.P(f"{avg:,} kcal avg / day", style={"fontSize": "26px", "fontWeight": "600", "color": "#f0ede8"}),
            ]),
            html.Div([
                html.Span("", style={"width": "10px", "height": "10px", "borderRadius": "3px", "background": "#378ADD", "display": "inline-block", "marginRight": "6px"}),
                html.Span("Under", style={"fontSize": "12px", "color": "#5f5e5a", "marginRight": "14px"}),
                html.Span("", style={"width": "10px", "height": "10px", "borderRadius": "3px", "background": "#5AAF32", "display": "inline-block", "marginRight": "6px"}),
                html.Span("On target", style={"fontSize": "12px", "color": "#5f5e5a", "marginRight": "14px"}),
                html.Span("", style={"width": "10px", "height": "10px", "borderRadius": "3px", "background": "#E24B4A", "display": "inline-block", "marginRight": "6px"}),
                html.Span("Over", style={"fontSize": "12px", "color": "#5f5e5a"}),
            ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap"}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-end", "flexWrap": "wrap", "gap": "12px", "marginBottom": "24px"}),

        # ── Bar chart ──
        dcc.Graph(
            id="bar-chart",
            figure=build_bar_chart(),
            config={"displayModeBar": False},
            style={"marginBottom": "24px"},
        ),

        # ── Day selector pills ──
        html.Div([
            html.Button(
                d["label"],
                id={"type": "day-pill", "index": i},
                className="day-pill" + (" selected" if i == 0 else ""),
                n_clicks=0,
            )
            for i, d in enumerate(days)
        ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap", "marginBottom": "24px"}),

        # ── Detail row: donut + meal list ──
        html.Div([

            # Donut
            html.Div([
                html.P("Meal split", className="section-title"),
                dcc.Graph(
                    id="donut-chart",
                    figure=build_donut(0),
                    config={"displayModeBar": False},
                ),
                # Donut legend
                html.Div([
                    html.Div([
                        html.Span(style={"width": "10px", "height": "10px", "borderRadius": "2px", "background": MEAL_COLORS[m], "display": "inline-block", "marginRight": "6px"}),
                        html.Span(m, style={"fontSize": "12px", "color": "#888780"}),
                    ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"})
                    for m in ["Breakfast", "Lunch", "Snacks", "Dinner"]
                ], style={"marginTop": "12px"}),
            ], className="panel", style={"flex": "0 0 220px"}),

            # Meal breakdown
            html.Div([
                html.P("Breakdown", className="section-title"),
                html.Div(id="meal-list", children=meal_breakdown_rows(0)),
            ], className="panel", style={"flex": "1"}),

        ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "marginBottom": "24px"}),

        # ── Metric cards ──
        html.Div([
            html.Div([
                html.P("Best day", className="metric-label"),
                html.P(f"{best['label']}", className="metric-value"),
                html.P(f"{best['total']:,} kcal — closest to goal", className="metric-sub"),
            ], className="metric-card"),
            html.Div([
                html.P("Days on target", className="metric-label"),
                html.P(f"{on_goal_count} / 7", className="metric-value"),
                html.P("within ±150 kcal of goal", className="metric-sub"),
            ], className="metric-card"),
            html.Div([
                html.P("Weekly total", className="metric-label"),
                html.P(f"{weekly_total:,}", className="metric-value"),
                html.P("kcal this week", className="metric-sub"),
            ], className="metric-card"),
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}),

    ], style={"maxWidth": "740px", "margin": "0 auto", "padding": "40px 20px"}),

    # Hidden store for selected day
    dcc.Store(id="selected-day", data=0),

], style={"fontFamily": FONT})


# ─────────────────────────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────────────────────────
@app.callback(
    Output("selected-day", "data"),
    Input({"type": "day-pill", "index": dash.ALL}, "n_clicks"),
    State("selected-day", "data"),
    prevent_initial_call=True,
)
def update_selected_day(n_clicks_list, current):
    ctx = dash.callback_context
    if not ctx.triggered:
        return current
    prop_id = ctx.triggered[0]["prop_id"]
    import json
    idx = json.loads(prop_id.split(".")[0])["index"]
    return idx


@app.callback(
    Output("bar-chart", "figure"),
    Output("donut-chart", "figure"),
    Output("meal-list", "children"),
    Input("selected-day", "data"),
)
def update_visuals(day_idx):
    return (
        build_bar_chart(day_idx),
        build_donut(day_idx),
        meal_breakdown_rows(day_idx),
    )


# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=8050)


   
