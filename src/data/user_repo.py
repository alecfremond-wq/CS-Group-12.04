# ============================================================================
#  user_repo.py  —  read / write the user profile in the SQLite database
# ----------------------------------------------------------------------------
#  MULTI-USER FIX: previously every function always read/wrote the FIRST row
#  of the users table, meaning every browser session shared the same profile.
#  Now every function uses a user_id so each user owns their own row.
# ============================================================================
#  AI-ASSISTED AUTHORSHIP: scaffold drafted with Anthropic Claude (05/2026),
#  reviewed by Group 12.04. See README.md.
# ============================================================================

from __future__ import annotations

from typing import Optional

from src.data.database import execute, query_df


_PROFILE_KEYS = ("name", "diet", "allergies", "budget_weekly", "skill_level")


def _allergies_to_str(allergies) -> str:
    """Convert allergies list → comma-separated string for the DB."""
    if isinstance(allergies, list):
        return ",".join(allergies)
    return str(allergies or "")


def _row_to_profile(row) -> dict:
    """Convert a DB row (pandas Series) → profile dict for session_state."""
    raw_allergies = row["allergies"] or ""
    allergies = [a.strip() for a in raw_allergies.split(",") if a.strip()]
    return {
        "id": int(row["id"]),
        "name": row["name"] or "",
        "diet": row["diet"] or "Omnivore",
        "allergies": allergies,
        "budget_weekly": float(row["budget_weekly"] or 0),
        "skill_level": row["skill_level"] or "beginner",
    }


def save_profile(profile: dict) -> int:
    """Persist the user profile to the `users` table.

    - If `profile` contains an `id` key, UPDATE that specific row.
    - Otherwise INSERT a new row.

    Returns the user_id (int) so the caller can store it in session_state.
    """
    allergies_str = _allergies_to_str(profile.get("allergies", []))

    values = (
        profile.get("name", ""),
        profile.get("diet", "Omnivore"),
        allergies_str,
        float(profile.get("budget_weekly", 0) or 0),
        profile.get("skill_level", "beginner"),
    )

    user_id = profile.get("id")

    if user_id:
        execute(
            "UPDATE users "
            "SET name = ?, diet = ?, allergies = ?, "
            "    budget_weekly = ?, skill_level = ? "
            "WHERE id = ?",
            values + (int(user_id),),
        )
        return int(user_id)
    else:
        execute(
            "INSERT INTO users (name, diet, allergies, budget_weekly, skill_level) "
            "VALUES (?, ?, ?, ?, ?)",
            values,
        )
        new_row = query_df(
            "SELECT id FROM users WHERE name = ? ORDER BY id DESC LIMIT 1",
            (profile.get("name", ""),),
        )
        return int(new_row.iloc[0]["id"]) if not new_row.empty else 1


def load_profile(user_id: int) -> Optional[dict]:
    """Return the profile for a specific user_id, or None if not found."""
    df = query_df("SELECT * FROM users WHERE id = ? LIMIT 1", (user_id,))
    if df.empty:
        return None
    return _row_to_profile(df.iloc[0])


def load_all_profiles() -> list[dict]:
    """Return all saved profiles ordered by name — used by the login screen."""
    df = query_df("SELECT * FROM users ORDER BY name ASC")
    if df.empty:
        return []
    return [_row_to_profile(row) for _, row in df.iterrows()]


def delete_profile(user_id: int) -> None:
    """Remove only the row belonging to the given user_id."""
    execute("DELETE FROM users WHERE id = ?", (user_id,))
