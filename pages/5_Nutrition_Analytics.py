"""
Nutrition Analytics — calorie tracker for the past 7 days.

Owner: <assign on Apr 22>
Grading coverage:
    * Req. 3 (visualisation — bar chart, meal breakdown, weekly stats)
    * Req. 4 (user interaction — select day, edit meals, save)

Sync logic
----------
The meal planner is the source of truth for planned meals.
Every time the page loads (or reruns) we:
  1. Start from a blank slate (all zeros).
  2. Overlay calories from the meal plan DB (kcal_per_serv on each recipe).
  3. Overlay any *manual* overrides the user saved via the edit panel
     (stored in calorie_data.json under the key "manual_overrides").
This means adding or removing a recipe in the Meal Planner is immediately
reflected here without the user having to do anything.
"""

import json
import os
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.components.ui import page_header
from src.data.database import query_df
from src.utils.session import init_session_state, require_profile

init_session_state()
require_profile()
page_header("📊 Nutrition Analytics", "Track your calorie intake.")

# ── Constants ──────────────────────────────────────────────────────────────────

DEFAULT_GOAL = 2000
DAYS      = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MEALS     = ["Breakfast", "Lunch", "Dinner", "Snacks"]
DATA_FILE = "calorie_data.json"

# ── Persistence helpers ────────────────────────────────────────────────────────

def load_overrides() -> dict:
    """Load manually-edited calorie values saved by the user."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            raw = json.load(f)
        return raw.get("manual_overrides", raw)
    return {}

def load_saved_goal() -> int:
    """Load the user's last saved calorie goal from disk."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            raw = json.load(f)
        return raw.get("calorie_goal", DEFAULT_GOAL)
    return DEFAULT_GOAL

def save_overrides(overrides: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump({
            "calorie_goal": st.session_state.get("calorie_goal", DEFAULT_GOAL),
            "manual_overrides": overrides,
        }, f, indent=2)

def save_goal(goal: int) -> None:
    """Persist the calorie goal to disk without touching overrides."""
    overrides = load_overrides()
    with open(DATA_FILE, "w") as f:
        json.dump({
            "calorie_goal": goal,
            "manual_overrides": overrides,
        }, f, indent=2)

# ── Calorie goal banner ────────────────────────────────────────────────────────

if "calorie_goal" not in st.session_state:
    st.session_state.calorie_goal = load_saved_goal()

with st.container(border=True):
    banner_col1, banner_col2, banner_col3 = st.columns([3, 2, 1])
    with banner_col1:
        st.markdown("🎯 **Your daily calorie goal**")
        st.caption("Set a personal target to track against the chart and stats.")
    with banner_col2:
        goal_input = st.number_input(
            "kcal/day",
            min_value=500,
            max_value=10000,
            value=st.session_state.calorie_goal,
            step=50,
            label_visibility="collapsed",
            key="goal_input_widget",
        )
    with banner_col3:
        if st.button("✅ Set goal", use_container_width=True):
            st.session_state.calorie_goal = goal_input
            save_goal(goal_input)
            st.rerun()

GOAL = st.session_state.calorie_goal

# ── Meal-planner sync ──────────────────────────────────────────────────────────

_DAY_MAP  = {
    "Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed",
    "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun",
}
_MEAL_MAP = {
    "Breakfast": "Breakfast", "Lunch": "Lunch",
    "Dinner": "Dinner", "Snacks": "Snacks",
}

def load_from_meal_plan(user_id) -> tuple:
    """Fetch this week's planned meals from the DB and return kcal per day/meal.

    Always called fresh on every Streamlit run so that adding or removing a
    dish in the Meal Planner is reflected here immediately.

    Returns:
        result       -- nested dict: { "Mon": { "Breakfast": 450, ... }, ... }
                        Only slots with a planned recipe *and* known kcal_per_serv
                        are filled; everything else stays at 0.
        missing_kcal -- list of recipe titles that have no kcal stored in the DB,
                        so the user knows which ones to fill in manually.
    """
    today      = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)

    result: dict           = {}
    missing_kcal: list     = []

    if not user_id:
        return result, missing_kcal

    try:
        df = query_df(
            """
            SELECT mp.meal_date, mp.meal_type, r.kcal_per_serv, r.title
            FROM meal_plan mp
            JOIN recipes r ON mp.recipe_id = r.id
            WHERE mp.user_id = ?
              AND mp.meal_date BETWEEN ? AND ?
            """,
            (user_id, week_start.isoformat(), week_end.isoformat()),
        )
        if df is None or df.empty:
            return result, missing_kcal

        for _, row in df.iterrows():
            full_day = pd.to_datetime(row["meal_date"]).strftime("%A")
            day  = _DAY_MAP.get(full_day)
            meal = _MEAL_MAP.get(row["meal_type"])
            if not (day and meal):
                continue

            if row["kcal_per_serv"]:
                kcal = int(row["kcal_per_serv"])
            else:
                kcal = 0
                # Track recipes that are in the plan but have no kcal data
                title = row.get("title", "Unknown")
                if title not in missing_kcal:
                    missing_kcal.append(title)

            result.setdefault(day, {})
            # Sum up in case multiple recipes are planned for the same slot.
            result[day][meal] = result[day].get(meal, 0) + kcal

    except Exception as e:
        st.warning(f"Errore nel caricamento del Meal Planner: {e}")

    return result, missing_kcal

# ── Build the working data dict ────────────────────────────────────────────────

def build_data(user_id) -> tuple:
    """Combine meal-planner calories with manual overrides.

    Priority:
      1. Start from all zeros.
      2. Fill in calories from the meal plan (live DB query).
      3. Apply manual overrides saved by the user — but ONLY for days/meals
         where no meal-plan entry exists, so that removing a dish from the
         planner zeroes out that slot rather than keeping the old manual value.

    Returns (data, planned_slots, missing_kcal).
    missing_kcal is a list of recipe titles whose kcal_per_serv is NULL in the
    DB — displayed as a warning so the user knows to fix them in Recipes.
    """
    # Step 1 — blank slate
    data = {day: {meal: 0 for meal in MEALS} for day in DAYS}

    # Step 2 — meal-plan calories (always fresh)
    plan_calories, missing_kcal = load_from_meal_plan(user_id)
    planned_slots: set = set()   # track which (day, meal) pairs have a real entry
    for day, meals in plan_calories.items():
        for meal, kcal in meals.items():
            data[day][meal] = kcal
            planned_slots.add((day, meal))

    # Step 3 — manual overrides only for unplanned slots
    overrides = load_overrides()
    for day in DAYS:
        for meal in MEALS:
            if (day, meal) not in planned_slots:
                manual = overrides.get(day, {}).get(meal)
                if manual is not None:
                    data[day][meal] = manual

    return data, planned_slots, missing_kcal

# ── Session state ──────────────────────────────────────────────────────────────

user_id = st.session_state.get("user_id")

# Rebuild data on every run so meal-planner changes appear immediately.
data, planned_slots, missing_kcal = build_data(user_id)
st.session_state.cal_data = data

# Warn about recipes without calorie data so the user can fix them in Recipes
if missing_kcal:
    with st.expander(
        f"⚠️ {len(missing_kcal)} ricetta/e nel Meal Planner senza dati calorici — clicca per dettagli",
        expanded=False,
    ):
        st.caption(
            "Queste ricette sono pianificate questa settimana ma non hanno "
            "calorie salvate nel database. Vai alla pagina **Ricette**, "
            "rimuovile dal Meal Planner e aggiungile di nuovo — le calorie "
            "verranno recuperate automaticamente da Spoonacular. "
            "In alternativa, inserisci i valori a mano tramite il pannello "
            "**✏️ Edit** qui sotto."
        )
        for t in missing_kcal:
            st.markdown(f"- {t}")

if "cal_selected" not in st.session_state:
    st.session_state.cal_selected = DAYS[0]

selected = st.session_state.cal_selected
totals   = [sum(data[d].values()) for d in DAYS]
avg      = sum(totals) / 7

def day_total(d: str) -> int:
    return sum(data[d].values())

# ── Header ────────────────────────────────────────────────────────────────────

col_left, col_right = st.columns([3, 1])
with col_left:
    st.caption("Current week")
    st.markdown(
        f"<span style='font-size:2em;font-weight:700'>{avg:,.0f} kcal avg/day</span>"
        f"<span style='font-size:1em;font-weight:400'> — Average daily calorie intake across the past 7 days</span>",
        unsafe_allow_html=True,
    )
with col_right:
    st.markdown(
        '<div style="text-align:right;padding-top:16px">'
        '<span style="color:#ED7D3A">■</span> Actual &nbsp;'
        '<span style="color:#F5F5DC">■</span> Goal'
        "</div>",
        unsafe_allow_html=True,
    )

# ── Bar chart ─────────────────────────────────────────────────────────────────

bar_colors = []
for day, total in zip(DAYS, totals):
    if day == selected:
        bar_colors.append("#ED7D3A")   # arancione — giorno selezionato
    else:
        bar_colors.append("#FFCC99")   # grigio — tutti gli altri

fig = go.Figure()

fig.add_trace(go.Bar(
    x=DAYS, y=[GOAL] * 7,
    name="Goal", marker_color="#F5F5DC", width=0.55,
))

fig.add_trace(go.Bar(
    x=DAYS, y=totals,
    name="Actual", marker_color=bar_colors, width=0.3,
))

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

    if day == selected:
        line_color = "#FF6B35"
    else:
        line_color = "#C8C8C8"

    border = "2px solid #FF6B35" if day == selected else "1px solid #e0e0e0"

    with pill_cols[i]:
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
total_day = day_total(selected)
max_kcal  = max(max(day_data.values(), default=1), 1)

with st.container(border=True):
    st.markdown(f"**{selected} — {total_day:,} kcal total**")

    for meal in MEALS:
        kcal = day_data[meal]
        is_from_plan = (selected, meal) in planned_slots

        c1, c2 = st.columns([5, 1])
        with c1:
            # Show a small tag if calories come from the meal planner
            tag = " 📅" if is_from_plan and kcal > 0 else ""
            st.markdown(f"{meal}{tag}")
            st.progress(kcal / max_kcal if max_kcal > 0 else 0)
        with c2:
            st.markdown(
                f"<div style='text-align:right;padding-top:22px'>{kcal:,} kcal</div>",
                unsafe_allow_html=True,
            )

    if any((selected, m) in planned_slots for m in MEALS):
        st.caption("📅 = calories synced automatically from your Meal Planner")

# ── Edit meals ────────────────────────────────────────────────────────────────

with st.expander(f"✏️ Edit calories manually for {selected}"):
    st.caption(
        "Slots marked 📅 are controlled by the Meal Planner. "
        "You can override them here, but removing the recipe from the "
        "Meal Planner will reset that slot to 0 automatically."
    )
    ecols = st.columns(4)
    new_vals = {}
    MAX_KCAL = 10000          # raised ceiling
    for i, meal in enumerate(MEALS):
        with ecols[i]:
            current = min(int(day_data[meal]), MAX_KCAL)   # clamp to max
            new_vals[meal] = st.number_input(
                meal, min_value=0, max_value=10000,
                value=min(int(day_data[meal]), 10000), step=10,
                key=f"inp_{selected}_{meal}",
            )
    if st.button("💾 Save", key="save_day"):
        overrides = load_overrides()
        overrides.setdefault(selected, {})
        for meal, val in new_vals.items():
            overrides[selected][meal] = val
        save_overrides(overrides)
        st.success("Saved! Meal-planner slots will still be overridden by the planner on the next sync.")
        st.rerun()

# ── Stats ──────────────────────────────────────────────────────────────────────

totals_dict = {d: day_total(d) for d in DAYS}
best_day    = min(totals_dict, key=lambda d: abs(totals_dict[d] - GOAL))
on_goal     = sum(
    1 for t in totals_dict.values()
    if t > 0 and abs(t - GOAL) / GOAL < 0.05
)
weekly = sum(totals_dict.values())

st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Best day",     f"{best_day} · {totals_dict[best_day]:,}")
c2.metric("Days on goal", f"{on_goal} / 7 days")
c3.metric("Weekly total", f"{weekly:,} kcal")
