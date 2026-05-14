# CookTogether 🍳

**Group 12.04 — FCS/BWL · Grundlagen und Methoden der Informatik (HSG, FS26)**

**Business problem:** 
Many students perceive cooking as a time-consuming chore. They can't think about what to eat, how to eat healthy or how to meal prep efficiently while balancing busy schedules. Cooking is often not considered an enjoyable activity.

**Our solution:**
CookTogether is a Streamlit web app designed to help students view cooking as a more pleasent activity. The app helps you find new recipies which are also sorted on an interactive map to explore new flavors. In addition it provides pantry-aware suggestions, a weekly meal planning table, nutrition analytics
and ML-powered recommendations. Furthermore there is also a social aspect to the app, you can create your profile and also add your friends in order to share personal recipies and wishlists. 

---

## Quick start

```bash
# 1. clone (you already have the repo)
git clone <repo-url>
cd CS-Group-Project

# 2. create & activate a virtual environment
python -m venv .venv

source .venv/bin/activate         # macOS / Linux
  .venv\Scripts\activate          # Windows PowerShell

# 3. install dependencies
pip install -r requirements.txt

# 4. run the app
streamlit run app.py

The app will open automatically in your browser at "http://localhost:8051". 

```

The first start creates `data/cooktogether.db` automatically from
`data/schema.sql` — nothing else to set up.

## Project structure

```
CS-Groupe-Project/
├── app.py
├── Home.py                    # Streamlit entrypoint (home page)
├── pages/                      # one file per feature — edit freely without conflicts
│   ├── 1_Pantry.py
│   ├── 2_Recipes.py
│   ├── 3_Meal_Planner.py
│   ├── 4_Nutrition.py
│   ├── 5_Reccomendations.py
│   ├── 6_Wishlist.py
│   ├── 7_My_Recipes.py
    └── 8_Friends.py
├── src/
│   ├── data/
│   │   ├── api_client.py       # TheMealDB API wrapper
│   │   ├── database.py         # SQLite helpers (init_db, query_df, execute)
│   │   ├── pantry_repo.py
│       └── user_repo.py
│   ├── models/
│   │   └── recommender.py      # ML recommender (scikit-learn)
│   ├── components/
│   │   └── ui.py               # shared UI helpers (page_header, empty_state)
│   └── utils/
│       └── session.py          # session_state init + require_profile()
├── data/
│   ├── schema.sql              # DB schema — edit here, not in database.py
│  
├── assets/                     # images, logos
├── tests/                      # (optional) pytest tests
├── docs/
│   ├── CONTRIBUTING.md         # git workflow — READ THIS
│   └── CONTRIBUTION_MATRIX.md  # REQUIRED deliverable — keep up to date!
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example    # copy to secrets.toml for API keys
├── requirements.txt
├── recipe_data.py
└── .gitignore
```
## Feature overview 
```
# 1. Home: This is the first page you land on. It introduces you to the app and makes you sign-up or log-in your profile.

# 2. Pantry: Here you can insert what you currently have in your kitchen. Afterwards the recipe page will tell you if the ingredients are "Pantry-friendly", "Pantry available" or not.

# 3. Recipes: You can search for new recipes using the search bar or the "Browse by cuisine" (interactive world map visualization) function and add them to your wishlist.

# 4. Meal Planner: It helps organize meals for the next week, you can add the recipes from your wishlist.

# 5. Nutrition Analytics: You can set your calorie goal, the chart will show the calorie intake of the week based on the meal planner (graph visualization).

# 6. Recommendations: Based on your wishlist this feature will recommend other recipes through machine learning (k-NN model, looks for recipes with similar ingredients).

# 7. Wishlist: Here you will see the recipes that were saved on the recipes page or from the recommendations function.

# 8. My Recipes: You can create and save your own personal recipes.

# 9. Friends: Here you can follow other users and see their own recipes and their wishlists (interactive).

```
## Data Sources and APIs

```
| API | Usage | Docs |
|-----|-------|------|
| [Spoonacular](https://spoonacular.com/food-api) | Recipe search, nutrition info | [Docs](https://spoonacular.com/food-api/docs) |
| [TheMealDB](https://www.themealdb.com/api.php) | Recipe search, meal categories | [Docs](https://www.themealdb.com/api.php) |

```




## Mapping features → grading requirements

The course grades 8 requirements (see `FCS-BWL-GroupProject.pdf` in the
`Group Project` folder). Here's which part of the code covers which:

| # | Requirement                               | Where it lives                                |
|---|-------------------------------------------|-----------------------------------------------|
| 1 | Problem clearly formulated                | `README.md`, video pitch                      |
| 2 | Data via API **and/or** database          | `src/data/api_client.py`, `src/data/database.py` |
| 3 | Useful data visualisation                 | `pages/5_Nutrition_Analytics.py`, `pages/6_World_Map.py`, `pages/4_Meal_Planner.py` |
| 4 | User interactions                         | `pages/1_Onboarding.py`, `pages/3_Pantry.py`, `pages/2_Recipes.py`, `pages/4_Meal_Planner.py` |
| 5 | Machine learning                          | `src/models/recommender.py`, `pages/7_Recommendations.py` |
| 6 | Well-commented source code                | every file — docstrings + inline notes        |
| 7 | Contribution documented                   | `docs/CONTRIBUTION_MATRIX.md`                 |
| 8 | 4-minute demo video                       | produced in week 11                           |

## Team split (5 people)

Each member owns **one page file** + one chunk of `src/`. Because pages are
isolated, you can all push at the same time without stepping on each other.

| Member | Page file                            | Shared module                  |
|--------|--------------------------------------|--------------------------------|
| TM1    | `pages/1_Onboarding.py`              | `src/data/database.py` (+ schema) |
| TM2    | `pages/2_Recipes.py`, `pages/3_Pantry.py` | `src/data/api_client.py`        |
| TM3    | `pages/4_Meal_Planner.py`            | `src/components/ui.py`         |
| TM4    | `pages/5_Nutrition_Analytics.py`, `pages/6_World_Map.py` | —  |
| TM5    | `pages/7_Recommendations.py`         | `src/models/recommender.py`    |

`CONTRIBUTION_MATRIX.md`.

## Next steps (MVP → final)

The MVP scaffolded here runs end-to-end with placeholder data. Before the
final submission on **14.05.2026**, each owner should:

1. replace the demo data in their page with real DB queries (`query_df(...)`);
2. wire user actions (form submits, button clicks) to `execute(...)` calls;
3. add at least one Plotly/Streamlit chart per page where it adds value;
4. keep docstrings and inline comments up to date for Req. 6;
5. update `docs/CONTRIBUTION_MATRIX.md` at the end of each work session.

## Useful commands

```bash
# Start the app
streamlit run app.py

# Format code (optional but nice)
pip install black
black .

# Run tests (when we add them)
pip install pytest
pytest
```

## Troubleshooting

* **`ModuleNotFoundError: streamlit`** → activate your venv, re-run `pip install -r requirements.txt`.
* **`sqlite3.OperationalError: no such table`** → delete `data/cooktogether.db` and restart; `init_db()` will recreate it.
* **API errors in Recipes** → TheMealDB occasionally rate-limits. Just retry.

## License & references

For educational use in FCS/BWL FS26. Any external code, images or datasets
must be credited in `docs/REFERENCES.md` (create it when you add anything).
