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

import matplotlib.pyplot as plt

def generate_calorie_report():
    # 1. Setup our timeline
    days = ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"]
    calories = []

    print("--- 7-Day Calorie Tracker Setup ---")
    
    # 2. Input Loop: Collecting your data
    for day in days:
        while True:
            try:
                val = int(input(f"Enter total calories for {day}: "))
                calories.append(val)
                break
            except ValueError:
                print("Please enter a valid number.")

    # 3. Visualization logic
    plt.figure(figsize=(10, 6))
    plt.bar(days, calories, color='skyblue', edgecolor='navy')
    
    # Adding a goal line (Optional: e.g., 2000 kcal)
    plt.axhline(y=2000, color='r', linestyle='--', label='Daily Goal (2000)')
    
    # Labeling the graph
    plt.title('Calorie Intake: Past 7 Days', fontsize=14)
    plt.xlabel('Days', fontsize=12)
    plt.ylabel('Calories (kcal)', fontsize=12)
    plt.legend()
    
    # Show the final product
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    generate_calorie_report()
