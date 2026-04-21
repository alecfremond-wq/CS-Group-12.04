"""
Recommendations — the machine-learning feature.

Owner: <assign on Apr 22>
Grading coverage:
    * Req. 5 (ML — content-based recommender)
    * Req. 3 (visualisation — match score bars)

TODOs for the owner:
    - load real recipes from the DB and real history from `cooking_history`.
    - add "👍 / 👎" buttons so users can give feedback that feeds the model.
"""

import pandas as pd
import streamlit as st

from src.components.ui import page_header
from src.models.recommender import Recommender
from src.utils.session import init_session_state, require_profile


init_session_state()
require_profile()
page_header("✨ Recommendations", "Recipes picked for you by ML.")

# --- tiny in-memory demo set (owner: replace with `query_df('SELECT …')`) --
recipes = pd.DataFrame(
    [
        {"id": 1, "title": "Pasta Pesto",      "ingredients": "basil pine-nuts parmesan olive-oil garlic pasta"},
        {"id": 2, "title": "Thai Green Curry", "ingredients": "coconut-milk curry-paste chicken basil lime rice"},
        {"id": 3, "title": "Rösti",            "ingredients": "potato butter salt pepper"},
        {"id": 4, "title": "Dal Tadka",        "ingredients": "lentils onion tomato cumin turmeric garlic ginger"},
        {"id": 5, "title": "Tacos al Pastor",  "ingredients": "pork pineapple onion cilantro tortilla lime"},
        {"id": 6, "title": "Tomato Risotto",   "ingredients": "rice tomato onion parmesan olive-oil stock"},
    ]
)

history = pd.DataFrame(st.session_state["cooking_history"])
if history.empty:
    st.info(
        "You haven't logged any cooking yet — showing a neutral starter set. "
        "Cook a few recipes and rate them to unlock personalised picks."
    )

rec = Recommender(recipes)
picks = rec.recommend(history, top_n=5)

for _, row in picks.iterrows():
    with st.container(border=True):
        st.subheader(row["title"])
        if pd.notna(row.get("score")):
            st.progress(float(row["score"]), text=f"Match score: {row['score']:.2f}")
        st.caption(f"Ingredients: {row['ingredients']}")
