import json
import multiprocessing
import time

import pytest
import uvicorn
from playwright.sync_api import Page, expect

from app.main import APP_ROOT, SAMPLE_DIR, app

PORT = 8003
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


def _app_files():
    return {
        (p, p.stat().st_mtime)
        for p in APP_ROOT.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


def test_upload_renders_viewers_without_storing_anything(page: Page, tmp_path):
    sample = sorted(SAMPLE_DIR.glob("*.json"))[0]
    txt_file = tmp_path / "my_app.txt"
    txt_file.write_text(json.loads(sample.read_text(encoding="utf-8"))["raw_txt"], encoding="utf-8")
    before = _app_files()

    page.goto(BASE_URL)
    page.locator("#sample-list .project-item").first.wait_for()
    page.set_input_files("#txt-file", str(txt_file))
    page.locator("#ready-state").wait_for()
    expect(page.locator("#current-file-name")).to_have_text("my_app")
    expect(page.locator("#txt-panel")).to_be_visible()

    # Graph viewer reads the upload from this tab's sessionStorage
    page.click("#open-graph-btn")
    page.locator("#graph g.node").first.wait_for()
    assert page.locator("#graph g.node").count() > 100
    expect(page.locator("#file-name")).to_have_text("my_app")
    expect(page.locator("#no-data")).to_be_hidden()

    # Coming back restores the upload, and filters are applied server-side on the fly
    page.go_back()
    page.locator("#ready-state").wait_for()
    page.fill("#filter-text", "okhttp")
    page.click("#open-tree-btn")
    page.locator("#graph-container svg g.node").first.wait_for()
    expect(page.locator("#file-name")).to_have_text("my_app")
    expect(page.locator("#no-data")).to_be_hidden()

    assert _app_files() == before


def test_viewer_without_upload_shows_hint(page: Page):
    page.goto(f"{BASE_URL}/viz/graph_viewer.html?source=upload")
    expect(page.locator("#no-data")).to_be_visible()
    expect(page.locator("#no-data")).to_contain_text("no longer available")
