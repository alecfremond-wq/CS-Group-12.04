"""
Recipe recommender — machine-learning module (course requirement 5).

This is deliberately small so it can be iterated on without touching the
rest of the app. The default implementation uses a content-based approach:

1. Represent each recipe by its ingredient list (bag-of-words).
2. Compute cosine similarity between recipes and the user's 'taste profile',
   which is the mean vector of the recipes they rated >= 4 stars.
3. Return the top-N recipes the user hasn't cooked yet.

Why this model?
* It works from day one — no training data required besides what the user
  generates themselves.
* It degrades gracefully: if the user has cooked nothing, we fall back to
  recommending the most popular recipes.

Later, the team can replace ``Recommender`` with a collaborative-filtering
or neural approach without changing the Streamlit page at all.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class Recommender:
    """Content-based recipe recommender.

    Parameters
    ----------
    recipes:
        DataFrame with at least columns ``id``, ``title`` and ``ingredients``
        (a single string, space- or comma-separated).
    """

    recipes: pd.DataFrame

    def __post_init__(self) -> None:
        # Tokens are whole words, possibly hyphenated (e.g. "olive-oil", "pine-nuts").
        self._vectorizer = CountVectorizer(token_pattern=r"[A-Za-z][A-Za-z\-]+")
        self._matrix = self._vectorizer.fit_transform(
            self.recipes["ingredients"].fillna("")
        )

    # ---- public API ------------------------------------------------------
    def recommend(
        self,
        history: pd.DataFrame,
        top_n: int = 5,
    ) -> pd.DataFrame:
        """Return the top-N recipe recommendations for a user.

        Parameters
        ----------
        history:
            DataFrame with columns ``recipe_id`` and ``rating`` (1-5).
        top_n:
            How many recommendations to return.
        """
        if history.empty:
            # Cold start: recommend anything — here we just take the first N.
            return self.recipes.head(top_n).assign(score=np.nan)

        liked = history[history["rating"] >= 4]["recipe_id"].tolist()
        if not liked:
            return self.recipes.head(top_n).assign(score=np.nan)

        liked_idx = self.recipes.index[self.recipes["id"].isin(liked)]
        taste_profile = np.asarray(self._matrix[liked_idx].mean(axis=0))
        scores = cosine_similarity(taste_profile, self._matrix).ravel()

        already_cooked = set(history["recipe_id"])
        ranked = (
            self.recipes.assign(score=scores)
            .query("id not in @already_cooked")
            .sort_values("score", ascending=False)
            .head(top_n)
        )
        return ranked
