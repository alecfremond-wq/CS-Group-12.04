-- CookTogether database schema.
-- Edit this file to add tables/columns. `init_db()` runs it on app start.
-- All statements are idempotent (IF NOT EXISTS) so reloading is safe.

CREATE TABLE IF NOT EXISTS recipes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    cuisine         TEXT,           -- e.g. "Italian", "Thai" — used by World Map
    country_iso     TEXT,           -- ISO-3 code for the map layer
    minutes         INTEGER,        -- total prep + cook time
    servings        INTEGER,
    difficulty      TEXT CHECK(difficulty IN ('easy','medium','hard')),
    kcal_per_serv   REAL,
    protein_g       REAL,
    carbs_g         REAL,
    fat_g           REAL,
    cost_chf        REAL,           -- estimated cost per serving in CHF
    instructions    TEXT,
    image_url       TEXT,
    source_url      TEXT,           -- where the recipe came from (API or manual)
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingredients (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT UNIQUE NOT NULL,
    category TEXT                   -- e.g. "vegetable", "dairy", "grain"
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id     INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity      REAL,
    unit          TEXT,
    PRIMARY KEY (recipe_id, ingredient_id)
);

-- Very light user model. The course is single-user in practice (each student
-- runs their own instance), but we keep a users table so multi-profile demos
-- are easy.
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    diet         TEXT,              -- "omnivore" / "vegetarian" / "vegan" / ...
    allergies    TEXT,              -- comma-separated for simplicity
    budget_weekly REAL,             -- CHF / week
    skill_level  TEXT CHECK(skill_level IN ('beginner','intermediate','advanced')),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cooking_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    recipe_id  INTEGER REFERENCES recipes(id) ON DELETE CASCADE,
    cooked_on  DATE    NOT NULL,
    rating     INTEGER CHECK(rating BETWEEN 1 AND 5)
);

CREATE INDEX IF NOT EXISTS idx_recipes_cuisine ON recipes(cuisine);
CREATE INDEX IF NOT EXISTS idx_history_user   ON cooking_history(user_id);

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
