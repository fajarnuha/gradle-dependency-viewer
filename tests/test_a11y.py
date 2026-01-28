
import pytest
from playwright.sync_api import Page, expect
import multiprocessing
import time
import uvicorn
import os
from app.main import app

PORT = 8002
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

def test_file_list_accessibility(page: Page):
    page.goto(BASE_URL)

    # Process a sample to populate history
    # Wait for sample list to be populated
    page.locator("#sample-list button").first.wait_for()
    page.locator("#sample-list button").first.click()

    # Wait for the file to be processed and appear in the list
    # The list is re-rendered after processing
    page.wait_for_selector(".file-item")

    # Check if we have buttons in the file list
    # The fix will change the structure to include a button with class .file-select-btn
    file_select_btn = page.locator(".file-item button.file-select-btn").first

    # This assertion ensures the button exists and is visible
    expect(file_select_btn).to_be_visible()

    # Verify aria-label on the select button
    aria_label_select = file_select_btn.get_attribute("aria-label")
    assert aria_label_select is not None and "Select" in aria_label_select

    # Check delete button has aria-label
    delete_btn = page.locator(".file-item .delete-btn").first
    expect(delete_btn).to_be_visible()
    aria_label_delete = delete_btn.get_attribute("aria-label")
    assert aria_label_delete is not None and "Delete" in aria_label_delete

def test_icon_buttons_accessibility(page: Page):
    page.goto(BASE_URL)

    # GitHub link
    github_link = page.locator(".github-link")
    expect(github_link).to_have_attribute("aria-label", "View on GitHub")

    # Copy hint button
    # Wait for welcome state
    page.locator("#welcome-state").wait_for()
    copy_btn = page.locator("#copy-hint-btn")
    expect(copy_btn).to_have_attribute("aria-label", "Copy command")

    # Enlist button (visible in ready state)
    # reusing the state from previous test or click sample again
    page.locator("#sample-list button").first.click()
    page.locator("#ready-state").wait_for()
    enlist_btn = page.locator("#enlist-btn")
    expect(enlist_btn).to_have_attribute("aria-label", "Enlist Dependencies")
