# ============================================================================
#  session.py  —  helpers for Streamlit's "memory" (st.session_state)
# ----------------------------------------------------------------------------
#  WHY DOES THIS FILE EXIST?
#  Streamlit re-runs your whole Python script every time the user clicks a
#  button or types in a text box. Anything stored in a normal variable is
#  forgotten on the next click. To keep data around (like the user's profile
#  or their pantry list) we put it into `st.session_state`, which is a
#  special dictionary Streamlit keeps alive between reruns.
#
#  This file centralises the default values so that every page can assume
#  the keys already exist, instead of checking "if 'pantry' not in ..." over
#  and over.
# ============================================================================
#  AI-ASSISTED AUTHORSHIP: scaffold drafted with Anthropic Claude (04/2026),
#  reviewed by Group 12.04. See README.md.
# ============================================================================

import json                                 # we need json to decode the ingredient list

import streamlit as st                     # we need st.session_state from Streamlit


# DEFAULTS is a dictionary that describes every key we want in session_state
# and what its initial value should be.
# Add new keys here instead of scattering `if "..." not in ...` checks everywhere.
DEFAULTS = {
    # Integer primary key from the `users` table. Defaults to 1 as a safe
    # placeholder so the Pantry / Meal Planner pages (which key their rows
    # on user_id) work out of the box. The Onboarding page should keep
    # this in sync with the actual id of the saved user.
    "user_id": 1,
    "user_profile": None,       # will become a dict like {"name": ..., "diet": ...} after onboarding
    "pantry": [],               # list of ingredient dicts: {"name":..., "quantity":..., "unit":..., "expires_on":...}
    "meal_plan": {},            # dict mapping a date string ("2026-04-21") to a list of meal names
    "cooking_history": [],      # list of dicts: {"recipe_id":..., "cooked_on":..., "rating":...}
    "wishlist": [],             # list of recipe IDs the user wants to try
}


def init_session_state():
    """Fill in the DEFAULTS above for any keys that are missing.

    Safe to call from every page — it only adds keys that don't exist yet,
    so we never overwrite data the user has already entered.

    After the defaults are set, this also tries to LOAD the saved profile
    from the SQLite `users` table. That way the user only has to fill in
    Onboarding once: on every subsequent reload of the app the profile is
    pulled out of the database back into session_state.
    """
    # Loop over every (key, default_value) pair in the DEFAULTS dictionary.
    for key, default in DEFAULTS.items():
        # If this key isn't already in session_state, add it.
        if key not in st.session_state:
            # We copy the default so each user session gets its own list/dict
            # (otherwise different pages could share the same list object).
            st.session_state[key] = _copy_default(default)

    # If we've just filled in user_profile with its default of None (i.e.
    # this is a fresh Streamlit session), try to hydrate it from the DB.
    # We import lazily to avoid a circular import (database.py -> session.py
    # would be a cycle if user_repo were imported at the top of this file).
    if st.session_state.get("user_profile") is None:
        try:
            from src.data.user_repo import load_profile
            saved = load_profile()
            if saved is not None:
                st.session_state["user_profile"] = saved
        except Exception:
            # The DB might not exist yet (e.g. very first run before
            # init_db()). In that case we silently fall back to the empty
            # default — the user will simply complete Onboarding once.
            pass

    # Load the wishlist from the database if it's empty in session_state.
    # This runs every time a fresh browser session starts so the user's
    # saved recipes are always there, even after closing and reopening the app.
    # We only do this when the wishlist is still empty — if the user already
    # has items loaded we don't want to overwrite them.
    if not st.session_state.get("wishlist"):
        try:
            from src.data.database import query_df
            user_id = st.session_state.get("user_id")
            if user_id:
                df = query_df(
                    "SELECT title, image, area, local_id, ingredients "
                    "FROM wishlist WHERE user_id = ?",
                    (user_id,),
                )
                if df is not None and not df.empty:
                    loaded = []
                    for _, row in df.iterrows():
                        # ingredients is stored as a JSON string in the DB,
                        # e.g. '["pasta", "eggs", "parmesan"]'
                        # json.loads converts it back to a Python list.
                        try:
                            ingredients = json.loads(row["ingredients"] or "[]")
                        except Exception:
                            ingredients = []
                        loaded.append({
                            "title":       row["title"],
                            "image":       row["image"],
                            "area":        row["area"],
                            "local_id":    row["local_id"],
                            "ingredients": ingredients,
                        })
                    st.session_state["wishlist"] = loaded
        except Exception:
            # If anything goes wrong (table doesn't exist yet, DB not ready),
            # we just keep the empty wishlist — no crash, no data loss.
            pass


def require_profile():
    """Stop the page and show a warning if the user hasn't completed Onboarding.

    Call this at the top of any page that needs a user profile.
    Returns the profile dictionary if it exists.
    """
    # Make sure all session keys exist before we try to read them — also
    # gives us the chance to hydrate user_profile from the DB on the very
    # first call from any page.
    init_session_state()

    # Try to read the profile from session_state. `.get()` returns None if missing.
    profile = st.session_state.get("user_profile")

    # `not profile` is True if profile is None or an empty dict.
    if not profile:
        # Show a yellow warning banner.
        st.warning(
            "Please complete **Onboarding** first so we can personalise this page."
        )
        # st.stop() halts this page's script here — the rest of the page
        # won't run, which prevents crashes from missing data.
        st.stop()

    # If we got here, the profile exists — return it for the calling page to use.
    return profile


def _copy_default(value):
    """Return a copy of a list or dict, or the value itself if it's simple.

    The underscore prefix (_copy_default) is a Python convention that means
    "this is a private helper — don't import it from outside this file".
    """
    # isinstance(x, dict) checks whether x is a dictionary.
    if isinstance(value, dict):
        return dict(value)          # make a shallow copy of the dictionary
    if isinstance(value, list):
        return list(value)          # make a shallow copy of the list
    # For simple types (None, strings, numbers), returning the value itself is safe.
    return value
