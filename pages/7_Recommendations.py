"""
Recommendations — the machine-learning feature.
Owner: <assign on Apr 22>
Grading coverage:
    * Req. 5 (ML — content-based recommender)
    * Req. 3 (visualisation — match score bars)
"""
import pandas as pd
import streamlit as st

from src.components.ui import page_header
from src.models.recommender import Recommender
from src.utils.session import init_session_state, require_profile

# Try to load real recipes from the DB; fall back to demo set if the helper
# isn't wired up yet or the table is empty.
try:
    from src.data.database import query_df  # type: ignore
except Exception:
    query_df = None  # type: ignore


init_session_state()
require_profile()

page_header("✨ Recommendations", "Recipes picked for you by ML.")


# ---------------------------------------------------------------------------
# TODO #1 (resolved): load real recipes from the DB.
# Falls back to the small demo set so the page still works pre-DB-sync.
# ---------------------------------------------------------------------------
def load_recipes() -> pd.DataFrame:
    if query_df is not None:
        try:
            df = query_df("SELECT id, title, ingredients FROM recipes")
            if df is not None and len(df) > 0:
                # Recommender expects ingredients as a single space-separated
                # string. The DB might store them comma-separated, so normalise.
                df = df.copy()
                df["ingredients"] = df["ingredients"].astype(str).apply(
                    lambda s: " ".join(
                        part.strip().replace(" ", "-")
                        for part in s.replace(",", " ").split()
                    )
                )
                return df
        except Exception:
            pass

    # demo fallback (the original starter set)
    return pd.DataFrame(
        [
            {"id": 1, "title": "Pasta Pesto",      "ingredients": "basil pine-nuts parmesan olive-oil garlic pasta"},
            {"id": 2, "title": "Thai Green Curry", "ingredients": "coconut-milk curry-paste chicken basil lime rice"},
            {"id": 3, "title": "Rösti",            "ingredients": "potato butter salt pepper"},
            {"id": 4, "title": "Dal Tadka",        "ingredients": "lentils onion tomato cumin turmeric garlic ginger"},
            {"id": 5, "title": "Tacos al Pastor",  "ingredients": "pork pineapple onion cilantro tortilla lime"},
            {"id": 6, "title": "Tomato Risotto",   "ingredients": "rice tomato onion parmesan olive-oil stock"},
        ]
    )


recipes = load_recipes()


# ---------------------------------------------------------------------------
# Cooking history — try the DB (cooking_history table) first, then fall back
# to whatever's been stashed in session_state by other pages or by the
# feedback buttons below.
# ---------------------------------------------------------------------------
def load_history() -> pd.DataFrame:
    if query_df is not None:
        try:
            user_id = st.session_state.get("user_id") \
                or st.session_state.get("profile", {}).get("id")
            if user_id is not None:
                df = query_df(
                    "SELECT recipe_id AS id, rating FROM cooking_history WHERE user_id = ?",
                    (user_id,),
                )
                if df is not None and len(df) > 0:
                    # join with recipes so the recommender sees ingredients text
                    return df.merge(recipes, on="id", how="left")
        except Exception:
            pass
    return pd.DataFrame(st.session_state["cooking_history"])


history = load_history()

if history.empty:
    st.info(
        "You haven't logged any cooking yet — showing a neutral starter set. "
        "Cook a few recipes and rate them to unlock personalised picks."
    )


# ---------------------------------------------------------------------------
# Run the recommender
# ---------------------------------------------------------------------------
rec = Recommender(recipes)
picks = rec.recommend(history, top_n=5)


# ---------------------------------------------------------------------------
# TODO #2 (resolved): 👍 / 👎 feedback buttons that feed back into history.
# Each click appends to st.session_state["cooking_history"] so the next
# rerun the Recommender treats it as a signal. When the DB is wired up,
# the same write is mirrored into the cooking_history table.
# ---------------------------------------------------------------------------
def record_feedback(recipe_row: pd.Series, rating: int) -> None:
    """rating: +1 for 👍, -1 for 👎."""
    st.session_state["cooking_history"].append(
        {
            "id": int(recipe_row["id"]),
            "title": recipe_row["title"],
            "ingredients": recipe_row["ingredients"],
            "rating": rating,
        }
    )
    # best-effort persistence
    try:
        from src.data.database import execute  # type: ignore
        user_id = st.session_state.get("user_id") \
            or st.session_state.get("profile", {}).get("id")
        if user_id is not None:
            execute(
                "INSERT INTO cooking_history (user_id, recipe_id, rating) VALUES (?, ?, ?)",
                (user_id, int(recipe_row["id"]), rating),
            )
    except Exception:
        # session_state is the source of truth for the demo
        pass


for _, row in picks.iterrows():
    with st.container(border=True):
        st.subheader(row["title"])

        if pd.notna(row.get("score")):
            # Req. 3 — visualisation: match-score progress bar.
            # Clamp to [0, 1] so st.progress never errors on edge cases.
            score_val = float(row["score"])
            score_val = max(0.0, min(1.0, score_val))
            st.progress(score_val, text=f"Match score: {row['score']:.2f}")

        st.caption(f"Ingredients: {row['ingredients']}")

        c1, c2, _ = st.columns([1, 1, 6])
        with c1:
            if st.button("👍", key=f"like_{row['id']}"):
                record_feedback(row, +1)
                st.toast(f"Saved 👍 for {row['title']}")
                st.rerun()
        with c2:
            if st.button("👎", key=f"dislike_{row['id']}"):
                record_feedback(row, -1)
                st.toast(f"Saved 👎 for {row['title']}")
                st.rerun()
