import streamlit as st
import sys
import os
from api_client import api

if os.path.exists('frontend'):
    sys.path.insert(0, 'frontend')

try:
    from config import ui_config
except ImportError:
    class UIConfig:
        page_title = "GeoInsight AI "
        layout = "wide"
        initial_sidebar_state = "collapsed"
    ui_config = UIConfig()

st.set_page_config(
    page_title=ui_config.page_title,
    layout=ui_config.layout,
    initial_sidebar_state="auto"
)

def _render_sidebar():
    with st.sidebar:
        st.markdown("GeoInsight AI")
        st.divider()

        st.markdown("Recent Searches")
        history = st.session_state.get("analysis_history", [])
        if history:
            for i, item in enumerate(reversed(history[-5:])):
                addr = item.get("address", "")[:30]
                ws   = item.get("walk_score")
                if st.button(f" {addr}", key=f"sb_{i}_{addr}", use_container_width=True):
                    st.session_state.nav_to_analysis = item.get("address", "")
                    st.rerun()
                if ws:
                    st.caption(f"Walk Score: {ws:.0f}/100")
        else:
            st.caption("Your recent searches will appear here.")

        st.divider()

        health = api.health_check()
        if health and health.get("status") == "healthy":
            st.success("● System Online")
        else:
            st.error("● System Offline")


def _render_topbar():
    st.markdown("## GeoInsight AI")
    st.divider()

for _key, _val in [
    ('analysis_history', []),
    ('agent_history', []),
    ('nav_to_analysis', ''),
    ('ai_query', ''),
    ('show_ai_history', False),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _val

_render_sidebar()
_render_topbar()

tab0, tab1, tab2, tab3, tab4  = st.tabs([
    " Dashboard",
    " Properties",
    " Neighborhood",
    " Assistant",
    " Similar Homes",
])

with tab0:
    try:
        from pages.dashboard import render_dashboard_page
        render_dashboard_page()
    except Exception as e:
        st.error(f"Dashboard error: {e}")

with tab1:
    try:
        from pages.properties import render_properties_page
        render_properties_page()
    except Exception as e:
        st.error(f" Properties page error: {e}")

with tab2:
    try:
        from pages.neighborhood import render_neighborhood_page
        render_neighborhood_page()
    except Exception as e:
        st.error(f"Neighborhood page error: {e}")

with tab3:
    try:
        from pages.ai_assistant import render_ai_assistant_page
        render_ai_assistant_page()
    except Exception as e:
        st.error(f" AI Assistant page error: {e}")

with tab4:
    try:
        from pages.vector_search import render_vector_search_page
        render_vector_search_page()
    except Exception as e:
        st.error(f" Visual Search page error: {e}")