
import pytest
import multiprocessing
import time
import uvicorn
import os
from pathlib import Path
from playwright.sync_api import Page, expect
from app.main import app

# Use a different port to avoid conflicts
PORT = 8001
BASE_URL = f"http://localhost:{PORT}"

def run_server():
    # Disable history for consistent testing
    os.environ["DEPS_HISTORY"] = "0"
    uvicorn.run(app, host="127.0.0.1", port=PORT)

@pytest.fixture(scope="module", autouse=True)
def server():
    proc = multiprocessing.Process(target=run_server, daemon=True)
    proc.start()
    # Give the server a moment to start
    time.sleep(3)
    yield
    proc.terminate()

def test_generate_screenshots(page: Page):
    # Ensure screenshot directory exists
    screenshot_dir = Path("screenshot")
    screenshot_dir.mkdir(exist_ok=True)
    
    # 1. Open Homepage
    page.goto(BASE_URL)
    
    # Wait for samples to be visible
    # We added #sample-list in the template and .sample-chip logic in JS
    sample_chip = page.locator(".sample-chip").first
    sample_chip.wait_for()
    
    # Click the first sample
    sample_chip.click()
    
    # Wait for the "Ready" state which contains the viewer buttons
    page.locator("#open-graph-btn").wait_for()
    
    # 2. Open Graph Viewer
    page.click("#open-graph-btn")
    
    # Wait for graph to load (check for SVG or specific element)
    # The graph viewer has #graph element
    page.locator("#graph").wait_for()
    # Wait a bit for D3 force simulation to settle slightly
    page.wait_for_timeout(2000)
    
    page.screenshot(path=str(screenshot_dir / "graph_viewer.png"))
    
    # Go back to home
    page.go_back()
    page.locator("#open-tree-btn").wait_for()
    
    # 3. Open Tree Viewer
    page.click("#open-tree-btn")
    
    # Wait for tree to load (check for SVG)
    page.locator("#graph-container svg").wait_for()
    page.wait_for_timeout(1000)
    
    page.screenshot(path=str(screenshot_dir / "tree_viewer.png"))
