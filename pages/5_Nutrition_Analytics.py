"""
Nutrition Analytics — calorie tracker for the current week.

Owner: <assign on Apr 22>
Grading coverage:
    * Req. 3 (visualisation — bar chart, meal breakdown, weekly stats)
    * Req. 4 (user interaction — select day, edit meals, save)

Sync logic
----------
The meal planner is the source of truth for planned meals.
Every time the page loads (or reruns) we:
  1. Start from a blank slate (all zeros).
  2. Pull this week's meal_plan rows from the DB.
  3. For each row that already has kcal_per_serv → use it directly.
     For rows with NULL kcal_per_serv (MealDB recipe never enriched, or
     Spoonacular recipe saved before nutrition was fetched) → call
     Spoonacular via _backfill_nutrition() and write the result back to
     the DB so future loads cost zero API calls for that recipe.
  4. Overlay any *manual* overrides the user saved via the edit panel
     (stored in calorie_data.json under "manual_overrides") but ONLY for
     slots that have no planned meal.
"""

import json
import os
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.components.ui import page_header
from src.data.api_client import fetch_nutrition_by_title
from src.data.database import execute, query_df
from src.utils.session import init_session_state, require_profile

init_session_state()
require_profile()
page_header("📊 Nutrition Analytics", "Track your calorie intake.")

# ── Constants ──────────────────────────────────────────────────────────────────

DEFAULT_GOAL = 2000
DAYS         = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MEALS        = ["Breakfast", "Lunch", "Dinner", "Snacks"]
DATA_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calorie_data.json")

_DAY_MAP = {
    "Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed",
    "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun",
}
_MEAL_MAP = {
    "Breakfast": "Breakfast", "Lunch": "Lunch",
    "Dinner": "Dinner",       "Snacks": "Snacks",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_null(v) -> bool:
    """True if v is None or a pandas/numpy NaN."""
    try:
        return v is None or (v != v)
    except TypeError:
        return True


def _safe_int(v, default: int = 0) -> int:
    try:
        return int(float(v)) if not _is_null(v) else default
    except (ValueError, TypeError):
        return default

# ── Persistence helpers ────────────────────────────────────────────────────────

def load_overrides() -> dict:
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                raw = json.load(f)
            return raw.get("manual_overrides", {})
    except (json.JSONDecodeError, OSError) as e:
        st.warning(f"Could not read saved overrides: {e}")
    return {}


def load_saved_goal() -> int:
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                raw = json.load(f)
            return int(raw.get("calorie_goal", DEFAULT_GOAL))
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return DEFAULT_GOAL


def save_overrides(overrides: dict) -> None:
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({
                "calorie_goal":     st.session_state.get("calorie_goal", DEFAULT_GOAL),
                "manual_overrides": overrides,
            }, f, indent=2)
    except OSError as e:
        st.error(f"Could not save overrides: {e}")


def save_goal(goal: int) -> None:
    try:
        overrides = load_overrides()
        with open(DATA_FILE, "w") as f:
            json.dump({"calorie_goal": goal, "manual_overrides": overrides}, f, indent=2)
    except OSError as e:
        st.error(f"Could not save goal: {e}")

# ── DB nutrition backfill ──────────────────────────────────────────────────────

def _backfill_nutrition(recipe_id: int, title: str) -> int | None:
    """Fetch kcal from Spoonacular and persist it to the DB.

    Called lazily the first time a recipe slot has NULL kcal_per_serv.
    After this runs once, all future page loads read straight from SQLite —
    zero additional Spoonacular API calls for that recipe.

    For MealDB recipes     → fetch_nutrition_for_meal() (ingredient parser + title fallback).
    For Spoonacular recipes → fetch_nutrition_by_title() (complexSearch, already per-serving).

    Returns kcal as int, or None if the lookup failed.
    """
    try:
        # The DB does not store the original MealDB ID — only the SQLite row id.
        # get_meal_by_id() would therefore look up the wrong recipe entirely.
        # fetch_nutrition_by_title() works for both MealDB and Spoonacular recipes
        # and is the correct strategy here.
        nutrition = fetch_nutrition_by_title(title)

        kcal = nutrition.get("kcal")

        if kcal is not None:
            execute(
                "UPDATE recipes SET kcal_per_serv = ? WHERE id = ?",
                (kcal, recipe_id),
            )
        return kcal

    except Exception as e:
        st.warning(f"Could not fetch nutrition for recipe {recipe_id} ({title}): {e}")
        return None

# ── Calorie goal banner ────────────────────────────────────────────────────────

if "calorie_goal" not in st.session_state:
    st.session_state.calorie_goal = load_saved_goal()

with st.container(border=True):
    b1, b2, b3 = st.columns([3, 2, 1])
    with b1:
        st.markdown("🎯 **Your daily calorie goal**")
        st.caption("Set a personal target to track against the chart and stats.")
    with b2:
        goal_input = st.number_input(
            "kcal/day", min_value=500, max_value=10000,
            value=st.session_state.calorie_goal, step=50,
            label_visibility="collapsed", key="goal_input_widget",
        )
    with b3:
        if st.button("✅ Set goal", use_container_width=True):
            st.session_state.calorie_goal = goal_input
            save_goal(goal_input)
            st.rerun()

GOAL = st.session_state.calorie_goal

# ── Meal-planner sync ──────────────────────────────────────────────────────────

def load_from_meal_plan(user_id) -> dict:
    """Return calorie data for the current week from the meal plan DB.

    { "Mon": { "Breakfast": 450, ... }, ... }

    Both MealDB and Spoonacular recipes are handled:
      - If kcal_per_serv is already in the DB → use it directly (no API call).
      - If kcal_per_serv is NULL → call Spoonacular via _backfill_nutrition()
        and write the result back so it's only fetched once per recipe ever.
    """
    result: dict = {}

    if not user_id:
        st.info(
            "ℹ️ No user profile found — meal-planner data not loaded. "
            "Please complete your profile to sync planned meals."
        )
        return result

    today      = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)

    try:
        df = query_df(
            """
            SELECT
                mp.meal_date,
                mp.meal_type,
                mp.recipe_id,
                r.title,
                r.kcal_per_serv
            FROM meal_plan mp
            JOIN recipes r ON mp.recipe_id = r.id
            WHERE mp.user_id     = ?
              AND mp.meal_date BETWEEN ? AND ?
            """,
            (user_id, week_start.isoformat(), week_end.isoformat()),
        )

        if df is None or df.empty:
            st.info(
                "ℹ️ No meals found in your Meal Planner for the current week. "
                "Add recipes there, or enter calories manually below."
            )
            return result

        for _, row in df.iterrows():
            full_day = pd.to_datetime(row["meal_date"]).strftime("%A")
            day  = _DAY_MAP.get(full_day)
            meal = _MEAL_MAP.get(row["meal_type"])
            if not (day and meal):
                continue

            kcal_raw = row.get("kcal_per_serv")

            # If kcal is missing, fetch from Spoonacular and backfill the DB
            if _is_null(kcal_raw):
                recipe_id = int(row["recipe_id"])
                title     = row.get("title", "")
                kcal_raw  = _backfill_nutrition(recipe_id, title)

            kcal = _safe_int(kcal_raw)

            result.setdefault(day, {})
            result[day][meal] = result[day].get(meal, 0) + kcal

    except Exception as e:
        st.error(
            f"⚠️ Could not load meal-plan data: **{e}**\n\n"
            "Calories from the Meal Planner won't appear until this is resolved. "
            "You can still enter calories manually using the edit panel below."
        )

    return result

# ── Build the working data dict ────────────────────────────────────────────────

def build_data(user_id) -> tuple[dict, set]:
    """Merge meal-plan calories with manual overrides.

    Returns (calorie_data, planned_slots).
    """
    data = {day: {meal: 0 for meal in MEALS} for day in DAYS}

    plan_calories = load_from_meal_plan(user_id)
    planned_slots: set = set()

    for day, meals_map in plan_calories.items():
        for meal, kcal in meals_map.items():
            if day in data and meal in data[day]:
                data[day][meal] = kcal
                planned_slots.add((day, meal))

    # Manual overrides — only for slots with no planned recipe
    overrides = load_overrides()
    for day in DAYS:
        for meal in MEALS:
            if (day, meal) not in planned_slots:
                manual = overrides.get(day, {}).get(meal)
                if manual is not None:
                    try:
                        data[day][meal] = int(manual)
                    except (ValueError, TypeError):
                        pass

    return data, planned_slots

# ── Session state ──────────────────────────────────────────────────────────────

user_id = st.session_state.get("user_id")

data, planned_slots = build_data(user_id)
st.session_state.cal_data = data

if "cal_selected" not in st.session_state:
    st.session_state.cal_selected = DAYS[0]

selected = st.session_state.cal_selected
totals   = [sum(data[d].values()) for d in DAYS]
avg      = sum(totals) / 7


def day_total(d: str) -> int:
    return sum(data[d].values())

# ── Header ─────────────────────────────────────────────────────────────────────

col_left, col_right = st.columns([3, 1])
with col_left:
    st.caption("Current week")
    st.markdown(
        f"<span style='font-size:2em;font-weight:700'>{avg:,.0f} kcal avg/day</span>"
        f"<span style='font-size:1em;font-weight:400'>"
        f" — Average daily calorie intake across the past 7 days</span>",
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

# ── Bar chart ──────────────────────────────────────────────────────────────────

bar_colors = ["#ED7D3A" if day == selected else "#FFCC99" for day in DAYS]

fig = go.Figure()
fig.add_trace(go.Bar(
    x=DAYS, y=[GOAL] * 7, name="Goal", marker_color="#F5F5DC", width=0.55,
))
fig.add_trace(go.Bar(
    x=DAYS, y=totals, name="Actual", marker_color=bar_colors, width=0.3,
))
fig.add_hline(y=GOAL, line_dash="dash", line_color="#AAAAAA", line_width=1)
fig.update_layout(
    barmode="overlay", showlegend=False,
    yaxis_range=[0, max(max(totals, default=GOAL), GOAL) + 300],
    plot_bgcolor="white", margin=dict(l=0, r=0, t=10, b=0), height=260,
    yaxis=dict(showgrid=True, gridcolor="#EEEEEE", tickformat=","),
    xaxis=dict(showgrid=False),
)
st.plotly_chart(fig, use_container_width=True)

# ── Day pills ──────────────────────────────────────────────────────────────────

pill_cols = st.columns(7)
for i, (day, total) in enumerate(zip(DAYS, totals)):
    label      = f"{total/1000:.1f}k" if total >= 1000 else str(total)
    line_color = "#FF6B35" if day == selected else "#C8C8C8"
    border     = "2px solid #FF6B35" if day == selected else "1px solid #e0e0e0"
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

# ── Detail panel ───────────────────────────────────────────────────────────────

day_data  = data[selected]
total_day = day_total(selected)
max_kcal  = max(max(day_data.values(), default=1), 1)

with st.container(border=True):
    st.markdown(f"**{selected} — {total_day:,} kcal total**")

    for meal in MEALS:
        kcal         = day_data[meal]
        is_from_plan = (selected, meal) in planned_slots

        c1, c2 = st.columns([5, 1])
        with c1:
            tag = " 📅" if is_from_plan and kcal > 0 else ""
            st.markdown(f"{meal}{tag}")
            st.progress(kcal / max_kcal if max_kcal > 0 else 0)
        with c2:
            st.markdown(
                f"<div style='text-align:right;padding-top:22px'>{kcal:,} kcal</div>",
                unsafe_allow_html=True,
            )

    if any((selected, m) in planned_slots for m in MEALS):
        st.caption("📅 = calories synced automatically from your Meal Planner (MealDB + Spoonacular)")

# ── Edit meals ─────────────────────────────────────────────────────────────────

with st.expander(f"✏️ Edit calories manually for {selected}"):
    st.caption(
        "Slots marked 📅 are controlled by the Meal Planner. "
        "You can override them here, but removing the recipe from the "
        "Meal Planner will reset that slot to 0 automatically."
    )
    ecols    = st.columns(4)
    new_vals = {}
    MAX_KCAL = 10000

    for i, meal in enumerate(MEALS):
        with ecols[i]:
            current = max(0, min(int(day_data[meal]), MAX_KCAL))
            new_vals[meal] = st.number_input(
                meal, min_value=0, max_value=MAX_KCAL,
                value=current, step=10, key=f"inp_{selected}_{meal}",
            )

    if st.button("💾 Save", key="save_day"):
        overrides = load_overrides()
        overrides.setdefault(selected, {})
        for meal, val in new_vals.items():
            overrides[selected][meal] = val
        save_overrides(overrides)
        st.success(
            "Saved! Meal-planner slots will still be overridden by the planner on the next sync."
        )
        st.rerun()

# ── Stats ───────────────────────────────────────────────────────────────────────

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
