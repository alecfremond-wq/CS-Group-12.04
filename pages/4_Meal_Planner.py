"""
4_Meal_Planner.py — Weekly Meal Planning Page
=============================================
What this page does:
  1. Shows a Mon–Sun grid with Breakfast / Lunch / Dinner slots
  2. Lets users add any recipe to any slot
  3. Uses the ML recommender to suggest recipes for empty slots
  4. Auto-generates a Shopping List (cross-checked against the pantry)
  5. Shows a Nutrition Summary for the week

How it connects to the rest of the project:
  - Reads/writes the `meal_plan` table (see schema_meal_planner.sql)
  - Calls src/data/database.py  → query_df(), execute()
  - Calls src/utils/session.py  → require_profile()  (redirects if not onboarded)
  - Calls src/components/ui.py  → page_header()
  - Optionally calls src/models/recommender.py → Recommender()
"""

# ─────────────────────────────────────────────────────────────────────────────
# 0. IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import sys, os

# Make sure Python can find the src/ folder no matter where Streamlit is run from
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.data.database import query_df, execute, init_db
from src.utils.session   import require_profile, init_session_state
from src.components.ui   import page_header

# Try to load the ML recommender; if it's not ready yet, we just skip suggestions
try:
    from src.models.recommender import Recommender
    ML_AVAILABLE = True
except Exception:
    ML_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# 1. PAGE CONFIG  (must be the very first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Meal Planner · CookTogether",
    page_icon="📅",
    layout="wide",
)

# Ensure ALL session_state keys exist (including user_id) before anything reads them.
# This is safe to call multiple times — it only fills in missing keys.
init_session_state()

# Redirect to onboarding if the user hasn't set up their profile yet
require_profile()

page_header("📅 Meal Planner", "Plan your week, eat with intention.")


# ─────────────────────────────────────────────────────────────────────────────
# 2. CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
DAYS       = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEAL_TYPES = ["Breakfast", "Lunch", "Dinner"]

# Emoji icons per meal type — purely cosmetic
MEAL_ICONS = {"Break": "🌅", "Lunch": "☀️", "Dinner": "🌙"}


# ─────────────────────────────────────────────────────────────────────────────
# 3. DATABASE HELPER FUNCTIONS
#    These are thin wrappers around the shared query_df / execute helpers.
#    All SQL is written here, never scattered across the UI code below.
# ─────────────────────────────────────────────────────────────────────────────

def get_week_start() -> date:
    """
    Return the Monday of the week the user is currently viewing.
    We store this in st.session_state so the ← → navigation works.
    """
    if "planner_week_start" not in st.session_state:
        today = date.today()
        # today.weekday() is 0 for Monday … 6 for Sunday
        st.session_state.planner_week_start = today - timedelta(days=today.weekday())
    return st.session_state.planner_week_start


def fetch_planned_meals(week_start: date) -> pd.DataFrame:
    """
    Load every meal the current user planned for the 7-day window
    starting on `week_start`.
    Returns a DataFrame with columns:
      id, meal_date, meal_type, recipe_id, recipe_name,
      calories, protein, carbs, fat, cuisine
    """
    week_end = week_start + timedelta(days=6)
    return query_df(
        """
        SELECT
            mp.id,
            mp.meal_date,
            mp.meal_type,
            mp.recipe_id,
            r.name        AS recipe_name,
            r.calories,
            r.protein,
            r.carbs,
            r.fat,
            r.cuisine
        FROM meal_plan mp
        JOIN recipes r ON mp.recipe_id = r.id
        WHERE mp.user_id  = ?
          AND mp.meal_date BETWEEN ? AND ?
        ORDER BY mp.meal_date, mp.meal_type
        """,
        (st.session_state.user_id, week_start.isoformat(), week_end.isoformat()),
    )


def fetch_all_recipes() -> pd.DataFrame:
    """All recipes in the DB (global + user-created), used to populate the picker."""
    return query_df(
        """
        SELECT id, name, cuisine, calories, protein, carbs, fat,
               cooking_time, spiciness
        FROM recipes
        ORDER BY name
        """,
        (),
    )


def add_meal_to_plan(meal_date: date, meal_type: str, recipe_id: int):
    """
    Insert (or replace) a meal into the plan.
    INSERT OR REPLACE prevents duplicates for the same slot.
    """
    execute(
        """
        INSERT OR REPLACE INTO meal_plan
            (user_id, meal_date, meal_type, recipe_id)
        VALUES (?, ?, ?, ?)
        """,
        (st.session_state.user_id, meal_date.isoformat(), meal_type, recipe_id),
    )


def remove_meal_from_plan(plan_id: int):
    """Delete a single planned-meal row by its primary key."""
    execute(
        "DELETE FROM meal_plan WHERE id = ? AND user_id = ?",
        (plan_id, st.session_state.user_id),
    )


def fetch_ingredients_for_plan(recipe_ids: list) -> pd.DataFrame:
    """
    Aggregate all ingredients needed for the given list of recipe IDs.
    Groups by ingredient so you see "300 g chicken" instead of it appearing 3×.
    """
    if not recipe_ids:
        return pd.DataFrame()
    placeholders = ",".join("?" * len(recipe_ids))
    return query_df(
        f"""
        SELECT
            i.name          AS ingredient,
            i.unit,
            SUM(ri.quantity) AS total_qty
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE ri.recipe_id IN ({placeholders})
        GROUP BY i.name, i.unit
        ORDER BY i.name
        """,
        tuple(recipe_ids),
    )


def fetch_pantry_items() -> set:
    """Returns a set of lower-case ingredient names the user already has."""
    df = query_df(
        """
        SELECT i.name AS ingredient
        FROM pantry p
        JOIN ingredients i ON p.ingredient_id = i.id
        WHERE p.user_id = ? AND p.quantity > 0
        """,
        (st.session_state.user_id,),
    )
    return set(df["ingredient"].str.lower()) if not df.empty else set()


# ─────────────────────────────────────────────────────────────────────────────
# 4. ML SUGGESTIONS
#    We call the recommender once per page load and cache the results.
#    If the recommender isn't ready, ml_suggested_ids stays empty.
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)  # cache for 5 minutes
def get_ml_suggestions(user_id: int, exclude_ids: tuple) -> list:
    """
    Ask the ML recommender for recipe IDs we should suggest.
    Returns a list of recipe IDs sorted by predicted relevance.
    """
    if not ML_AVAILABLE:
        return []
    try:
        rec = Recommender()
        all_r = fetch_all_recipes()
        if all_r.empty:
            return []
        rec.fit(all_r)
        result = rec.recommend(user_id=user_id, exclude_ids=list(exclude_ids), n=10)
        # result can be a list of IDs or a dict — handle both
        if isinstance(result, dict):
            return list(result.keys())
        return list(result)
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# 5. WEEK NAVIGATION BAR
# ─────────────────────────────────────────────────────────────────────────────
week_start = get_week_start()
week_end   = week_start + timedelta(days=6)

nav_left, nav_mid, nav_right = st.columns([1, 3, 1])

with nav_left:
    if st.button("← Prev week", use_container_width=True):
        st.session_state.planner_week_start = week_start - timedelta(weeks=1)
        st.rerun()

with nav_mid:
    st.markdown(
        f"<h3 style='text-align:center;margin:0'>"
        f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"
        f"</h3>",
        unsafe_allow_html=True,
    )

with nav_right:
    if st.button("Next week →", use_container_width=True):
        st.session_state.planner_week_start = week_start + timedelta(weeks=1)
        st.rerun()

# Jump-to-today shortcut
if week_start != date.today() - timedelta(days=date.today().weekday()):
    if st.button("↩ Back to this week"):
        today = date.today()
        st.session_state.planner_week_start = today - timedelta(days=today.weekday())
        st.rerun()

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# 6. LOAD DATA FOR THIS WEEK
# ─────────────────────────────────────────────────────────────────────────────
planned_df  = fetch_planned_meals(week_start)
all_recipes = fetch_all_recipes()

# Build a fast lookup: (date_iso, meal_type) → list of row-dicts
plan_lookup: dict[tuple, list] = {}
if not planned_df.empty:
    for _, row in planned_df.iterrows():
        key = (str(row["meal_date"]), row["meal_type"])
        plan_lookup.setdefault(key, []).append(row.to_dict())

# ML suggestions (we pass currently-planned IDs so they're excluded)
already_planned = tuple(planned_df["recipe_id"].tolist()) if not planned_df.empty else ()
ml_ids = get_ml_suggestions(st.session_state.user_id, already_planned)


# ─────────────────────────────────────────────────────────────────────────────
# 7. WEEKLY GRID
#    Layout: one row per meal type, one column per day.
#    Each cell shows planned meals + a "＋ Add" button.
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("🗓 Your Week")

# Column widths: slightly wider first column for the meal-type label
COL_WEIGHTS = [1.1] + [1] * 7

# ── Header row ──
header_cols = st.columns(COL_WEIGHTS)
header_cols[0].write("")  # empty corner cell

for i, day in enumerate(DAYS):
    day_date = week_start + timedelta(days=i)
    is_today = (day_date == date.today())
    header_cols[i + 1].markdown(
        f"**{'🟢 ' if is_today else ''}{day}**  \n"
        f"<span style='font-size:0.8em;color:gray'>{day_date.strftime('%b %d')}</span>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── One row per meal type ──
for meal_type in MEAL_TYPES:
    row_cols = st.columns(COL_WEIGHTS)

    # Left label
    row_cols[0].markdown(
        f"{MEAL_ICONS[meal_type]} **{meal_type}**"
    )

    for i, day in enumerate(DAYS):
        day_date = week_start + timedelta(days=i)
        cell_key  = (day_date.isoformat(), meal_type)
        cell_meals = plan_lookup.get(cell_key, [])

        with row_cols[i + 1]:
            # Show each planned meal as a small card with a remove button
            for meal in cell_meals:
                kcal = int(meal.get("calories") or 0)
                st.markdown(
                    f"""
                    <div style="
                        background: #1a3a2a;
                        border-left: 3px solid #4caf7d;
                        border-radius: 6px;
                        padding: 5px 8px;
                        margin-bottom: 4px;
                        font-size: 0.78em;
                        line-height: 1.4;
                    ">
                        🍽 <b>{meal['recipe_name']}</b><br>
                        <span style="color:#8bc4a8">{kcal} kcal</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "✕ Remove",
                    key=f"del_{meal['id']}",
                    help=f"Remove {meal['recipe_name']}",
                ):
                    remove_meal_from_plan(int(meal["id"]))
                    st.rerun()

            # "＋ Add" button — stores target date+type in session_state
            if st.button("＋ Add", key=f"open_{day}_{meal_type}"):
                st.session_state["adding_slot"] = (day_date, meal_type)

    st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# 8. RECIPE PICKER (appears when user clicks "＋ Add")
# ─────────────────────────────────────────────────────────────────────────────
if "adding_slot" in st.session_state:
    target_date, target_type = st.session_state["adding_slot"]

    with st.expander(
        f"➕  Add {target_type} · {target_date.strftime('%A, %b %d')}",
        expanded=True,
    ):
        if all_recipes.empty:
            st.warning("No recipes in the database yet. Add some on the Recipes page first!")
        else:
            # ── Search bar ──
            search_query = st.text_input(
                "🔍 Search by name or cuisine",
                key="recipe_search_input",
                placeholder="e.g. pasta, Thai, quick...",
            )
            filtered = (
                all_recipes[
                    all_recipes["name"].str.contains(search_query, case=False, na=False)
                    | all_recipes["cuisine"].str.contains(search_query, case=False, na=False)
                ]
                if search_query
                else all_recipes
            )

            # ── ML suggestions at the top ──
            if ml_ids:
                suggested_df = filtered[filtered["id"].isin(ml_ids)]
                if not suggested_df.empty:
                    st.markdown("**✨ Recommended for you**")
                    st.caption(
                        "These suggestions are based on your cooking history "
                        "(k-Nearest Neighbours algorithm)."
                    )
                    for _, r in suggested_df.head(3).iterrows():
                        col_a, col_b = st.columns([4, 1])
                        col_a.write(
                            f"⭐ **{r['name']}**  ·  {r.get('cuisine','?')}  "
                            f"·  {int(r.get('calories') or 0)} kcal"
                        )
                        if col_b.button("Add", key=f"sug_{r['id']}_{target_date}_{target_type}"):
                            add_meal_to_plan(target_date, target_type, int(r["id"]))
                            del st.session_state["adding_slot"]
                            st.rerun()
                    st.markdown("---")

            # ── Full recipe list ──
            st.markdown("**All recipes**")
            for _, r in filtered.head(30).iterrows():
                col_a, col_b = st.columns([4, 1])
                cuisine  = r.get("cuisine") or "—"
                kcal     = int(r.get("calories") or 0)
                time_min = int(r.get("cooking_time") or 0)
                col_a.write(f"**{r['name']}**  ·  {cuisine}  ·  {kcal} kcal  ·  {time_min} min")
                if col_b.button("Add", key=f"pick_{r['id']}_{target_date}_{target_type}"):
                    add_meal_to_plan(target_date, target_type, int(r["id"]))
                    del st.session_state["adding_slot"]
                    st.rerun()

        if st.button("✕ Cancel"):
            del st.session_state["adding_slot"]
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# 9. NUTRITION SUMMARY
#    Shown below the grid; visible at a glance, no extra navigation needed.
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("📊 Nutrition Summary")

if planned_df.empty:
    st.info("Add meals above to see your weekly nutrition summary here.")
else:
    # Totals for the whole week
    total_kcal    = planned_df["calories"].fillna(0).sum()
    total_protein = planned_df["protein"].fillna(0).sum()
    total_carbs   = planned_df["carbs"].fillna(0).sum()
    total_fat     = planned_df["fat"].fillna(0).sum()
    avg_kcal      = total_kcal / 7   # per day average

    # Top-level metrics
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("🔥 Week total",  f"{int(total_kcal):,} kcal")
    m2.metric("📅 Daily avg",   f"{int(avg_kcal):,} kcal")
    m3.metric("💪 Protein",     f"{int(total_protein)} g")
    m4.metric("🌾 Carbs",       f"{int(total_carbs)} g")
    m5.metric("🧈 Fat",         f"{int(total_fat)} g")

    # Daily calorie bar chart — Streamlit's native bar_chart
    daily = planned_df.copy()
    daily["meal_date"] = pd.to_datetime(daily["meal_date"])
    daily_agg = (
        daily.groupby("meal_date")["calories"]
        .sum()
        .reset_index()
        .rename(columns={"meal_date": "Day", "calories": "Calories (kcal)"})
    )
    daily_agg["Day"] = daily_agg["Day"].dt.strftime("%a %d")
    daily_agg = daily_agg.set_index("Day")

    st.bar_chart(daily_agg, use_container_width=True, height=220)
    st.caption("Calories per day — aim for your personal target set during onboarding.")

    # Macro breakdown pie-ish table
    with st.expander("Macro breakdown by day"):
        by_day = (
            daily.groupby(daily["meal_date"].dt.strftime("%a %d"))[
                ["calories", "protein", "carbs", "fat"]
            ]
            .sum()
            .round(0)
            .astype(int)
            .rename(columns={
                "calories": "kcal",
                "protein":  "Protein (g)",
                "carbs":    "Carbs (g)",
                "fat":      "Fat (g)",
            })
        )
        st.dataframe(by_day, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# 10. SHOPPING LIST
#    Auto-generated from planned meals, cross-checked with pantry.
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("🛒 Shopping List")
st.caption("Auto-generated from this week's plan — items you already have are ticked off.")

if planned_df.empty:
    st.info("Plan your meals above to auto-generate a shopping list.")
else:
    recipe_ids    = planned_df["recipe_id"].tolist()
    ingredients   = fetch_ingredients_for_plan(recipe_ids)
    pantry_items  = fetch_pantry_items()

    if ingredients.empty:
        st.info(
            "No ingredient data found for your planned recipes. "
            "Make sure recipes have ingredients linked in the database."
        )
    else:
        need_df = ingredients[~ingredients["ingredient"].str.lower().isin(pantry_items)]
        have_df = ingredients[ingredients["ingredient"].str.lower().isin(pantry_items)]

        col_buy, col_owned = st.columns(2)

        with col_buy:
            st.markdown("**🛒 Still need to buy**")
            if need_df.empty:
                st.success("🎉 You already have everything in your pantry!")
            else:
                for _, row in need_df.iterrows():
                    qty  = f"{row['total_qty']:.0f}" if pd.notna(row.get("total_qty")) else ""
                    unit = row.get("unit") or ""
                    st.markdown(f"- **{row['ingredient']}** {qty} {unit}".strip())

        with col_owned:
            st.markdown("**✅ Already in pantry**")
            if have_df.empty:
                st.caption("Nothing matched your pantry yet.")
            else:
                for _, row in have_df.iterrows():
                    st.markdown(f"- ~~{row['ingredient']}~~")

        # Download button so they can take the list to the supermarket
        if not need_df.empty:
            shopping_text = "\n".join(
                f"{r['ingredient']} – {r['total_qty']:.0f} {r.get('unit','')}"
                for _, r in need_df.iterrows()
            )
            st.download_button(
                "⬇️  Download shopping list (.txt)",
                data=shopping_text,
                file_name=f"shopping_list_{week_start}.txt",
                mime="text/plain",
            )


# ─────────────────────────────────────────────────────────────────────────────
# END OF FILE
# ─────────────────────────────────────────────────────────────────────────────
