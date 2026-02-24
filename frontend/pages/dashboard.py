import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from api_client import api
from utils import format_currency


def render_dashboard_page():
    st.subheader("Overview")
    stats  = api.get_stats()
    health = api.health_check()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Properties", stats.get("total_properties", 0) if stats else "—")
    with col2:
        st.metric("Analyses Run", stats.get("total_analyses", 0) if stats else "—")
    with col3:
        st.metric("Cities Covered", stats.get("unique_cities", 0) if stats else "—")
    with col4:
        status = "● Live" if health and health.get("status") == "healthy" else "● Offline"
        st.metric("System", status)

    st.divider()

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("Recent Analyses")
        recent   = api.get("/api/neighborhood/recent", params={"limit": 6})
        analyses = recent.get("analyses", []) if recent else []

        if analyses:
            for a in analyses:
                status = a.get("status", "unknown")
                ws     = a.get("walk_score")
                gs     = a.get("green_space_percentage")

                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 2, 2])
                    with c1:
                        st.markdown(f"{a.get('address', 'Unknown')[:45]}")
                        st.caption(a.get("created_at", "")[:10])
                    with c2:
                        st.metric("Walk Score", f"{ws:.0f}" if ws else "—")
                    with c3:
                        st.metric("Green", f"{gs:.0f}%" if gs else "—")
        else:
            st.info("No analyses yet. Go to the Neighbourhood tab to run your first one.")

    with col_right:
        st.markdown("Property Price Distribution")
        properties = api.get_properties(limit=200)
        if properties:
            df = pd.DataFrame(properties)
            if "price" in df.columns:
                avg_price = df['price'].mean()
                st.caption(f"Avg Price: {format_currency(avg_price)}")

                fig = px.histogram(
                    df, x="price", nbins=25,
                    labels={"price": "Price", "count": "Properties"},
                    color_discrete_sequence=["#2563EB"],
                )
                fig.update_layout(
                    showlegend=False,
                    margin=dict(l=0, r=0, t=20, b=0),
                    height=280,
                    plot_bgcolor="white",
                    yaxis=dict(gridcolor="#f0f0f0"),
                )
                st.plotly_chart(fig, use_container_width=True)

            if "property_type" in df.columns:
                type_counts = df["property_type"].value_counts().head(6)
                fig2 = go.Figure(go.Pie(
                    labels=type_counts.index,
                    values=type_counts.values,
                    hole=0.5,
                    marker_colors=["#2563EB","#7C3AED","#059669","#D97706","#DC2626","#0891B2"],
                ))
                fig2.update_layout(
                    showlegend=True,
                    margin=dict(l=0, r=0, t=20, b=0),
                    height=250,
                )
                st.plotly_chart(fig2, use_container_width=True)