"""Streamlit entrypoint. Run from the project root:  streamlit run frontend/app.py"""
import streamlit as st

import api

st.set_page_config(page_title="Wyscout x MongoDB", layout="wide")

pages = [
    st.Page("pages/1_ingest.py", title="Ingest", default=True),
    st.Page("pages/2_update.py", title="Update"),
    st.Page("pages/3_delete.py", title="Delete"),
    st.Page("pages/4_analytics.py", title="Analytics"),
]
navigation = st.navigation(pages)


@st.cache_data(ttl=30, show_spinner=False)
def cached_health() -> dict:
    return api.health()


try:
    status = cached_health()
except api.ApiError as exc:
    st.error(f"{exc}\n\nOpen a second terminal in the project folder and run:")
    st.code(api.START_HINT, language="bash")
    st.stop()

with st.sidebar:
    st.markdown("**API / Atlas**")
    if status["mongo"] == "ok":
        st.success(status["message"])
        for name, count in status["counts"].items():
            st.write(f"{name}: **{count}**")
    else:
        st.warning(status["message"])
    if st.button("Refresh status"):
        cached_health.clear()
        st.rerun()

navigation.run()
