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
     Spoonacular recipe saved before nutrition was fetched):
       - Try Spoonacular complexSearch by title (Strategy 1).
       - If that returns nothing, search MealDB for the dish name and
         run Spoonacular's ingredient parser on its ingredients,
         dividing totals by 4 servings (Strategy 2).
       - Write the result back to the DB so future loads cost zero
         API calls for that recipe.
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
from src.data.api_client import (
    fetch_nutrition_by_title,
    fetch_nutrition_from_ingredients,
    search_recipes_by_name,
)
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


def _extract_ingredients_from_mealdb(meal: dict) -> list[str]:
    """Pull the ingredient+measure strings from a raw TheMealDB meal dict."""
    ingredients = []
    for i in range(1, 21):
        name    = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}")    or "").strip()
        if not name:
            continue
        ingredients.append(f"{measure} {name}" if measure else name)
    return ingredients


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

    Delegates entirely to fetch_nutrition_for_meal() in api_client.py which
    already implements both strategies correctly:
      1. complexSearch by title (fast, works for well-known dishes)
      2. parseIngredients fallback (works for any MealDB recipe, passes
         ingredients as a tuple as required by @st.cache_data)

    Both sub-calls are @st.cache_data(ttl=24h) in api_client.py so results
    are reused across reruns. Once a value is found it is written back to
    the DB so future loads cost zero API calls for that recipe.
    """
    kcal: int | None = None

    try:
        # Strategy 1: title-based Spoonacular lookup (fast, works for
        # well-known dishes). fetch_nutrition_by_title is already cached.
        nutrition = fetch_nutrition_by_title(title)
        kcal = nutrition.get("kcal")

        # Strategy 2: ingredient-parser fallback.
        # Search MealDB for the dish to get its ingredient list, then send
        # those to Spoonacular's parseIngredients endpoint.
        # We do NOT require an exact title match — any MealDB result for
        # the query gives us a real ingredient list to parse, which is
        # more reliable than matching on dish name (e.g. "Lamb & Apricot
        # Meatballs" vs "Lamb and Apricot Meatballs").
        if kcal is None:
            matches = search_recipes_by_name(title)
            if matches:
                # Use the closest title match if available, else first result
                meal = next(
                    (m for m in matches
                     if m.get("strMeal", "").lower() == title.lower()),
                    None,
                ) or matches[0]
                ingredients = tuple(_extract_ingredients_from_mealdb(meal))
                if ingredients:
                    raw = fetch_nutrition_from_ingredients(ingredients)
                    if raw.get("kcal") is not None:
                        kcal = int(round(raw["kcal"] / 4))
    except Exception as e:
        print(f"[nutrition backfill] '{title}' failed — {e}")

    # Persist to DB so this is only fetched once per recipe ever
    if kcal is not None:
        try:
            execute(
                "UPDATE recipes SET kcal_per_serv = ? WHERE id = ?",
                (kcal, recipe_id),
            )
        except Exception as e:
            print(f"[nutrition backfill] could not persist '{title}': {e}")

    return kcal


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

def load_from_meal_plan(user_id) -> tuple[dict, list[str]]:
    """Return calorie data for the current week from the meal plan DB,
    plus a list of recipe titles whose kcal could not be fetched.

    { "Mon": { "Breakfast": 450, ... }, ... }, ["Beef Mechado", ...]

    Works for both MealDB and Spoonacular recipes:
      - If kcal_per_serv is already in the DB → use it directly (no API call).
      - If kcal_per_serv is NULL → call _backfill_nutrition() which tries
        Spoonacular complexSearch first, then MealDB ingredient parser as
        a fallback, and writes the result back so it's only fetched once
        per recipe ever.

    Also checks planner_pool for any saved recipes with NULL kcal — even
    ones not yet scheduled — so the missing-calories warning is shown for
    everything the user has added, not just scheduled meals.
    """
    result: dict = {}

    if not user_id:
        st.info(
            "ℹ️ No user profile found — meal-planner data not loaded. "
            "Please complete your profile to sync planned meals."
        )
        return result, []

    today      = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)

    failed_titles: list[str] = []

    try:
        # ── 1. Scheduled meals → feed the chart ───────────────────────────
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
            return result, []
        else:
            for _, row in df.iterrows():
                full_day = pd.to_datetime(row["meal_date"]).strftime("%A")
                day  = _DAY_MAP.get(full_day)
                meal = _MEAL_MAP.get(row["meal_type"])
                if not (day and meal):
                    continue

                kcal_raw = row.get("kcal_per_serv")

                # If kcal is missing, run the two-strategy backfill and persist to DB.
                if _is_null(kcal_raw):
                    recipe_id = int(row["recipe_id"])
                    title     = row.get("title", "")
                    kcal_raw  = _backfill_nutrition(recipe_id, title)
                    if kcal_raw is None:
                        failed_titles.append(title)

                kcal = _safe_int(kcal_raw)
                result.setdefault(day, {})
                result[day][meal] = result[day].get(meal, 0) + kcal

        # ── 2. All planner_pool recipes → catch unscheduled NULL kcal ────
        # Recipes saved to the pool but not yet placed on a day won't appear
        # in meal_plan, so we check them separately just for the warning.
        pool_df = query_df(
            """
            SELECT r.id AS recipe_id, r.title, r.kcal_per_serv
            FROM planner_pool pp
            JOIN recipes r ON pp.recipe_id = r.id
            WHERE pp.user_id = ?
            """,
            (user_id,),
        )

        if pool_df is not None and not pool_df.empty:
            for _, row in pool_df.iterrows():
                if _is_null(row.get("kcal_per_serv")):
                    title = row.get("title", "")
                    # Only attempt backfill + warn if not already in failed_titles
                    if title not in failed_titles:
                        kcal_result = _backfill_nutrition(int(row["recipe_id"]), title)
                        if kcal_result is None:
                            failed_titles.append(title)

        # Backfill attempted for all NULL kcal recipes — no banner shown here.
        # failed_titles is returned to the caller which shows a single notice.

    except Exception as e:
        st.error(
            f"⚠️ Could not load meal-plan data: **{e}**\n\n"
            "Calories from the Meal Planner won't appear until this is resolved. "
            "You can still enter calories manually using the edit panel below."
        )

    return result, failed_titles


# ── Build the working data dict ────────────────────────────────────────────────

def build_data(user_id) -> tuple[dict, set, list[str]]:
    """
    The function build_data() takes a user_id and returns a tuple of three variables: 
    - a dictionary called data, which contains the calorie information for each day and meal of the week, initialized to 0;
    - a set called planned_slots, which keeps track of the meal slots that have planned meals
    - a list called failed_titles, which contains the titles of recipes for which calorie data could not be fetched automatically.
    The function starts by creating an empty table with all days and meals set to 0. 
    It then fetches calories from the meal planner and fills in the table, keeping track of which 
    slots are planned-controlled. Any recipes that couldn't be fetches are stored in a separate list so 
    the user can enter them manually. 
    Next, it loads any manual ovverrides saved by the user. 
    For planned-controlled slots it removes any stale manual values to avoid conflicts; 
    for empty slots it applies the manual value instead. 
    Finally it returns the completed calorie table, the set of planner-controlled slots, and the list of failed recipes. 
    """
    data = {day: {meal: 0 for meal in MEALS} for day in DAYS}

    plan_calories, failed_titles = load_from_meal_plan(user_id)
    planned_slots: set = set()

    for day, meals_map in plan_calories.items():
        for meal, kcal in meals_map.items():
            if day in data and meal in data[day]:
                data[day][meal] = kcal
                planned_slots.add((day, meal))


    overrides = load_overrides()
    """
    Loads any calorie values manually entered by the user. There are two cases:
    - If a slot is already controlled by the planner → delete the manual override if it exists to avoid stale conflicts
    - If a slot is empty (0) → apply the manual override if it exists, allowing the user to fill in missing values or add non-planned meals. 
    """
    stale_cleaned = False
    for day in DAYS:
        for meal in MEALS:
            if (day, meal) in planned_slots:
                if day in overrides and meal in overrides[day]:
                    del overrides[day][meal]
                    stale_cleaned = True
            else:
                manual = overrides.get(day, {}).get(meal)
                if manual is not None:
                    try:
                        data[day][meal] = int(manual)
                    except (ValueError, TypeError):
                        pass
    if stale_cleaned:
        save_overrides(overrides)

    return data, planned_slots, failed_titles


# ── Session state ──────────────────────────────────────────────────────────────
#Retrive the logge-in user's ID from the session state (none if not set)
user_id = st.session_state.get("user_id")

#Call build_data and unpack the returned tuple into three named variables:
#- data: the main calorie data structure used for display and calculations
#- planned_slots: a set of (day, meal) tuples that are controlled by the meal planner 
#(used to determine which slots can be manually overridden)
#- failed_titles: a list of recipe titles for which calorie data could not be
#Then it stores the clalories in session state so other parts of the app can access it. 
data, planned_slots, failed_titles = build_data(user_id)
st.session_state.cal_data = data

#If any recipe titles could not fetched, show and info banner to the user. 
if failed_titles:
    names = ", ".join(f"**{t}**" for t in failed_titles)
    st.info(
        f"Calorie data for {names} could not be fetched automatically. "
        "This can happen when the Spoonacular free-tier quota (50 points/day) "
        "is exhausted, or when the dish name isn't recognised by Spoonacular. "
        "You can enter the missing calories manually in the edit panel below.",
        icon="ℹ️",
    )

#Initialise the selected day to the first day of the week, but if 
#it hasn't already been set (preserves the user's current selection)
if "cal_selected" not in st.session_state:
    st.session_state.cal_selected = DAYS[0]

#Shorthand for the currently selected day 
selected = st.session_state.cal_selected
totals   = [sum(data[d].values()) for d in DAYS]
avg      = sum(totals) / 7
#totals is a list with the total calories for each day, 
#avg is the weekly average, and day_total() is a small helper function that computes the total for a specific day.


def day_total(d: str) -> int:
    """ 
    day_total(d) takes a day name as a string (e.g. "Mon") and returns the total colaries 
    for that days as an integer. 
    It does this by looking up data(d) which is the inner dictionary for that days
    (e.g. {"Breakfast": 450, "Lunch": 600, ...}) 
    Then calling .values() to get the numbers, and sum() to add them all up. 
    """
    return sum(data[d].values())


# ── Header ─────────────────────────────────────────────────────────────────────

col_left, col_right = st.columns([3, 1]) #split the heaader into two columns with a 3:1 width ratio 
with col_left:
    st.caption("Current week") #display a small "current week" label above the main number 
    st.markdown(
        #it displays: 
        #- the averge calories as a large vold hedline (2em font size, weight 700)
        #- a smaller description text next to it (1em font size, weight 400 - average daily calorie intake across the past 7 days)
        f"<span style='font-size:2em;font-weight:700'>{avg:,.0f} kcal avg/day</span>" 
        f"<span style='font-size:1em;font-weight:400'>"
        f" — Average daily calorie intake across the past 7 days</span>",
        unsafe_allow_html=True,
    )
with col_right:
    st.markdown(
        '<div style="text-align:right;padding-top:16px">' #display a colour legend right-aligned 
        '<span style="color:#72BF6A">■</span> Actual &nbsp;' #a green square for "Actual" 
        '<span style="color:#F5F5DC">■</span> Goal' #a beige square for "Goal" 
        "</div>",
        unsafe_allow_html=True,
    )
#Raw HTML is needed here because Streamlit doesn't support multi-style text in a single st.markdown call

# ── Bar chart ──────────────────────────────────────────────────────────────────

bar_colors = ["#72BF6A" if day == selected else "#CCE7C9" for day in DAYS] #build a clour list: the selected day gets bright green, all others get light green

#Create an empty Plotly figure
#Add the Goal bars - wide (0.55) and beige, one per day at the same height (GOAL)
#These acts as the background layer showing where the target is for each day.
fig = go.Figure()  
fig.add_trace(go.Bar(
    x=DAYS, y=[GOAL] * 7, name="Goal", marker_color="#F5F5DC", width=0.55,
))
#Add the actual bars - narrower (0.3) and coloured, overlaid on top of the goal barss.
#Each bar's height is the real daily calories total. 
fig.add_trace(go.Bar(
    x=DAYS, y=totals, name="Actual", marker_color=bar_colors, width=0.3,
))
#Add a dashed horizontal line at the goal value as an additional visual reference. 
fig.add_hline(y=GOAL, line_dash="dash", line_color="#AAAAAA", line_width=1)

#Configure the chart layout: 
fig.update_layout(
    barmode="overlay", #Overlay mode: actual bars sit on top of goal bars. 
    showlegend=False, #Hide the legend (the header has its own colour legend)
    yaxis_range=[0, max(max(totals, default=GOAL), GOAL) + 300], #Y axis starts at 0 and leaves 300kcal of room above the tallest bar for visual clarity.
    plot_bgcolor="white", margin=dict(l=0, r=0, t=10, b=0), height=260, #Compact size with a bit of top margin for room.
    yaxis=dict(showgrid=True, gridcolor="#EEEEEE", tickformat=","), #Y axis has light grey grid lines and comma as thousand separator.
    xaxis=dict(showgrid=False), #X axis has no grid lines. 
)
st.plotly_chart(fig, use_container_width=True) #Render the chart in Streamlit, allowing it to take the full width of the container.

# ── Day pills ──────────────────────────────────────────────────────────────────

pill_cols = st.columns(7) #create seven equal columns for each day of the week. 

#Loop over each day and its total calories simultaneously.
#enmurate() is used to get both the index (i) and the values (day, total) for each iteration.
for i, (day, total) in enumerate(zip(DAYS, totals)):

    label      = f"{total/1000:.1f}k" if total >= 1000 else str(total) #format the calorie label: show "1.8k" for value >= 1000, otherwise show the raw number.
    line_color = "#72BF6A" if day == selected else "#CCE7C9" #the small line at the bottom of the pill is bright green for the selected day. 
    border = "2px solid #72BF6A" if day == selected else "1px solid #CCE7C9" #the pill border is light green fot the non-selected days. 
    
    with pill_cols[i]:
        #render a styled HTLM card showing the day name, calorie total, 
        #and a small line at the bottom as a visual indicator of selection.
        st.markdown(
            f'<div style="border:{border};border-radius:8px;padding:8px 4px 0;'
            f'text-align:center;background:white;margin-bottom:2px">'
            f'<div style="font-size:13px;font-weight:600">{day}</div>' #day name 
            f'<div style="font-size:14px;font-weight:700">{label}</div>' #calorie total 
            f'<div style="height:3px;background:{line_color};border-radius:0 0 4px 4px;margin-top:6px"></div>' #coloured bottom bar 
            f"</div>",
            unsafe_allow_html=True,
        ) #Raw HTML is needed here because Streamlit doesn't support multi-style text in a single st.markdown call

        #Invisible buttom overlaid on the card. 
        #When clicked, it sets the selected day in session state and reruns the app to update all displays.
        if st.button(day, key=f"pill_{day}", use_container_width=True):
            st.session_state.cal_selected = day
            st.rerun()

# ── Detail panel ───────────────────────────────────────────────────────────────

day_data  = data[selected] #bsegin code generated by Claude Sonnet 4.6 
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

    btn_save, btn_clear = st.columns([1, 1])

    with btn_save:
        if st.button("💾 Save", key="save_day", use_container_width=True):
            overrides = load_overrides()
            overrides.setdefault(selected, {})
            for meal, val in new_vals.items():
                if (selected, meal) not in planned_slots and val > 0:
                    overrides[selected][meal] = val
                elif (selected, meal) not in planned_slots and val == 0:
                    overrides[selected].pop(meal, None)
            save_overrides(overrides)
            st.success("Saved!")
            st.rerun()

    with btn_clear:
        if st.button("🗑️ Clear manual entries", key="clear_day", use_container_width=True):
            overrides = load_overrides()
            overrides.pop(selected, None)
            save_overrides(overrides)
            st.success(f"Manual entries for {selected} cleared.")
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
c3.metric("Weekly total", f"{weekly:,} kcal") #end code generate by Claude Sonnet 4.6 
