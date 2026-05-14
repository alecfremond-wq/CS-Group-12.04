"""
My Recipes — create and save your own recipes with a photo.

How this page works:
    1. A form at the top lets you enter a title, ingredients,
       instructions, and optionally upload a photo from your device.
    2. The photo is converted to base64 (a way to store binary image
       data as plain text) and saved in the database.
    3. Below the form, all your saved recipes are shown as cards —
       each one has the photo always visible and a collapsible section
       for the full ingredient list and instructions.
    4. A Delete button removes the recipe from the database permanently.

Owner: <assign>
"""

# base64   → converts image bytes to a text string safe to store in SQLite,
#             and decodes it back when we want to display the image.
# streamlit → the framework that draws the whole web app.
import base64

import streamlit as st

# page_header → draws the consistent title banner used on every page.
from src.components.ui import page_header

# execute  → runs INSERT / DELETE queries (no return value).
# query_df → runs SELECT queries and returns a pandas DataFrame.
from src.data.database import execute, query_df

# init_session_state → fills in default session keys before we read them.
# require_profile    → stops the page with a warning if the user isn't logged in.
from src.utils.session import init_session_state, require_profile


# ── Page setup ────────────────────────────────────────────────────────────────

init_session_state()
require_profile()
page_header("📝 My Recipes", "Create and save your own recipes.")

# my_id is the database ID of the currently logged-in user.
# We attach it to every INSERT and SELECT so users only see their own recipes.
my_id = st.session_state.get("user_id")


# ── Add a new recipe ──────────────────────────────────────────────────────────

st.subheader("➕ Add a new recipe")

# clear_on_submit=True resets the form fields after the user clicks Save.
with st.form("new_recipe_form", clear_on_submit=True):
    title        = st.text_input("Recipe title")
    ingredients  = st.text_area(
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
    # We only accept common image formats to keep it simple.
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
        # base64 turns raw bytes (e.g. JPEG data) into a string of normal characters.
        # Without this step, we'd need a separate folder on disk or an external service.
        image_data = None
        if image_file is not None:
            raw_bytes  = image_file.read()
            image_data = base64.b64encode(raw_bytes).decode("utf-8")

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


# ── Your saved recipes ────────────────────────────────────────────────────────

st.subheader("📖 Your recipes")

# Load all recipes for this user, newest first.
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

            # ── Card header: image always visible ─────────────────────────────
            # Two columns: narrow image on the left, title on the right.
            col_img, col_info = st.columns([1, 4])

            with col_img:
                if recipe.get("image_data"):
                    # Decode the base64 string back to raw bytes.
                    # st.image() can display bytes directly — no file needed.
                    img_bytes = base64.b64decode(recipe["image_data"])
                    st.image(img_bytes, use_container_width=True)
                else:
                    # No photo uploaded — show a placeholder emoji.
                    st.markdown("📷")

            with col_info:
                st.subheader(recipe["title"])
                st.caption(f"Added on {str(recipe['created_at'])[:10]}")

                # Delete button — removes the recipe from the DB permanently.
                if st.button("🗑️ Delete", key=f"delete_{recipe['id']}"):
                    execute(
                        "DELETE FROM user_recipes WHERE id = ? AND user_id = ?",
                        (int(recipe["id"]), my_id),
                    )
                    st.rerun()

            # ── Expandable details ─────────────────────────────────────────────
            with st.expander("📖 Show details"):
                col_ing, col_inst = st.columns([1, 2])

                with col_ing:
                    st.markdown("**Ingredients**")
                    ingredients_text = recipe.get("ingredients") or ""
                    if ingredients_text:
                        # Each line is one ingredient — we show it as a bullet point.
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
