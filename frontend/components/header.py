
import streamlit as st
from datetime import datetime

# DELETE this function entirely:
def render_header():
    st.title("GeoInsight AI ")
    st.divider()

def render_page_header(title: str, subtitle: str = None):
    if subtitle:
        st.caption(subtitle)

def render_section_header(title: str, icon: str = ""):
    if icon:
        st.subheader(f"{icon} {title}")
    else:
        st.subheader(title)

def render_footer():
    st.divider()
    
    col1, col3, col4 = st.columns(4)
    
    with col1:
        st.caption(" GeoInsight")
    
    with col3:
        st.caption(f"{datetime.now().strftime('%Y-%m-%d')}")
    
    with col4:
        st.caption(f"{datetime.now().strftime('%H:%M:%S')}")