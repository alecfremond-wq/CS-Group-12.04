# ============================================================================
#  user_repo.py  —  read / write user profiles in the SQLite database
# ----------------------------------------------------------------------------
#  Each student (or demo user) has their own row in the `users` table.
#  Every function that touches a specific profile takes an explicit `user_id`
#  so that pantry / meal-plan data (which already carry user_id FKs) stays
#  properly scoped per person.
# ============================================================================
#  AI-ASSISTED AUTHORSHIP: scaffold drafted with Anthropic Claude (05/2026),
#  reviewed by Group 12.04. See README.md.
# ============================================================================

from __future__ import annotations

import hashlib
from typing import Optional

from src.data.database import execute, query_df


_PROFILE_KEYS = ("name", "diet", "allergies", "budget_weekly", "skill_level")


def _hash(password: str) -> str:
    # sha256 turns the password into a fixed-length string — we never store the real password
    return hashlib.sha256(password.encode()).hexdigest()


def create_account(profile: dict, username: str, password: str) -> int:
    """Create a new user with login credentials. Returns the new user_id.
    Raises ValueError if the username is already taken.
    """
    username = username.strip().lower()

    taken = query_df("SELECT id FROM users WHERE username = ?", (username,))
    if not taken.empty:
        raise ValueError("This username is already taken.")

    allergies = profile.get("allergies", [])
    allergies_str = ",".join(allergies) if isinstance(allergies, list) else str(allergies or "")

    execute(
        "INSERT INTO users (name, username, password_hash, diet, allergies, skill_level) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            profile.get("name", ""),
            username,
            _hash(password),
            profile.get("diet", "omnivore"),
            allergies_str,
            profile.get("skill_level", "beginner"),
        ),
    )
    df = query_df("SELECT id FROM users WHERE username = ?", (username,))
    return int(df.iloc[0]["id"])


def check_login(username: str, password: str) -> Optional[int]:
    """Return user_id if username + password match, otherwise None."""
    df = query_df(
        "SELECT id FROM users WHERE username = ? AND password_hash = ?",
        (username.strip().lower(), _hash(password)),
    )
    return int(df.iloc[0]["id"]) if not df.empty else None


def save_profile(profile: dict, user_id: Optional[int] = None) -> int:
    """Persist a user profile and return its database id.

    - If `user_id` is given → UPDATE that row in place (keeps FK stable).
    - If `user_id` is None  → INSERT a new row and return the new id.

    `profile["allergies"]` may be a list or a comma-separated string; we
    always store it as a comma-separated string to match the schema.
    """
    allergies = profile.get("allergies", [])
    if isinstance(allergies, list):
        allergies_str = ",".join(allergies)
    else:
        allergies_str = str(allergies or "")

    values = (
        profile.get("name", ""),
        profile.get("diet", "omnivore"),
        allergies_str,
        profile.get("skill_level", "beginner"),
    )

    if user_id is not None:
        execute(
            "UPDATE users "
            "SET name=?, diet=?, allergies=?, skill_level=? "
            "WHERE id=?",
            values + (user_id,),
        )
        return user_id

    execute(
        "INSERT INTO users (name, diet, allergies, skill_level) "
        "VALUES (?, ?, ?, ?)",
        values,
    )
    df = query_df("SELECT id FROM users ORDER BY id DESC LIMIT 1")
    return int(df.iloc[0]["id"])


def load_profile(user_id: int) -> Optional[dict]:
    """Return the profile for `user_id` as a dict, or None if not found.

    The dict shape matches st.session_state["user_profile"] exactly.
    """
    df = query_df("SELECT * FROM users WHERE id = ?", (user_id,))
    if df.empty:
        return None

    row = df.iloc[0]
    raw_allergies = row["allergies"] or ""
    allergies = [a.strip() for a in raw_allergies.split(",") if a.strip()]

    return {
        "name": row["name"] or "",
        "diet": row["diet"] or "omnivore",
        "allergies": allergies,
        "skill_level": row["skill_level"] or "beginner",
    }


def load_all_profiles() -> list[dict]:
    """Return a list of {id, name} dicts for every row in the users table.

    Used by the Onboarding page to render the profile-selection screen.
    Returns an empty list if no profiles have been created yet.
    """
    df = query_df("SELECT id, name FROM users ORDER BY id ASC")
    if df.empty:
        return []
    return df.to_dict("records")


def delete_profile(user_id: int) -> None:
    """Delete the users row for `user_id`.

    The ON DELETE CASCADE on pantry and meal_plan tables means those rows
    are cleaned up automatically by SQLite.
    """
    execute("DELETE FROM users WHERE id = ?", (user_id,))
