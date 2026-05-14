"""
My Recipes: Create and save your own homemade recipes.

This page lets users write down their own recipes, not recipes from an API,
but dishes they invented or cook at home. They can give it a title, list the
ingredients, write the steps, and optionally upload a photo.

How this page works:
  1. The user fills out a form: title, ingredients, instructions, optional photo.
  2. Clicking Save writes the recipe to the user_recipes table in the database.
     The photo is converted to a base64 string before storing, so we don't need
     any external file storage, everything lives in the same SQLite file.
  3. Below the form, all existing recipes are loaded from the database and
     shown as cards (thumbnail + title always visible, full details in an expander).
  4. Each card has a Delete button that removes the recipe permanently from the DB.
  5. Friends who follow you can see your recipes on the Friends page — the
     user_recipes table is read there too.

Why we store images as base64 (explained by Claude Sonnet 4.6):
  SQLite can only store text and numbers, not raw binary files. base64 converts
  any file (like a JPEG) into a long string of normal characters, which SQLite
  can store in a TEXT column. When we want to display it again, we just decode
  the string back to bytes and pass it to st.image(). This avoids needing a
  separate images folder or a cloud storage service.

Dependencies:

  base64    (stdlib)      — encodes uploaded image bytes to a base64 text string
                            for DB storage, and decodes it back when displaying.

  src.components.ui       — Shared UI helpers:
                              page_header(title, subtitle) → renders the title banner.

  src.data.database       — SQLite helpers:
                              query_df(sql, params) → SELECT → pandas DataFrame.
                              execute(sql, params)  → INSERT / DELETE.

  src.utils.session       — Session management:
                              init_session_state() → seeds all default session keys.
                              require_profile()    → stops the page if not logged in.

Database tables used:
- user_recipes : one row per recipe per user.
                 Columns: id, user_id, title, ingredients (plain text, one per line),
                 instructions, image_data (base64 string or NULL), created_at.

Author: Ines Buzel

Sources: Claude Sonnet 4.6 (see comments below)

"""

import base64

import streamlit as st

from src.components.ui import page_header

from src.data.database import execute, query_df

from src.utils.session import init_session_state, require_profile


## Section 1: Page setup

init_session_state()
require_profile()
page_header("📝 My Recipes", "Create and save your own recipes.")

# my_id is the database ID of the currently logged-in user.
# Every INSERT and SELECT uses it so users only ever see their own recipes.
my_id = st.session_state.get("user_id")


## Section 2: Add a new recipe form
# st.form with clear_on_submit=True so the page only re-runs on submit, not every keystroke.

st.subheader("➕ Add a new recipe")

with st.form("new_recipe_form", clear_on_submit=True):
    title = st.text_input("Recipe title")

    ingredients = st.text_area(
        "Ingredients",
        placeholder="One ingredient per line, e.g.\n2 eggs\n200g flour\n1 tsp salt",
        height=150,
    )

    instructions = st.text_area(
        "Instructions",
        placeholder="Step-by-step cooking instructions…",
        height=200,
    )

    # file_uploader lets the user pick a photo from their device.
    # We only accept common image formats to keep things simple.
    image_file = st.file_uploader(
        "Upload a photo (optional)",
        type=["jpg", "jpeg", "png"],
    )

    submitted = st.form_submit_button("Save recipe", type="primary")

if submitted:
    if not title.strip():
        st.error("Please enter a recipe title.")
    else:
        # Convert the uploaded photo to base64 so we can store it as text in SQLite.
        # base64.b64encode() turns raw bytes (JPEG/PNG data) into a safe ASCII string.
        # base64.b64decode() reverses this when we want to display the image later.
        #/ Begin code generated with Claude Sonnet 4.6
        image_data = None
        if image_file is not None:
            raw_bytes  = image_file.read()
            image_data = base64.b64encode(raw_bytes).decode("utf-8")
        #/ End code generated with Claude Sonnet 4.6

        execute(
            """
            INSERT INTO user_recipes (user_id, title, ingredients, instructions, image_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (my_id, title.strip(), ingredients.strip(), instructions.strip(), image_data),
        )
        st.success(f"'{title.strip()}' saved!")
        st.rerun()

st.divider()


## Section 3: Display saved recipes
# Load recipes newest first. Each one is a card: thumbnail visible, details in an expander.

st.subheader("📖 Your recipes")

my_recipes = query_df(
    """
    SELECT id, title, ingredients, instructions, image_data, created_at
    FROM user_recipes
    WHERE user_id = ?
    ORDER BY created_at DESC
    """,
    (my_id,),
)

if my_recipes is None or my_recipes.empty:
    st.info(
        "You haven't created any recipes yet. "
        "Use the form above to add your first one!"
    )
else:
    for _, recipe in my_recipes.iterrows():
        with st.container(border=True):

            # Card header: image on the left, title + date + Delete button on the right.
            col_img, col_info = st.columns([1, 4])

            with col_img:
                #/ Begin code generated with Claude Sonnet 4.6
                if recipe.get("image_data"):
                    # Decode the base64 string back to raw bytes.
                    # st.image() can display bytes directly — no file path needed.
                    img_bytes = base64.b64decode(recipe["image_data"])
                    st.image(img_bytes, use_container_width=True)
                else:
                    st.markdown("📷")  # No photo uploaded → placeholder emoji.
                #/ End code generated with Claude Sonnet 4.6

            with col_info:
                st.subheader(recipe["title"])
                # created_at is a full timestamp like "2026-04-21 14:32:00".
                # We slice the first 10 characters to show just the date.
                st.caption(f"Added on {str(recipe['created_at'])[:10]}")

                # AND user_id = ? makes sure users can only delete their own recipes.
                if st.button("🗑️ Delete", key=f"delete_{recipe['id']}"):
                    execute(
                        "DELETE FROM user_recipes WHERE id = ? AND user_id = ?",
                        (int(recipe["id"]), my_id),
                    )
                    st.rerun()

            # Expandable details: full ingredient list and cooking instructions.
            # Sits below the two columns so it spans the full card width.
            with st.expander("📖 Show details"):
                col_ing, col_inst = st.columns([1, 2])

                with col_ing:
                    st.markdown("**Ingredients**")
                    ingredients_text = recipe.get("ingredients") or ""
                    if ingredients_text:
                        # The user typed one ingredient per line in the form.
                        # We split on newlines and show each line as a bullet point.
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
