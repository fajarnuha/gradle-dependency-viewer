
import pytest
import multiprocessing
import time
import uvicorn
import os
from playwright.sync_api import Page, expect
from app.main import app

PORT = 8003
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

def test_delete_functionality(page: Page):
    page.goto(BASE_URL)

    # 1. Populate history by processing a sample
    # Wait for sample list
    page.locator("#sample-list button").first.wait_for()
    page.locator("#sample-list button").first.click()

    # Wait for processing to complete and ready state to appear
    page.locator("#ready-state").wait_for()

    # Wait for the file to appear in the history list
    # The list re-renders.
    file_item = page.locator(".file-item").first
    file_item.wait_for()

    # Get the filename to verify deletion later
    filename = file_item.locator(".file-name").text_content().strip()

    # 2. Check delete button attributes (Accessibility)
    delete_btn = file_item.locator(".delete-btn")
    expect(delete_btn).to_be_visible()

    # It should have a title
    expect(delete_btn).to_have_attribute("title", "Delete file")

    # It should have aria-label
    aria_label = delete_btn.get_attribute("aria-label")
    assert aria_label and "Delete" in aria_label

    # 3. Click delete
    delete_btn.click()

    # 4. Verify Dialog
    dialog = page.locator("#delete-confirm-dialog")
    expect(dialog).to_be_visible()

    # Verify dialog content
    expect(dialog.locator("h2")).to_have_text("Delete File?")
    expect(dialog.locator("#delete-filename")).to_have_text(filename)

    # 5. Confirm Delete
    confirm_btn = dialog.locator("#confirm-delete-btn")
    confirm_btn.click()

    # 6. Verify file is gone
    # Wait for list to update
    # If it was the only file, .file-item might be gone entirely, replaced by .empty-list

    # We'll wait a moment for the fetch and render
    time.sleep(1)

    # Check if the specific file is gone
    # We look for any element with text content equal to filename
    # But easier to look at .file-name elements

    # Reload page or wait? The app.js updates the list in place without reload.

    current_files = page.locator(".file-name").all_text_contents()
    current_files = [f.strip() for f in current_files]

    assert filename not in current_files
