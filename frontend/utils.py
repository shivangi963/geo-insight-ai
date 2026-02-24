import streamlit as st
import time
from datetime import datetime
from typing import Optional, Dict, Any
from config import TASK_POLL_INTERVAL, TASK_MAX_WAIT, TASK_PROGRESS_BAR_ENABLED

def format_currency(amount: float, decimals: int = 0) -> str:
    if amount is None:
        return "0"
    return f"{amount:,.{decimals}f}"

def format_number(num: float, decimals: int = 0) -> str:
    return f"{num:,.{decimals}f}"

def format_percentage(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"

def format_date(date_str: str) -> str:
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return date_str

def truncate_text(text: str, max_length: int = 100) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def calculate_price_per_sqft(price: float, square_feet: int) -> float:
    if square_feet > 0:
        return price / square_feet
    return 0

def get_walkability_label(score: float) -> tuple[str, str]:
    if score >= 90:
        return ("Walker's Paradise", "walk-score-excellent")
    elif score >= 70:
        return ("Very Walkable", "walk-score-excellent")
    elif score >= 50:
        return ("Somewhat Walkable", "walk-score-good")
    elif score >= 25:
        return ("Car-Dependent", "walk-score-moderate")
    else:
        return ("Very Car-Dependent", "walk-score-poor")

def get_roi_label(roi: float) -> tuple[str, str]:
    if roi > 12:
        return ("Excellent")
    elif roi > 8:
        return ("Good")
    elif roi > 5:
        return ("Fair")
    else:
        return ("Poor")

def validate_file_size(file, max_size_mb: int = 10) -> bool:
    if file.size > max_size_mb * 1024 * 1024:
        st.error(f"File too large. Max size: {max_size_mb} MB")
        return False
    return True

def show_loading_spinner(message: str = "Loading..."):
    return st.spinner(message)

def _clean_message(raw: Any) -> str:
    if raw is None or raw == "":
        return "Processing..."
    if isinstance(raw, dict):
        return (
            raw.get("status")
            or raw.get("message")
            or raw.get("detail")
            or "Processing..."
        )
    msg = str(raw).strip()
    if msg.startswith("{") and msg.endswith("}"):
        try:
            import ast
            parsed = ast.literal_eval(msg)
            if isinstance(parsed, dict):
                return parsed.get("status") or parsed.get("message") or "Processing..."
        except Exception:
            pass
        return "Processing..."
    return msg or "Processing..."

def poll_task_status(task_id: str,
                     max_wait: int = TASK_MAX_WAIT,
                     show_progress: bool = TASK_PROGRESS_BAR_ENABLED) -> Optional[Dict]:

    import requests
    from api_client import api

    progress_bar = st.progress(0) if show_progress else None
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(
                f"{api.base_url}/api/tasks/{task_id}",
                timeout=5,
            )

            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                progress = data.get("progress", 0)

                if progress_bar:
                    progress_bar.progress(min(progress / 100, 1.0))

                if status == "completed":
                    if progress_bar:
                        progress_bar.progress(1.0)
                        time.sleep(0.3)
                        progress_bar.empty()
                    return data.get("result") or {}

                if status == "failed":
                    if progress_bar:
                        progress_bar.empty()
                    error = data.get("error", "Unknown error")
                    st.error(f"Analysis failed: {error}")
                    return None

        except Exception:
            pass

        time.sleep(2)

    if progress_bar:
        progress_bar.empty()

    return None

def display_metric_card(label: str, value: str, delta: str = None, help_text: str = None):
    if delta:
        st.metric(label, value, delta=delta, help=help_text)
    else:
        st.metric(label, value, help=help_text)

def create_download_button(data: str, filename: str, label: str = "Download"):
    st.download_button(label=label, data=data, file_name=filename, mime="text/plain")

def show_success_message(message: str):
    st.success(f"{message}")

def show_error_message(message: str):
    st.error(f" {message}")

def show_info_message(message: str):
    st.info(f" {message}")

def show_warning_message(message: str):
    st.warning(f" {message}")

def init_session_state(key: str, default_value: Any):
    if key not in st.session_state:
        st.session_state[key] = default_value

def get_session_state(key: str, default: Any = None) -> Any:
    return st.session_state.get(key, default)

def set_session_state(key: str, value: Any):
    st.session_state[key] = value

def clear_session_state(*keys: str):
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]

def format_analysis_summary(analysis: Dict) -> str:
    lines = []
    lines.append(f"**Address:** {analysis.get('address', 'N/A')}")
    lines.append(f"**Walk Score:** {analysis.get('walk_score', 'N/A')}/100")
    lines.append(f"**Total Amenities:** {analysis.get('total_amenities', 0)}")
    lines.append(f"**Status:** {analysis.get('status', 'unknown').title()}")
    created = analysis.get("created_at")
    if created:
        lines.append(f"**Created:** {format_date(created)}")
    return "\n".join(lines)

def get_amenity_display_name(amenity_type: str) -> str:
    name = amenity_type.replace("_", " ").title()
    return f"{name}"