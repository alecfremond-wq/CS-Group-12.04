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
    # sha256 converts the password into a fixed-length string of characters
    # We store this hash instead of the real password — so even if the database
    # is exposed, nobody can recover the original passwords
    return hashlib.sha256(password.encode()).hexdigest()


def create_account(profile: dict, username: str, password: str) -> int:
    # Create a new user row in the database and return the new user_id
    # Raises ValueError if the username is already taken (enforced by UNIQUE index)
    username = username.strip().lower()

    # Check if the username already exists before trying to insert
    taken = query_df("SELECT id FROM users WHERE username = ?", (username,))
    if not taken.empty:
        raise ValueError("This username is already taken.")

    # Convert the allergies list to a comma-separated string for storage
    # e.g. ["Gluten", "Nuts"] → "gluten,nuts"
    allergies = profile.get("allergies", [])
    allergies_str = ",".join(allergies) if isinstance(allergies, list) else str(allergies or "")

    execute(
        "INSERT INTO users (name, username, password_hash, diet, allergies, skill_level) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            profile.get("name", ""),
            username,
            _hash(password),        # store the hash, never the plain password
            profile.get("diet", "omnivore"),
            allergies_str,
            profile.get("skill_level", "beginner"),
        ),
    )
    # Retrieve the id of the row we just inserted
    df = query_df("SELECT id FROM users WHERE username = ?", (username,))
    return int(df.iloc[0]["id"])


def check_login(username: str, password: str) -> Optional[int]:
    # Verify login credentials — hash the given password and compare to the stored hash
    # Returns the user_id if they match, or None if they don't (wrong username or password)
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
    # Normalise allergies to a comma-separated string regardless of input format
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
        # Update the existing row — keeps the same id so all foreign keys stay valid
        execute(
            "UPDATE users "
            "SET name=?, diet=?, allergies=?, skill_level=? "
            "WHERE id=?",
            values + (user_id,),
        )
        return user_id

    # No user_id provided — insert a new row
    execute(
        "INSERT INTO users (name, diet, allergies, skill_level) "
        "VALUES (?, ?, ?, ?)",
        values,
    )
    # Retrieve the id of the row we just inserted (last inserted row has the highest id)
    df = query_df("SELECT id FROM users ORDER BY id DESC LIMIT 1")
    return int(df.iloc[0]["id"])


def load_profile(user_id: int) -> Optional[dict]:
    # Load a user's profile from the database by their id
    # Returns a dict that matches the shape of st.session_state["user_profile"]
    # Returns None if no user with that id exists
    df = query_df("SELECT * FROM users WHERE id = ?", (user_id,))
    if df.empty:
        return None

    row = df.iloc[0]
    # Convert the comma-separated allergies string back into a list
    raw_allergies = row["allergies"] or ""
    allergies = [a.strip() for a in raw_allergies.split(",") if a.strip()]

    return {
        "name": row["name"] or "",
        "diet": row["diet"] or "omnivore",
        "allergies": allergies,
        "skill_level": row["skill_level"] or "beginner",
    }


def load_all_profiles() -> list[dict]:
    # Return a list of {id, name} for every user in the database
    # Used to display a profile-selection screen
    df = query_df("SELECT id, name FROM users ORDER BY id ASC")
    if df.empty:
        return []
    return df.to_dict("records")


def delete_profile(user_id: int) -> None:
    # Delete the user row — SQLite CASCADE automatically removes
    # all their pantry items and meal plan entries as well
    execute("DELETE FROM users WHERE id = ?", (user_id,))
