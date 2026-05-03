-- ============================================================
-- schema_meal_planner.sql
-- Run this ONCE to add the meal_plan table to your database.
-- Paste these lines at the bottom of your existing data/schema.sql
-- ============================================================

-- meal_plan: one row per (user, date, meal-type, recipe) combination
-- INSERT OR REPLACE prevents duplicate slots (enforced by UNIQUE key below)
CREATE TABLE IF NOT EXISTS meal_plan (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    meal_date   TEXT    NOT NULL,  -- stored as "YYYY-MM-DD"
    meal_type   TEXT    NOT NULL   CHECK(meal_type IN ('Breakfast','Lunch','Dinner')),
    recipe_id   INTEGER NOT NULL,

    -- Each slot can only hold one recipe at a time
    UNIQUE (user_id, meal_date, meal_type),

    FOREIGN KEY (user_id)   REFERENCES users(id)   ON DELETE CASCADE,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);

-- Speed up the weekly queries (WHERE meal_date BETWEEN ? AND ?)
CREATE INDEX IF NOT EXISTS idx_meal_plan_user_date
    ON meal_plan (user_id, meal_date);

-- ============================================================
-- Existing tables the Meal Planner also reads
-- (already in your schema — listed here just for reference):
--
--   recipes (id, name, cuisine, calories, protein, carbs, fat,
--            cooking_time, spiciness)
--
--   recipe_ingredients (recipe_id, ingredient_id, quantity)
--
--   ingredients (id, name, unit)
--
--   pantry (user_id, ingredient_id, quantity)
--
--   users (id, ...)
-- ============================================================
