# ============================================================================
#  session.py  —  helpers for Streamlit's "memory" (st.session_state)
# ----------------------------------------------------------------------------
#  MULTI-USER FIX: user_id is no longer hardcoded to 1. It starts as None
#  and is only set after the user picks their profile on the login screen.
#  init_session_state() no longer auto-loads the last DB profile, so each
#  browser session starts fresh until the user explicitly logs in.
# ============================================================================
#  AI-ASSISTED AUTHORSHIP: scaffold drafted with Anthropic Claude (04/2026),
#  reviewed by Group 12.04. See README.md.
# ============================================================================

import streamlit as st


DEFAULTS = {
    # None until the user selects/creates their profile on the login screen.
    # Previously hardcoded to 1, which caused every session to share the
    # same user row in the DB.
    "user_id": None,
    "user_profile": None,       # dict like {"name": ..., "diet": ...} after login
    "pantry": [],
    "meal_plan": {},
    "cooking_history": [],
    "wishlist": [],
}


def init_session_state():
    """Fill in the DEFAULTS above for any keys that are missing.

    Safe to call from every page — it only adds keys that don't exist yet,
    so we never overwrite data the user has already entered.

    NOTE: We deliberately do NOT auto-load a profile from the DB here
    anymore. Previously this caused every new browser session to inherit
    the last saved profile. Now the user must select their name on the
    home/login screen, which sets user_id and user_profile explicitly.
    """
    for key, default in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = _copy_default(default)


def require_profile():
    """Stop the page and show a warning if the user hasn't logged in yet.

    Call this at the top of any page that needs a user profile.
    Returns the profile dictionary if it exists.
    """
    init_session_state()

    profile = st.session_state.get("user_profile")

    if not profile:
        st.warning(
            "Please go to the **Home** page and select or create your profile first."
        )
        st.stop()

    return profile


def _copy_default(value):
    """Return a shallow copy of a list/dict, or the value itself for scalars."""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value
