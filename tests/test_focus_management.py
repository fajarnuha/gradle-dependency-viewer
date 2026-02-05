import pytest
import multiprocessing
import time
import uvicorn
import os
from playwright.sync_api import Page, expect
from app.main import app

# Use a different port
PORT = 8005
BASE_URL = f"http://localhost:{PORT}"

def run_server():
    os.environ["DEPS_HISTORY"] = "1"
    uvicorn.run(app, host="127.0.0.1", port=PORT)

@pytest.fixture(scope="module", autouse=True)
def server():
    proc = multiprocessing.Process(target=run_server, daemon=True)
    proc.start()
    time.sleep(3)
    yield
    proc.terminate()

def test_focus_restoration(page: Page):
    try:
        # Navigate to the app
        page.goto(BASE_URL)

        # 1. Populate list using sample
        print("Clicking sample...")
        sample_chip = page.locator("button.sample-chip", has_text="homeassistant").first
        expect(sample_chip).to_be_visible()
        sample_chip.click()

        # Wait for processing to complete and file to be selected
        print("Waiting for processing...")
        expect(page.locator("#current-file-name")).to_contain_text("homeassistant", timeout=10000)

        # Verify item is in the history list
        list_item = page.locator("#file-list li").first
        expect(list_item).to_be_visible()

        # 2. Trigger Delete
        print("Triggering delete...")
        delete_btn = list_item.locator(".delete-btn").first

        delete_btn.focus()
        page.keyboard.press("Enter")

        # 3. Confirm Delete Dialog
        print("Confirming delete...")
        dialog = page.locator("#delete-confirm-dialog")
        expect(dialog).to_be_visible()

        confirm_btn = page.locator("#confirm-delete-btn")
        confirm_btn.click()

        # 4. Wait for dialog to close
        expect(dialog).not_to_be_visible()

        # Wait a bit for the focus restoration logic
        time.sleep(1)

        focused_tag = page.evaluate("document.activeElement.tagName")
        focused_id = page.evaluate("document.activeElement.id")
        focused_class = page.evaluate("document.activeElement.className")

        print(f"Focused Element: {focused_tag}#{focused_id}.{focused_class}")

        if focused_tag == "BODY":
            pytest.fail("Focus lost to BODY")
        else:
            print(f"SUCCESS: Focus restored to {focused_tag}#{focused_id}")

    except Exception as e:
        print(f"Error: {e}")
        raise
