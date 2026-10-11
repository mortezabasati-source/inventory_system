"""Streamlit UI checks with fake data; no credentials or network calls."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from test_analytics import snapshot

CHAT_SCRIPT = "from modules.analytics_chat import render_chat\nrender_chat()"


class ChatUITests(unittest.TestCase):
    def test_missing_configuration_disables_input(self):
        with patch("modules.analytics_chat.configuration", side_effect=ValueError("Konfigurera AI-analys")):
            app = AppTest.from_string(CHAT_SCRIPT).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.chat_input[0].disabled)
        self.assertIn("Konfigurera", app.info[0].value)

    def test_history_isolation_clear_refresh_and_evidence(self):
        result = {"answer": "Tre producerade.", "evidence": [{"tool": "production", "sources": ["Production_Log"], "fetched_at": "2026-10-11", "rows": [{"Quantity_Produced": 3}], "warnings": []}]}
        with patch("modules.analytics_chat.configuration", return_value=("secret", "model", "sheet", {"client_email": "viewer"})), \
             patch("modules.analytics_chat.load_snapshot", return_value=snapshot()) as loader, \
             patch("modules.analytics_chat.answer_question", return_value=result):
            first = AppTest.from_string(CHAT_SCRIPT).run()
            first.chat_input[0].set_value("Visa produktion").run()
            self.assertFalse(first.exception)
            self.assertEqual(len(first.session_state["analytics_chat_history"]), 1)
            self.assertEqual(len(first.dataframe), 1)
            second = AppTest.from_string(CHAT_SCRIPT).run()
            self.assertEqual(second.session_state["analytics_chat_history"], [])
            first.button(key="analytics_refresh").click().run()
            loader.clear.assert_called_once()
            self.assertEqual(len(first.session_state["analytics_chat_history"]), 1)
            first.button(key="analytics_clear").click().run()
            self.assertFalse(first.exception)
            self.assertEqual(first.session_state["analytics_chat_history"], [])

    def test_unexpected_errors_have_safe_diagnostics(self):
        with patch("modules.analytics_chat.configuration", return_value=("sensitive-token-xyz", "model", "sheet", {})), \
             patch("modules.analytics_chat.load_snapshot", return_value=snapshot()), \
             patch("modules.analytics_chat.answer_question", side_effect=AttributeError("sensitive-token-xyz")), \
             self.assertLogs("modules.analytics_chat", level="ERROR") as logs:
            app = AppTest.from_string(CHAT_SCRIPT).run()
            app.chat_input[0].set_value("Visa produktion").run()
        self.assertFalse(app.exception)
        self.assertIn("AttributeError", app.error[0].value)
        self.assertIn("Referens:", app.error[0].value)
        self.assertNotIn("sensitive-token-xyz", app.error[0].value)
        self.assertIn("stage=run_analysis", " ".join(logs.output))
        self.assertNotIn("sensitive-token-xyz", " ".join(logs.output))
        self.assertEqual(app.session_state["analytics_chat_history"], [])

    @patch.dict(os.environ, {"IDLE_TIMEOUT_MINUTES": "0"})
    def test_existing_desktop_pages_and_mobile(self):
        fixture = Path(__file__).with_name("idle_browser_fixture.py")
        app = AppTest.from_file(str(fixture)).run(timeout=20)
        self.assertFalse(app.exception)
        self.assertIn("AI-analys", app.sidebar.radio[0].options)
        app.sidebar.radio[0].set_value("💰 Marginaler").run()
        self.assertFalse(app.exception)
        app.sidebar.radio[0].set_value("📥 Registrera Inleverans").run()
        self.assertFalse(app.exception)
        mobile = AppTest.from_file(str(fixture))
        mobile.query_params["mobile"] = "true"
        mobile.run(timeout=20)
        self.assertFalse(mobile.exception)
        self.assertEqual(len(mobile.sidebar.radio), 0)
        self.assertIn("Inleverans", mobile.header[0].value)


if __name__ == "__main__":
    unittest.main()
