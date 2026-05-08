"""
Nutrition Analytics — calorie tracker for the past 7 days.

Owner: <assign on Apr 22>
Grading coverage:
    * Req. 3 (visualisation — bar chart, meal breakdown, weekly stats)
    * Req. 4 (user interaction — select day, edit meals, save)
"""

import json
import os

import plotly.graph_objects as go
import streamlit as st

from src.components.ui import page_header
from src.utils.session import init_session_state, require_profile

init_session_state()
require_profile()
page_header("📊 Nutrition Analytics", "Track your calorie intake.")

# ── Constants ──────────────────────────────────────────────────────────────────

GOAL      = 2000
DAYS      = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MEALS     = ["Breakfast", "Lunch", "Snacks", "Dinner"]
DATA_FILE = "calorie_data.json"

# ── Data helpers ───────────────────────────────────────────────────────────────

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {day: {meal: 0 for meal in MEALS} for day in DAYS}

def save_data(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def day_total(data: dict, day: str) -> int:
    return sum(data[day].values())

# ── Session state ──────────────────────────────────────────────────────────────

if "cal_data" not in st.session_state:
    st.session_state.cal_data = load_data()
if "cal_selected" not in st.session_state:
    st.session_state.cal_selected = DAYS[0]

data     = st.session_state.cal_data
selected = st.session_state.cal_selected
totals   = [day_total(data, d) for d in DAYS]
avg      = sum(totals) / 7

# ── Header ────────────────────────────────────────────────────────────────────

col_left, col_right = st.columns([3, 1])
with col_left:
    st.caption("Past 7 days")
    st.markdown(f"## {avg:,.0f} kcal avg/day")
with col_right:
    st.markdown(
        '<div style="text-align:right;padding-top:16px">'
        '<span style="color:#4A90D9">■</span> Actual &nbsp;'
        '<span style="color:#D0CFC8">■</span> Goal'
        "</div>",
        unsafe_allow_html=True,
    )

# ── Bar chart ─────────────────────────────────────────────────────────────────

# Color each bar: green = selected day, red = over goal, blue = under goal.
bar_colors = []
for day, total in zip(DAYS, totals):
    if day == selected:
        bar_colors.append("#4CAF50")
    elif total > GOAL:
        bar_colors.append("#E05C5C")
    else:
        bar_colors.append("#4A90D9")

fig = go.Figure()

# Light background bars show the goal height for reference.
fig.add_trace(go.Bar(
    x=DAYS, y=[GOAL] * 7,
    name="Goal", marker_color="#D0CFC8", width=0.55,
))

# Actual calorie bars drawn on top, narrower so both are visible.
fig.add_trace(go.Bar(
    x=DAYS, y=totals,
    name="Actual", marker_color=bar_colors, width=0.3,
))

# Dashed goal line so it's easy to see which days were on target.
fig.add_hline(y=GOAL, line_dash="dash", line_color="#AAAAAA", line_width=1)

fig.update_layout(
    barmode="overlay",
    showlegend=False,
    yaxis_range=[0, max(max(totals, default=GOAL), GOAL) + 300],
    plot_bgcolor="white",
    margin=dict(l=0, r=0, t=10, b=0),
    height=260,
    yaxis=dict(showgrid=True, gridcolor="#EEEEEE", tickformat=","),
    xaxis=dict(showgrid=False),
)
st.plotly_chart(fig, use_container_width=True)

# ── Day pills ─────────────────────────────────────────────────────────────────

pill_cols = st.columns(7)
for i, (day, total) in enumerate(zip(DAYS, totals)):
    label = f"{total/1000:.1f}k" if total >= 1000 else str(total)

    # Pick the underline color to match the bar color for this day.
    if day == selected:
        line_color = "#4CAF50" if abs(total - GOAL) / max(GOAL, 1) < 0.05 else "#4A90D9"
    elif total > GOAL:
        line_color = "#E05C5C"
    else:
        line_color = "#4A90D9"

    border = "2px solid #4A90D9" if day == selected else "1px solid #e0e0e0"

    with pill_cols[i]:
        # HTML card for the visual appearance.
        st.markdown(
            f'<div style="border:{border};border-radius:8px;padding:8px 4px 0;'
            f'text-align:center;background:white;margin-bottom:2px">'
            f'<div style="font-size:13px;font-weight:600">{day}</div>'
            f'<div style="font-size:14px;font-weight:700">{label}</div>'
            f'<div style="height:3px;background:{line_color};border-radius:0 0 4px 4px;margin-top:6px"></div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.button(day, key=f"pill_{day}", use_container_width=True):
            st.session_state.cal_selected = day
            st.rerun()

# ── Detail panel ──────────────────────────────────────────────────────────────

day_data  = data[selected]
total_day = day_total(data, selected)
max_kcal  = max(max(day_data.values(), default=1), 1)

with st.container(border=True):
    st.markdown(f"**{selected} — {total_day:,} kcal total**")

    for meal in MEALS:
        kcal = day_data[meal]
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(meal)
            # Progress bar shows this meal relative to the biggest meal today.
            st.progress(kcal / max_kcal if max_kcal > 0 else 0)
        with c2:
            st.markdown(f"<div style='text-align:right;padding-top:22px'>{kcal:,} kcal</div>",
                        unsafe_allow_html=True)

# ── Edit meals ────────────────────────────────────────────────────────────────

with st.expander(f"✏️ Edit calories for {selected}"):
    ecols = st.columns(4)
    new_vals = {}
    for i, meal in enumerate(MEALS):
        with ecols[i]:
            new_vals[meal] = st.number_input(
                meal, min_value=0, max_value=5000,
                value=int(day_data[meal]), step=10,
                key=f"inp_{selected}_{meal}",
            )
    if st.button("💾 Save", key="save_day"):
        for meal, val in new_vals.items():
            st.session_state.cal_data[selected][meal] = val
        save_data(st.session_state.cal_data)
        st.success("Saved!")
        st.rerun()

# ── Stats ──────────────────────────────────────────────────────────────────────

totals_dict = {d: day_total(data, d) for d in DAYS}
# Best day = the day whose total is closest to the goal.
best_day    = min(totals_dict, key=lambda d: abs(totals_dict[d] - GOAL))
on_goal     = sum(
    1 for t in totals_dict.values()
    if t > 0 and abs(t - GOAL) / GOAL < 0.05
)
weekly      = sum(totals_dict.values())

st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Best day",     f"{best_day} · {totals_dict[best_day]:,}")
c2.metric("Days on goal", f"{on_goal} / 7 days")
c3.metric("Weekly total", f"{weekly:,} kcal")
