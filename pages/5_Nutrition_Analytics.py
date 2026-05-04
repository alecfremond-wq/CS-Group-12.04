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
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict
import tabulate

class MealTracker:
    def __init__(self, data_file: str = "meals.json"):
        self.data_file = data_file
        self.meals = self.load_meals()

    def load_meals(self) -> List[Dict]:
        """Load meals from JSON file"""
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                return json.load(f)
        return []

    def save_meals(self):
        """Save meals to JSON file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.meals, f, indent=2)

    def add_meal(self, date: str, meal_name: str, calories: int):
        """
        Add a meal to the tracker
        date format: YYYY-MM-DD
        """
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD")
            return False

        meal = {
            "date": date,
            "name": meal_name,
            "calories": calories,
            "timestamp": datetime.now().isoformat()
        }
        self.meals.append(meal)
        self.save_meals()
        print(f"✓ Added {meal_name} ({calories} cal) on {date}")
        return True

    def get_last_seven_days(self) -> Dict[str, int]:
        """Get calorie totals for the last 7 days"""
        today = datetime.now().date()
        calorie_map = {}

        for i in range(6, -1, -1):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            calorie_map[date] = 0

        for meal in self.meals:
            if meal["date"] in calorie_map:
                calorie_map[meal["date"]] += meal["calories"]

        return calorie_map

    def display_matrix(self):
        """Display calorie intake as a matrix for the past 7 days"""
        calorie_data = self.get_last_seven_days()
        
        if not calorie_data:
            print("No meal data available")
            return

        print("\n" + "="*60)
        print("CALORIE INTAKE MATRIX - LAST 7 DAYS")
        print("="*60)

        # Create table data
        table_data = []
        dates = list(calorie_data.keys())
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        for idx, date in enumerate(dates):
            day_name = day_names[idx % 7]
            calories = calorie_data[date]
            bar_length = calories // 100
            bar = "█" * min(bar_length, 30)
            table_data.append([day_name, date, calories, bar])

        headers = ["Day", "Date", "Calories", "Visual"]
        print(tabulate.tabulate(table_data, headers=headers, tablefmt="grid"))

        # Summary statistics
        total = sum(calorie_data.values())
        average = total / 7
        max_day = max(calorie_data, key=calorie_data.get)
        min_day = min(calorie_data, key=calorie_data.get)

        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Total Calories (7 days):  {total:,} cal")
        print(f"Daily Average:            {average:.0f} cal")
        print(f"Highest Day:              {max_day} ({calorie_data[max_day]:,} cal)")
        print(f"Lowest Day:               {min_day} ({calorie_data[min_day]:,} cal)")
        print("="*60 + "\n")

    def display_meals_by_date(self, date: str = None):
        """Display all meals for a specific date or all dates"""
        if date:
            meals_on_date = [m for m in self.meals if m["date"] == date]
            if not meals_on_date:
                print(f"No meals recorded for {date}")
                return
            print(f"\nMeals on {date}:")
            table_data = [[m["name"], m["calories"]] for m in meals_on_date]
            print(tabulate.tabulate(table_data, headers=["Meal", "Calories"], tablefmt="grid"))
            print(f"Total: {sum(m['calories'] for m in meals_on_date)} cal\n")
        else:
            # Group by date
            by_date = {}
            for meal in self.meals:
                if meal["date"] not in by_date:
                    by_date[meal["date"]] = []
                by_date[meal["date"]].append(meal)

            for date in sorted(by_date.keys(), reverse=True):
                meals = by_date[date]
                print(f"\n{date}:")
                table_data = [[m["name"], m["calories"]] for m in meals]
                print(tabulate.tabulate(table_data, headers=["Meal", "Calories"], tablefmt="grid"))
                print(f"Total: {sum(m['calories'] for m in meals)} cal")


def main():
    tracker = MealTracker()
    
    while True:
        print("\n" + "="*60)
        print("MEAL TRACKER MENU")
        print("="*60)
        print("1. Add meal")
        print("2. View 7-day matrix")
        print("3. View meals by date")
        print("4. View all meals")
        print("5. Exit")
        print("="*60)
        
        choice = input("Select an option (1-5): ").strip()

        if choice == "1":
            date = input("Enter date (YYYY-MM-DD) [today]: ").strip() or datetime.now().strftime("%Y-%m-%d")
            meal_name = input("Enter meal name: ").strip()
            try:
                calories = int(input("Enter calories: ").strip())
                tracker.add_meal(date, meal_name, calories)
            except ValueError:
                print("Invalid calorie input")

        elif choice == "2":
            tracker.display_matrix()

        elif choice == "3":
            date = input("Enter date (YYYY-MM-DD) [show all]: ").strip()
            tracker.display_meals_by_date(date if date else None)

        elif choice == "4":
            tracker.display_meals_by_date()

        elif choice == "5":
            print("Goodbye!")
            break

        else:
            print("Invalid option")


if __name__ == "__main__":
    main()
>>>>>>> main
