"""
Small, reusable UI helpers.

Keep this module tiny: only widgets that would otherwise be copy-pasted
across multiple pages. Anything feature-specific belongs in that feature's
page file.
"""

from __future__ import annotations

import streamlit as st


def page_header(title: str, subtitle: str = "") -> None:
    """Render a consistent page header across all pages."""
    st.title(title)
    if subtitle:
        st.caption(subtitle)
    st.divider()


def empty_state(message: str, icon: str = "ℹ️") -> None:
    """Friendly placeholder for pages that have no data yet."""
    st.info(f"{icon} {message}")
