import json

from playwright.sync_api import Page, expect

from .conftest import APP_ROOT, SAMPLE_DIR

BASE_URL = "http://127.0.0.1:8003"


def _app_files():
    return {
        (p, p.stat().st_mtime)
        for p in APP_ROOT.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


def _write_txt(tmp_path):
    sample = sorted(SAMPLE_DIR.glob("*.json"))[0]
    txt_file = tmp_path / "my_app.txt"
    txt_file.write_text(json.loads(sample.read_text(encoding="utf-8"))["raw_txt"], encoding="utf-8")
    return txt_file


def test_upload_renders_viewers_without_storing_anything(page: Page, tmp_path):
    txt_file = _write_txt(tmp_path)
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

    # Coming back restores the upload for the tree viewer too
    page.go_back()
    page.locator("#ready-state").wait_for()
    page.click("#open-tree-btn")
    page.locator("#graph-container svg g.node").first.wait_for()
    expect(page.locator("#file-name")).to_have_text("my_app")
    expect(page.locator("#no-data")).to_be_hidden()

    assert _app_files() == before


def test_clear_result(page: Page, tmp_path):
    page.goto(BASE_URL)
    project_btn = page.locator("#sample-list .project-item").first
    project_btn.wait_for()

    # Clearing an upload asks for confirmation first
    page.set_input_files("#txt-file", str(_write_txt(tmp_path)))
    page.locator("#ready-state").wait_for()
    page.click("#clear-btn")
    expect(page.locator("#clear-dialog")).to_be_visible()
    page.click("#clear-dialog button[value=cancel]")
    expect(page.locator("#ready-state")).to_be_visible()
    assert page.evaluate("sessionStorage.getItem('gdv:upload')") is not None

    page.click("#clear-btn")
    page.click("#clear-dialog button[value=confirm]")
    expect(page.locator("#welcome-state")).to_be_visible()
    expect(page.locator("#ready-state")).to_be_hidden()
    assert page.evaluate("sessionStorage.getItem('gdv:upload')") is None
    assert page.evaluate("sessionStorage.getItem('gdv:current')") is None

    # Clearing a pre-compiled project needs no confirmation
    project_btn.click()
    page.locator("#ready-state").wait_for()
    page.click("#clear-btn")
    expect(page.locator("#clear-dialog")).to_be_hidden()
    expect(page.locator("#welcome-state")).to_be_visible()
    expect(project_btn).to_have_attribute("aria-pressed", "false")


def test_viewer_without_upload_shows_hint(page: Page):
    page.goto(f"{BASE_URL}/viz/graph_viewer.html?source=upload")
    expect(page.locator("#no-data")).to_be_visible()
    expect(page.locator("#no-data")).to_contain_text("no longer available")


def test_gradle_graph_upload_opens_both_viewers_and_downloads_yaml(page: Page):
    data = {
        "schemaVersion": 1,
        "projectPath": ":app",
        "configuration": "debugRuntimeClasspath",
        "rootId": "app",
        "nodes": [
            {"id": "app", "module": "project :app", "version": "", "resolution": "", "full": "project :app"},
            {"id": "lib", "module": "org.example:lib", "version": "2", "resolution": "", "full": "org.example:lib:2"},
        ],
        "edges": [{"source": "app", "target": "lib", "requested": "org.example:lib:1", "constraint": False}],
    }
    page.goto(BASE_URL)
    page.set_input_files("#txt-file", {
        "name": "gradle-graph.json",
        "mimeType": "application/json",
        "buffer": json.dumps(data).encode(),
    })
    expect(page.locator("#current-file-name")).to_have_text("gradle-graph")
    expect(page.locator("#txt-panel")).to_be_hidden()

    page.get_by_text("Dependency JSON", exact=True).click()
    with page.expect_download() as download:
        page.click("#enlist-btn")
    assert '"org.example:lib:2"' in download.value.path().read_text()

    page.click("#open-graph-btn")
    expect(page.locator("#graph g.node")).to_have_count(2)
    expect(page.locator("#no-data")).to_be_hidden()
    page.go_back()
    page.click("#open-tree-btn")
    expect(page.locator("#graph-container svg g.node")).to_have_count(2)
    expect(page.locator("#no-data")).to_be_hidden()
