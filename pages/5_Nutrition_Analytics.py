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

----feature/ml-recommendations
# Everything below this point used to be a standalone CLI calorie tracker script
# that someone accidentally pasted into the middle of this Streamlit page.
# It was never reachable (Streamlit had already finished rendering above),
# and the line of dashes right before it was breaking Python's parser entirely,
# causing the whole page to crash on load. Removed it cleanly — if you want
# that CLI tool back, it belongs in its own separate file, not here.
-------

st.subheader ("Calorie intake of the past 7 days")
import streamlit as st
import pandas as pd
import altair as alt

# --- SET UP THE APPLICATION ---
st.set_page_config(page_title="Weekly Calorie Intake Dashboard", layout="wide")

# Custom CSS for UI styling
st.markdown("""
<style>
    .stApp { background-color: #fcfcfc; }
    .calorie-avg { font-size: 2.8rem; font-weight: bold; margin-bottom: 20px; }
    .dashboard-header { font-size: 1.2rem; color: #757575; }
    
    div.stButton > button {
        background-color: white;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        width: 100%;
        height: 80px;
    }
    
    .summary-card {
        background-color: #f8f8f8;
        border-radius: 12px;
        padding: 20px;
    }
    .summary-value { font-size: 1.8rem; font-weight: bold; }
</style>
""", unsafe_allow_stdio=True)

# --- DATA SETUP ---
DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAILY_GOAL = 2000

weekly_history = {
    "Mon": {"total": 1840, "breakdown": {"Breakfast": 420, "Lunch": 680, "Snacks": 210, "Dinner": 530}},
    "Tue": {"total": 2200, "breakdown": {"Breakfast": 500, "Lunch": 800, "Snacks": 300, "Dinner": 600}},
    "Wed": {"total": 1780, "breakdown": {"Breakfast": 400, "Lunch": 650, "Snacks": 200, "Dinner": 530}},
    "Thu": {"total": 2450, "breakdown": {"Breakfast": 550, "Lunch": 900, "Snacks": 400, "Dinner": 600}},
    "Fri": {"total": 1980, "breakdown": {"Breakfast": 450, "Lunch": 730, "Snacks": 250, "Dinner": 550}},
    "Sat": {"total": 2330, "breakdown": {"Breakfast": 520, "Lunch": 850, "Snacks": 360, "Dinner": 600}},
    "Sun": {"total": 1650, "breakdown": {"Breakfast": 380, "Lunch": 600, "Snacks": 180, "Dinner": 490}},
}

bar_data = []
for day, data in weekly_history.items():
    status = 'Goal'
    if data["total"] < DAILY_GOAL - 50: status = 'Under'
    elif data["total"] > DAILY_GOAL + 50: status = 'Over'
    bar_data.append({"Day": day, "Calories": data["total"], "Status": status, "Goal": DAILY_GOAL})

df = pd.DataFrame(bar_data)

# --- MAIN UI ---
st.markdown('<p class="dashboard-header">Past 7 days</p>', unsafe_allow_stdio=True)
st.markdown(f'<p class="calorie-avg">2,031 kcal avg/day</p>', unsafe_allow_stdio=True)

# Chart
chart = alt.Chart(df).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8, size=40).encode(
    x=alt.X('Day', sort=DAYS_OF_WEEK, title=None),
    y=alt.Y('Calories', title=None),
    color=alt.Color('Status', scale=alt.Scale(domain=['Under', 'Over', 'Goal'], range=['#3e88e2', '#e84c4c', '#72ac4c']), legend=None)
).properties(height=300)

goal_line = alt.Chart(df).mark_rule(strokeDash=[4, 4], color='#a0a0a0').encode(y='Goal')

st.altair_chart(chart + goal_line, use_container_width=True)

# Interaction State
if 'selected_day' not in st.session_state:
    st.session_state.selected_day = 'Mon'

# Day Cards
cols = st.columns(7)
for i, day in enumerate(DAYS_OF_WEEK):
    val = df.loc[df['Day'] == day, 'Calories'].values[0]
    if cols[i].button(f"{day}\n\n{val/1000:.1f}k", key=day):
        st.session_state.selected_day = day

# Breakdown Section
day_data = weekly_history[st.session_state.selected_day]
st.markdown(f"### {st.session_state.selected_day} — {day_data['total']:,} kcal total")

for meal, cals in day_data['breakdown'].items():
    c1, c2, c3 = st.columns([2, 6, 1])
    c1.write(f"**{meal}**")
    c2.progress(min(cals/1000, 1.0))
    c3.write(f"{cals} kcal")

# Bottom Summary
st.markdown("---")
sc1, sc2, sc3 = st.columns(3)
sc1.markdown(f'<div class="summary-card"><p>Best day</p><p class="summary-value">Fri · 1,980</p></div>', unsafe_allow_stdio=True)
sc2.markdown(f'<div class="summary-card"><p>Days on goal</p><p class="summary-value">1 / 7 days</p></div>', unsafe_allow_stdio=True)
sc3.markdown(f'<div class="summary-card"><p>Weekly total</p><p class="summary-value">14,220 kcal</p></div>', unsafe_allow_stdio=True)
