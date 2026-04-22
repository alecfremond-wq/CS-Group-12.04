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
import { useState, useEffect } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

// ─── Mock recipe data (replace with your Spoonacular API calls) ───────────────
const RECIPES = [
  { id: 1, title: "Spaghetti Carbonara", calories: 620, protein: 28, carbs: 72, fat: 24, emoji: "🍝" },
  { id: 2, title: "Grilled Chicken Salad", calories: 380, protein: 42, carbs: 18, fat: 14, emoji: "🥗" },
  { id: 3, title: "Avocado Toast", calories: 290, protein: 9, carbs: 34, fat: 16, emoji: "🥑" },
  { id: 4, title: "Greek Yogurt Parfait", calories: 240, protein: 18, carbs: 32, fat: 5, emoji: "🫙" },
  { id: 5, title: "Beef Tacos (x2)", calories: 540, protein: 31, carbs: 46, fat: 22, emoji: "🌮" },
  { id: 6, title: "Veggie Stir Fry", calories: 310, protein: 12, carbs: 52, fat: 8, emoji: "🥦" },
  { id: 7, title: "Banana Oat Smoothie", calories: 185, protein: 7, carbs: 38, fat: 3, emoji: "🍌" },
  { id: 8, title: "Salmon & Quinoa", calories: 490, protein: 44, carbs: 38, fat: 15, emoji: "🐟" },
  { id: 9, title: "Margherita Pizza (2 slices)", calories: 560, protein: 22, carbs: 68, fat: 18, emoji: "🍕" },
  { id: 10, title: "Lentil Soup", calories: 280, protein: 16, carbs: 44, fat: 4, emoji: "🍲" },
];

const DAILY_GOAL = 2000;

// Generate last 7 days
const getLast7Days = () => {
  const days = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push({
      date: d.toISOString().split("T")[0],
      label: i === 0 ? "Today" : d.toLocaleDateString("en-US", { weekday: "short" }),
      meals: [],
    });
  }
  return days;
};

// Seed some initial data
const seedData = (days) => {
  const seeded = days.map((d, i) => ({ ...d, meals: [...d.meals] }));
  seeded[0].meals = [RECIPES[2], RECIPES[6]];
  seeded[1].meals = [RECIPES[0], RECIPES[3]];
  seeded[2].meals = [RECIPES[7], RECIPES[4]];
  seeded[3].meals = [RECIPES[1], RECIPES[9]];
  seeded[4].meals = [RECIPES[5], RECIPES[3]];
  seeded[5].meals = [RECIPES[8], RECIPES[2], RECIPES[6]];
  return seeded;
};

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const cal = payload[0].value;
    const pct = Math.round((cal / DAILY_GOAL) * 100);
    return (
      <div style={{
        background: "#0f0f14",
        border: "1px solid #2a2a3a",
        borderRadius: "12px",
        padding: "12px 16px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
      }}>
        <p style={{ color: "#8b8ba0", fontSize: "11px", margin: "0 0 4px", textTransform: "uppercase", letterSpacing: "0.1em" }}>{label}</p>
        <p style={{ color: "#f0e6ff", fontSize: "22px", fontWeight: "700", margin: "0 0 2px", fontFamily: "'DM Serif Display', serif" }}>
          {cal.toLocaleString()} <span style={{ fontSize: "13px", color: "#a78bfa" }}>kcal</span>
        </p>
        <p style={{ color: cal > DAILY_GOAL ? "#f87171" : "#34d399", fontSize: "12px", margin: 0 }}>
          {pct}% of daily goal
        </p>
      </div>
    );
  }
  return null;
};

export default function CalorieTracker() {
  const [days, setDays] = useState(() => seedData(getLast7Days()));
  const [selectedDay, setSelectedDay] = useState(6); // today
  const [showPicker, setShowPicker] = useState(false);
  const [search, setSearch] = useState("");
  const [added, setAdded] = useState(null);

  const chartData = days.map((d) => ({
    label: d.label,
    calories: d.meals.reduce((s, m) => s + m.calories, 0),
  }));

  const todayCalories = chartData[selectedDay]?.calories ?? 0;
  const todayMeals = days[selectedDay]?.meals ?? [];
  const filtered = RECIPES.filter((r) =>
    r.title.toLowerCase().includes(search.toLowerCase())
  );

  const addMeal = (recipe) => {
    setDays((prev) => {
      const next = prev.map((d, i) =>
        i === selectedDay ? { ...d, meals: [...d.meals, recipe] } : d
      );
      return next;
    });
    setAdded(recipe.id);
    setTimeout(() => setAdded(null), 1200);
  };

  const removeMeal = (mealIndex) => {
    setDays((prev) =>
      prev.map((d, i) =>
        i === selectedDay
          ? { ...d, meals: d.meals.filter((_, j) => j !== mealIndex) }
          : d
      )
    );
  };

  const deficit = DAILY_GOAL - todayCalories;
  const fillPct = Math.min((todayCalories / DAILY_GOAL) * 100, 100);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#080810",
      fontFamily: "'DM Sans', sans-serif",
      color: "#e2e2f0",
      padding: "32px 20px",
    }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet" />

      <style>{`
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #2a2a3a; border-radius: 4px; }
        .day-pill { cursor: pointer; transition: all 0.2s; }
        .day-pill:hover { background: #1e1e2e !important; }
        .recipe-row { transition: all 0.15s; cursor: pointer; }
        .recipe-row:hover { background: #1a1a28 !important; }
        .remove-btn { opacity: 0; transition: opacity 0.15s; }
        .meal-item:hover .remove-btn { opacity: 1; }
        @keyframes pop { 0%{transform:scale(0.9);opacity:0} 60%{transform:scale(1.05)} 100%{transform:scale(1);opacity:1} }
        .pop { animation: pop 0.3s ease forwards; }
        @keyframes slideUp { from{transform:translateY(10px);opacity:0} to{transform:translateY(0);opacity:1} }
        .slide-up { animation: slideUp 0.4s ease forwards; }
      `}</style>

      <div style={{ maxWidth: "860px", margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: "36px" }}>
          <p style={{ color: "#6b6b82", fontSize: "13px", letterSpacing: "0.15em", textTransform: "uppercase", margin: "0 0 6px" }}>Weekly Overview</p>
          <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: "clamp(28px,5vw,42px)", margin: 0, background: "linear-gradient(135deg,#e2d9ff,#a78bfa)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Calorie Tracker
          </h1>
        </div>

        {/* Chart Card */}
        <div style={{ background: "#0f0f1a", borderRadius: "20px", border: "1px solid #1e1e30", padding: "28px 24px 16px", marginBottom: "24px" }} className="slide-up">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", flexWrap: "wrap", gap: "8px" }}>
            <div>
              <p style={{ margin: 0, color: "#6b6b82", fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.1em" }}>7-Day Calories</p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", background: "#1a1a28", padding: "6px 12px", borderRadius: "8px" }}>
              <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#f87171" }} />
              <span style={{ fontSize: "12px", color: "#8b8ba0" }}>Goal: {DAILY_GOAL.toLocaleString()} kcal</span>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}
              onClick={(e) => { if (e?.activeTooltipIndex !== undefined) setSelectedDay(e.activeTooltipIndex); }}>
              <defs>
                <linearGradient id="calGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#a78bfa" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e1e30" vertical={false} />
              <XAxis dataKey="label" tick={{ fill: "#6b6b82", fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#6b6b82", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: "#a78bfa", strokeWidth: 1, strokeDasharray: "4 4" }} />
              <ReferenceLine y={DAILY_GOAL} stroke="#f87171" strokeDasharray="5 5" strokeOpacity={0.5} />
              <Area type="monotone" dataKey="calories" stroke="#a78bfa" strokeWidth={2.5}
                fill="url(#calGrad)" dot={(props) => {
                  const isSelected = props.index === selectedDay;
                  return <circle key={props.index} cx={props.cx} cy={props.cy} r={isSelected ? 6 : 4}
                    fill={isSelected ? "#a78bfa" : "#1e1e30"} stroke="#a78bfa" strokeWidth={2} style={{ cursor: "pointer" }} />;
                }} activeDot={{ r: 7, fill: "#a78bfa", stroke: "#fff", strokeWidth: 2 }} />
            </AreaChart>
          </ResponsiveContainer>

          {/* Day pills */}
          <div style={{ display: "flex", gap: "8px", marginTop: "16px", justifyContent: "space-between" }}>
            {days.map((d, i) => {
              const cal = chartData[i]?.calories ?? 0;
              const over = cal > DAILY_GOAL;
              return (
                <div key={d.date} className="day-pill" onClick={() => setSelectedDay(i)}
                  style={{
                    flex: 1, textAlign: "center", padding: "8px 4px", borderRadius: "10px", cursor: "pointer",
                    background: selectedDay === i ? "#1e1530" : "transparent",
                    border: selectedDay === i ? "1px solid #a78bfa44" : "1px solid transparent",
                  }}>
                  <div style={{ fontSize: "11px", color: selectedDay === i ? "#a78bfa" : "#6b6b82", fontWeight: selectedDay === i ? "600" : "400" }}>{d.label}</div>
                  <div style={{ fontSize: "11px", color: over ? "#f87171" : "#34d399", marginTop: "2px" }}>
                    {cal > 0 ? `${(cal / 1000).toFixed(1)}k` : "–"}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Bottom row */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>

          {/* Today's Stats */}
          <div style={{ background: "#0f0f1a", borderRadius: "20px", border: "1px solid #1e1e30", padding: "24px" }}>
            <p style={{ margin: "0 0 16px", color: "#6b6b82", fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.1em" }}>
              {days[selectedDay]?.label ?? ""}
            </p>
            <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: "48px", lineHeight: 1, marginBottom: "4px", color: todayCalories > DAILY_GOAL ? "#f87171" : "#e2d9ff" }}>
              {todayCalories.toLocaleString()}
            </div>
            <div style={{ color: "#6b6b82", fontSize: "13px", marginBottom: "20px" }}>kcal consumed</div>

            {/* Progress bar */}
            <div style={{ background: "#1a1a28", borderRadius: "999px", height: "6px", overflow: "hidden", marginBottom: "8px" }}>
              <div style={{
                height: "100%", borderRadius: "999px", transition: "width 0.5s ease",
                width: `${fillPct}%`,
                background: todayCalories > DAILY_GOAL
                  ? "linear-gradient(90deg,#f87171,#fb923c)"
                  : "linear-gradient(90deg,#a78bfa,#60a5fa)",
              }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#6b6b82" }}>
              <span>0</span>
              <span style={{ color: deficit < 0 ? "#f87171" : "#34d399" }}>
                {deficit < 0 ? `${Math.abs(deficit)} over` : `${deficit} left`}
              </span>
              <span>{DAILY_GOAL.toLocaleString()}</span>
            </div>

            {/* Macros */}
            {todayMeals.length > 0 && (
              <div style={{ display: "flex", gap: "8px", marginTop: "16px" }}>
                {[
                  { label: "Protein", val: todayMeals.reduce((s, m) => s + m.protein, 0), color: "#60a5fa", unit: "g" },
                  { label: "Carbs", val: todayMeals.reduce((s, m) => s + m.carbs, 0), color: "#fbbf24", unit: "g" },
                  { label: "Fat", val: todayMeals.reduce((s, m) => s + m.fat, 0), color: "#f472b6", unit: "g" },
                ].map((m) => (
                  <div key={m.label} style={{ flex: 1, background: "#1a1a28", borderRadius: "10px", padding: "10px 8px", textAlign: "center" }}>
                    <div style={{ color: m.color, fontWeight: "600", fontSize: "16px" }}>{m.val}{m.unit}</div>
                    <div style={{ color: "#6b6b82", fontSize: "10px", marginTop: "2px" }}>{m.label}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Meals logged */}
          <div style={{ background: "#0f0f1a", borderRadius: "20px", border: "1px solid #1e1e30", padding: "24px", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <p style={{ margin: 0, color: "#6b6b82", fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.1em" }}>Meals Logged</p>
              {selectedDay === 6 && (
                <button onClick={() => setShowPicker(true)} style={{
                  background: "linear-gradient(135deg,#7c3aed,#4f46e5)", border: "none", borderRadius: "8px",
                  color: "#fff", fontSize: "12px", fontWeight: "600", padding: "6px 14px", cursor: "pointer",
                  fontFamily: "'DM Sans', sans-serif",
                }}>+ Add</button>
              )}
            </div>

            <div style={{ flex: 1, overflowY: "auto", maxHeight: "220px", display: "flex", flexDirection: "column", gap: "8px" }}>
              {todayMeals.length === 0 ? (
                <div style={{ textAlign: "center", color: "#3a3a50", padding: "32px 0", fontSize: "13px" }}>
                  No meals logged yet
                </div>
              ) : todayMeals.map((meal, i) => (
                <div key={i} className="meal-item" style={{
                  display: "flex", alignItems: "center", gap: "10px",
                  background: "#131320", borderRadius: "10px", padding: "10px 12px",
                  border: "1px solid #1e1e30",
                }}>
                  <span style={{ fontSize: "20px" }}>{meal.emoji}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: "13px", fontWeight: "500", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{meal.title}</div>
                    <div style={{ fontSize: "11px", color: "#6b6b82" }}>{meal.calories} kcal</div>
                  </div>
                  {selectedDay === 6 && (
                    <button className="remove-btn" onClick={() => removeMeal(i)} style={{
                      background: "none", border: "none", color: "#f87171", cursor: "pointer", fontSize: "16px", padding: "2px 4px", lineHeight: 1,
                    }}>×</button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Recipe Picker Modal */}
        {showPicker && (
          <div onClick={() => setShowPicker(false)} style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100, padding: "20px",
          }}>
            <div onClick={(e) => e.stopPropagation()} className="pop" style={{
              background: "#0f0f1a", border: "1px solid #2a2a3a", borderRadius: "24px",
              width: "100%", maxWidth: "460px", maxHeight: "80vh", display: "flex", flexDirection: "column",
              overflow: "hidden",
            }}>
              <div style={{ padding: "24px 24px 16px", borderBottom: "1px solid #1e1e30" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <h2 style={{ margin: 0, fontFamily: "'DM Serif Display', serif", fontSize: "22px" }}>Log a Meal</h2>
                  <button onClick={() => setShowPicker(false)} style={{ background: "#1a1a28", border: "none", borderRadius: "50%", width: "32px", height: "32px", color: "#8b8ba0", fontSize: "18px", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>×</button>
                </div>
                <input
                  autoFocus
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search recipes…"
                  style={{
                    width: "100%", background: "#1a1a28", border: "1px solid #2a2a3a", borderRadius: "12px",
                    color: "#e2e2f0", fontSize: "14px", padding: "12px 16px", outline: "none",
                    fontFamily: "'DM Sans', sans-serif",
                  }}
                />
              </div>
              <div style={{ overflowY: "auto", padding: "12px" }}>
                {filtered.map((r) => (
                  <div key={r.id} className="recipe-row" onClick={() => { addMeal(r); }}
                    style={{
                      display: "flex", alignItems: "center", gap: "12px",
                      padding: "12px", borderRadius: "12px", marginBottom: "4px",
                      background: added === r.id ? "#1e1530" : "transparent",
                      border: added === r.id ? "1px solid #a78bfa44" : "1px solid transparent",
                    }}>
                    <span style={{ fontSize: "24px", flexShrink: 0 }}>{r.emoji}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: "14px", fontWeight: "500", marginBottom: "2px" }}>{r.title}</div>
                      <div style={{ display: "flex", gap: "10px" }}>
                        <span style={{ fontSize: "11px", color: "#a78bfa" }}>{r.calories} kcal</span>
                        <span style={{ fontSize: "11px", color: "#6b6b82" }}>P:{r.protein}g · C:{r.carbs}g · F:{r.fat}g</span>
                      </div>
                    </div>
                    <div style={{
                      width: "28px", height: "28px", borderRadius: "50%", flexShrink: 0,
                      background: added === r.id ? "#7c3aed" : "#1a1a28",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: "14px", transition: "all 0.2s",
                    }}>
                      {added === r.id ? "✓" : "+"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}


   
