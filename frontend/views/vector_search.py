from __future__ import annotations
import io
import time
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
from PIL import Image

from api_client import api
from components.header import render_section_header
from utils import show_error_message, show_success_message, validate_file_size, _clean_message

_THRESHOLD_HELP = "How closely the results should match your photo (higher = stricter)"
_LIMIT_HELP = "Maximum number of similar properties to return"
BACKEND_URL = api.base_url


def render_vector_search_page():
    render_section_header("Find Similar Properties")
    st.markdown("Upload any property photo to find similar listings")
    _render_search_ui()


def _render_search_ui():
    uploaded = st.file_uploader(
        "Property photo",
        type=["jpg", "jpeg", "png", "webp"],
        help="Max 10 MB · JPEG / PNG / WEBP",
        key="vs_query_upload",
    )

    current_name = uploaded.name if uploaded else None
    if current_name != st.session_state.get("vs_last_file"):
        st.session_state["vs_results"] = None
        st.session_state["vs_last_file"] = current_name
        _clear_all_panels()

    if not uploaded:
        st.info("Upload a property image above to begin.")
        return

    if not validate_file_size(uploaded, max_size_mb=10):
        return

    image_bytes = uploaded.getvalue()

    col_img, col_params = st.columns([2, 1])
    with col_img:
        st.image(
            Image.open(io.BytesIO(image_bytes)),
            caption=f"{uploaded.name}  ·  {uploaded.size / 1024:.1f} KB",
            use_container_width=True,
        )

    with col_params:
        st.markdown("Search Parameters")
        with st.form("vs_search_form"):
            limit = st.slider("Max results", 1, 20, 3, help=_LIMIT_HELP)
            threshold = st.slider("Min similarity", 0.0, 1.0, 0.70, step=0.05, help=_THRESHOLD_HELP)
            st.caption("Tip: Lower the threshold if you get no results.")
            submitted = st.form_submit_button("Search", type="primary", use_container_width=True)

        if submitted:
            _run_search(uploaded, image_bytes, limit, threshold)

    if st.session_state.get("vs_results"):
        st.divider()
        results = st.session_state["vs_results"]
        st.markdown(f"{len(results)} Similar Properties Found")
        _render_results(results)


def _clear_all_panels():
    for k in list(st.session_state.keys()):
        if k.startswith("vs_nbr") or k.startswith("vs_img_"):
            del st.session_state[k]



def _load_image_cached(url: str) -> Optional[bytes]:
    cache_key = f"vs_img_{hash(url)}"
    if cache_key not in st.session_state:
        try:
            r = requests.get(url, timeout=5)
            st.session_state[cache_key] = r.content if r.status_code == 200 else None
        except Exception:
            st.session_state[cache_key] = None
    return st.session_state[cache_key]


def _run_search(uploaded, image_bytes: bytes, limit: int, threshold: float):
    with st.spinner("Searching for similar properties…"):
        try:
            uploaded.seek(0)
            resp = requests.post(
                f"{BACKEND_URL}/api/vector/search",
                files={"file": (uploaded.name, image_bytes, uploaded.type)},
                params={"limit": limit, "threshold": threshold},
                timeout=30,
            )
        except requests.exceptions.RequestException as exc:
            show_error_message(f"Network error: {exc}")
            return

    if resp.status_code == 503:
        detail = resp.json().get("detail", {})
        st.error("Vector DB unavailable")
        hint = detail.get("hint") if isinstance(detail, dict) else str(detail)
        st.info(hint or "Set SUPABASE_URL and SUPABASE_KEY in your .env and restart the backend.")
        return

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        show_error_message(f"Search failed ({resp.status_code}): {detail}")
        return

    results: List[Dict[str, Any]] = resp.json().get("results", [])
    if not results:
        st.warning("No similar properties found. Try lowering Min similarity.")
        return

    st.session_state["vs_results"] = results
    _clear_all_panels()

def _render_results(results: List[Dict[str, Any]]):
    for rank, item in enumerate(results, start=1):
        sim = item.get("similarity", 0.0)
        addr = item.get("address", "Unknown address")
        imgurl = item.get("image_url", "")
        meta = item.get("metadata", {})

        with st.container(border=True):
            col_rank, col_main, col_score = st.columns([0.5, 5, 2])
            with col_rank:
                st.markdown(f"{rank}")
            with col_main:
                st.markdown(f"{addr}")
                if meta:
                    parts = []
                    if meta.get("price"):
                        parts.append(f"₹{meta['price']:,.0f}")
                    if meta.get("bedrooms"):
                        parts.append(f"{meta['bedrooms']} BHK")
                    if meta.get("city"):
                        parts.append(meta["city"])
                    if parts:
                        st.caption("  ·  ".join(parts))
            with col_score:
                st.metric("Similarity", f"{sim:.1%}")

            st.progress(sim)

            if imgurl:
                with st.expander("View property image"):
                    img_bytes = _load_image_cached(imgurl)
                    if img_bytes:
                        st.image(Image.open(io.BytesIO(img_bytes)), width=320)
                    else:
                        st.caption("Image unavailable")

            nbr_open = st.session_state.get("vs_nbr", {}).get("rank") == rank

            if not nbr_open:
                if st.button("Analyse Area", key=f"vs_open_{rank}", use_container_width=True):
                    locality = meta.get("locality", "").strip()
                    city = meta.get("city", "").strip()
                    if locality and city and locality.lower() != city.lower():
                        geo_addr = f"{locality}, {city}, India"
                    elif locality:
                        geo_addr = f"{locality}, India"
                    else:
                        geo_addr = addr
                    st.session_state["vs_nbr"] = {
                        "addr": geo_addr,
                        "display_addr": addr,
                        "rank": rank,
                    }
                    st.rerun()
            else:
                if st.button("Close Area Analysis", key=f"vs_close_{rank}", use_container_width=True):
                    st.session_state.pop("vs_nbr", None)
                    st.session_state.pop(f"vs_nbr_result_{rank}", None)
                    st.session_state.pop(f"vs_nbr_ran_{rank}", None)
                    st.rerun()

        if nbr_open:
            _render_inline_neighbourhood(
                st.session_state["vs_nbr"]["addr"],
                rank,
                display_addr=st.session_state["vs_nbr"].get("display_addr", ""),
            )


def _render_inline_neighbourhood(address: str, rank: int, display_addr: str = ""):
    st.markdown("---")
    with st.container(border=True):
        label = display_addr or address
        st.markdown(f"Neighbourhood — {label[:60]}")
        if display_addr and display_addr != address:
            st.caption(f"Geocoding via: {address}")

        col1, col2 = st.columns(2)
        with col1:
            radius = st.slider(
                "Search radius (m)", 100, 3000, 1000, 100,
                key=f"vs_nbr_radius_{rank}"
            )
        with col2:
            amenity_options = {
                "Restaurants": "restaurant",
                "Cafes": "cafe",
                "Schools": "school",
                "Hospitals": "hospital",
                "Parks": "park",
                "Supermarkets": "supermarket",
                "Banks": "bank",
                "Pharmacies": "pharmacy",
            }
            selected = st.multiselect(
                "Amenities to search",
                list(amenity_options.keys()),
                default=["Restaurants", "Cafes", "Schools", "Hospitals"],
                key=f"vs_nbr_am_{rank}",
            )
            amenity_types = [amenity_options[a] for a in selected]

        cache_key = f"vs_nbr_result_{rank}"
        ran_key = f"vs_nbr_ran_{rank}"

        if st.button("Run Analysis", type="primary", key=f"vs_nbr_run_{rank}"):
            st.session_state[ran_key] = True
            st.session_state.pop(cache_key, None)

        if not st.session_state.get(ran_key):
            return

        if cache_key not in st.session_state:
            with st.spinner("Analysing neighbourhood…"):
                response = api.start_neighborhood_analysis({
                    "address": address,
                    "radius_m": radius,
                    "amenity_types": amenity_types or ["restaurant", "cafe", "school", "hospital"],
                    "include_buildings": False,
                    "generate_map": False,
                })

            if not response:
                st.error("Could not start analysis")
                st.session_state.pop(ran_key, None)
                return

            task_id = response.get("task_id")
            result = _poll_task(task_id)
            if result is None:
                st.warning("Analysis is taking longer than expected. Check Neighbourhood tab in a few minutes.")
                st.session_state.pop(ran_key, None)
                return
            st.session_state[cache_key] = result

        result = st.session_state.get(cache_key)
        if result:
            _display_neighbourhood_result(result)


def _display_neighbourhood_result(result: dict):
    walk = result.get("walk_score") or 0
    amen = result.get("total_amenities", 0)
    gs = result.get("green_space_percentage")

    if gs is not None:
        c1, c2, c3 = st.columns(3)
    else:
        c1, c2 = st.columns(2)

    c1.metric("Walk Score", f"{walk:.0f}/100")
    c2.metric("Amenities Nearby", amen)
    if gs is not None:
        c3.metric("Green Space", f"{gs:.1f}%")

    if walk >= 70:
        st.success("Very Walkable — most errands can be done on foot.")
    elif walk >= 50:
        st.info("Somewhat Walkable — some amenities reachable on foot.")
    elif walk >= 25:
        st.warning("Car-Dependent — most errands require a car.")
    else:
        st.error("Very Car-Dependent.")

    amenities = result.get("amenities", {})
    if amenities and any(len(v) > 0 for v in amenities.values()):
        with st.expander(f"Nearby Places ({amen} found)", expanded=True):
            for atype, items in amenities.items():
                if not items:
                    continue
                label = atype.replace("_", " ").title()
                st.markdown(f"{label} — {len(items)} found")
                for it in items[:4]:
                    name = it.get("name", "Unknown")
                    dist = it.get("distance_km", 0)
                    st.caption(f"• {name} ({dist:.2f} km away)")
    else:
        coords = result.get("coordinates")
        if not amen:
            if coords:
                st.warning(
                    "0 amenities found. Try increasing the search radius or using a broader area name."
                )
            else:
                st.error(
                    "Could not geocode this address. Try a more specific address including city and state."
                )


def _poll_task(task_id: str, max_wait: int = 420) -> Optional[dict]:
    bar = st.progress(0)
    t0 = time.time()

    while time.time() - t0 < max_wait:
        try:
            r = requests.get(f"{BACKEND_URL}/api/tasks/{task_id}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                status = data.get("status", "")
                progress = min(int(data.get("progress", 0)), 100)

                bar.progress(progress)

                if status == "completed":
                    bar.empty()
                    inner = data.get("result")
                    return inner if (inner and isinstance(inner, dict)) else data

                if status == "failed":
                    bar.empty()
                    st.error("Analysis failed. Please try again.")
                    return None
        except Exception:
            pass
        time.sleep(3)

    bar.empty()
    return None