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

import json                                 # used to decode the wishlist ingredient list from the database

import streamlit as st                     # we need st.session_state from Streamlit


# DEFAULTS defines every key we want in session_state and its initial value
# Adding new keys here is safer than scattering checks across every page
DEFAULTS = {
    # Integer primary key from the `users` table — None means no user is logged in yet
    # Set to the real id by app.py once the user logs in or creates an account
    "user_id": None,
    "user_profile": None,       # dict like {"name": ..., "diet": ...} — filled after login
    "pantry": [],               # list of dicts: {"name":..., "quantity":..., "unit":..., "expires_on":...}
    "meal_plan": {},            # dict mapping date string ("2026-04-21") to a list of meal names
    "cooking_history": [],      # list of dicts: {"recipe_id":..., "cooked_on":..., "rating":...}
    "wishlist": [],             # list of recipe dicts the user saved
}


def init_session_state():
    """Fill in the DEFAULTS above for any keys that are missing.

    Safe to call from every page — it only adds keys that don't exist yet,
    so we never overwrite data the user has already entered.
    """
    # Set all missing keys to their default values
    for key, default in DEFAULTS.items():
        if key not in st.session_state:
            # Copy lists/dicts so each session gets its own independent object
            st.session_state[key] = _copy_default(default)

    # --- Login persistence across page refreshes ---
    # When the user refreshes the browser, Streamlit wipes session_state
    # but the URL still contains ?uid=... which we added at login
    # We read that uid back and restore the session automatically
    if st.session_state.get("user_id") is None:
        try:
            uid_str = st.query_params.get("uid")
            if uid_str:
                st.session_state["user_id"] = int(uid_str)
        except Exception:
            pass

    # If we recovered a user_id but the profile isn't loaded yet, fetch it from the database
    if st.session_state.get("user_profile") is None and st.session_state.get("user_id") is not None:
        try:
            from src.data.user_repo import load_profile
            saved = load_profile(st.session_state["user_id"])
            if saved is not None:
                st.session_state["user_profile"] = saved
        except Exception:
            pass

    # --- Keep the uid in the URL on every page ---
    # Streamlit drops query params when the user navigates to a different page
    # We re-set it here so the uid is always present, enabling persistence on refresh
    user_id = st.session_state.get("user_id")
    try:
        if user_id is not None:
            if st.query_params.get("uid") != str(user_id):
                st.query_params["uid"] = user_id
        else:
            # No user logged in — clear the uid from the URL
            if "uid" in st.query_params:
                st.query_params.clear()
    except Exception:
        pass

    # --- Restore wishlist from database on fresh session ---
    # If the user opens a new browser tab, session_state is empty
    # We reload the wishlist from the database so saved recipes are always there
    if not st.session_state.get("wishlist"):
        try:
            from src.data.database import query_df
            if user_id:
                df = query_df(
                    "SELECT title, image, area, local_id, ingredients "
                    "FROM wishlist WHERE user_id = ?",
                    (user_id,),
                )
                if df is not None and not df.empty:
                    loaded = []
                    for _, row in df.iterrows():
                        try:
                            # Ingredients are stored as a JSON string in the database
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
            pass


def require_profile():
    """Stop the page and show a warning if the user hasn't completed Onboarding.

    Call this at the top of any page that needs a user profile.
    Returns the profile dictionary if it exists.
    """
    # Run init_session_state first to try to recover the session from the URL uid
    init_session_state()

    profile = st.session_state.get("user_profile")

    if not profile:
        # Show a warning banner and stop the page from rendering further
        st.warning(
            "Please complete **Onboarding** first so we can personalise this page."
        )
        # st.stop() prevents the rest of the page from running — avoids crashes
        st.stop()

    return profile


def _copy_default(value):
    # Return a shallow copy of lists/dicts so each session gets its own object
    # For simple values (None, strings, numbers) return the value directly
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value
