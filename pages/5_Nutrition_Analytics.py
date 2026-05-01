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

Copy

import json
import os
from datetime import date, timedelta
from pathlib import Path
 
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
 
DATA_FILE = Path(__file__).parent / "data.json"
 
# ── Data helpers ──────────────────────────────────────────────────────────────
 
def load_data() -> list[dict]:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return []
 
 
def save_data(entries: list[dict]) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(entries, f, indent=2)
 
 
def add_entry(
    recipe: str,
    calories: float,
    protein: float,
    carbs: float,
    fat: float,
    meal_type: str = "Lunch",
    entry_date: str | None = None,
) -> None:
    """Add a meal entry to the database."""
    entries = load_data()
    entry_date = entry_date or str(date.today())
    entries.append(
        {
            "id": int(date.today().strftime("%Y%m%d%H%M%S")),
            "date": entry_date,
            "meal": meal_type,
            "recipe": recipe,
            "calories": round(calories, 1),
            "protein": round(protein, 1),
            "carbs": round(carbs, 1),
            "fat": round(fat, 1),
        }
    )
    save_data(entries)
    print(f"  Saved: {recipe} ({calories:.0f} kcal) on {entry_date}")
 
 
def delete_entry(entry_id: int) -> None:
    entries = load_data()
    before = len(entries)
    entries = [e for e in entries if e["id"] != entry_id]
    save_data(entries)
    print(f"  Deleted {before - len(entries)} entry.")
 
 
# ── Chart generation ──────────────────────────────────────────────────────────
 
GOAL_KCAL = 2000  # Daily calorie goal
COLORS = {
    "bar":     "#3266ad",
    "goal":    "#e07b39",
    "protein": "#3266ad",
    "carbs":   "#73726c",
    "fat":     "#c44444",
    "grid":    "#e8e8e8",
    "bg":      "#ffffff",
    "text":    "#1a1a1a",
    "muted":   "#666666",
}
 
 
def _last_7_days() -> list[str]:
    today = date.today()
    return [str(today - timedelta(days=i)) for i in range(6, -1, -1)]
 
 
def _day_totals(entries: list[dict], day: str) -> dict:
    day_entries = [e for e in entries if e["date"] == day]
    return {
        "calories": sum(e["calories"] for e in day_entries),
        "protein":  sum(e["protein"]  for e in day_entries),
        "carbs":    sum(e["carbs"]    for e in day_entries),
        "fat":      sum(e["fat"]      for e in day_entries),
    }
 
 
def generate_charts(output_path: str = "nutrition_report.png") -> str:
    """Generate a 3-panel nutrition chart for the last 7 days."""
    entries = load_data()
    days = _last_7_days()
    totals = [_day_totals(entries, d) for d in days]
 
    labels = []
    for d in days:
        dt = date.fromisoformat(d)
        labels.append(dt.strftime("%a\n%b %d"))
 
    cal_vals  = [t["calories"] for t in totals]
    prot_vals = [t["protein"]  for t in totals]
    carb_vals = [t["carbs"]    for t in totals]
    fat_vals  = [t["fat"]      for t in totals]
 
    x = np.arange(len(days))
    bar_w = 0.55
 
    # ── Figure layout ─────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(14, 11), facecolor=COLORS["bg"])
    fig.suptitle(
        "7-Day Nutrition Dashboard",
        fontsize=18, fontweight="bold", color=COLORS["text"], y=0.97,
    )
 
    gs = fig.add_gridspec(3, 2, hspace=0.55, wspace=0.35,
                          left=0.07, right=0.95, top=0.91, bottom=0.06)
 
    ax_cal   = fig.add_subplot(gs[0, :])   # full-width calorie bar chart
    ax_macro = fig.add_subplot(gs[1, :])   # full-width stacked macro bars
    ax_avg   = fig.add_subplot(gs[2, 0])   # average macro pie
    ax_tbl   = fig.add_subplot(gs[2, 1])   # summary table
 
    _style_axes(ax_cal, ax_macro, ax_avg, ax_tbl)
 
    # ── Panel 1 — Calorie bar chart ───────────────────────────────────────────
    bars = ax_cal.bar(x, cal_vals, width=bar_w, color=COLORS["bar"],
                      zorder=3, label="Calories", linewidth=0)
    ax_cal.axhline(GOAL_KCAL, color=COLORS["goal"], linewidth=1.8,
                   linestyle="--", zorder=4, label=f"Goal ({GOAL_KCAL} kcal)")
 
    for bar, val in zip(bars, cal_vals):
        if val > 0:
            ax_cal.text(
                bar.get_x() + bar.get_width() / 2,
                val + 25, f"{val:.0f}",
                ha="center", va="bottom", fontsize=9,
                color=COLORS["text"], fontweight="500",
            )
 
    ax_cal.set_xticks(x)
    ax_cal.set_xticklabels(labels, fontsize=9, color=COLORS["muted"])
    ax_cal.set_ylabel("kcal", fontsize=10, color=COLORS["muted"])
    ax_cal.set_title("Daily Calorie Intake", fontsize=12,
                     fontweight="bold", color=COLORS["text"], pad=8)
    ax_cal.set_ylim(0, max(max(cal_vals, default=0), GOAL_KCAL) * 1.18)
    ax_cal.legend(fontsize=9, framealpha=0.9, loc="upper right")
    ax_cal.yaxis.set_tick_params(labelsize=9, labelcolor=COLORS["muted"])
 
    # ── Panel 2 — Stacked macro bars ─────────────────────────────────────────
    ax_macro.bar(x, prot_vals, width=bar_w, color=COLORS["protein"],
                 label="Protein", zorder=3, linewidth=0)
    ax_macro.bar(x, carb_vals, width=bar_w, bottom=prot_vals,
                 color=COLORS["carbs"], label="Carbs", zorder=3, linewidth=0)
    bottom2 = [p + c for p, c in zip(prot_vals, carb_vals)]
    ax_macro.bar(x, fat_vals, width=bar_w, bottom=bottom2,
                 color=COLORS["fat"], label="Fat", zorder=3, linewidth=0)
 
    ax_macro.set_xticks(x)
    ax_macro.set_xticklabels(labels, fontsize=9, color=COLORS["muted"])
    ax_macro.set_ylabel("grams", fontsize=10, color=COLORS["muted"])
    ax_macro.set_title("Daily Macros Breakdown", fontsize=12,
                       fontweight="bold", color=COLORS["text"], pad=8)
    ax_macro.legend(fontsize=9, framealpha=0.9, loc="upper right")
    ax_macro.yaxis.set_tick_params(labelsize=9, labelcolor=COLORS["muted"])
 
    # ── Panel 3 — 7-day average pie ───────────────────────────────────────────
    avg_p = np.mean(prot_vals) if any(prot_vals) else 0
    avg_c = np.mean(carb_vals) if any(carb_vals) else 0
    avg_f = np.mean(fat_vals)  if any(fat_vals)  else 0
 
    if avg_p + avg_c + avg_f > 0:
        sizes  = [avg_p * 4, avg_c * 4, avg_f * 9]   # convert to kcal
        clrs   = [COLORS["protein"], COLORS["carbs"], COLORS["fat"]]
        explode= [0.03, 0.03, 0.03]
        wedges, texts, autotexts = ax_avg.pie(
            sizes, labels=["Protein", "Carbs", "Fat"],
            colors=clrs, autopct="%1.0f%%", startangle=90,
            explode=explode, pctdistance=0.78,
            textprops={"fontsize": 9, "color": COLORS["text"]},
        )
        for at in autotexts:
            at.set_fontsize(8)
            at.set_color("white")
            at.set_fontweight("bold")
    else:
        ax_avg.text(0.5, 0.5, "No data yet", ha="center", va="center",
                    transform=ax_avg.transAxes, color=COLORS["muted"])
 
    ax_avg.set_title("7-Day Macro Split\n(by kcal)", fontsize=11,
                     fontweight="bold", color=COLORS["text"], pad=8)
 
    # ── Panel 4 — Summary table ───────────────────────────────────────────────
    avg_cal = np.mean(cal_vals) if any(cal_vals) else 0
 
    row_labels = ["Avg calories / day", "Avg protein / day",
                  "Avg carbs / day",    "Avg fat / day",
                  "Days logged",        "Total meals logged"]
    row_values = [
        f"{avg_cal:.0f} kcal",
        f"{avg_p:.1f} g",
        f"{avg_c:.1f} g",
        f"{avg_f:.1f} g",
        str(sum(1 for v in cal_vals if v > 0)),
        str(len(entries)),
    ]
 
    ax_tbl.axis("off")
    ax_tbl.set_title("Weekly Summary", fontsize=11,
                     fontweight="bold", color=COLORS["text"], pad=8)
 
    for i, (lbl, val) in enumerate(zip(row_labels, row_values)):
        y_pos = 0.88 - i * 0.155
        ax_tbl.text(0.04, y_pos, lbl, transform=ax_tbl.transAxes,
                    fontsize=9.5, color=COLORS["muted"], va="center")
        ax_tbl.text(0.96, y_pos, val, transform=ax_tbl.transAxes,
                    fontsize=9.5, color=COLORS["text"], fontweight="bold",
                    va="center", ha="right")
        if i < len(row_labels) - 1:
            ax_tbl.axhline(
                y_pos - 0.075, xmin=0.02, xmax=0.98,
                color=COLORS["grid"], linewidth=0.7,
                transform=ax_tbl.transAxes,
            )
 
    fig.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=COLORS["bg"])
    plt.close(fig)
    print(f"  Chart saved → {output_path}")
    return output_path
 
 
def _style_axes(*axes):
    for ax in axes:
        ax.set_facecolor(COLORS["bg"])
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines["left"].set_color(COLORS["grid"])
        ax.spines["bottom"].set_color(COLORS["grid"])
        ax.yaxis.grid(True, color=COLORS["grid"], linewidth=0.7, zorder=0)
        ax.set_axisbelow(True)
 
 
# ── CLI helpers ───────────────────────────────────────────────────────────────
 
def list_entries() -> None:
    entries = load_data()
    if not entries:
        print("  No entries yet.")
        return
    days = _last_7_days()
    recent = [e for e in entries if e["date"] in days]
    recent.sort(key=lambda e: (e["date"], e["id"]), reverse=True)
    print(f"\n  {'ID':<14} {'Date':<12} {'Meal':<10} {'Recipe':<25} {'Cal':>6} {'P':>5} {'C':>5} {'F':>5}")
    print("  " + "-" * 85)
    for e in recent:
        print(f"  {e['id']:<14} {e['date']:<12} {e['meal']:<10} {e['recipe'][:24]:<25} "
              f"{e['calories']:>6.0f} {e['protein']:>5.1f} {e['carbs']:>5.1f} {e['fat']:>5.1f}")
 
 
def interactive_menu() -> None:
    print("\n╔══════════════════════════════════════╗")
    print("║     Student Nutrition Tracker         ║")
    print("╚══════════════════════════════════════╝")
 
    while True:
        print("\n  1  Log a meal")
        print("  2  View 7-day entries")
        print("  3  Generate nutrition charts")
        print("  4  Delete an entry")
        print("  5  Exit")
        choice = input("\n  Choose an option: ").strip()
 
        if choice == "1":
            print()
            recipe    = input("  Recipe name:       ").strip()
            calories  = float(input("  Calories (kcal):   "))
            protein   = float(input("  Protein (g):       "))
            carbs     = float(input("  Carbs (g):         "))
            fat       = float(input("  Fat (g):           "))
            meal_type = input("  Meal type [Breakfast/Lunch/Dinner/Snack]: ").strip() or "Lunch"
            entry_date= input(f"  Date (YYYY-MM-DD, leave blank for today): ").strip() or str(date.today())
            add_entry(recipe, calories, protein, carbs, fat, meal_type, entry_date)
 
        elif choice == "2":
            list_entries()
 
        elif choice == "3":
            path = input("  Output filename [nutrition_report.png]: ").strip() or "nutrition_report.png"
            generate_charts(path)
 
        elif choice == "4":
            list_entries()
            try:
                eid = int(input("\n  Enter the ID to delete: ").strip())
                delete_entry(eid)
            except ValueError:
                print("  Invalid ID.")
 
        elif choice == "5":
            print("  Goodbye!\n")
            break
        else:
            print("  Please choose 1–5.")
 
 
# ── Quick demo ────────────────────────────────────────────────────────────────
 
def seed_demo_data() -> None:
    """Add sample data for the last 7 days so the charts look populated."""
    entries = load_data()
    if entries:
        return  # already has data
    today = date.today()
    samples = [
        ("Oatmeal with banana",    350, 12, 60, 7,  "Breakfast"),
        ("Chicken & rice bowl",    620, 42, 75, 10, "Lunch"),
        ("Greek yogurt",           130, 15,  9,  2, "Snack"),
        ("Pasta with tomato sauce",580, 22, 90, 11, "Dinner"),
        ("Scrambled eggs on toast",410, 24, 38, 14, "Breakfast"),
        ("Tuna salad sandwich",    480, 35, 40, 12, "Lunch"),
        ("Apple & peanut butter",  200,  5, 26,  8, "Snack"),
        ("Beef stir-fry",          670, 40, 55, 18, "Dinner"),
        ("Granola with milk",      390, 14, 58,  9, "Breakfast"),
        ("Lentil soup",            420, 20, 60,  7, "Lunch"),
        ("Banana smoothie",        280, 10, 50,  4, "Snack"),
        ("Grilled salmon & veg",   540, 45, 30, 18, "Dinner"),
        ("Avocado toast",          360, 10, 42, 14, "Breakfast"),
        ("Veggie wrap",            430, 16, 60,  9, "Lunch"),
    ]
    for i, (name, cal, p, c, f, meal) in enumerate(samples):
        day = str(today - timedelta(days=i % 7))
        add_entry(name, cal, p, c, f, meal, day)
    print("  Demo data loaded.")
 
 
if __name__ == "__main__":
    import sys
    os.makedirs(Path(__file__).parent, exist_ok=True)
 
    if "--demo" in sys.argv:
        seed_demo_data()
        generate_charts("nutrition_report.png")
    elif "--chart" in sys.argv:
        generate_charts("nutrition_report.png")
    else:
        interactive_menu()


   
