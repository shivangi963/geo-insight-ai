import streamlit as st
import requests
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, Dict
import io
from PIL import Image as PILImage

from api_client import api
from utils import (
    poll_task_status, format_number, get_walkability_label,
    show_success_message, show_error_message, get_amenity_display_name,
    init_session_state, get_session_state, format_percentage, show_warning_message,
)
from components.header import render_section_header
from config import map_config, TASK_MAX_WAIT

def render_neighborhood_page():
    render_section_header("Neighborhood Analysis")
    st.markdown(
        "Get a complete picture of any neighbourhood — nearby places, walkability score, green coverage, and map."
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.success("Amenities")
    with col2:
        st.success("Walk Score")
    with col3:
        st.success("Green Space")
    with col4:
        st.success("Map")

    st.divider()

    default_address = get_session_state("nav_to_analysis", "")
    triggered = _render_analysis_form(default_address)

    if not triggered and "current_analysis" in st.session_state:
        stored = st.session_state.current_analysis
        _display_analysis_results(stored["result"], stored["analysis_id"])

    st.divider()
    _render_recent_analyses()

def _render_analysis_form(default_address: str = "") -> bool:
    with st.form("neighborhood_form"):
        address = st.text_input(
            "Enter Neighbourhood",
            value=default_address,
            placeholder="Koramangala, Bengaluru, Karnataka, India",
        )

        email = st.text_input(
            "Your Email (for results notification)",
            placeholder="you@gmail.com",
            help="We'll email you when the analysis is complete",
        )

        col1, _ = st.columns(2)
        with col1:
            radius = st.slider(
                "Search Radius (metres)",
                map_config.min_radius,
                map_config.max_radius,
                map_config.default_radius,
                100,
            )

        st.markdown("Select Amenities")
        amenities_selected = _render_amenity_selector()

        submitted = st.form_submit_button(
            "Analyse Neighbourhood",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not address:
            show_error_message("Please enter an address")
            return False
        if not amenities_selected:
            show_error_message("Select at least one amenity type")
            return False
        if "current_analysis" in st.session_state:
            del st.session_state["current_analysis"]
        _handle_analysis_submission(address, radius, amenities_selected, email)

        return True
    return False

def _render_amenity_selector() -> list:
    amenity_options = {
        "Restaurants":  "restaurant",
        "Cafes":        "cafe",
        "Schools":      "school",
        "Hospitals":    "hospital",
        "Parks":        "park",
        "Supermarkets": "supermarket",
        "Banks":        "bank",
        "Pharmacies":   "pharmacy",
        "Gyms":         "gym",
        "Libraries":    "library",
        "Transit":      "transit_station",
    }

    cols = st.columns(4)
    default_types = ["restaurant", "cafe", "school", "hospital"]
    selected = []

    for idx, (label, value) in enumerate(amenity_options.items()):
        with cols[idx % 4]:
            if st.checkbox(label, value=(value in default_types), key=f"amenity_{value}"):
                selected.append(value)

    return selected

def _handle_analysis_submission(address: str, radius: int, amenities: list, email: str = ""):
    st.divider()

    import requests as _req

    with st.spinner("Starting analysis..."):
        try:
            payload = {
                "address": address,
                "radius_m": radius,
                "email": email or "",
                "amenity_types": amenities,          
            }
            resp = _req.post(
                f"{api.base_url}/api/workflow/webhook/analysis",
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            response = resp.json()
        except Exception as exc:
            show_warning_message(f"Workflow unavailable ({exc}), running direct analysis (no email).")
         
            response = api.start_neighborhood_analysis({
                "address": address,
                "radius_m": radius,
                "amenity_types": amenities,          
                "include_buildings": False,
                "generate_map": True,
            })

    if not response:
        return

    analysis_id = response.get("analysis_id")
    task_id     = response.get("task_id")

    if email:
        st.info(f" Results will be emailed to **{email}** when the analysis completes.")

    with st.spinner("Analysing neighbourhood..."):
        result = poll_task_status(task_id, max_wait=TASK_MAX_WAIT)

    if result:
        history = get_session_state("analysis_history", [])
        history.append({
            "address":               address,
            "analysis_id":           analysis_id,
            "walk_score":            result.get("walk_score"),
            "total_amenities":       result.get("total_amenities"),
            "green_space_percentage": result.get("green_space_percentage"),
        })

        st.session_state.analysis_history = history[-10:]
        st.session_state.current_analysis = {
            "result":      result,
            "analysis_id": analysis_id,
        }

        _display_analysis_results(result, analysis_id)


def _display_analysis_results(result: dict, analysis_id: str, generate_map: bool = True):
    st.divider()

    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader("Analysis Results")
    with col2:
        if st.button("Clear", key="clear_analysis"):
            if "current_analysis" in st.session_state:
                del st.session_state["current_analysis"]
            st.rerun()

    _render_key_metrics(result)
    _render_walkability_interpretation(result.get("walk_score", 0))

    amenities = result.get("amenities", {})
    if amenities:
        _render_amenities_breakdown(amenities)

    _render_green_space_section(result, analysis_id)

    if generate_map:
        _render_interactive_map(analysis_id)

def _render_key_metrics(result: dict):
    green_pct = result.get("green_space_percentage")

    if green_pct is not None:
        col1, col2, col3, col4, col5 = st.columns(5)
    else:
        col1, col2, col3, col4 = st.columns(4)

    with col1:
        ws = result.get("walk_score", 0) or 0
        st.metric("Walk Score", f"{ws:.1f}/100")

    with col2:
        st.metric("Amenities", format_number(result.get("total_amenities", 0)))

    coords = result.get("coordinates")

    with col3:
        if isinstance(coords, (list, tuple)):
            st.metric("Latitude", f"{coords[0]:.4f}")
        elif isinstance(coords, dict):
            st.metric("Latitude", f"{coords.get('latitude', 0):.4f}")
        else:
            st.metric("Latitude", "—")

    with col4:
        if isinstance(coords, (list, tuple)):
            st.metric("Longitude", f"{coords[1]:.4f}")
        elif isinstance(coords, dict):
            st.metric("Longitude", f"{coords.get('longitude', 0):.4f}")
        else:
            st.metric("Longitude", "—")

    if green_pct is not None:
        with col5:
            st.metric("Green Space", f"{green_pct:.1f}%")

def _render_walkability_interpretation(walk_score: float):
    st.divider()

    if walk_score >= 90:
        st.success("Walker's Paradise. Daily errands do not require a car.")
    elif walk_score >= 70:
        st.success("Very Walkable. Most errands can be accomplished on foot.")
    elif walk_score >= 50:
        st.info("Somewhat Walkable. Some amenities within walking distance.")
    elif walk_score >= 25:
        st.warning("Car-Dependent. Most errands require a car.")
    else:
        st.error("Very Car-Dependent. Almost all errands require a car.")

def _render_amenities_breakdown(amenities: dict):
    st.divider()
    st.subheader("Nearby Amenities")

    amenity_counts = {
        k.replace("_", " ").title(): len(v)
        for k, v in amenities.items() if v
    }

    if amenity_counts:
        fig = px.bar(
            x=list(amenity_counts.keys()),
            y=list(amenity_counts.values()),
            labels={"x": "Amenity Type", "y": "Count"},
            title="Amenity Distribution",
            color=list(amenity_counts.values()),
            color_continuous_scale="viridis",
        )

        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("Nearby Places")

        cols = st.columns(3)

        for idx, (atype, items) in enumerate(amenities.items()):
            if items:
                with cols[idx % 3]:
                    display_name = get_amenity_display_name(atype)
                    with st.expander(f"{display_name} ({len(items)})"):
                        for i, item in enumerate(items, 1):
                            st.write(f"{i}. {item.get('name', 'Unknown')}")
                            st.caption(f"{item.get('distance_km', 0):.2f} km away")
    else:
        st.info("No amenities found in the search radius")

def _render_green_space_section(result: dict, analysis_id: str):
    green_pct = result.get("green_space_percentage")

    st.divider()
    st.subheader("Green Space Analysis")

    breakdown = result.get("green_space_breakdown") or {}
    viz_path = result.get("green_space_visualization")
    green_px = result.get("green_pixels", 0) or 0
    total_px = result.get("total_pixels", 0) or 0

    col1, _, _ = st.columns(3)
    with col1:
        st.metric("Green Coverage", f"{green_pct:.1f}%" if green_pct is not None else "—")

    if green_pct is not None:
        col_gauge, col_interp = st.columns([2, 1])

        with col_gauge:
            st.plotly_chart(_create_green_gauge(green_pct), use_container_width=True)

        with col_interp:
            st.markdown("What this means")
            st.info(_green_interpretation(green_pct))

            if green_pct >= 60:
                st.success("Excellent green coverage")
            elif green_pct >= 40:
                st.success("Good green coverage")
            elif green_pct >= 20:
                st.warning("Moderate green coverage")
            else:
                st.error("Low green coverage")

    if breakdown and any(v > 0 for v in breakdown.values()):
        st.markdown("Green Space Breakdown by Type")

        labels_map = {
            "parks_grass": ("Parks / Grass", ""),
            "forests_woods": ("Forests / Woods", ""),
            "recreation": ("Recreation", ""),
            "natural_areas": ("Natural Areas", ""),
        }

        bcols = st.columns(4)

        for idx, (key, pct) in enumerate(breakdown.items()):
            label, icon = labels_map.get(key, (key.replace("_", " ").title(), ""))
            with bcols[idx % 4]:
                st.metric(f"{label}", f"{pct:.1f}%")

        st.plotly_chart(_create_breakdown_chart(breakdown), use_container_width=True)

    if viz_path:
        st.markdown("Green Space Overlay")

        col_img, col_legend = st.columns([3, 1])

        with col_img:
            try:
                img_resp = requests.get(f"{api.base_url}/{viz_path}", timeout=10)
                if img_resp.status_code == 200:
                    img = PILImage.open(io.BytesIO(img_resp.content))
                    st.image(img, caption="Green areas highlighted on the OSM map", use_container_width=True)
                else:
                    st.warning(f"Visualization image not available (HTTP {img_resp.status_code})")
            except Exception as exc:
                st.warning(f"Could not load visualization: {exc}")

        with col_legend:
            st.markdown("Detected green space")
            st.markdown("---")
            st.caption("Green areas are highlighted on the map.")

def _create_green_gauge(percentage: float) -> go.Figure:
    color = (
        "#28a745" if percentage >= 50
        else "#ffc107" if percentage >= 30
        else "#dc3545"
    )

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=percentage,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Green Coverage %", "font": {"size": 20}},
        number={"suffix": "%", "font": {"size": 36}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "darkblue"},
            "bar": {"color": color},
            "bgcolor": "white",
            "borderwidth": 2,
            "bordercolor": "gray",
            "steps": [
                {"range": [0, 20], "color": "#ffe6e6"},
                {"range": [20, 40], "color": "#fff4e6"},
                {"range": [40, 60], "color": "#ffffcc"},
                {"range": [60, 80], "color": "#e6ffe6"},
                {"range": [80, 100], "color": "#ccffcc"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": 50,
            },
        },
    ))

    fig.update_layout(height=280, margin=dict(l=20, r=20, t=60, b=20))
    return fig

def _create_breakdown_chart(breakdown: Dict[str, float]) -> go.Figure:
    labels_map = {
        "parks_grass": "Parks / Grass",
        "forests_woods": "Forests / Woods",
        "recreation": "Recreation",
        "natural_areas": "Natural Areas",
    }

    colors_map = {
        "parks_grass": "#90EE90",
        "forests_woods": "#228B22",
        "recreation": "#3CB371",
        "natural_areas": "#6B8E23",
    }

    labels = [labels_map.get(k, k) for k in breakdown]
    values = list(breakdown.values())
    colors = [colors_map.get(k, "#00FF00") for k in breakdown]

    fig = go.Figure(data=[go.Bar(
        x=labels,
        y=values,
        marker_color=colors,
        text=[f"{v:.1f}%" for v in values],
        textposition="auto",
    )])

    fig.update_layout(
        title="Green Space by Type",
        xaxis_title="Green Type",
        yaxis_title="Coverage (%)",
        height=350,
        showlegend=False,
    )

    return fig

def _green_interpretation(pct: float) -> str:
    if pct >= 60:
        return "Excellent. Abundant parks, forests, and natural spaces."
    elif pct >= 40:
        return "Good. Healthy vegetation and park coverage."
    elif pct >= 20:
        return "Moderate. Some parks and green areas present."
    elif pct >= 10:
        return "Limited. Mostly urban with minimal vegetation."
    return "Very low. Highly urbanised area."

def _render_interactive_map(analysis_id: str):
    st.divider()
    st.subheader("Interactive Amenities Map")

    map_url = f"{api.base_url}/api/neighborhood/{analysis_id}/map"
    response = api.get(f"/api/neighborhood/{analysis_id}")

    if not response:
        st.error("Could not load analysis data")
        return

    if response.get("status") != "completed":
        st.warning(f"Analysis not completed yet. Status: {response.get('status')}")
        return

    if not response.get("map_path"):
        st.warning("Map was not generated for this analysis")
        return

    with st.spinner("Loading map"):
        try:
            html_response = requests.get(map_url, timeout=10)
            if html_response.status_code == 200:
                st.components.v1.html(html_response.text, height=700, scrolling=True)
            else:
                st.error(f"Failed to load map: HTTP {html_response.status_code}")
        except requests.exceptions.RequestException as exc:
            st.error(f"Network error: {exc}")

def _render_recent_analyses():
    st.subheader("Recent Analyses")

    recent = api.get("/api/neighborhood/recent", params={"limit": 10})

    if not recent:
        st.info("No recent analyses available")
        return

    analyses = recent.get("analyses", [])

    if not analyses:
        st.info("No analyses yet. Start your first analysis above.")
        return

    for analysis in analyses:
        _render_analysis_card(analysis)

def _render_analysis_card(analysis: dict):
    status = analysis.get("status", "unknown")
    address = analysis.get("address", "Unknown")
    gs_pct = analysis.get("green_space_percentage")

    emoji = {
        "completed": "",
        "processing": "",
        "pending": "",
        "failed": ""
    }.get(status, "")

    gs_tag = f" · {gs_pct:.1f}%" if gs_pct is not None else ""

    with st.expander(f"{address}{gs_tag}"):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.write(f"Status: {status.title()}")
            if ws := analysis.get("walk_score"):
                st.write(f"Walk Score: {ws:.1f}/100")

        with col2:
            st.write(f"Amenities: {analysis.get('total_amenities', 0)}")
            if gs_pct is not None:
                st.write(f"Green Space: {gs_pct:.1f}%")

        with col3:
            st.write(f"Created: {analysis.get('created_at', 'N/A')}")
            if aid := analysis.get("analysis_id"):
                if st.button("View Details", key=f"view_{aid}"):
                    full = api.get_analysis(aid)
                    if full:
                        _display_analysis_results(full, aid)