"""Desktop-only chat UI. History belongs exclusively to Streamlit session_state."""
import json
import logging
import traceback
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

from modules.analytics_agent import answer_question
from modules.analytics_reader import configuration, load_snapshot
from modules.analytics_tools import AnalysisError, AnalysisTools

LOGGER = logging.getLogger(__name__)


def report_unexpected_error(exc, stage, message):
    """Log code locations only: never exception messages, locals, or cell data."""
    reference = uuid4().hex[:12]
    locations = [(Path(frame.filename).name, frame.lineno, frame.name)
                 for frame in traceback.extract_tb(exc.__traceback__)]
    LOGGER.error("analytics_failure reference=%s stage=%s type=%s locations=%s",
                 reference, stage, type(exc).__name__, locations)
    st.error(f"{message} Feltyp: {type(exc).__name__}. Referens: {reference}.")


def render_evidence(evidence):
    for entry in evidence:
        with st.expander(f"Underlag: {entry['tool']}"):
            st.caption("Källor: " + ", ".join(entry["sources"]) + " · Hämtat (UTC): " + entry["fetched_at"])
            for warning in entry.get("warnings", []):
                st.warning(warning)
            if entry["rows"]:
                st.dataframe(pd.DataFrame(entry["rows"]), width="stretch", hide_index=True)


def render_chat():
    st.header("AI-analys")
    st.caption("Analysera data med Gemini. Assistenten har endast läsbehörighet. Frågor och analysunderlag skickas till Google.")
    history = st.session_state.setdefault("analytics_chat_history", [])
    try:
        api_key, model, sheet_id, credentials = configuration()
    except ValueError as exc:
        st.info(str(exc))
        st.chat_input("Konfigurera AI-analys för att börja", disabled=True)
        return

    left, right = st.columns(2)
    if left.button("Rensa konversation", key="analytics_clear"):
        st.session_state["analytics_chat_history"] = []
        st.rerun()
    if right.button("Hämta senaste data", key="analytics_refresh"):
        load_snapshot.clear(sheet_id, json.dumps(credentials, sort_keys=True))
        st.success("Nästa fråga använder nyhämtade data. Tidigare svar behåller sitt ursprungliga underlag.")

    for turn in history:
        with st.chat_message("user"):
            st.write(turn["question"])
        with st.chat_message("assistant"):
            st.write(turn["answer"])
            render_evidence(turn.get("evidence", []))

    suggested = None
    if not history:
        st.write("Exempel på frågor")
        for index, question in enumerate(("Vilka artiklar har negativt lagersaldo?", "Visa produktionen denna månad.", "Vilka produkter har lägst kalkylerad marginal?")):
            if st.button(question, key=f"analytics_example_{index}"):
                suggested = question
    prompt = st.chat_input("Fråga om lager och produktion", max_chars=4000) or suggested
    if not prompt:
        return
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Analyserar data …"):
            try:
                snapshot = load_snapshot(sheet_id, json.dumps(credentials, sort_keys=True))
            except Exception as exc:
                report_unexpected_error(exc, "read_snapshot", "Analysdata kunde inte läsas. Kontrollera analyskontots Viewer-behörighet, arkets ID och nätverket.")
                return
            try:
                result = answer_question(prompt, history, AnalysisTools(snapshot), api_key, model)
            except AnalysisError as exc:
                st.error(str(exc))
                return
            except Exception as exc:
                report_unexpected_error(exc, "run_analysis", "Analysen kunde inte slutföras. Kontrollera datakolumner och AI-konfiguration.")
                return
        st.write(result["answer"])
        render_evidence(result["evidence"])
    history.append({"question": prompt, **result})
    del history[:-10]
