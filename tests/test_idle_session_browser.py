"""Browser regression checks against idle_browser_fixture.py on localhost:8517.

Install Playwright separately from production dependencies. Start the fixture:
APP_SECRET_KEY=test-key IDLE_TEST_DISCONNECT_MARKER=/tmp/smartlager-idle-disconnects \
    streamlit run tests/idle_browser_fixture.py --server.port 8517
Then run with the same IDLE_TEST_DISCONNECT_MARKER:
python tests/test_idle_session_browser.py
"""

import re
import os
import time
from pathlib import Path

BASE = "http://localhost:8517/"


def expire(page):
    page.evaluate("""() => {
        window.__smartlagerIdleState.lastActivity = Date.now() - 31 * 60000;
        document.dispatchEvent(new Event('visibilitychange'));
    }""")


def mounted(page):
    page.wait_for_function("Boolean(window.__smartlagerIdleState)")


def main():
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        errors = []
        marker = Path(os.getenv("IDLE_TEST_DISCONNECT_MARKER", "/tmp/smartlager-idle-disconnects"))
        previous_disconnects = marker.read_text() if marker.exists() else ""
        page.on("pageerror", lambda error: errors.append(str(error)))

        page.goto(BASE + "?mobile=true")
        mounted(page)
        expire(page)
        page.wait_for_url(re.compile(r"^blob:"))
        expect(page.get_by_role("heading", name="SmartLager är pausad")).to_be_visible()
        expect(page.get_by_role("link", name="Anslut igen")).to_have_attribute("href", BASE + "?mobile=true")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if marker.exists() and marker.read_text() != previous_disconnects:
                break
            page.wait_for_timeout(100)
        assert marker.exists() and marker.read_text() != previous_disconnects, "Server must observe WebSocket disconnect"
        page.get_by_role("link", name="Anslut igen").click()
        mounted(page)
        assert page.url == BASE + "?mobile=true"
        print("PASS: real disconnect, WebSocket closure, reconnect, mobile query preserved")

        # Unsaved form edits are protected before they reach Python.
        quantity = page.get_by_role("spinbutton", name="Antal förpackningar")
        quantity.fill("3")
        expire(page)
        assert not page.url.startswith("blob:")
        assert "pausad" in page.locator("[role=status]").last.inner_text()
        page.get_by_role("button", name="➕ Lägg till", exact=True).click()
        expect(page.get_by_role("heading", name="Poster att spara")).to_be_visible()
        expire(page)
        assert not page.url.startswith("blob:"), "Pending basket must prevent disconnect"
        print("PASS: unsubmitted form and basket protected")

        page.get_by_role("button", name="🗑️ Töm listan", exact=True).click()
        expect(page.get_by_role("heading", name="Poster att spara")).to_have_count(0)
        page.wait_for_timeout(500)
        expire(page)
        page.wait_for_url(re.compile(r"^blob:"))
        print("PASS: clearing basket re-enables timeout")

        # Search filters are not unsaved business data and must not block timeout.
        page.goto(BASE)
        mounted(page)
        page.get_by_role("textbox", name="🔍 Sök efter artikelnamn eller SI-kod:").fill("Flour")
        page.get_by_role("textbox", name="🔍 Sök efter artikelnamn eller SI-kod:").press("Enter")
        page.wait_for_timeout(500)
        expire(page)
        page.wait_for_url(re.compile(r"^blob:"))
        print("PASS: search does not prevent idle disconnect")
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    main()
