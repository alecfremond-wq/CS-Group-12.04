# ============================================================================
#  user_repo.py  —  read / write the user profile in the SQLite database
# ----------------------------------------------------------------------------
#  WHY DOES THIS FILE EXIST?
#  Streamlit's st.session_state is wiped every time the Python process
#  restarts (e.g. when the dev re-runs `streamlit run app.py`). That means
#  the user profile entered on the Onboarding page used to disappear and
#  the user had to fill the form in again on every launch.
#
#  This module is the bridge between st.session_state (in-memory) and the
#  `users` table (on disk). Three small functions:
#       save_profile(profile)   -> INSERT or UPDATE
#       load_profile()          -> dict or None
#       delete_profile()        -> wipe the table (handy for demos)
#
#  The course is single-user (each student runs their own instance), so we
#  always read/write the FIRST row of the users table. If we later add a
#  proper login screen, we'd take a `user_id` argument here instead.
# ============================================================================
#  AI-ASSISTED AUTHORSHIP: scaffold drafted with Anthropic Claude (05/2026),
#  reviewed by Group 12.04. See README.md.
# ============================================================================

from __future__ import annotations

from typing import Optional

from src.data.database import execute, query_df


# The exact set of keys that make up a profile dict, in the order they appear
# in the users table. Centralised here so we don't repeat the column list
# all over the place.
_PROFILE_KEYS = ("name", "diet", "allergies", "budget_weekly", "skill_level")


def save_profile(profile: dict) -> None:
    """Persist the user profile to the `users` table.

    If a row already exists, it is UPDATEd in place (so the auto-incremented
    id stays stable, which keeps any future foreign keys from breaking).
    Otherwise a new row is INSERTed.

    `profile["allergies"]` may be either a list (as used in session_state)
    or a comma-separated string. We always store it as a comma-separated
    string in the DB to match the schema.
    """
    allergies = profile.get("allergies", [])
    if isinstance(allergies, list):
        # Join the list into a "gluten,nuts,soy"-style string for the DB.
        allergies_str = ",".join(allergies)
    else:
        allergies_str = str(allergies or "")

    # Build the value tuple in the same order as _PROFILE_KEYS / the table.
    values = (
        profile.get("name", ""),
        profile.get("diet", "omnivore"),
        allergies_str,
        float(profile.get("budget_weekly", 0) or 0),
        profile.get("skill_level", "beginner"),
    )

    # Look up the existing row (if any). LIMIT 1 because we treat this as a
    # single-user app; the `id` will let us UPDATE the same row in place.
    existing = query_df("SELECT id FROM users ORDER BY id ASC LIMIT 1")

    if existing.empty:
        execute(
            "INSERT INTO users (name, diet, allergies, budget_weekly, skill_level) "
            "VALUES (?, ?, ?, ?, ?)",
            values,
        )
    else:
        user_id = int(existing.iloc[0]["id"])
        execute(
            "UPDATE users "
            "SET name = ?, diet = ?, allergies = ?, "
            "    budget_weekly = ?, skill_level = ? "
            "WHERE id = ?",
            values + (user_id,),
        )


def load_profile() -> Optional[dict]:
    """Return the saved profile as a dict, or None if no row exists yet.

    The dict has exactly the same shape as the one stored in
    st.session_state["user_profile"], so callers can drop it straight into
    session_state without further conversion.
    """
    df = query_df("SELECT * FROM users ORDER BY id ASC LIMIT 1")
    if df.empty:
        return None

    row = df.iloc[0]

    # The DB stores allergies as a comma-separated string; convert back to
    # a list (and skip empty/whitespace-only entries that would creep in).
    raw_allergies = row["allergies"] or ""
    allergies = [a.strip() for a in raw_allergies.split(",") if a.strip()]

    return {
        "name": row["name"] or "",
        "diet": row["diet"] or "omnivore",
        "allergies": allergies,
        "budget_weekly": float(row["budget_weekly"] or 0),
        "skill_level": row["skill_level"] or "beginner",
    }


def delete_profile() -> None:
    """Remove every row from the `users` table.

    Useful for the "Delete my profile" button on the Onboarding page and
    for demo resets. Single-user app, so wiping the whole table is fine.
    """
    execute("DELETE FROM users")
