"""Web app entry point.   streamlit run app/streamlit_app.py

Pages: Home (landing page with features and a short manual), Convert (the tool), Dashboard (history of
conversions), Guide (options, formats, limits). Navigation is a top bar; the sidebar is hidden.
Needs Streamlit 1.36 or newer (st.navigation).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

import ui  # noqa: E402

st.set_page_config(page_title="Document Analyst", page_icon="📄", layout="wide", initial_sidebar_state="collapsed")
ui.inject_css()

pages = [
    st.Page("views/home.py", title="Home", icon="🏠", default=True),
    st.Page("views/convert.py", title="Convert", icon="📄"),
    st.Page("views/dashboard.py", title="Dashboard", icon="📊"),
    st.Page("views/guide.py", title="Guide", icon="📘"),
    st.Page("views/docs.py", title="Documentation", icon="📚"),
]
current = st.navigation(pages)          # registers the pages; the sidebar list is hidden by CSS
ui.topbar(current.title)
current.run()
