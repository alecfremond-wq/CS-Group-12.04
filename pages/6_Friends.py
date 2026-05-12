"""
Friends — find other users and see their wishlists.

!!! fertig kommentieren!!!

How this page works:
    1. The user types a username into the search box.
    2. We look that username up in the 'users' table in our database.
    3. If found, we show a Follow / Unfollow button next to the result.
    4. At the bottom of the page we show the wishlists of everyone
       the current user is already following.
    5. Each recipe in a friend's wishlist can be expanded to see the
       full ingredient list and cooking instructions, loaded live from
       TheMealDB or Spoonacular so we don't have to store that data ourselves.

Owner: <assign on Apr 22>
Grading coverage:
    * Req. 4 (user interaction — follow users, browse their wishlists)
"""

# ── Imports ───────────────────────────────────────────────────────────────────
# json      → decodes the ingredient list we stored as a JSON string in the DB.
#             e.g. '["egg","flour"]' → ["egg", "flour"]
# streamlit → the framework that draws the whole web app.
import json
import streamlit as st

# page_header → draws the consistent title banner at the top of every page.
from src.components.ui import page_header

# search_recipes_by_name → searches TheMealDB by title and returns matching meals.
#   Used as the first attempt to load full recipe details (image + instructions).
#   Cached by Streamlit for 1 hour so the same title is only fetched once.
#
# search_spoonacular → searches Spoonacular by title.
#   Used as a fallback when TheMealDB doesn't know the recipe (e.g. recipes
#   that were originally found via Spoonacular search on the Recipes page).
#   Also cached for 1 hour in api_client.py.
from src.data.api_client import search_recipes_by_name, search_spoonacular

# query_df → runs a SELECT and returns a pandas DataFrame.
# execute  → runs INSERT / UPDATE / DELETE (no return value).
from src.data.database import execute, query_df

# init_session_state → fills in all default session keys before we read them.
# require_profile    → stops the page and shows a warning if not logged in.
from src.utils.session import init_session_state, require_profile


# ── Page setup ────────────────────────────────────────────────────────────────

init_session_state()
require_profile()
page_header("👥 Friends", "Follow other users and see their saved recipes.")

# my_id is the database ID of the person currently logged in.
# We use it in every query so we only touch data that belongs to this user.
my_id = st.session_state.get("user_id")

# ── Make sure the follows table exists ────────────────────────────────────────
# We create the table here with a 'status' column that tracks whether a follow
# request is waiting for approval ('pending') or has been accepted ('accepted').
#
#   When user A clicks "Follow" on user B, we don't want B's wishlist to be
#   visible immediately. Instead, B gets a follow request they can accept or
#   decline. Only after accepting does A see B's wishlist.
#
# The DEFAULT 'accepted' means that if we ever insert a row without specifying
# the status, it defaults to accepted — useful for the migration below.
execute(
    """
    CREATE TABLE IF NOT EXISTS follows (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        follower_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        followed_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        status      TEXT    NOT NULL DEFAULT 'pending',
        UNIQUE (follower_id, followed_id)
    )
    """
)

# ── Migration: add 'status' column to existing follows table ──────────────────
# If the app was already running before we added this feature, the follows table
# exists but has no 'status' column. SQLite lets us add a column with
# ALTER TABLE ... ADD COLUMN. We wrap it in try/except because SQLite throws
# an error if the column already exists — and that's fine, we just ignore it.
try:
    execute("ALTER TABLE follows ADD COLUMN status TEXT NOT NULL DEFAULT 'accepted'")
except Exception:
    # Column already exists — nothing to do.
    pass


# ── Helper: load full recipe details from TheMealDB (same as in recipes page)───────────────────────────

def fetch_full_recipe(title: str) -> dict | None:
    """Try to load the complete recipe data for a given title from TheMealDB.

    Our wishlist only stores the title and ingredients — not the image or
    the cooking instructions. This function asks TheMealDB for the full
    recipe by searching for the exact title.

        We never stored the TheMealDB ID in the wishlist table, so we
        have to search by name. TheMealDB's search endpoint returns all
        meals whose name CONTAINS the query, so we then check whether
        any result matches the title exactly (case-insensitive).

    Returns the meal dict if found, or None if TheMealDB doesn't know
    this recipe (e.g. it came from Spoonacular instead).
    """
    # Ask TheMealDB for meals matching this title.
    # search_recipes_by_name is cached, so repeat calls are free.
    results = search_recipes_by_name(title)

    if not results:
        # TheMealDB returned nothing — probably a Spoonacular recipe.
        return None

    # The search can return partial matches (e.g. searching "pasta" returns
    # many dishes). We want the one whose name matches our title exactly.
    for meal in results:
        if meal.get("strMeal", "").lower() == title.lower():
            return meal

    # No exact match found.
    return None


# ── Helper: extract ingredients + measures from a TheMealDB meal dict ─────────

def extract_full_ingredients(meal: dict) -> list[str]:
    """Build a list of 'measure + ingredient' strings from a TheMealDB meal.

    TheMealDB stores ingredients and their amounts in separate numbered fields:
        strIngredient1 = "Chicken"   strMeasure1 = "500g"
        strIngredient2 = "Garlic"    strMeasure2 = "2 cloves"
        ...up to strIngredient20 / strMeasure20

    We combine them into readable strings like "500g Chicken", "2 cloves Garlic".
    Empty slots (TheMealDB fills unused ones with "" or None) are skipped.
    """
    ingredients = []
    for i in range(1, 21):
        name    = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}")    or "").strip()

        # Skip the slot if the ingredient name is empty.
        if not name:
            continue

        # Combine measure and name, or just use name if there's no measure.
        if measure:
            ingredients.append(f"{measure} {name}")
        else:
            ingredients.append(name)

    return ingredients


# ── Section 1: Search + Followers side by side ────────────────────────────────
#
# We use st.columns([3, 2]) to split the top of the page into two panels:
#   col_search    (left, wider)  → search box and results
#   col_followers (right)        → list of people who follow YOU
#
# This way the user can search for someone AND see their own followers
# at the same time without scrolling.

col_search, col_followers = st.columns([3, 2])

# ── Left panel: Search ────────────────────────────────────────────────────────
with col_search:
    st.subheader("🔎 Find a user")
    st.caption("Type the exact username of the person you want to follow.")

    # A text box where the user types the username they're looking for.
    search_query = st.text_input("Username", placeholder="e.g. alex123")

    # Only run the search if something was typed.
    if search_query:

        # Query the users table for a matching username.
        # LOWER() makes it case-insensitive, AND id != my_id stops self-following.
        results = query_df(
            """
            SELECT id, name, username
            FROM users
            WHERE LOWER(username) = LOWER(?)
              AND id != ?
            """,
            (search_query.strip(), my_id),
        )

        if results is None or results.empty:
            st.info("No user found with that username. Make sure you typed it exactly.")
        else:
            for _, user in results.iterrows():
                with st.container(border=True):

                    # Two columns: user info on the left, button on the right.
                    col_info, col_btn = st.columns([3, 1])

                    with col_info:
                        st.markdown(f"**{user['name']}** (@{user['username']})")

                    with col_btn:
                        # Check the current follow status between us and this user.
                        # We select the 'status' column so we know whether a request
                        # is still pending or has already been accepted.
                        follow_row = query_df(
                            """
                            SELECT status FROM follows
                            WHERE follower_id = ? AND followed_id = ?
                            """,
                            (my_id, int(user["id"])),
                        )

                        # Three possible states:
                        #   1. No row exists          → we don't follow them yet
                        #   2. Row exists, pending    → request sent, waiting
                        #   3. Row exists, accepted   → we follow them

                        if follow_row is None or follow_row.empty:
                            # State 1: not following yet → show Follow button.
                            # Clicking sends a follow REQUEST (status = 'pending').
                            # The other user must accept before we can see their wishlist.
                            if st.button("Follow ＋", key=f"follow_{user['id']}",
                                         use_container_width=True):
                                execute(
                                    """
                                    INSERT OR IGNORE INTO follows
                                        (follower_id, followed_id, status)
                                    VALUES (?, ?, 'pending')
                                    """,
                                    (my_id, int(user["id"])),
                                )
                                st.rerun()

                        elif follow_row.iloc[0]["status"] == "pending":
                            # State 2: request sent but not yet accepted.
                            # Show a greyed-out label and a cancel button.
                            st.caption("⏳ Pending")
                            if st.button("Cancel", key=f"cancel_{user['id']}",
                                         use_container_width=True):
                                execute(
                                    "DELETE FROM follows WHERE follower_id = ? AND followed_id = ?",
                                    (my_id, int(user["id"])),
                                )
                                st.rerun()

                        else:
                            # State 3: accepted → we follow them, show Unfollow button.
                            if st.button("Unfollow", key=f"unfollow_{user['id']}",
                                         use_container_width=True):
                                execute(
                                    "DELETE FROM follows WHERE follower_id = ? AND followed_id = ?",
                                    (my_id, int(user["id"])),
                                )
                                st.rerun()

# ── Right panel: My Followers ─────────────────────────────────────────────────
with col_followers:
    st.subheader("👤 My Followers")

    # Load ALL follow rows where the current user is the one being followed.
    # We also fetch the follower's id so we can use it in Accept/Decline buttons.
    # The 'status' column tells us whether each request is pending or accepted.
    all_followers = query_df(
        """
        SELECT u.id, u.name, u.username, f.status
        FROM follows f
        JOIN users u ON f.follower_id = u.id
        WHERE f.followed_id = ?
        ORDER BY CASE WHEN f.status = 'pending' THEN 0 ELSE 1 END, f.id DESC
        """,
        (my_id,),
    )

    # st.container(height=...) creates a fixed-height box with its own scrollbar.
    # Everything inside stays contained — the Wishlists section below won't move
    # no matter how many followers there are.
    # ~320px shows roughly 2-3 follower cards before you need to scroll.
    with st.container(height=240):

        # ── Part A: Pending follow requests ──────────────────────────────────
        # Filter to only the rows where status = 'pending'.
        # These are people who clicked Follow on your profile but you haven't
        # decided yet — you can Accept or Decline each one.

        if all_followers is not None and not all_followers.empty:
            pending = all_followers[all_followers["status"] == "pending"]
        else:
            pending = None

        if pending is not None and not pending.empty:
            st.markdown("**📬 Follow Requests**")
            for _, req in pending.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{req['name']}** (@{req['username']})")

                    btn_accept, btn_decline = st.columns(2)

                    with btn_accept:
                        # Accept → update the status from 'pending' to 'accepted'.
                        # After this, the follower can see your wishlist.
                        if st.button("✅ Accept", key=f"accept_{req['id']}",
                                     use_container_width=True):
                            execute(
                                """
                                UPDATE follows SET status = 'accepted'
                                WHERE follower_id = ? AND followed_id = ?
                                """,
                                (int(req["id"]), my_id),
                            )
                            st.rerun()

                    with btn_decline:
                        # Decline → delete the row entirely.
                        # The person can try to follow again later if they want.
                        if st.button("❌ Decline", key=f"decline_{req['id']}",
                                     use_container_width=True):
                            execute(
                                """
                                DELETE FROM follows
                                WHERE follower_id = ? AND followed_id = ?
                                """,
                                (int(req["id"]), my_id),
                            )
                            st.rerun()

        # ── Part B: Accepted followers ────────────────────────────────────────
        # Filter to only the rows where status = 'accepted'.
        # These are people whose follow request you already approved.

        if all_followers is not None and not all_followers.empty:
            accepted = all_followers[all_followers["status"] == "accepted"]
        else:
            accepted = None


        if accepted is None or accepted.empty:
            st.caption("Nobody is following you yet.")
        else:
            for _, follower in accepted.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{follower['name']}**")
                    st.caption(f"@{follower['username']}")

                    # Check whether WE already follow this person back.
                    # We look for a row where we are the follower and they are followed.
                    back_row = query_df(
                        """
                        SELECT status FROM follows
                        WHERE follower_id = ? AND followed_id = ?
                        """,
                        (my_id, int(follower["id"])),
                    )

                    if back_row is None or back_row.empty:
                        # We don't follow them yet → show a "Follow back" button.
                        # Clicking sends a pending follow request to them, just like
                        # the normal Follow button in the search panel.
                        if st.button("Follow back ＋", key=f"followback_{follower['id']}",
                                     use_container_width=True):
                            execute(
                                """
                                INSERT OR IGNORE INTO follows
                                    (follower_id, followed_id, status)
                                VALUES (?, ?, 'pending')
                                """,
                                (my_id, int(follower["id"])),
                            )
                            st.rerun()

                    elif back_row.iloc[0]["status"] == "pending":
                        # We sent a request but they haven't accepted it yet.
                        # Just show a small grey label — no button needed.
                        st.caption("⏳ Request sent")

st.divider()


# ── Section 2: Wishlists of people you follow ─────────────────────────────────

st.subheader("❤️ Friends' Wishlists")

# Load only the people the current user follows AND whose request was accepted.
# We add AND f.status = 'accepted' so that pending requests don't show up here
# yet — you can only see someone's wishlist after they approved your request.
following = query_df(
    """
    SELECT u.id, u.name, u.username
    FROM follows f
    JOIN users u ON f.followed_id = u.id
    WHERE f.follower_id = ?
      AND f.status = 'accepted'
    ORDER BY u.name
    """,
    (my_id,),
)

if following is None or following.empty:
    st.info("You're not following anyone yet (or your requests are still pending).")
else:
    # One collapsible section per followed user.
    for _, friend in following.iterrows():

        # Load this friend's wishlist from the database.
        wishlist = query_df(
            """
            SELECT title, image, area, ingredients
            FROM wishlist
            WHERE user_id = ?
            ORDER BY title
            """,
            (int(friend["id"]),),
        )

        recipe_count = len(wishlist) if (wishlist is not None and not wishlist.empty) else 0

        # st.expander creates a collapsible section.
        # The header shows the friend's name and how many recipes they saved.
        with st.expander(
            f"**{friend['name']}** (@{friend['username']}) "
            f"— {recipe_count} saved recipe(s)"
        ):
            if recipe_count == 0:
                st.caption("This user hasn't saved any recipes yet.")
            else:
                # Show each recipe as a collapsible expander.
                # The header shows just the title + area — small and compact.
                # Everything else (image, ingredients, instructions) is hidden
                # inside and only loads when the user clicks to open it.
                for _, recipe in wishlist.iterrows():
                    title = recipe["title"]

                    # Build a compact one-line header for the expander.
                    # Shows the title and the cuisine area (if we have it).
                    area_label = f"  ·  🌍 {recipe['area']}" if recipe.get("area") else ""
                    expander_label = f"🍽️ {title}{area_label}"

                    # st.expander collapses the content by default (expanded=False).
                    # The user clicks the arrow to open it and load the full details.
                    with st.expander(expander_label, expanded=False):

                        # Only fetch the full recipe data when the expander is open.
                        # In Streamlit, code inside an expander still runs on every
                        # page reload — but because search_recipes_by_name is cached,
                        # repeat calls cost nothing after the first fetch.
                        with st.spinner("Loading recipe details…"):
                            full_meal = fetch_full_recipe(title)

                        if full_meal:
                            # ── Full recipe found on TheMealDB ────────────────

                            # Three columns: small image on the left, then
                            # ingredients, then instructions.
                            # [1, 1, 2] means: image gets 1 part, ingredients
                            # get 1 part, instructions get 2 parts of the width.
                            col_img, col_ing, col_inst = st.columns([1, 1, 2])

                            with col_img:
                                image_url = full_meal.get("strMealThumb")
                                if image_url:
                                    st.image(image_url, use_container_width=True)

                            with col_ing:
                                st.markdown("**Ingredients**")
                                # extract_full_ingredients builds the list of
                                # "measure + name" strings from the meal dict.
                                for ing in extract_full_ingredients(full_meal):
                                    st.caption(f"• {ing}")

                            with col_inst:
                                st.markdown("**Instructions**")
                                instructions = full_meal.get("strInstructions", "")
                                if instructions:
                                    st.write(instructions)
                                else:
                                    st.caption("No instructions available.")

                        else:
                            # ── Not found on TheMealDB → try Spoonacular ──────
                            # Some recipes in the wishlist originally came from
                            # Spoonacular (searched on the Recipes page). TheMealDB
                            # doesn't know them, so we try Spoonacular as a backup.
                            # search_spoonacular returns the first result that
                            # matches the title closely enough.
                            spoon_results = search_spoonacular(query=title)

                            # Find the result whose title matches exactly.
                            spoon_meal = None
                            for r in spoon_results:
                                if r.get("strMeal", "").lower() == title.lower():
                                    spoon_meal = r
                                    break

                            # If no exact match, just take the first result —
                            # it's likely the same dish even if the name differs
                            # slightly (e.g. "Spaghetti Bolognese" vs "Bolognese").
                            if spoon_meal is None and spoon_results:
                                spoon_meal = spoon_results[0]

                            if spoon_meal:
                                # ── Spoonacular recipe found ──────────────────

                                # Same three-column layout as TheMealDB above.
                                col_img, col_ing, col_inst = st.columns([1, 1, 2])

                                with col_img:
                                    image_url = spoon_meal.get("strMealThumb")
                                    if image_url:
                                        st.image(image_url, use_container_width=True)

                                with col_ing:
                                    st.markdown("**Ingredients**")
                                    # Spoonacular stores ingredients in "_ingredients"
                                    # as a list of strings — no extra parsing needed.
                                    for ing in spoon_meal.get("_ingredients", []):
                                        st.caption(f"• {ing}")

                                with col_inst:
                                    st.markdown("**Instructions**")
                                    instructions = spoon_meal.get("strInstructions", "")
                                    if instructions:
                                        st.write(instructions)
                                    else:
                                        st.caption("No instructions available.")

                            else:
                                # ── Neither API returned results ──────────────
                                # Last resort: show whatever ingredients we saved
                                # in the wishlist table (stored as a JSON string).
                                st.caption(
                                    "Could not load full details — "
                                    "showing saved ingredients only."
                                )
                                try:
                                    ingredients = json.loads(recipe["ingredients"] or "[]")
                                    if ingredients:
                                        st.markdown("**Ingredients**")
                                        for ing in ingredients:
                                            st.markdown(f"- {ing}")
                                except Exception:
                                    pass

                        # ── Save to my wishlist button ────────────────────────
                        # Check if the current user already has this recipe saved.
                        # We compare by title because that's the unique identifier
                        # we use in the wishlist table (UNIQUE on user_id + title).
                        already_saved = any(
                            isinstance(w, dict) and w.get("title") == title
                            for w in st.session_state.get("wishlist", [])
                        )

                        if already_saved:
                            # Already saved — just show a small label.
                            st.caption("❤️ Already in your wishlist")
                        else:
                            # The key must be unique per button on the page.
                            # We combine friend ID + recipe title to achieve that.
                            if st.button(
                                "+ Save to wishlist",
                                key=f"save_{friend['id']}_{title}",
                            ):
                                # Add to the in-memory session list so the rest
                                # of the app (Recipes page, ML model) sees it right away.
                                st.session_state.setdefault("wishlist", []).append({
                                    "title":       title,
                                    "image":       recipe.get("image"),
                                    "area":        recipe.get("area", ""),
                                    "local_id":    None,
                                    "ingredients": json.loads(recipe["ingredients"] or "[]"),
                                })
                                # Persist to the database so it survives a reload.
                                execute(
                                    """
                                    INSERT OR IGNORE INTO wishlist
                                        (user_id, title, image, area, local_id, ingredients)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        my_id,
                                        title,
                                        recipe.get("image"),
                                        recipe.get("area", ""),
                                        None,
                                        recipe["ingredients"] or "[]",
                                    ),
                                )
                                st.rerun()
