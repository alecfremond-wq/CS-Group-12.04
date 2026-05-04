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

<<<<<<< feature/ml-recommendations
# Everything below this point used to be a standalone CLI calorie tracker script
# that someone accidentally pasted into the middle of this Streamlit page.
# It was never reachable (Streamlit had already finished rendering above),
# and the line of dashes right before it was breaking Python's parser entirely,
# causing the whole page to crash on load. Removed it cleanly — if you want
# that CLI tool back, it belongs in its own separate file, not here.
=======

st.subheader ("Nutrition facts for the past 7 days")
import streamlit as st
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Student Meal Tracker",
    page_icon="🥗",
    layout="wide",
)

# ─────────────────────────────────────────────────────────────
# CONFIGURATION  ← put your Spoonacular key here
# Get a free key at https://spoonacular.com/food-api
# ─────────────────────────────────────────────────────────────
SPOONACULAR_API_KEY = "YOUR_API_KEY_HERE"
SPOONACULAR_BASE    = "https://api.spoonacular.com"
CALORIE_GOAL        = 2000

# ─────────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Import font */
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&display=swap');

  html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

  /* Dark background */
  .stApp { background-color: #0f0f0d; color: #f0ede8; }

  /* Hide default header/footer */
  #MainMenu, footer, header { visibility: hidden; }

  /* Panels */
  .panel {
    background: #1a1a17;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    padding: 20px 22px;
    margin-bottom: 16px;
  }

  /* Section labels */
  .section-label {
    font-size: 11px; letter-spacing: 0.08em;
    text-transform: uppercase; color: #5f5e5a; margin-bottom: 12px;
  }

  /* Metric cards */
  .metric-card {
    background: #1a1a17;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px; padding: 16px 20px;
  }
  .metric-label { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: #5f5e5a; }
  .metric-value { font-size: 26px; font-weight: 600; color: #f0ede8; margin: 4px 0 2px; }
  .metric-sub   { font-size: 11px; color: #5f5e5a; }

  /* Recipe cards */
  .recipe-card {
    display: flex; align-items: center; gap: 12px;
    background: #222220; border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px; padding: 10px 14px; margin-bottom: 8px;
  }
  .recipe-title { font-size: 13px; font-weight: 500; color: #f0ede8; }
  .recipe-kcal  { font-size: 12px; color: #5f5e5a; }

  /* Meal chips */
  .meal-chip {
    display: flex; align-items: center; gap: 10px;
    background: #222220; border: 1px solid rgba(255,255,255,0.07);
    border-radius: 8px; padding: 10px 14px; margin-bottom: 8px;
  }
  .meal-chip-title { font-size: 13px; font-weight: 500; color: #f0ede8; }
  .meal-chip-sub   { font-size: 11px; color: #5f5e5a; }

  /* Status badges */
  .badge-over  { display:inline-block; background:#E24B4A22; color:#E24B4A; border:1px solid #E24B4A44; border-radius:20px; padding:3px 12px; font-size:12px; font-weight:500; }
  .badge-ok    { display:inline-block; background:#5AAF3222; color:#5AAF32; border:1px solid #5AAF3244; border-radius:20px; padding:3px 12px; font-size:12px; font-weight:500; }
  .badge-under { display:inline-block; background:#378ADD22; color:#378ADD; border:1px solid #378ADD44; border-radius:20px; padding:3px 12px; font-size:12px; font-weight:500; }
  .badge-none  { display:inline-block; background:#22221f;   color:#5f5e5a; border:1px solid #333;      border-radius:20px; padding:3px 12px; font-size:12px; font-weight:500; }

  /* Day selector buttons */
  div[data-testid="column"] button {
    width: 100%; background: #1a1a17 !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 50px !important; color: #888780 !important;
    font-size: 13px !important; padding: 8px 4px !important;
    transition: all 0.15s;
  }
  div[data-testid="column"] button:hover {
    border-color: rgba(255,255,255,0.2) !important; color: #f0ede8 !important;
  }

  /* Streamlit input */
  .stTextInput input {
    background: #1a1a17 !important; border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important; color: #f0ede8 !important;
    font-size: 14px !important;
  }
  .stTextInput input:focus { border-color: #378ADD !important; }

  /* Dividers */
  hr { border-color: rgba(255,255,255,0.06) !important; }

  /* Scrollable recipe list */
  .recipe-scroll { max-height: 340px; overflow-y: auto; padding-right: 4px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────
def last_7_days():
    today = datetime.today()
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]

DATES  = last_7_days()
LABELS = [datetime.strptime(d, "%Y-%m-%d").strftime("%a") for d in DATES]

if "meal_log"       not in st.session_state: st.session_state.meal_log       = {d: [] for d in DATES}
if "selected_date"  not in st.session_state: st.session_state.selected_date  = DATES[-1]
if "search_results" not in st.session_state: st.session_state.search_results = []
if "search_query"   not in st.session_state: st.session_state.search_query   = ""

# ─────────────────────────────────────────────────────────────
# SPOONACULAR HELPERS
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def search_recipes(query: str) -> list:
    if not query.strip(): return []
    try:
        r = requests.get(
            f"{SPOONACULAR_BASE}/recipes/complexSearch",
            params={"apiKey": SPOONACULAR_API_KEY, "query": query,
                    "number": 8, "addRecipeNutrition": True},
            timeout=8,
        )
        r.raise_for_status()
        out = []
        for item in r.json().get("results", []):
            kcal = 0
            for n in item.get("nutrition", {}).get("nutrients", []):
                if n.get("name") == "Calories":
                    kcal = round(n.get("amount", 0)); break
            out.append({"id": item["id"], "title": item["title"],
                        "image": item.get("image", ""), "calories": kcal})
        return out
    except Exception as e:
        st.error(f"Spoonacular error: {e}")
        return []

@st.cache_data(ttl=3600, show_spinner=False)
def get_nutrition(recipe_id: int) -> dict:
    try:
        r = requests.get(
            f"{SPOONACULAR_BASE}/recipes/{recipe_id}/nutritionWidget.json",
            params={"apiKey": SPOONACULAR_API_KEY}, timeout=8,
        )
        r.raise_for_status()
        def _val(key):
            for n in r.json().get("nutrients", []):
                if n.get("name") == key: return round(float(n.get("amount", 0)))
            return 0
        return {"calories": _val("Calories"), "protein": _val("Protein"),
                "carbs": _val("Carbohydrates"), "fat": _val("Fat")}
    except:
        return {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}

# ─────────────────────────────────────────────────────────────
# COLOR HELPERS
# ─────────────────────────────────────────────────────────────
def bar_color(total):
    if total > CALORIE_GOAL + 150: return "#E24B4A"
    if total < CALORIE_GOAL - 150: return "#378ADD"
    return "#5AAF32"

MACRO_COLORS = {"calories": "#F4A522", "protein": "#378ADD", "carbs": "#9B6FD8", "fat": "#E24B4A"}
FONT = "DM Sans, Segoe UI, sans-serif"

# ─────────────────────────────────────────────────────────────
# CHART BUILDERS
# ─────────────────────────────────────────────────────────────
def build_bar_chart(selected_date):
    log    = st.session_state.meal_log
    totals = [sum(m["calories"] for m in log.get(d, [])) for d in DATES]
    sel_i  = DATES.index(selected_date) if selected_date in DATES else None

    colors = []
    for i, t in enumerate(totals):
        c = bar_color(t)
        colors.append(c if sel_i is None or i == sel_i else "rgba(255,255,255,0.07)")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=LABELS, y=totals,
        marker=dict(color=colors, cornerradius=8),
        hovertemplate="<b>%{x}</b><br>%{y:,} kcal<extra></extra>",
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=LABELS, y=[CALORIE_GOAL]*7, mode="lines",
        line=dict(color="rgba(255,255,255,0.2)", width=1.5, dash="dot"),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_annotation(
        x=LABELS[-1], y=CALORIE_GOAL,
        text=f"Goal {CALORIE_GOAL:,}", showarrow=False,
        xanchor="right", yanchor="bottom", yshift=6,
        font=dict(size=11, color="rgba(255,255,255,0.25)", family=FONT),
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0), height=240,
        font=dict(family=FONT, color="#888780"),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=13, color="#888780")),
        yaxis=dict(
            range=[0, max(max(totals, default=0)+500, CALORIE_GOAL+600)],
            showgrid=True, gridcolor="rgba(255,255,255,0.05)",
            zeroline=False, tickfont=dict(size=11, color="#555"), tickformat=",",
        ),
        bargap=0.35,
        hoverlabel=dict(bgcolor="#1e1e1c", font=dict(family=FONT, color="#f0ede8", size=13)),
    )
    return fig


def build_macro_donut(selected_date):
    meals = st.session_state.meal_log.get(selected_date, [])
    p = sum(m.get("protein", 0) for m in meals)
    c = sum(m.get("carbs",   0) for m in meals)
    f = sum(m.get("fat",     0) for m in meals)
    total_kcal = sum(m.get("calories", 0) for m in meals)

    if not meals:
        fig = go.Figure()
        fig.add_annotation(text="No meals logged", x=0.5, y=0.5, showarrow=False,
                           font=dict(size=13, color="#5f5e5a", family=FONT))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=200,
                          margin=dict(l=0,r=0,t=0,b=0))
        return fig

    fig = go.Figure(go.Pie(
        labels=["Protein", "Carbs", "Fat"], values=[p, c, f], hole=0.62,
        marker=dict(colors=[MACRO_COLORS["protein"], MACRO_COLORS["carbs"], MACRO_COLORS["fat"]],
                    line=dict(color="#0f0f0d", width=3)),
        hovertemplate="<b>%{label}</b><br>%{value}g (%{percent})<extra></extra>",
        textinfo="none", direction="clockwise", sort=False,
    ))
    fig.add_annotation(
        text=f"<b>{total_kcal:,}</b><br>kcal",
        x=0.5, y=0.5, showarrow=False, align="center",
        font=dict(size=16, color="#f0ede8", family=FONT),
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=0,b=0),
        height=200, showlegend=False,
        hoverlabel=dict(bgcolor="#1e1e1c", font=dict(family=FONT, color="#f0ede8", size=13)),
    )
    return fig

# ─────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────

# ── Header ──
log     = st.session_state.meal_log
totals  = [sum(m["calories"] for m in log.get(d, [])) for d in DATES]
logged  = [t for t in totals if t > 0]
avg_val = f"{round(sum(logged)/len(logged)):,}" if logged else "—"

st.markdown(f"""
<div style="margin-bottom:28px">
  <p style="font-size:11px;color:#5f5e5a;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px">🥗 Student Meal Tracker</p>
  <h1 style="font-size:30px;font-weight:600;color:#f0ede8;margin:0">Weekly Nutrition</h1>
  <p style="font-size:14px;color:#5f5e5a;margin-top:4px">{avg_val} kcal average per day · goal {CALORIE_GOAL:,} kcal</p>
</div>
""", unsafe_allow_html=True)

# ── Bar chart ──
st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown('<p class="section-label">7-day calorie overview</p>', unsafe_allow_html=True)
st.plotly_chart(build_bar_chart(st.session_state.selected_date),
                use_container_width=True, config={"displayModeBar": False})

# Legend row
st.markdown("""
<div style="display:flex;gap:16px;margin-top:-8px;flex-wrap:wrap">
  <span style="font-size:12px;color:#5f5e5a;display:flex;align-items:center;gap:6px">
    <span style="width:10px;height:10px;border-radius:2px;background:#378ADD;display:inline-block"></span>Under goal
  </span>
  <span style="font-size:12px;color:#5f5e5a;display:flex;align-items:center;gap:6px">
    <span style="width:10px;height:10px;border-radius:2px;background:#5AAF32;display:inline-block"></span>On target
  </span>
  <span style="font-size:12px;color:#5f5e5a;display:flex;align-items:center;gap:6px">
    <span style="width:10px;height:10px;border-radius:2px;background:#E24B4A;display:inline-block"></span>Over goal
  </span>
</div>
""", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Day selector ──
st.markdown('<p class="section-label">Select a day to log meals</p>', unsafe_allow_html=True)
day_cols = st.columns(7)
for i, (col, date, lbl) in enumerate(zip(day_cols, DATES, LABELS)):
    day_total = sum(m["calories"] for m in log.get(date, []))
    dot = "🟢" if CALORIE_GOAL-150 <= day_total <= CALORIE_GOAL+150 and day_total > 0 \
          else ("🔴" if day_total > CALORIE_GOAL+150 else ("🔵" if day_total > 0 else ""))
    label = f"{lbl}\n{dot}" if dot else lbl
    if col.button(label, key=f"day_{date}", use_container_width=True):
        st.session_state.selected_date = date
        st.rerun()

selected = st.session_state.selected_date
selected_label = datetime.strptime(selected, "%Y-%m-%d").strftime("%A, %b %d")

st.markdown("<br>", unsafe_allow_html=True)

# ── Main columns ──
left_col, right_col = st.columns([3, 2], gap="large")

# ════════════════════════════════════
# LEFT — Search + logged meals
# ════════════════════════════════════
with left_col:

    # Search
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<p class="section-label">Search recipes (Spoonacular)</p>', unsafe_allow_html=True)

    query = st.text_input("", placeholder="e.g. pasta, chicken salad, oatmeal…",
                          label_visibility="collapsed", key="search_box")

    if query and query != st.session_state.search_query:
        st.session_state.search_query   = query
        with st.spinner("Searching recipes…"):
            st.session_state.search_results = search_recipes(query)

    results = st.session_state.search_results
    if results:
        st.markdown(f'<p style="font-size:12px;color:#5f5e5a;margin-bottom:10px">{len(results)} results for "{query}"</p>', unsafe_allow_html=True)
        for r in results:
            r_col1, r_col2, r_col3 = st.columns([1, 4, 1])
            with r_col1:
                if r["image"]:
                    st.image(r["image"], width=52)
                else:
                    st.markdown('<div style="width:52px;height:52px;background:#222;border-radius:8px"></div>', unsafe_allow_html=True)
            with r_col2:
                st.markdown(f"""
                <div style="padding:4px 0">
                  <p class="recipe-title">{r['title']}</p>
                  <p class="recipe-kcal">{r['calories']} kcal</p>
                </div>
                """, unsafe_allow_html=True)
            with r_col3:
                if st.button("＋ Add", key=f"add_{r['id']}_{selected}", use_container_width=True):
                    with st.spinner("Fetching nutrition…"):
                        nutrition = get_nutrition(r["id"])
                    entry = {
                        "id":       r["id"],
                        "title":    r["title"],
                        "calories": nutrition["calories"] or r["calories"],
                        "protein":  nutrition["protein"],
                        "carbs":    nutrition["carbs"],
                        "fat":      nutrition["fat"],
                    }
                    st.session_state.meal_log[selected].append(entry)
                    st.success(f"Added {r['title']} to {selected_label}!")
                    st.rerun()
            st.markdown('<hr style="margin:4px 0;border-color:rgba(255,255,255,0.05)">', unsafe_allow_html=True)
    elif query:
        st.markdown('<p style="color:#5f5e5a;font-size:13px;padding:8px 0">No results found.</p>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # Logged meals
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    day_meals  = st.session_state.meal_log.get(selected, [])
    day_total  = sum(m["calories"] for m in day_meals)

    # Status badge
    if day_total == 0:
        badge = '<span class="badge-none">No meals logged</span>'
    elif day_total > CALORIE_GOAL + 150:
        badge = f'<span class="badge-over">Over by {day_total - CALORIE_GOAL:,} kcal</span>'
    elif day_total < CALORIE_GOAL - 150:
        badge = f'<span class="badge-under">Under by {CALORIE_GOAL - day_total:,} kcal</span>'
    else:
        badge = '<span class="badge-ok">On target ✓</span>'

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <p class="section-label" style="margin:0">Logged meals · {selected_label}</p>
      {badge}
    </div>
    """, unsafe_allow_html=True)

    if day_meals:
        for i, m in enumerate(day_meals):
            m_col1, m_col2 = st.columns([6, 1])
            with m_col1:
                st.markdown(f"""
                <div class="meal-chip">
                  <span style="font-size:18px">🍽</span>
                  <div>
                    <p class="meal-chip-title">{m['title']}</p>
                    <p class="meal-chip-sub">{m['calories']} kcal &nbsp;·&nbsp; {m.get('protein',0)}g protein &nbsp;·&nbsp; {m.get('carbs',0)}g carbs &nbsp;·&nbsp; {m.get('fat',0)}g fat</p>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            with m_col2:
                if st.button("✕", key=f"remove_{selected}_{i}", help="Remove meal"):
                    st.session_state.meal_log[selected].pop(i)
                    st.rerun()
    else:
        st.markdown('<p style="color:#5f5e5a;font-size:13px;text-align:center;padding:20px 0">No meals yet. Search and add recipes above ↑</p>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ════════════════════════════════════
# RIGHT — Macro chart + totals
# ════════════════════════════════════
with right_col:

    # Donut
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<p class="section-label">Macro split</p>', unsafe_allow_html=True)
    st.plotly_chart(build_macro_donut(selected),
                    use_container_width=True, config={"displayModeBar": False})

    # Legend
    st.markdown("""
    <div style="display:flex;flex-direction:column;gap:6px;margin-top:8px">
    """, unsafe_allow_html=True)
    for k, label in [("protein","Protein"), ("carbs","Carbs"), ("fat","Fat")]:
        val = sum(m.get(k, 0) for m in st.session_state.meal_log.get(selected, []))
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px">
          <span style="width:10px;height:10px;border-radius:2px;background:{MACRO_COLORS[k]};display:inline-block;flex-shrink:0"></span>
          <span style="font-size:13px;color:#888780;flex:1">{label}</span>
          <span style="font-size:13px;font-weight:500;color:#f0ede8">{val}g</span>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Progress bar vs goal
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<p class="section-label">Daily progress</p>', unsafe_allow_html=True)
    pct = min(round((day_total / CALORIE_GOAL) * 100), 100) if day_total else 0
    fill_color = bar_color(day_total)
    st.markdown(f"""
    <div style="margin-bottom:8px">
      <div style="display:flex;justify-content:space-between;font-size:12px;color:#5f5e5a;margin-bottom:6px">
        <span>{day_total:,} kcal consumed</span><span>{CALORIE_GOAL:,} kcal goal</span>
      </div>
      <div style="background:rgba(255,255,255,0.06);border-radius:6px;height:10px;overflow:hidden">
        <div style="width:{pct}%;height:100%;background:{fill_color};border-radius:6px;transition:width 0.4s ease"></div>
      </div>
      <p style="font-size:11px;color:#5f5e5a;margin-top:6px;text-align:right">{pct}% of daily goal</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ════════════════════════════════════
# BOTTOM — Weekly metrics
# ════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<p class="section-label">Weekly summary</p>', unsafe_allow_html=True)

logged_totals = [t for t in totals if t > 0]
weekly_avg    = f"{round(sum(logged_totals)/len(logged_totals)):,}" if logged_totals else "—"
on_target_cnt = sum(1 for t in totals if CALORIE_GOAL-150 <= t <= CALORIE_GOAL+150 and t > 0)
weekly_sum    = f"{sum(totals):,}" if any(t > 0 for t in totals) else "—"
best_days     = [(abs(t-CALORIE_GOAL), lbl) for t, lbl in zip(totals, LABELS) if t > 0]
best_day_lbl  = min(best_days)[1] if best_days else "—"

m1, m2, m3, m4 = st.columns(4)
for col, label, value, sub in [
    (m1, "Avg / day",      weekly_avg,           "kcal"),
    (m2, "Days on target", f"{on_target_cnt} / 7","within ±150 kcal"),
    (m3, "Weekly total",   weekly_sum,            "kcal this week"),
    (m4, "Best day",       best_day_lbl,          "closest to goal"),
]:
    col.markdown(f"""
    <div class="metric-card">
      <p class="metric-label">{label}</p>
      <p class="metric-value">{value}</p>
      <p class="metric-sub">{sub}</p>
    </div>
    """, unsafe_allow_html=True)

