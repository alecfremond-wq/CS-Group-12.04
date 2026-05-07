"""
Recipes — search and browse recipes (API + DB).
Owner: <assign on Apr 22>
Grading coverage:
    * Req. 2 (API — TheMealDB + Spoonacular)
    * Req. 4 (user interaction — search, filter, add-to-wishlist)
    * Req. 5 (ML — search results ranked by taste profile when available)
TODOs for the owner:
    - when a user clicks "Save recipe", persist to the `recipes` table
      so the Recommender has data to learn from.
"""

import pandas as pd
import streamlit as st

from recipes_data import RECIPES as LOCAL_RECIPES
from src.components.ui import empty_state, page_header
from src.data.api_client import (
    list_cuisines,
    search_recipes_by_name,
    search_spoonacular,
)
from src.data.database import query_df, execute
from src.models.recommender import Recommender
from src.utils.session import init_session_state, require_profile

init_session_state()

# require_profile() stops the page if the user hasn't done onboarding yet,
# so by the time we reach the next line we're guaranteed to have a profile.
profile = require_profile()

page_header("🍲 Recipes", "Search recipes or browse by cuisine.")

# Build a lookup table: lowercase recipe name → local ID.
local_title_to_id = {r["name"].lower(): r["id"] for r in LOCAL_RECIPES}


def extract_ingredients(meal: dict) -> list[str]:
    """Pull the ingredient list out of a TheMealDB or Spoonacular result."""
    if meal.get("_ingredients"):
        return [i.strip() for i in meal["_ingredients"] if i.strip()]

    return [
        meal[f"strIngredient{i}"].strip()
        for i in range(1, 21)
        if (meal.get(f"strIngredient{i}") or "").strip()
    ]


# ── Pantry helper ─────────────────────────────────────────────────────────────

def get_pantry() -> set[str]:
    """Load the user's pantry from the database."""
    user_id = st.session_state.get("user_id")
    if not user_id:
        return set()

    try:
        df = query_df(
            """
            SELECT i.name
            FROM pantry p
            JOIN ingredients i ON p.ingredient_id = i.id
            WHERE p.user_id = ? AND p.quantity > 0
            """,
            (user_id,),
        )
        if df.empty:
            return set()

        return set(df["name"].str.lower())
    except Exception:
        return set()


def pantry_pct(meal: dict, pantry: set[str]) -> float | None:
    """Return fraction of ingredients already in pantry."""
    if not pantry:
        return None

    ingredients = extract_ingredients(meal)
    if not ingredients:
        return None

    names = [i.lower() for i in ingredients]
    return sum(1 for n in names if n in pantry) / len(names)


# ── Wishlist / taste-profile setup ────────────────────────────────────────────

wishlist = st.session_state.get("wishlist", [])

wishlist_ids = [
    w["local_id"]
    for w in wishlist
    if isinstance(w, dict) and w.get("local_id") is not None
]

liked_ingredients = [
    w["ingredients"]
    for w in wishlist
    if isinstance(w, dict) and w.get("ingredients")
]

history_df = pd.DataFrame(st.session_state.get("cooking_history", []))

has_taste_profile = (
    bool(wishlist_ids)
    or bool(liked_ingredients)
    or (
        not history_df.empty
        and "rating" in history_df.columns
        and (history_df["rating"] >= 4).any()
    )
)

tab_search, tab_cuisine = st.tabs(["🔎 Search", "🌍 Browse by cuisine"])


# ── Helper: render one recipe card ────────────────────────────────────────────

def render_meal_card(
    meal: dict,
    ml_score: float | None = None,
    pantry: float | None = None,
) -> None:
    """Draw a single recipe card."""
    meal_title = meal["strMeal"]

    with st.container(border=True):
        col_img, col_meta = st.columns([1, 3])

        with col_img:
            st.image(meal.get("strMealThumb"), use_container_width=True)

        with col_meta:
            st.subheader(meal_title)
            st.caption(
                f"{meal.get('strArea', '—')} · {meal.get('strCategory', '—')}"
            )

            if ml_score is not None and not pd.isna(ml_score):
                st.progress(float(ml_score), text=f"Match score: {ml_score:.0%}")

            if pantry is not None:
                if pantry > 0.6:
                    st.success("🟢 Pantry-friendly")
                elif pantry > 0.3:
                    st.warning("🟡 Partially available")

            with st.expander("Instructions"):
                st.write(meal.get("strInstructions", ""))

            # ── Save to wishlist ──────────────────────────────────────────────

            already_saved = any(
                isinstance(w, dict) and w.get("title") == meal_title
                for w in st.session_state.get("wishlist", [])
            )

            if already_saved:
                st.caption("❤️ Saved to wishlist")
            else:
                if st.button("❤️ Save to wishlist", key=f"wish_{meal_title}"):
                    local_id = local_title_to_id.get(meal_title.lower())

                    st.session_state["wishlist"].append(
                        {
                            "title": meal_title,
                            "image": meal.get("strMealThumb"),
                            "area": meal.get("strArea", ""),
                            "local_id": local_id,
                            "ingredients": extract_ingredients(meal),
                        }
                    )
                    st.rerun()
      # ── Add / Remove from meal planner pool ─────────────────────────────

            user_id = st.session_state.get("user_id")
            local_id = local_title_to_id.get(meal_title.lower())
            if local_id is None:
                existing_recipe = query_df(
                    """
                    SELECT id
                    FROM recipes
                    WHERE LOWER(title) = LOWER(?)
                    LIMIT 1
                    """,
                    (meal_title,),
                )

                if not existing_recipe.empty:
                    local_id = int(existing_recipe.iloc[0]["id"])

            already_in_planner = False

            if user_id and local_id:
                planner_check = query_df(
                    """
                    SELECT 1
                    FROM planner_pool
                    WHERE user_id = ? AND recipe_id = ?
                    LIMIT 1
                    """,
                    (user_id, local_id),
                )

                already_in_planner = not planner_check.empty


            if already_in_planner:
                st.caption("🍽️ Added to Meal Planner")

                if st.button(
                    "❌ Remove from Meal Planner",
                    key=f"remove_planner_{meal_title}",
                ):
                    execute(
                        """
                        DELETE FROM planner_pool
                        WHERE user_id = ? AND recipe_id = ?
                        """,
                        (user_id, local_id),
                    )

                    st.rerun()

            else:
                if st.button(
                    "➕ Add to Meal Planner",
                    key=f"planner_{meal_title}",
                ):

                    if local_id is None:
                        execute(
                            """
                            INSERT INTO recipes (title)
                            VALUES (?)
                            """,
                            (meal_title,),
                        )

                        new_row = query_df(
                            """
                            SELECT id FROM recipes
                            WHERE title = ?
                            ORDER BY id DESC LIMIT 1
                            """,
                            (meal_title,),
                        )

                        if not new_row.empty:
                            local_id = int(new_row.iloc[0]["id"])

                    if local_id:
                        execute(
                            """
                            INSERT OR IGNORE INTO planner_pool (user_id, recipe_id)
                            VALUES (?, ?)
                            """,
                            (user_id, local_id),
                        )

                    st.success("Added to Meal Planner 🍽️")
                    st.rerun()


# ── Search tab ────────────────────────────────────────────────────────────────

with tab_search:
    query = st.text_input(
        "What would you like to cook?",
        placeholder="e.g. pasta, curry…",
    )

    if query:
        diet = profile.get("diet", "omnivore")
        allergies = profile.get("allergies", [])

        veg = diet in ("vegetarian", "vegan")
        vgn = diet == "vegan"
        gf = "gluten" in allergies
        df = "lactose" in allergies

        results = search_recipes_by_name(query) + search_spoonacular(
            query=query,
            vegetarian=veg,
            vegan=vgn,
            gluten_free=gf,
            dairy_free=df,
        )

        if not results:
            empty_state("No recipes found — try another word.")
        else:
            recipes_df = pd.DataFrame(LOCAL_RECIPES).rename(
                columns={"name": "title"}
            )

            rec = Recommender(recipes_df)
            top_results = results[:10]

            ingredient_lists = [
                extract_ingredients(m) for m in top_results
            ]

            raw_scores = (
                rec.score_external(
                    ingredient_lists,
                    history_df,
                    wishlist_ids,
                    liked_ingredients,
                )
                if has_taste_profile
                else [None] * len(top_results)
            )

            scored_results = sorted(
                zip(top_results, raw_scores),
                key=lambda pair: (
                    (0, -(pair[1] or 0))
                    if pair[1] is not None
                    else (1, 0)
                ),
            )

            any_scored = any(s is not None for _, s in scored_results)

            if any_scored:
                st.caption(
                    "🎯 Results ranked by ingredient similarity to your taste profile. "
                    "Save more recipes to improve the ranking."
                )
            elif has_taste_profile:
                st.caption(
                    "ℹ️ These results don't have ingredient data, "
                    "so ML ranking isn't available here."
                )

            user_pantry = get_pantry()

            for meal, score in scored_results:
                render_meal_card(
                    meal,
                    ml_score=score,
                    pantry=pantry_pct(meal, user_pantry),
                )


# ── Cuisine tab ───────────────────────────────────────────────────────────────

with tab_cuisine:
    cuisines = list_cuisines()

    if not cuisines:
        empty_state("Cuisine list couldn't be loaded — check your internet.")
    else:
        choice = st.selectbox("Cuisine", cuisines)
        st.caption(f"(Owner: render recipes for cuisine = **{choice}**)")


