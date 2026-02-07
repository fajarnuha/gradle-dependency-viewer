
import pytest
import multiprocessing
import time
import uvicorn
import os
import shutil
import json
from pathlib import Path
from playwright.sync_api import Page, expect
from app.main import app

# Use a different port to avoid conflicts
PORT = 8003
BASE_URL = f"http://localhost:{PORT}"
DATA_DIR = Path("app/static/data")
TEST_FILE = "test_history_ux.json"

def run_server():
    # Enable history for testing
    os.environ["DEPS_HISTORY"] = "1"
    uvicorn.run(app, host="127.0.0.1", port=PORT)

@pytest.fixture(scope="module", autouse=True)
def server():
    proc = multiprocessing.Process(target=run_server, daemon=True)
    proc.start()
    # Give the server a moment to start
    time.sleep(3)
    yield
    proc.terminate()

@pytest.fixture
def setup_data():
    # Create a dummy JSON file
    data_path = DATA_DIR / TEST_FILE
    data_content = {
        "dependencies": {},
        "raw_txt": "implementation 'com.example:lib:1.0.0'"
    }
    with open(data_path, "w") as f:
        json.dump(data_content, f)

    yield

    # Cleanup
    if data_path.exists():
        data_path.unlink()

def test_history_delete(page: Page, setup_data):
    # 1. Open Homepage
    page.goto(BASE_URL)

    # Verify the file appears in the list
    file_item = page.locator(f".file-item:has-text('{TEST_FILE}')")
    expect(file_item).to_be_visible()

    # 2. Click Delete Button
    # Find the delete button within the file item
    delete_btn = file_item.locator(".delete-btn")
    delete_btn.click()

    # 3. Verify Confirmation Dialog
    dialog = page.locator("#delete-confirm-dialog")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text(f"Delete File?")
    expect(dialog).to_contain_text(TEST_FILE)

    # 4. Confirm Delete
    confirm_btn = dialog.locator("#confirm-delete-btn")
    confirm_btn.click()

    # 5. Verify Removal
    # Wait for the item to disappear
    expect(file_item).not_to_be_visible()

    # Verify file is gone from filesystem
    # Give the server a moment to process the delete
    time.sleep(1)
    data_path = DATA_DIR / TEST_FILE
    assert not data_path.exists()
