
import pytest
from playwright.sync_api import Page, expect
import multiprocessing
import time
import uvicorn
from app.main import app

PORT = 8002
BASE_URL = f"http://localhost:{PORT}"

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=PORT)

@pytest.fixture(scope="module", autouse=True)
def server():
    proc = multiprocessing.Process(target=run_server, daemon=True)
    proc.start()
    time.sleep(3)
    yield
    proc.terminate()

def test_project_list_accessibility(page: Page):
    page.goto(BASE_URL)

    # Pre-compiled open source projects are listed as buttons
    project_btn = page.locator("#sample-list .project-item").first
    project_btn.wait_for()
    expect(project_btn).to_be_visible()

    aria_label = project_btn.get_attribute("aria-label")
    assert aria_label is not None and "Open" in aria_label
    expect(project_btn).to_have_attribute("aria-pressed", "false")

    # Selecting a project marks it as pressed
    project_btn.click()
    page.locator("#ready-state").wait_for()
    expect(project_btn).to_have_attribute("aria-pressed", "true")

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
    page.locator("#sample-list button").first.click()
    page.locator("#ready-state").wait_for()
    enlist_btn = page.locator("#enlist-btn")
    expect(enlist_btn).to_have_attribute("aria-label", "Enlist Dependencies")
