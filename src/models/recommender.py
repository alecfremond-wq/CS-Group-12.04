"""
Recipe recommender — ingredient-based k-Nearest Neighbours (course requirement 5).

How this actually works, in plain English:
    Every recipe is turned into a row of 0s and 1s — one column per ingredient.
    "Pasta Carbonara" gets a 1 under "pasta", "eggs", "parmesan", "guanciale", etc.,
    and a 0 for every ingredient it doesn't contain.
    This is called a binary feature vector, and it's exactly what the professor
    described: garlic {0,1}, tomatoes {0,1}, pepper {0,1}, and so on.

    When a user likes some recipes, we average those vectors to get a "taste
    profile" — a vector that has high values for ingredients that keep showing
    up in things they enjoy.

    k-NN then finds the recipes whose ingredient vectors sit closest to that
    taste profile. Those become the recommendations.

    The big advantage of ingredient-based features over nutritional ones
    is that ANY recipe with a known ingredient list can be scored — including
    recipes that come from the TheMealDB or Spoonacular APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MultiLabelBinarizer


def _clean(ingredients: list[str]) -> list[str]:
    """Lowercase and strip each ingredient name.  'Garlic Cloves' → 'garlic cloves'."""
    return [i.lower().strip() for i in ingredients if i and i.strip()]


@dataclass
class Recommender:
    """Ingredient-based k-NN recommender.

    Parameters
    ----------
    recipes :
        DataFrame built from recipes_data.RECIPES.  Must have columns
        'id', 'title', and 'ingredients' (a list of strings per row).
    """

    recipes: pd.DataFrame

    # Built automatically in __post_init__ — callers never touch these directly.
    _mlb:    MultiLabelBinarizer = field(init=False, repr=False)
    _matrix: np.ndarray          = field(init=False, repr=False)
    _model:  NearestNeighbors    = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.recipes = self.recipes.reset_index(drop=True)

        # Clean every ingredient list: lowercase + strip whitespace.
        cleaned = [_clean(lst) for lst in self.recipes["ingredients"]]

        # MultiLabelBinarizer turns lists of labels into binary rows.
        # e.g. ["pasta", "eggs"] → [0, 0, 1, 0, 1, 0, ...] (one column per unique ingredient)
        # This is the sklearn way of building the feature matrix the professor described.
        self._mlb = MultiLabelBinarizer()
        self._matrix = self._mlb.fit_transform(cleaned).astype(float)

        # NearestNeighbors with cosine similarity works well here because
        # ingredient lists vary in length — cosine ignores that and focuses
        # purely on which ingredients overlap.
        self._model = NearestNeighbors(metric="cosine", algorithm="brute")
        self._model.fit(self._matrix)

    # ── internal helpers ──────────────────────────────────────────────────────

    def _liked_ids(
        self,
        history: pd.DataFrame,
        wishlist: list[int] | None,
    ) -> set[int]:
        """Collect the local catalogue IDs of recipes the user has expressed interest in."""
        ids: set[int] = set()
        if not history.empty and "recipe_id" in history.columns:
            ids.update(history[history["rating"] >= 4]["recipe_id"].tolist())
        if wishlist:
            ids.update(wishlist)
        return ids

    def _taste_profile(
        self,
        liked_ids: set[int],
        liked_ingredients: list[list[str]] | None = None,
    ) -> np.ndarray | None:
        """Build one taste-profile vector that captures everything the user has saved.

        We combine two sources:
          • liked_ids          — recipes from our local catalogue (already in the matrix)
          • liked_ingredients  — recipes saved from external APIs, encoded on the fly

        This means saving a recipe from the search page ALSO influences the
        recommendations, even if that recipe doesn't exist in our local catalogue.
        Both sources are averaged together into a single taste-profile vector.
        """
        vectors = []

        # Source 1: local catalogue recipes — look them up in the pre-computed matrix.
        mask = self.recipes["id"].isin(liked_ids)
        if mask.any():
            vectors.append(self._matrix[mask.values])

        # Source 2: external/API recipes — encode their ingredient lists on the fly.
        # Unknown ingredients (not in our vocabulary) just become 0s, which is fine.
        if liked_ingredients:
            ext = self._encode_external(liked_ingredients)
            # Skip vectors that are entirely zero — they'd just pull the profile
            # toward the origin without contributing any useful signal.
            non_empty = ext[ext.sum(axis=1) > 0]
            if non_empty.shape[0] > 0:
                vectors.append(non_empty)

        if not vectors:
            return None

        # Stack all vectors and take the mean — the "centre of gravity" of liked recipes.
        return np.vstack(vectors).mean(axis=0)

    def _encode_external(self, ingredient_lists: list[list[str]]) -> np.ndarray:
        """Encode ingredient lists that may contain words not seen during training.

        MultiLabelBinarizer.transform() raises an error on unknown labels,
        so we filter each list down to only the ingredients the model knows about.
        Unknown ingredients just become 0s — the recipe still gets a fair score
        based on the ingredients it shares with our vocabulary.
        """
        known = set(self._mlb.classes_)
        filtered = [
            [i for i in _clean(lst) if i in known]
            for lst in ingredient_lists
        ]
        return self._mlb.transform(filtered).astype(float)

    # ── public API ────────────────────────────────────────────────────────────

    def recommend(
        self,
        history: pd.DataFrame,
        top_n: int = 5,
        wishlist: list[int] | None = None,
        liked_ingredients: list[list[str]] | None = None,
    ) -> pd.DataFrame:
        """Return the top-N local recipes most similar to the user's taste profile.

        Parameters
        ----------
        history :
            DataFrame with columns 'recipe_id' and 'rating' (1–5).
            Recipes rated ≥ 4 count as "liked" and feed the taste profile.
            (Note: there is no rating UI yet — this is wired up for Sprint 2.
            Right now history will always be empty, and that's fine.)
        top_n :
            How many recommendations to return.
        wishlist :
            List of local recipe IDs the user has saved. These are the main
            signal the model currently uses to build the taste profile.
        liked_ingredients :
            Ingredient lists from recipes saved via the search page (API results
            that don't have a local ID). The model folds these in alongside the
            wishlist so that every save — anywhere in the app — counts.
        """
        liked = self._liked_ids(history, wishlist)
        seen: set[int] = set()
        if not history.empty and "recipe_id" in history.columns:
            seen.update(history["recipe_id"].tolist())

        # Cold start: the user hasn't saved anything yet, so we have no idea
        # what they like. Return the first top_n unseen recipes as a neutral
        # starter set rather than showing an empty page.
        has_signal = bool(liked) or bool(liked_ingredients)
        profile = self._taste_profile(liked, liked_ingredients) if has_signal else None
        if profile is None:
            candidates = self.recipes[~self.recipes["id"].isin(seen)]
            return candidates.head(top_n).assign(score=np.nan).reset_index(drop=True)

        # Ask k-NN for more neighbours than we actually need, because we're about
        # to filter out recipes the user has already seen or explicitly saved —
        # and we want enough left over to fill the top_n slots.
        buffer = len(liked) + len(seen) + 5
        k = min(top_n + buffer, len(self.recipes))
        distances, indices = self._model.kneighbors(profile.reshape(1, -1), n_neighbors=k)

        # Cosine distance of 0 means perfectly identical → similarity of 1.0.
        # Cosine distance of 1 means completely opposite → similarity of 0.0.
        scores = 1.0 - distances.ravel()

        result = self.recipes.iloc[indices.ravel()].copy()
        result["score"] = scores

        # Only show recipes the user hasn't cooked or saved yet — we want
        # to surface new discoveries, not things they already know about.
        result = result[~result["id"].isin(seen)]
        result = result[~result["id"].isin(liked)]

        return result.head(top_n).reset_index(drop=True)

    def rank(
        self,
        candidate_ids: list[int],
        history: pd.DataFrame,
        wishlist: list[int] | None = None,
        liked_ingredients: list[list[str]] | None = None,
    ) -> pd.DataFrame:
        """Score and sort a specific set of local recipes by taste-profile similarity.

        Unlike recommend(), this doesn't filter out recipes the user has already
        seen or saved — it just scores and re-orders the candidates you hand it.

        The main use case is re-ranking search results: when a search query
        returns recipes that also exist in our local catalogue, we score them
        so the best matches float to the top of the results list.

        Parameters
        ----------
        candidate_ids :
            The local recipe IDs you want scored — usually a small subset
            that matched the user's search query.
        history, wishlist, liked_ingredients :
            Same as recommend() — used to build the taste profile.
        """
        liked   = self._liked_ids(history, wishlist)
        has_signal = bool(liked) or bool(liked_ingredients)
        profile = self._taste_profile(liked, liked_ingredients) if has_signal else None

        candidate_mask = self.recipes["id"].isin(candidate_ids)
        candidates = self.recipes[candidate_mask].copy()

        if profile is None or not candidate_mask.any():
            return candidates.assign(score=np.nan).reset_index(drop=True)

        indices = candidates.index.tolist()
        vectors = self._matrix[indices]

        # Compute cosine similarity between each candidate and the taste profile.
        # We add a tiny epsilon (1e-9) to the denominator to avoid dividing by zero
        # in the unlikely case that a recipe vector is all zeros.
        distances = np.array([
            1.0 - float(np.dot(profile, v) / (np.linalg.norm(profile) * np.linalg.norm(v) + 1e-9))
            for v in vectors
        ])
        candidates["score"] = 1.0 - distances
        return candidates.sort_values("score", ascending=False).reset_index(drop=True)

    def _jaccard(self, a: set[str], b: set[str]) -> float:
        """Jaccard similarity between two ingredient sets: |A ∩ B| / |A ∪ B|."""
        if not a and not b:
            return 0.0
        return len(a & b) / len(a | b)

    def score_external(
        self,
        ingredient_lists: list[list[str]],
        history: pd.DataFrame,
        wishlist: list[int] | None = None,
        liked_ingredients: list[list[str]] | None = None,
    ) -> list[float | None]:
        """Score any set of recipes by ingredient similarity to the user's taste profile.

        This is what makes ML ranking work on the search results page. We only
        need each recipe's ingredient list — no local ID, no nutrition data.
        That means TheMealDB results, Spoonacular results, or any other source
        can be scored as long as they come with ingredients.

        We use Jaccard similarity here (ingredient set overlap) instead of the
        cosine/vocabulary approach used internally. This is because external
        recipes (TheMealDB, Spoonacular) use ingredient names that often don't
        match our small local vocabulary — e.g. "Spaghetti" vs "pasta".
        Jaccard compares ingredient strings directly, so "spaghetti" in a saved
        recipe matches "spaghetti" in a new search result without needing the
        ingredient to exist in the local catalogue first.

        Parameters
        ----------
        ingredient_lists :
            One ingredient list per recipe you want scored.
        history, wishlist, liked_ingredients :
            Same as recommend() — used to build the taste profile.

        Returns
        -------
        A list of floats (0.0–1.0) in the same order as ingredient_lists.
        Returns None for every item when the user has no taste profile yet
        (i.e. they haven't saved anything), so the caller knows not to show
        misleading "match" percentages to a brand-new user.
        """
        liked      = self._liked_ids(history, wishlist)
        has_signal = bool(liked) or bool(liked_ingredients)

        if not has_signal:
            return [None] * len(ingredient_lists)

        # Build one big reference set from ALL ingredients the user has liked —
        # both from our local catalogue and from API recipes they saved.
        # Using a union means "if you saved any pasta recipe, pasta-like
        # ingredients count as a signal for future results."
        ref_set: set[str] = set()

        # Add ingredients from local catalogue recipes they saved.
        local_mask = self.recipes["id"].isin(liked)
        if local_mask.any():
            for ing_list in self.recipes[local_mask]["ingredients"]:
                ref_set.update(_clean(ing_list))

        # Add ingredients from API recipes they saved directly.
        if liked_ingredients:
            for ing_list in liked_ingredients:
                ref_set.update(_clean(ing_list))

        if not ref_set:
            return [None] * len(ingredient_lists)

        # Score each candidate recipe by how much its ingredients overlap with
        # the reference set using Jaccard similarity.
        scores = []
        for ing_list in ingredient_lists:
            candidate_set = set(_clean(ing_list))
            if not candidate_set:
                # Recipe has no parseable ingredients — can't score it.
                scores.append(None)
            else:
                scores.append(self._jaccard(ref_set, candidate_set))

        return scores
