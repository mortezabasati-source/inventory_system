"""Browser-side inactivity guard; no polling or extra server reruns."""

import os
from pathlib import Path

import streamlit as st
from streamlit import components as st_components
from streamlit.components.v1 import html as st_html


def idle_timeout_minutes() -> int:
    """Zero disables the guard. Invalid deployment values use 30 minutes."""
    try:
        return max(0, int(os.getenv("IDLE_TIMEOUT_MINUTES", "30")))
    except ValueError:
        return 30


_component_v2 = getattr(st_components, "v2", None)
if _component_v2 is not None:
    _IDLE_GUARD = _component_v2.component(
        "smartlager_idle_guard",
        html="<small role='status' aria-live='polite'></small>",
        js=Path(__file__).with_name("idle_session.js").read_text(encoding="utf-8"),
    )
else:
    def _idle_guard_component(*, key: str | None = None, data: dict | None = None) -> None:
        """Fallback for Streamlit versions that do not expose components.v2."""
        payload = data or {}
        timeout_ms = int(payload.get("timeoutMs", 0))
        has_pending = bool(payload.get("hasPendingChanges", False))
        st_html(
            f"""
            <div id="smartlager_idle_guard"
                 data-timeout-ms="{timeout_ms}"
                 data-has-pending="{str(has_pending).lower()}"></div>
            <script>
            {Path(__file__).with_name("idle_session.js").read_text(encoding="utf-8")}
            </script>
            """,
            height=0,
            scrolling=False,
        )

    _IDLE_GUARD = _idle_guard_component


def render_idle_guard() -> None:
    minutes = idle_timeout_minutes()
    if not minutes:
        return

    pending = any(st.session_state.get(key) for key in (
        "inbound_basket", "production_basket", "insats_basket",
        "stickprov_basket", "bom_components",
        "new_product_id", "new_product_name", "new_product_price",
    ))
    _IDLE_GUARD(
        key="idle_session_guard",
        data={"timeoutMs": minutes * 60_000, "hasPendingChanges": pending},
    )
