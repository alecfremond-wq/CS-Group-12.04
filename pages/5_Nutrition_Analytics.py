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
import numpy as np

# --- 1. SET UP THE APPLICATION ---
st.set_page_config(page_title="Weekly Calorie Intake Dashboard", layout="wide")

# Custom CSS for UI styling (matching image_1.png and image_2.png)
st.markdown("""
<style>
    /* Global style fixes */
    .stApp { background-color: #fcfcfc; }
    .reportview-container .main .block-container { padding-top: 2rem; }
    
    /* Chart and Summary Header Styles */
    .dashboard-header { font-size: 1.2rem; color: #757575; font-weight: normal; margin-bottom: -10px; }
    .calorie-avg { font-size: 2.8rem; font-weight: bold; margin-bottom: 20px; }

    /* Custom CSS for clickable day cards */
    div.stButton > button {
        background-color: white;
        color: #757575;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 10px 15px;
        width: 100%;
        text-align: center;
        transition: all 0.2s;
        box-shadow: 0px 2px 4px rgba(0,0,0,0.05);
    }
    div.stButton > button:hover {
        border-color: #a0a0a0;
        color: #333;
    }
    div.stButton > button:active {
        background-color: #f8f8f8;
        transform: translateY(1px);
    }
    
    /* Highlight style for the selected day card */
    div.stButton > button.selected-day {
        border: 2px solid #3e88e2;
        color: black;
        font-weight: bold;
    }

    /* Styles for the summary metrics */
    .summary-card {
        background-color: #f8f8f8;
        border-radius: 12px;
        padding: 20px;
        margin-top: 15px;
    }
    .summary-title { color: #757575; font-size: 1rem; margin-bottom: 5px; }
    .summary-value { font-size: 1.8rem; font-weight: bold; }

    /* Define metric colors for the chart and bars */
    :root {
        --color-under: #3e88e2; /* Blue */
        --color-over: #e84c4c;  /* Red */
        --color-goal: #72ac4c;  /* Green */
    }
</style>
""", unsafe_allow_stdio=True)


# --- 2. GENERATE AND MANAGE DATA ---
# (Simulating user data based on the images)
DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAILY_GOAL = 2000

# Function to generate a realistic weekly dataset
@st.cache_data
def get_weekly_data():
    # Data structure from image_1.png bar chart
    weekly_history = {
        "Mon": {"total": 1840, "breakdown": {"Breakfast": 420, "Lunch": 680, "Snacks": 210, "Dinner": 530}},
        "Tue": {"total": 2200, "breakdown": {"Breakfast": 500, "Lunch": 800, "Snacks": 300, "Dinner": 600}},
        "Wed": {"total": 1780, "breakdown": {"Breakfast": 400, "Lunch": 650, "Snacks": 200, "Dinner": 530}},
        "Thu": {"total": 2450, "breakdown": {"Breakfast": 550, "Lunch": 900, "Snacks": 400, "Dinner": 600}},
        "Fri": {"total": 1980, "breakdown": {"Breakfast": 450, "Lunch": 730, "Snacks": 250, "Dinner": 550}}, # Close to goal
        "Sat": {"total": 2330, "breakdown": {"Breakfast": 520, "Lunch": 850, "Snacks": 360, "Dinner": 600}},
        "Sun": {"total": 1650, "breakdown": {"Breakfast": 380, "Lunch": 600, "Snacks": 180, "Dinner": 490}},
    }
    
    # Pre-process history data for main chart
    bar_chart_data = []
    for day, data in weekly_history.items():
        total = data["total"]
        status = 'Goal'
        if total < DAILY_GOAL - 50: status = 'Under' # A tolerance range for 'Goal'
        elif total > DAILY_GOAL + 50: status = 'Over'
        
        bar_chart_data.append({
            "Day": day,
            "Calories": total,
            "Goal": DAILY_GOAL,
            "Status": status
        })

    return pd.DataFrame(bar_chart_data), weekly_history

# Load the data
df_bars, history_dict = get_weekly_data()

# Calculate dynamic aggregate metrics
avg_calories_raw = df_bars["Calories"].mean()
formatted_avg = "{:,.0f}".format(avg_calories_raw)
weekly_total_raw = df_bars["Calories"].sum()
formatted_total = "{:,.0f}".format(weekly_total_raw)
best_day_row = df_bars.loc[df_bars["Calories"].idxmin()] # "Best" is closest to goal, here interpreted as lowest
best_day_text = f"{best_day_row['Day']} · {best_day_row['Calories']:,}"
days_on_goal = len(df_bars[df_bars['Status'] == 'Goal'])


# --- 3. BUILD THE UI ---

# 3.1: HEADER SECTION
st.markdown('<p class="dashboard-header">Past 7 days</p>', unsafe_allow_stdio=True)
st.markdown(f'<p class="calorie-avg">{formatted_avg} kcal avg/day</p>', unsafe_allow_stdio=True)


# 3.2: THE MAIN BAR CHART (image_1.png)
# Color mapping matching the colors from the image
status_color_scale = alt.Scale(
    domain=['Under', 'Over', 'Goal'],
    range=['#3e88e2', '#e84c4c', '#72ac4c'] # Blue, Red, Green
)

base_chart = alt.Chart(df_bars).encode(
    x=alt.X('Day', sort=DAYS_OF_WEEK, axis=alt.Axis(title=None, labelAngle=0, labelColor='#757575', tickColor='#e0e0e0', domain=False)),
    y=alt.Y('Calories', axis=alt.Axis(title=None, values=[1200, 1400, 1600, 1800, 2000, 2200, 2400, 2600, 2800], gridColor='#e0e0e0', labelColor='#757575', tickColor='#e0e0e0', domain=False)),
)

# The bars, colored by status
bars = base_chart.mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8, size=40).encode(
    color=alt.Color('Status', scale=status_color_scale, legend=None),
    tooltip=['Day', alt.Tooltip('Calories', format=',') ]
)

# The dashed goal line
goal_line = base_chart.mark_rule(strokeDash=[4, 4], color='#a0a0a0', size=1).encode(
    y='Goal'
)

# Combine and render the chart
main_bar_chart = (bars + goal_line).properties(height=350).configure_view(strokeWidth=0)
st.altair_chart(main_bar_chart, use_container_width=True)


# 3.3: CLICKABLE DAY CARDS (NAVIGATION) (image_1.png footer)
st.markdown("### ") # Spacer

# Create 7 columns for the day selection buttons
cols = st.columns(7)

# Need to manage which day is currently selected across interactions
# We will use Streamlit's session state to track this.
if 'selected_day' not in st.session_state:
    st.session_state.selected_day = 'Mon' # Default to Monday

# Render each day card as a button
for i, day in enumerate(DAYS_OF_WEEK):
    day_total_raw = df_bars.loc[df_bars['Day'] == day, 'Calories'].values[0]
    # Format total as "1.8k" as seen in image_1.png
    formatted_total_k = f"{day_total_raw/1000:.1f}k"
    
    # Create the button content (Day + Total)
    button_label = f"**{day}**\n\n{formatted_total_k}"
    
    # We apply custom CSS class if the day is currently selected
    is_selected = (day == st.session_state.selected_day)
    button_type = "primary" if is_selected else "secondary"

    # Important trick: use columns and st.button callback to manage selection
    # We define a function for the callback
    def make_day_selector(day_to_select):
        def select_day():
            st.session_state.selected_day = day_to_select
        return select_day

    # Place the button in its column
    cols[i].button(
        button_label, 
        key=f"btn_{day}", 
        on_click=make_day_selector(day), 
        type=button_type, 
        help=f"View details for {day}"
    )


# 3.4: DAY BREAKDOWN & SUMMARY (image_2.png)
st.markdown("---") # Visual separator

# Get the data for the currently selected day
selected_data = history_dict[st.session_state.selected_day]
breakdown_data = selected_data['breakdown']
selected_day_total = selected_data['total']
formatted_selected_total = "{:,.0f}".format(selected_day_total)

# Header for the breakdown section
st.markdown(f"#### {st.session_state.selected_day} — {formatted_selected_total} kcal total")

# Calculate meal breakdown percentages/maxes for normalization
meal_names = list(breakdown_data.keys())
meal_cals = list(breakdown_data.values())
# For the 'max' background bar, we use a fixed max or make it dynamic.
# Let's use the largest meal in the whole history as the scale benchmark.
MAX_MEAL_CAL = 950 # An arbitrary max benchmark based on the history data

# Build the meal breakdown list
for meal, cals in breakdown_data.items():
    # Percentage of benchmark
    filled_pct = min(100, (cals / MAX_MEAL_CAL) * 100)
    remaining_pct = 100 - filled_pct
    
    col_meal, col_bar, col_val = st.columns([2, 6, 1])
    
    col_meal.markdown(f"**{meal}**")
    
    # Create the progress bar using HTML/CSS
    # We use linear gradients to create the blue-filled portion on a grey background.
    bar_html = f"""
    <div style="background-color: #f1f1f1; border-radius: 8px; width: 100%; height: 10px; margin-top: 5px; position: relative; overflow: hidden;">
        <div style="background-color: #3e88e2; width: {filled_pct}%; height: 10px; border-radius: 8px 0 0 8px;"></div>
    </div>
    """
    col_bar.markdown(bar_html, unsafe_allow_stdio=True)
    
    col_val.markdown(f"{cals:,} kcal")


# 3.5: BOTTOM SUMMARY CARDS (image_2.png)
st.markdown("### ") # Spacer

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div class="summary-card">
        <div class="summary-title">Best day</div>
        <div class="summary-value">{best_day_text}</div>
    </div>
    """, unsafe_allow_stdio=True)

with col2:
    st.markdown(f"""
    <div class="summary-card">
        <div class="summary-title">Days on goal</div>
        <div class="summary-value">{days_on_goal} / 7 days</div>
    </div>
    """, unsafe_allow_stdio=True)

with col3:
    st.markdown(f"""
    <div class="summary-card">
        <div class="summary-title">Weekly total</div>
        <div class="summary-value">{formatted_total} kcal</div>
    </div>
    """, unsafe_allow_stdio=True)
