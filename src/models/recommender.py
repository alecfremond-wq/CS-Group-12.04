"""
ML Recommender: content-based filtering using k-Nearest Neighbours.

The idea behind our approach:
  We wanted to recommend recipes based on what a user actually likes, not just
  what's popular. The simplest signal we have is the ingredient list of every
  recipe. If you love Pasta Carbonara, you probably also like other dishes
  that use eggs, parmesan, and pasta. That's the core idea.

How we turn recipes into numbers:
  A recipe can't be fed directly into a ML model, we need numbers. We convert
  each recipe into a binary vector: one column per ingredient across the whole
  catalogue. If a recipe contains that ingredient, the column is 1, otherwise 0.

      Pasta Carbonara  →  [1, 0, 0, 1, 1, 0, 1, ...]
                            ^pasta     ^eggs ^parmesan

  This is called a "bag of ingredients" and it's the binary feature
  representation described in the course slides (garlic {0,1}, etc.).

How k-NN fits in:
  Once every recipe is a vector, k-Nearest Neighbours (k-NN) can find which
  recipes are "closest" to the user's taste. We measure closeness using
  cosine similarity, which works well here because recipes differ in how many
  ingredients they have, a 3-ingredient recipe and a 20-ingredient recipe
  should still be comparable.

Building a taste profile:
  When a user saves recipes to their wishlist, we average their ingredient
  vectors into one "taste profile" vector. This vector represents the centre
  of gravity of everything they've liked so far. k-NN then finds the local
  catalogue recipes that sit closest to that centre.

Why we have TWO similarity methods:
  For local recipes (our own catalogue), we use cosine similarity through the
  k-NN model, this works because all the ingredient names are consistent.

  For external API results (TheMealDB, Spoonacular), we use Jaccard similarity
  instead. The reason: API recipes use ingredient names that often don't match
  our vocabulary ("spaghetti" vs "pasta", "aubergine" vs "eggplant"). Jaccard
  compares the actual strings directly, so it still finds overlap without needing
  the ingredient to be in our training vocabulary.

  We also use "max Jaccard" instead of "union Jaccard" — instead of merging
  all saved recipes into one big ingredient pool (which caused scores to shrink
  as the wishlist grew), we compute similarity against each saved recipe
  individually and take the highest match. This way, saving more recipes can
  only improve recommendations, never make them worse.

Dependencies:

  numpy                     — array math: stacking vectors (vstack), averaging
                              (mean), dot products and norms for cosine similarity.

  pandas                    — DataFrames for the recipe catalogue and history.

  sklearn.neighbors         — NearestNeighbors: the actual k-NN model that finds
                              the closest recipes to a taste profile vector.
                              We use metric="cosine" and algorithm="brute" because
                              our ingredient matrix is sparse and small enough that
                              brute-force search is fast and cosine distance handles
                              the varying ingredient-count problem better than
                              Euclidean distance.

  sklearn.preprocessing     — MultiLabelBinarizer: converts a list of ingredient
                              names into a binary row (one column per unique
                              ingredient across the whole catalogue).
                              e.g. ["garlic", "pasta"] → [0, 0, 1, 0, 1, ...]

Author: Ines Buzel

Sources: Claude Sonnet 4.6 (see comments below)
         Chat Gpt (explaining of kNN model and how it's working and generally how to 
         build it in vs code)

"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MultiLabelBinarizer


def _clean(ingredients: list[str]) -> list[str]:
    """Lowercase and strip whitespace so "Garlic Cloves" and "garlic cloves" are treated the same."""
    return [i.lower().strip() for i in ingredients if i and i.strip()]


# Words skipped in Jaccard similarity, grammatical stop words plus universal cooking
# words like "paste", "oil", "sauce" that appear in every cuisine and cause false matches.
_STOP_WORDS = {
    # grammatical
    "a", "an", "of", "the", "and", "or", "with", "to", "in", "for",
    # universal cooking words that don't distinguish between cuisines
    "oil", "salt", "pepper", "water", "butter", "sugar", "flour",
    "egg", "eggs", "sauce", "paste", "stock", "broth",
}


def _ingredient_words(ingredients: list[str]) -> set[str]:
    """Split ingredient strings into word sets for Jaccard comparison, skipping stop words.
    e.g. "green curry paste" → {"green", "curry"} (paste is a stop word).
    """
    words: set[str] = set()
    for ing in _clean(ingredients):
        for word in ing.split():
            if len(word) > 2 and word not in _STOP_WORDS:
                words.add(word)
    return words


@dataclass
class Recommender:
    """Content-based recipe recommender built on top of scikit-learn's k-NN.

    We chose content-based filtering (ingredients) over collaborative
    filtering (what other users liked) because we only have one user per
    app instance. There's no community of users to learn from, so we rely
    purely on the ingredients of recipes the current user has saved.

    Usage:
        rec = Recommender(recipes_df)          # build the model
        recs = rec.recommend(history, top_n=5, wishlist=[1, 3, 7])
    """

    recipes: pd.DataFrame  # must have columns: id, title, ingredients (list of str)

    # These three are built in __post_init__ and used internally.
    _mlb:    MultiLabelBinarizer = field(init=False, repr=False)
    _matrix: np.ndarray          = field(init=False, repr=False)
    _model:  NearestNeighbors    = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Build the ingredient matrix and fit the k-NN model.

        This runs automatically when you create a Recommender instance.
        It converts every recipe's ingredient list into a binary row
        (one column per unique ingredient across the whole catalogue),
        then fits the k-NN model on that matrix.
        """
        self.recipes = self.recipes.reset_index(drop=True)
        cleaned = [_clean(lst) for lst in self.recipes["ingredients"]]

        # \ Begin code generated with Claude Sonnet 4.6
        # fit_transform learns all unique ingredients as the vocabulary and encodes every recipe.
        self._mlb    = MultiLabelBinarizer()
        self._matrix = self._mlb.fit_transform(cleaned).astype(float)

        # cosine similarity handles recipes with different numbers of ingredients fairly.
        # algorithm="brute" is fine because our catalogue is small (~40 recipes).
        self._model = NearestNeighbors(metric="cosine", algorithm="brute")
        self._model.fit(self._matrix)
        # \ End code generated with Claude Sonnet 4.6

    # ── private helpers ───────────────────────────────────────────────────────────

    def _liked_ids(self, history: pd.DataFrame, wishlist: list[int] | None) -> set[int]:
        """Return IDs of all recipes the user liked: wishlist saves + ratings ≥ 4."""
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
        """Build the user's taste profile as a single averaged ingredient vector.

        We average the binary vectors of all liked recipes into one vector.
        Think of it as finding the "centre of gravity" in ingredient space 
        a point that represents the mix of ingredients the user tends to enjoy.

        We have two sources of liked recipes:
          1. Local catalogue recipes (already in our matrix, fast to look up)
          2. External API recipes (TheMealDB/Spoonacular) saved from the search
             page — these we encode on the fly using only ingredients our model
             already knows about.

        Returns None if there's nothing to build the profile from.
        """
        vectors = []

        # Source 1: local catalogue just index into the pre-built matrix.
        mask = self.recipes["id"].isin(liked_ids)
        if mask.any():
            vectors.append(self._matrix[mask.values])

        # Source 2: API recipes re-encode using only known ingredients (unknowns → 0).
        if liked_ingredients:
            ext = self._encode_external(liked_ingredients)
            non_empty = ext[ext.sum(axis=1) > 0]
            if non_empty.shape[0] > 0:
                vectors.append(non_empty)

        if not vectors:
            return None

        # \ Begin code generated with Claude Sonnet 4.6
        # np.vstack stacks all the row vectors into one matrix,
        # then .mean(axis=0) averages column by column to get one profile vector.
        return np.vstack(vectors).mean(axis=0)
        # \ End code generated with Claude Sonnet 4.6

    def _encode_external(self, ingredient_lists: list[list[str]]) -> np.ndarray:
        """Encode API recipe ingredients using only the vocabulary we already trained on.
        Unknown ingredients are filtered out first, otherwise sklearn would throw an error.
        """
        # \ Begin code generated with Claude Sonnet 4.6
        known    = set(self._mlb.classes_)
        filtered = [
            [i for i in _clean(lst) if i in known]
            for lst in ingredient_lists
        ]
        return self._mlb.transform(filtered).astype(float)
        # \ End code generated with Claude Sonnet 4.6

    # ── public API ────────────────────────────────────────────────────────────────

    def recommend(
        self,
        history: pd.DataFrame,
        top_n: int = 5,
        wishlist: list[int] | None = None,
        liked_ingredients: list[list[str]] | None = None,
    ) -> pd.DataFrame:
        """Find the top-N recipes from our local catalogue that best match the user's taste.

        Steps:
          1. Build a taste profile by averaging the ingredient vectors of all
             liked recipes (wishlist + highly-rated history).
          2. Ask k-NN for the nearest neighbours to that profile.
          3. Filter out anything the user has already seen or saved
             (we want to surface new discoveries, not repeat the obvious).
          4. Return the top_n results with a match score (0–1).

        Cold start: if the user hasn't saved anything yet, we just return
        the first top_n recipes from the catalogue. Not personalised, but
        at least the page isn't empty.
        """
        liked = self._liked_ids(history, wishlist)
        seen: set[int] = set()
        if not history.empty and "recipe_id" in history.columns:
            seen.update(history["recipe_id"].tolist())

        has_signal = bool(liked) or bool(liked_ingredients)
        profile    = self._taste_profile(liked, liked_ingredients) if has_signal else None

        if profile is None:
            candidates = self.recipes[~self.recipes["id"].isin(seen)]
            return candidates.head(top_n).assign(score=np.nan).reset_index(drop=True)

        # We ask for more neighbours than we need because we'll filter some out.
        # Without the buffer we might end up with fewer than top_n results.
        buffer = len(liked) + len(seen) + 5
        k      = min(top_n + buffer, len(self.recipes))

        # \ Begin code generated with Claude Sonnet 4.6
        distances, indices = self._model.kneighbors(profile.reshape(1, -1), n_neighbors=k)

        # k-NN returns cosine *distance* (0 = identical, 1 = opposite).
        # We flip it to similarity (1 = identical, 0 = opposite) for display.
        scores = 1.0 - distances.ravel()
        result = self.recipes.iloc[indices.ravel()].copy()
        result["score"] = scores
        # \ End code generated with Claude Sonnet 4.6

        result = result[~result["id"].isin(seen)]   # don't repeat history
        result = result[~result["id"].isin(liked)]  # don't repeat wishlist

        return result.head(top_n).reset_index(drop=True)

    def rank(
        self,
        candidate_ids: list[int],
        history: pd.DataFrame,
        wishlist: list[int] | None = None,
        liked_ingredients: list[list[str]] | None = None,
    ) -> pd.DataFrame:
        """Re-rank a specific subset of recipes by taste similarity (not the full catalogue).
        Uses manual cosine similarity instead of k-NN since we're scoring a fixed list.
        """
        liked      = self._liked_ids(history, wishlist)
        has_signal = bool(liked) or bool(liked_ingredients)
        profile    = self._taste_profile(liked, liked_ingredients) if has_signal else None

        candidate_mask = self.recipes["id"].isin(candidate_ids)
        candidates     = self.recipes[candidate_mask].copy()

        if profile is None or not candidate_mask.any():
            return candidates.assign(score=np.nan).reset_index(drop=True)

        vectors = self._matrix[candidates.index.tolist()]

        # \ Begin code generated with Claude Sonnet 4.6
        # Cosine similarity = dot product / (magnitude A × magnitude B).
        # The tiny epsilon (1e-9) stops a division-by-zero if a recipe vector
        # happens to be all zeros (e.g. no known ingredients).
        distances = np.array([
            1.0 - float(
                np.dot(profile, v)
                / (np.linalg.norm(profile) * np.linalg.norm(v) + 1e-9)
            )
            for v in vectors
        ])
        candidates["score"] = 1.0 - distances
        # \ End code generated with Claude Sonnet 4.6

        return candidates.sort_values("score", ascending=False).reset_index(drop=True)

    def _jaccard(self, a: set[str], b: set[str]) -> float:
        """Jaccard similarity: how much do two ingredient sets overlap?

        Formula: |A ∩ B| / |A ∪ B|
        → 1.0 means the two sets are identical
        → 0.0 means they share nothing at all

        We use this (instead of cosine) when scoring API results, because
        the ingredient names from TheMealDB and Spoonacular often don't
        match the vocabulary we trained on. Jaccard works on raw strings,
        so "garlic cloves" still matches "garlic cloves" across any source.
        """
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
        """Score API recipes against the user's taste using max-Jaccard similarity.

        Returns None per item if the user has no profile yet (no "0% match" for new users).
        max-Jaccard: compare each candidate against every liked recipe individually and
        take the highest, so saving more recipes can only raise scores, never lower them.
        """
        liked      = self._liked_ids(history, wishlist)
        has_signal = bool(liked) or bool(liked_ingredients)

        if not has_signal:
            return [None] * len(ingredient_lists)

        # One set per liked recipe, we deliberately keep them separate
        # so the max-Jaccard can compare each candidate against each liked recipe.
        liked_sets: list[set[str]] = []

        local_mask = self.recipes["id"].isin(liked)
        if local_mask.any():
            for ing_list in self.recipes[local_mask]["ingredients"]:
                s = _ingredient_words(ing_list)
                if s:
                    liked_sets.append(s)

        if liked_ingredients:
            for ing_list in liked_ingredients:
                s = _ingredient_words(ing_list)
                if s:
                    liked_sets.append(s)

        if not liked_sets:
            return [None] * len(ingredient_lists)

        scores = []
        for ing_list in ingredient_lists:
            # Use word-level sets so "green curry paste" overlaps with
            # "massaman curry paste" via the shared word "curry".
            candidate_set = _ingredient_words(ing_list)
            if not candidate_set:
                scores.append(None)
            else:
                # \ Begin code generated with Claude Sonnet 4.6
                # Best match across all liked recipes (max-Jaccard).
                # max(...) with a generator expression: computes Jaccard against
                # every liked recipe and keeps only the highest score.
                scores.append(max(self._jaccard(ls, candidate_set) for ls in liked_sets))
                # \ End code generated with Claude Sonnet 4.6

        return scores
