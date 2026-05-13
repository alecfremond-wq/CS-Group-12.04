"""
Reusable UI helper functions shared across all pages.
Only widgets that would otherwise be copy-pasted across multiple pages live here.
Anything feature-specific belongs in that feature's page file.

Dependencies:

  - streamlit : UI framework; renders every widget.

Author: Alec Frémond

"""

from __future__ import annotations

import streamlit as st


#1. Page layout helpers ################
# Functions to render consistent headers and empty state placeholders.

def page_header(title: str, subtitle: str = "") -> None:
    """
    Renders a consistent page header across all pages.

    Parameters:
        title    : str — the page title displayed as h1.
        subtitle : str — optional caption shown below the title.
    """
    st.title(title)
    if subtitle:
        st.caption(subtitle)
    st.divider()


def empty_state(message: str, icon: str = "ℹ️") -> None:
    """
    Renders a friendly placeholder for pages that have no data yet.

    Parameters:
        message : str — the message to display.
        icon    : str — optional emoji icon shown before the message.
    """
    st.info(f"{icon} {message}")
