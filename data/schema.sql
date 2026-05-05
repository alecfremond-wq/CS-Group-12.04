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
-- These two tables are required by the Meal Planner page.
-- Both use IF NOT EXISTS so it's safe to run multiple times.
-- ============================================================

-- pantry: ingredients the user currently has at home
-- Used by the Meal Planner to tick off items from the shopping list
-- and by the Pantry page (3_Pantry.py) to manage stock.
CREATE TABLE IF NOT EXISTS pantry (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id)       ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity      REAL    NOT NULL DEFAULT 0,
    unit          TEXT,
    expires_on    DATE,
    UNIQUE (user_id, ingredient_id)   -- one row per ingredient per user
);

CREATE INDEX IF NOT EXISTS idx_pantry_user
    ON pantry (user_id);
-- meal_plan: which recipe is planned for which slot
-- One row = one meal (e.g. user 1, Monday 2026-05-05, Lunch, recipe 42)
-- UNIQUE constraint means each slot can only hold one recipe at a time;
-- INSERT OR REPLACE in the Python code swaps it out cleanly.
CREATE TABLE IF NOT EXISTS meal_plan (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    meal_date   TEXT    NOT NULL,          -- stored as "YYYY-MM-DD"
    meal_type   TEXT    NOT NULL
                    CHECK(meal_type IN ('Breakfast','Lunch','Dinner')),
    recipe_id   INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    UNIQUE (user_id, meal_date, meal_type)
);

CREATE INDEX IF NOT EXISTS idx_meal_plan_user_date
    ON meal_plan (user_id, meal_date);

-- ============================================================
-- trying to link meal planner and recipes page
-- ============================================================

CREATE TABLE IF NOT EXISTS planner_pool (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    recipe_id INTEGER,
    title TEXT,
    meal_type TEXT
);
CREATE TABLE meal_plan_new (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    meal_date TEXT,
    meal_type TEXT CHECK(meal_type IN ('Breakfast','Lunch','Dinner','Dessert')),
    recipe_id INTEGER
);

INSERT INTO meal_plan_new
SELECT * FROM meal_plan;

DROP TABLE meal_plan;

ALTER TABLE meal_plan_new RENAME TO meal_plan;

