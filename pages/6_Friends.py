"""
Friends: Find other users, follow them, and see their saved recipes.

This page lets users build a social layer on top of CookMate.
You can search for other users by username, send them a follow request,
and once they accept, you can browse their wishlist and their own homemade recipes.

How the follow system works:
  1. You type a username in the search box.
  2. We look it up in the 'users' table, if someone matches, a Follow button appears.
  3. Clicking Follow inserts a row into the 'follows' table with status = 'pending'.
     The other person sees the request in their "My Followers" panel.
  4. They click Accept → the status changes to 'accepted'.
     Only then does their wishlist and their recipes become visible to you.
  5. Declining deletes the row entirely, as if the request never happened.

Why we use 'pending' / 'accepted' instead of just a boolean:
  We wanted to give users control over who can see their saved recipes.
  A simple "follow = true" system would expose your wishlist the moment
  someone clicks a button — that felt too open. The request-approval flow
  mirrors how Instagram/Twitter private accounts work.

Dependencies:

  base64 (stdlib)      — decodes recipe images we stored as base64 strings in the DB.
                         We stored images this way so we don't need a separate file server.

  json   (stdlib)      — decodes the ingredient list stored as a JSON string.
                         e.g. '["egg","flour"]' → ["egg", "flour"]

  src.components.ui    — Shared UI helpers:
                           page_header(title, subtitle) → renders the styled title banner.

  src.data.api_client  — All outbound API calls, each decorated with @st.cache_data:
                           search_recipes_by_name(title) → TheMealDB: search by name.
                                                           Used to load the full image +
                                                           instructions for wishlist recipes
                                                           (we only store the title in the DB).
                           search_spoonacular(query)     → Spoonacular: fallback search when
                                                           TheMealDB doesn't know a recipe
                                                           (e.g. it came from Spoonacular originally).

  src.data.database    — SQLite helpers:
                           query_df()  → SELECT → pandas DataFrame
                           execute()   → INSERT / UPDATE / DELETE

  src.utils.session    — Session management:
                           init_session_state() → seeds st.session_state with all default keys
                           require_profile()    → redirects to Home if not logged in yet

Database tables used:
- follows      : one row per (follower, followed) pair.
                 'status' is 'pending' (waiting for approval) or 'accepted' (approved).
                 We CREATE this table here if it doesn't exist yet.
- users        : joined to get display names and usernames for search results.
- wishlist     : recipes each user has saved from the Recipes or Recommendations page.
- user_recipes : recipes users created themselves on the My Recipes page.

Author: Ines Buzel

Sources: Claude Sonnet 4.6 (see comments below)

"""

import base64
import json
import streamlit as st

from src.components.ui import page_header

from src.data.api_client import search_recipes_by_name, search_spoonacular

from src.data.database import execute, query_df

from src.utils.session import init_session_state, require_profile


## Section 1: Page setup
# Initialise session, check login, draw the page header.
# my_id is the database ID of the person currently logged in
# we use it in every query so we only touch data for this user.

init_session_state()
require_profile()
page_header("👥 Friends", "Follow other users and see their saved recipes.")

my_id = st.session_state.get("user_id")

# Created here instead of schema.sql because we added this feature after the app launched.
# 'status' is 'pending' (waiting for approval) or 'accepted'.
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

# Add 'status' to any older follows table that didn't have it yet.
# SQLite throws if the column already exists, so we just ignore that error.
#/ Begin code generated with Claude Sonnet 4.6
try:
    execute("ALTER TABLE follows ADD COLUMN status TEXT NOT NULL DEFAULT 'accepted'")
except Exception:
    pass  # Column already exists → nothing to do.
#/ End code generated with Claude Sonnet 4.6


## Section 2: Helper functions
# These two functions are used when displaying recipe details inside
# a friend's wishlist. We only store the title in the DB, so we fetch
# the full image + instructions from the API on demand.

def fetch_full_recipe(title: str) -> dict | None:
    """Search TheMealDB by title and return the first exact match.
    Returns None if not found (e.g. the recipe originally came from Spoonacular).
    """
    results = search_recipes_by_name(title)

    if not results:
        return None  # TheMealDB returned nothing → probably a Spoonacular recipe.

    # The search can return partial matches (searching "pasta" returns many dishes).
    # We want the one whose name matches our title exactly.
    for meal in results:
        if meal.get("strMeal", "").lower() == title.lower():
            return meal

    return None  # No exact match found.


def extract_full_ingredients(meal: dict) -> list[str]:
    """Build 'measure + name' strings from TheMealDB's numbered fields (strIngredient1..20).
    Skips empty slots and returns a readable list like ["500g Chicken", "2 cloves Garlic"].
    """
    ingredients = []
    for i in range(1, 21):
        name    = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}")    or "").strip()
        if not name:
            continue
        ingredients.append(f"{measure} {name}" if measure else name)
    return ingredients


## Section 3: Search and Followers
# Two columns: search box on the left, follower list on the right.

col_search, col_followers = st.columns([3, 2])


# ── Left column: Search ───────────────────────────────────────────────────────

with col_search:
    st.subheader("🔎 Find a user")
    st.caption("Type the exact username of the person you want to follow.")

    search_query = st.text_input("Username", placeholder="e.g. alex123")

    if search_query:
        # Look up the typed username in the users table.
        # LOWER() on both sides makes it case-insensitive.
        # AND id != my_id prevents you from following yourself.
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
                    col_info, col_btn = st.columns([3, 1])

                    with col_info:
                        st.markdown(f"**{user['name']}** (@{user['username']})")

                    with col_btn:
                        # Check the current follow status so we know which button to show.
                        follow_row = query_df(
                            """
                            SELECT status FROM follows
                            WHERE follower_id = ? AND followed_id = ?
                            """,
                            (my_id, int(user["id"])),
                        )

                        # Three possible states:
                        #   1. No row → we don't follow them yet        → show Follow button
                        #   2. Row, status = 'pending' → request sent   → show Cancel button
                        #   3. Row, status = 'accepted' → following      → show Unfollow button

                        if follow_row is None or follow_row.empty:
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
                            # Request sent but not accepted yet — show a grey label.
                            st.caption("⏳ Pending")
                            if st.button("Cancel", key=f"cancel_{user['id']}",
                                         use_container_width=True):
                                execute(
                                    "DELETE FROM follows WHERE follower_id = ? AND followed_id = ?",
                                    (my_id, int(user["id"])),
                                )
                                st.rerun()

                        else:
                            # Already following → show Unfollow button.
                            if st.button("Unfollow", key=f"unfollow_{user['id']}",
                                         use_container_width=True):
                                execute(
                                    "DELETE FROM follows WHERE follower_id = ? AND followed_id = ?",
                                    (my_id, int(user["id"])),
                                )
                                st.rerun()


# ── Right column: My Followers ────────────────────────────────────────────────
#/ Begin code generated with Claude Sonnet 4.6

with col_followers:
    st.subheader("👤 My Followers")

    # Load all users who follow the current user, with their status.
    # ORDER BY puts pending requests first (so you notice them at the top),
    # then the rest sorted by newest first.
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

    # Fixed-height scrollable box so this panel doesn't push the page down
    # when there are many followers, the Wishlists section stays in place.
    with st.container(height=240):

        # Part A: Pending follow requests,people waiting for your approval.
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
                        # Accept → update the row from 'pending' to 'accepted'.
                        # After this the follower can see your wishlist.
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
                        # The person can send a new request later if they want.
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

        # Part B: Accepted followers → people whose request you already approved.
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
                    back_row = query_df(
                        """
                        SELECT status FROM follows
                        WHERE follower_id = ? AND followed_id = ?
                        """,
                        (my_id, int(follower["id"])),
                    )

                    if back_row is None or back_row.empty:
                        # We don't follow them yet → offer a "Follow back" button.
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
                        # We sent a request but they haven't accepted yet.
                        st.caption("⏳ Request sent")

st.divider()
#/ End code generated with Claude Sonnet 4.6

## Section 4: Friends' Wishlists
# Show saved recipes of everyone we follow (only 'accepted' follows).
# Each friend gets a collapsible section, details loaded from TheMealDB or Spoonacular.

st.subheader("❤️ Friends' Wishlists")

# Load only friends whose follow request we sent AND who already accepted it.
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
    for _, friend in following.iterrows():

        # Load this friend's saved recipes from the wishlist table.
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

        # One collapsible section per friend.
        # The header shows their name and how many recipes they've saved.
        with st.expander(
            f"**{friend['name']}** (@{friend['username']}) "
            f"— {recipe_count} saved recipe(s)"
        ):
            if recipe_count == 0:
                st.caption("This user hasn't saved any recipes yet.")
            else:
                for _, recipe in wishlist.iterrows():
                    title = recipe["title"]

                    area_label     = f"  ·  🌍 {recipe['area']}" if recipe.get("area") else ""
                    expander_label = f"🍽️ {title}{area_label}"

                    with st.expander(expander_label, expanded=False):

                        # Fetch the full recipe details from TheMealDB.
                        # search_recipes_by_name is cached so repeat clicks are free.
                        with st.spinner("Loading recipe details…"):
                            full_meal = fetch_full_recipe(title)

                        if full_meal:
                            # Full recipe found on TheMealDB, show image, ingredients, instructions.
                            # [1, 1, 2] means: image 1 part, ingredients 1 part, instructions 2 parts.
                            col_img, col_ing, col_inst = st.columns([1, 1, 2])

                            with col_img:
                                image_url = full_meal.get("strMealThumb")
                                if image_url:
                                    st.image(image_url, use_container_width=True)

                            with col_ing:
                                st.markdown("**Ingredients**")
                                for ing in extract_full_ingredients(full_meal):
                                    st.caption(f"• {ing}")

                            with col_inst:
                                st.markdown("**Instructions**")
                                instructions = full_meal.get("strInstructions", "")
                                st.write(instructions) if instructions else st.caption("No instructions available.")

                        else:
                            # TheMealDB didn't find it, try Spoonacular as a fallback.
                            # This happens for recipes that were originally found via Spoonacular search.
                            spoon_results = search_spoonacular(query=title)

                            # First look for an exact title match among the results.
                            spoon_meal = None
                            for r in spoon_results:
                                if r.get("strMeal", "").lower() == title.lower():
                                    spoon_meal = r
                                    break

                            # If no exact match, take the first result, it's likely the same dish
                            # with a slightly different title (e.g. "Spaghetti Bolognese" vs "Bolognese").
                            if spoon_meal is None and spoon_results:
                                spoon_meal = spoon_results[0]

                            if spoon_meal:
                                # Spoonacular recipe found, same three-column layout.
                                col_img, col_ing, col_inst = st.columns([1, 1, 2])

                                with col_img:
                                    image_url = spoon_meal.get("strMealThumb")
                                    if image_url:
                                        st.image(image_url, use_container_width=True)

                                with col_ing:
                                    st.markdown("**Ingredients**")
                                    # Spoonacular stores ingredients in "_ingredients" as a plain list.
                                    for ing in spoon_meal.get("_ingredients", []):
                                        st.caption(f"• {ing}")

                                with col_inst:
                                    st.markdown("**Instructions**")
                                    instructions = spoon_meal.get("strInstructions", "")
                                    st.write(instructions) if instructions else st.caption("No instructions available.")

                            else:
                                # Neither API returned results, last resort: show whatever
                                # ingredients we saved in the wishlist table (stored as JSON).
                                st.caption("Could not load full details — showing saved ingredients only.")
                                try:
                                    ingredients = json.loads(recipe["ingredients"] or "[]")
                                    if ingredients:
                                        st.markdown("**Ingredients**")
                                        for ing in ingredients:
                                            st.markdown(f"- {ing}")
                                except Exception:
                                    pass

                        # Save to wishlist button, lets you save a friend's recipe to your own wishlist.
                        # We compare by title because that's the unique identifier we use.
                        already_saved = any(
                            isinstance(w, dict) and w.get("title") == title
                            for w in st.session_state.get("wishlist", [])
                        )

                        if already_saved:
                            st.caption("❤️ Already in your wishlist")
                        else:
                            if st.button(
                                "+ Save to wishlist",
                                key=f"save_{friend['id']}_{title}",
                            ):
                                # 1. Add to session so the rest of the app sees it immediately.
                                st.session_state.setdefault("wishlist", []).append({
                                    "title":       title,
                                    "image":       recipe.get("image"),
                                    "area":        recipe.get("area", ""),
                                    "local_id":    None,
                                    "ingredients": json.loads(recipe["ingredients"] or "[]"),
                                })
                                # 2. Persist to DB so it survives a page reload.
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

st.divider()


## Section 5: Friends' own recipes
# Recipes friends wrote themselves on the My Recipes page (not from an API).
# Images are stored as base64 in the DB and decoded here before displaying.

st.subheader("📝 Friends' Recipes")
st.caption("Recipes your friends created themselves.")

if following is None or following.empty:
    pass  
else:
    for _, friend in following.iterrows():

        # Load all recipes this friend has created themselves, newest first.
        friend_recipes = query_df(
            """
            SELECT id, title, ingredients, instructions, image_data, created_at
            FROM user_recipes
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (int(friend["id"]),),
        )

        recipe_count = (
            len(friend_recipes)
            if (friend_recipes is not None and not friend_recipes.empty)
            else 0
        )

        with st.expander(
            f"**{friend['name']}** (@{friend['username']}) "
            f"— {recipe_count} recipe(s)"
        ):
            if recipe_count == 0:
                st.caption("This user hasn't created any recipes yet.")
            else:
                for _, recipe in friend_recipes.iterrows():
                    with st.container(border=True):

                        # Card header: image on the left, title + date on the right.
                        col_img, col_info = st.columns([1, 4])

                        with col_img:
                            if recipe.get("image_data"):
                                # The image was stored as a base64 string, decode it back
                                # to raw bytes so st.image() can display it.
                                img_bytes = base64.b64decode(recipe["image_data"])
                                st.image(img_bytes, use_container_width=True)
                            else:
                                st.markdown("📷")

                        with col_info:
                            st.subheader(recipe["title"])
                            st.caption(f"Added on {str(recipe['created_at'])[:10]}")

                        # Expandable details: ingredients on the left, instructions on the right.
                        with st.expander("📖 Show details", expanded=False):
                            col_ing, col_inst = st.columns([1, 2])

                            with col_ing:
                                st.markdown("**Ingredients**")
                                ingredients_text = recipe.get("ingredients") or ""
                                if ingredients_text:
                                    for line in ingredients_text.splitlines():
                                        if line.strip():
                                            st.caption(f"• {line.strip()}")
                                else:
                                    st.caption("No ingredients listed.")

                            with col_inst:
                                st.markdown("**Instructions**")
                                instructions_text = recipe.get("instructions") or ""
                                if instructions_text:
                                    st.write(instructions_text)
                                else:
                                    st.caption("No instructions provided.")
