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
st.subheader("Calories over the past 7 days") 
"""
Calorie Tracker — Python version of the interactive weekly graph.
Connects to the Spoonacular API to fetch real recipe nutrition data.

Requirements:
    pip install matplotlib requests

Usage:
    python calorie_tracker.py
"""

import json
import os
import datetime
import requests
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter

# ─── CONFIG ──────────────────────────────────────────────────────────────────

SPOONACULAR_API_KEY = "YOUR_API_KEY_HERE"   # ← Replace with your key
DAILY_GOAL = 2000                            # kcal goal per day
DATA_FILE = "calorie_data.json"              # Local storage for logged meals

# ─── SPOONACULAR API ──────────────────────────────────────────────────────────

def search_recipes(query: str, number: int = 8) -> list[dict]:
    """Search Spoonacular for recipes matching the query."""
    url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {
        "apiKey": SPOONACULAR_API_KEY,
        "query": query,
        "number": number,
        "addRecipeNutrition": True,
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        results = res.json().get("results", [])
        recipes = []
        for r in results:
            nutrients = {n["name"]: n["amount"] for n in r.get("nutrition", {}).get("nutrients", [])}
            recipes.append({
                "id": r["id"],
                "title": r["title"],
                "calories": round(nutrients.get("Calories", 0)),
                "protein": round(nutrients.get("Protein", 0)),
                "carbs": round(nutrients.get("Carbohydrates", 0)),
                "fat": round(nutrients.get("Fat", 0)),
            })
        return recipes
    except Exception as e:
        print(f"  [API error] {e}")
        return []


def get_recipe_by_id(recipe_id: int) -> dict | None:
    """Fetch full nutrition info for a recipe by its Spoonacular ID."""
    url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
    params = {"apiKey": SPOONACULAR_API_KEY, "includeNutrition": True}
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        r = res.json()
        nutrients = {n["name"]: n["amount"] for n in r.get("nutrition", {}).get("nutrients", [])}
        return {
            "id": r["id"],
            "title": r["title"],
            "calories": round(nutrients.get("Calories", 0)),
            "protein": round(nutrients.get("Protein", 0)),
            "carbs": round(nutrients.get("Carbohydrates", 0)),
            "fat": round(nutrients.get("Fat", 0)),
        }
    except Exception as e:
        print(f"  [API error] {e}")
        return None


# ─── FALLBACK DEMO RECIPES (used if no API key is set) ───────────────────────

DEMO_RECIPES = [
    {"id": 1, "title": "Spaghetti Carbonara",    "calories": 620, "protein": 28, "carbs": 72, "fat": 24},
    {"id": 2, "title": "Grilled Chicken Salad",  "calories": 380, "protein": 42, "carbs": 18, "fat": 14},
    {"id": 3, "title": "Avocado Toast",           "calories": 290, "protein":  9, "carbs": 34, "fat": 16},
    {"id": 4, "title": "Greek Yogurt Parfait",    "calories": 240, "protein": 18, "carbs": 32, "fat":  5},
    {"id": 5, "title": "Beef Tacos (x2)",         "calories": 540, "protein": 31, "carbs": 46, "fat": 22},
    {"id": 6, "title": "Veggie Stir Fry",         "calories": 310, "protein": 12, "carbs": 52, "fat":  8},
    {"id": 7, "title": "Banana Oat Smoothie",     "calories": 185, "protein":  7, "carbs": 38, "fat":  3},
    {"id": 8, "title": "Salmon & Quinoa",         "calories": 490, "protein": 44, "carbs": 38, "fat": 15},
    {"id": 9, "title": "Margherita Pizza (2sl)",  "calories": 560, "protein": 22, "carbs": 68, "fat": 18},
    {"id":10, "title": "Lentil Soup",             "calories": 280, "protein": 16, "carbs": 44, "fat":  4},
]

# ─── DATA PERSISTENCE ─────────────────────────────────────────────────────────

def load_data() -> dict:
    """Load saved meal log from JSON file."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_data(data: dict):
    """Persist meal log to JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_today() -> str:
    return datetime.date.today().isoformat()


def get_last_7_days() -> list[str]:
    today = datetime.date.today()
    return [(today - datetime.timedelta(days=i)).isoformat() for i in range(6, -1, -1)]


# ─── CHART ────────────────────────────────────────────────────────────────────

def draw_chart(data: dict):
    """Render the weekly calorie area chart using matplotlib."""
    days = get_last_7_days()
    calories = []
    labels = []
    today_str = get_today()

    for d in days:
        meals = data.get(d, [])
        total = sum(m["calories"] for m in meals)
        calories.append(total)
        dt = datetime.date.fromisoformat(d)
        label = "Today" if d == today_str else dt.strftime("%a")
        labels.append(label)

    # ── Style ──
    bg_dark   = "#080810"
    bg_card   = "#0f0f1a"
    purple    = "#a78bfa"
    red       = "#f87171"
    green     = "#34d399"
    muted     = "#6b6b82"
    text      = "#e2e2f0"

    fig, axes = plt.subplots(1, 2, figsize=(14, 5),
                              gridspec_kw={"width_ratios": [2, 1]})
    fig.patch.set_facecolor(bg_dark)

    # ── Left: Area chart ──
    ax = axes[0]
    ax.set_facecolor(bg_card)
    ax.spines[:].set_visible(False)
    ax.tick_params(colors=muted, labelsize=10)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.xaxis.label.set_color(muted)
    ax.yaxis.label.set_color(muted)

    xs = list(range(len(days)))

    # Area fill
    ax.fill_between(xs, calories, alpha=0.25, color=purple)
    ax.plot(xs, calories, color=purple, linewidth=2.5, zorder=3)

    # Dots — highlight over-goal days
    for i, (x, c) in enumerate(zip(xs, calories)):
        color = red if c > DAILY_GOAL else purple
        ax.scatter(x, c, color=color, s=60, zorder=4, edgecolors="white", linewidths=1)

    # Goal line
    ax.axhline(DAILY_GOAL, color=red, linewidth=1.2, linestyle="--", alpha=0.55, label=f"Goal: {DAILY_GOAL:,} kcal")

    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.set_title("Weekly Calorie Intake", color=text, fontsize=14, pad=14, fontweight="bold")
    ax.set_ylabel("kcal", color=muted, fontsize=10)
    ax.grid(axis="y", color="#1e1e30", linewidth=0.8)
    ax.legend(facecolor=bg_card, edgecolor="#2a2a3a", labelcolor=muted, fontsize=9)

    # Value labels on top of each bar
    for x, c in zip(xs, calories):
        if c > 0:
            ax.text(x, c + 30, f"{c:,}", ha="center", va="bottom",
                    color=red if c > DAILY_GOAL else text, fontsize=9)

    # ── Right: Today's breakdown ──
    ax2 = axes[1]
    ax2.set_facecolor(bg_card)
    ax2.axis("off")

    today_meals = data.get(today_str, [])
    today_cal   = sum(m["calories"] for m in today_meals)
    today_prot  = sum(m["protein"]  for m in today_meals)
    today_carbs = sum(m["carbs"]    for m in today_meals)
    today_fat   = sum(m["fat"]      for m in today_meals)
    deficit     = DAILY_GOAL - today_cal
    pct         = min(today_cal / DAILY_GOAL, 1.0)

    # Title
    ax2.text(0.5, 0.96, "Today", ha="center", va="top", color=text,
             fontsize=14, fontweight="bold", transform=ax2.transAxes)

    # Big calorie number
    cal_color = red if today_cal > DAILY_GOAL else text
    ax2.text(0.5, 0.80, f"{today_cal:,}", ha="center", va="top",
             color=cal_color, fontsize=36, fontweight="bold", transform=ax2.transAxes)
    ax2.text(0.5, 0.65, "kcal consumed", ha="center", va="top",
             color=muted, fontsize=10, transform=ax2.transAxes)

    # Progress bar
    bar_y, bar_h, bar_x0, bar_w = 0.56, 0.045, 0.05, 0.90
    ax2.add_patch(mpatches.FancyBboxPatch((bar_x0, bar_y), bar_w, bar_h,
        boxstyle="round,pad=0.01", linewidth=0,
        facecolor="#1a1a28", transform=ax2.transAxes, zorder=2))
    fill_color = red if today_cal > DAILY_GOAL else purple
    if pct > 0:
        ax2.add_patch(mpatches.FancyBboxPatch((bar_x0, bar_y), bar_w * pct, bar_h,
            boxstyle="round,pad=0.01", linewidth=0,
            facecolor=fill_color, transform=ax2.transAxes, zorder=3))

    deficit_label = f"{abs(deficit)} kcal over" if deficit < 0 else f"{deficit} kcal left"
    deficit_color = red if deficit < 0 else green
    ax2.text(0.5, 0.50, deficit_label, ha="center", va="top",
             color=deficit_color, fontsize=10, transform=ax2.transAxes)

    # Macros
    macros = [("Protein", today_prot, "#60a5fa"), ("Carbs", today_carbs, "#fbbf24"), ("Fat", today_fat, "#f472b6")]
    for i, (name, val, color) in enumerate(macros):
        x = 0.15 + i * 0.32
        ax2.text(x, 0.40, f"{val}g", ha="center", va="top",
                 color=color, fontsize=14, fontweight="bold", transform=ax2.transAxes)
        ax2.text(x, 0.31, name, ha="center", va="top",
                 color=muted, fontsize=9, transform=ax2.transAxes)

    # Meals list
    ax2.text(0.05, 0.22, "Meals logged:", ha="left", va="top",
             color=muted, fontsize=9, transform=ax2.transAxes)
    if today_meals:
        for j, meal in enumerate(today_meals[:4]):
            y_pos = 0.15 - j * 0.08
            ax2.text(0.05, y_pos, f"• {meal['title'][:28]}", ha="left", va="top",
                     color=text, fontsize=8, transform=ax2.transAxes)
            ax2.text(0.95, y_pos, f"{meal['calories']} kcal", ha="right", va="top",
                     color=purple, fontsize=8, transform=ax2.transAxes)
        if len(today_meals) > 4:
            ax2.text(0.5, 0.15 - 4 * 0.08, f"+ {len(today_meals) - 4} more…",
                     ha="center", va="top", color=muted, fontsize=8, transform=ax2.transAxes)
    else:
        ax2.text(0.5, 0.13, "No meals logged yet", ha="center", va="top",
                 color="#3a3a50", fontsize=9, transform=ax2.transAxes)

    plt.tight_layout(pad=2.0)
    plt.savefig("calorie_chart.png", dpi=150, bbox_inches="tight", facecolor=bg_dark)
    plt.show()
    print("\n  Chart saved as calorie_chart.png")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def print_header():
    print("\n" + "─" * 52)
    print("  🍽  Calorie Tracker — Weekly Overview")
    print("─" * 52)


def print_summary(data: dict):
    days = get_last_7_days()
    today = get_today()
    print()
    for d in days:
        meals = data.get(d, [])
        total = sum(m["calories"] for m in meals)
        dt    = datetime.date.fromisoformat(d)
        label = "Today    " if d == today else dt.strftime("%a %b %d")
        bar   = "█" * int(total / 100) + ("▓" if total % 100 >= 50 else "")
        bar   = bar[:30]
        flag  = " ⚠ over!" if total > DAILY_GOAL else ""
        print(f"  {label}  {total:>5} kcal  {bar}{flag}")
    print()


def log_meal_flow(data: dict) -> dict:
    """Interactive flow to search and log a meal for today."""
    today = get_today()

    if SPOONACULAR_API_KEY == "YOUR_API_KEY_HERE":
        print("\n  [Demo mode] No API key set — using built-in recipes.")
        recipes = DEMO_RECIPES
    else:
        query = input("\n  Search recipe: ").strip()
        if not query:
            return data
        print("  Searching Spoonacular…")
        recipes = search_recipes(query)
        if not recipes:
            print("  No results found. Try a different query.")
            return data

    print()
    for i, r in enumerate(recipes, 1):
        print(f"  {i:>2}. {r['title']:<35} {r['calories']:>4} kcal  "
              f"P:{r['protein']}g C:{r['carbs']}g F:{r['fat']}g")

    choice = input("\n  Pick a number (or Enter to cancel): ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(recipes)):
        print("  Cancelled.")
        return data

    recipe = recipes[int(choice) - 1]
    if today not in data:
        data[today] = []
    data[today].append(recipe)
    save_data(data)

    total = sum(m["calories"] for m in data[today])
    print(f"\n  ✓ Added: {recipe['title']}  ({recipe['calories']} kcal)")
    print(f"  Today's total: {total} / {DAILY_GOAL} kcal")
    return data


def remove_meal_flow(data: dict) -> dict:
    """Remove a meal from today's log."""
    today = get_today()
    meals = data.get(today, [])
    if not meals:
        print("\n  No meals logged today.")
        return data

    print("\n  Today's meals:")
    for i, m in enumerate(meals, 1):
        print(f"  {i}. {m['title']:<35} {m['calories']} kcal")

    choice = input("\n  Remove number (or Enter to cancel): ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(meals)):
        print("  Cancelled.")
        return data

    removed = meals.pop(int(choice) - 1)
    data[today] = meals
    save_data(data)
    print(f"\n  ✓ Removed: {removed['title']}")
    return data


def main():
    data = load_data()

    while True:
        print_header()
        print_summary(data)
        print("  1. Log a meal for today")
        print("  2. Remove a meal from today")
        print("  3. Show weekly chart")
        print("  4. Quit")
        print()
        choice = input("  Choose: ").strip()

        if choice == "1":
            data = log_meal_flow(data)
        elif choice == "2":
            data = remove_meal_flow(data)
        elif choice == "3":
            draw_chart(data)
        elif choice == "4":
            print("\n  Bye! 👋\n")
            break
        else:
            print("  Invalid choice, try again.")


if __name__ == "__main__":
    main()
