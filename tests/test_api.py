import json
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import APP_ROOT, SAMPLE_DIR, app

client = TestClient(app)

SAMPLE = sorted(SAMPLE_DIR.glob("*.json"))[0]


def _sample_data():
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    data.pop("raw_txt", None)
    return data


def _app_files():
    return {
        (p, p.stat().st_mtime)
        for p in APP_ROOT.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


def test_read_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Pre-Compiled Open Source Projects" in response.text


def test_list_samples():
    response = client.get("/api/samples")
    assert response.status_code == 200
    samples = response.json()
    assert {s["filename"] for s in samples} == {p.name for p in SAMPLE_DIR.glob("*.json")}
    assert all(s["entries"] > 0 and s["modules"] > 0 for s in samples)


def test_history_endpoints_are_gone():
    assert client.get("/api/files").status_code in (404, 405)
    assert client.delete(f"/api/files/{SAMPLE.name}").status_code in (404, 405)
    assert client.post(f"/api/samples/{SAMPLE.name}/process").status_code in (404, 405)


def test_upload_is_not_persisted():
    raw_txt = json.loads(SAMPLE.read_text(encoding="utf-8"))["raw_txt"]
    before = _app_files()

    response = client.post(
        "/api/upload", files={"file": ("my_app.txt", raw_txt.encode("utf-8"), "text/plain")}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "my_app"
    assert "raw_txt" not in payload["json"]
    assert _app_files() == before


def test_graph_api_converts_and_filters():
    graph = client.post("/api/graph", json={"data": _sample_data()}).json()
    assert len(graph["nodes"]) > 100
    assert any(n["id"] == "root:" for n in graph["nodes"])

    filtered = client.post("/api/graph", json={"data": _sample_data(), "filter": "okhttp"}).json()
    assert 0 < len(filtered["nodes"]) < len(graph["nodes"])

    nothing = client.post("/api/graph", json={"data": _sample_data(), "filter": "no-such-dependency"}).json()
    assert nothing["nodes"] == []


def test_tree_api_filters():
    tree = client.post("/api/tree", json={"data": _sample_data(), "project_only": True}).json()
    root_key = next(k for k, v in tree.items() if isinstance(v, list))
    assert tree[root_key]


def test_enlist_api():
    response = client.post("/api/enlist", json={"data": _sample_data()})
    assert response.status_code == 200
    assert "dependencies:" in response.text


def test_viewers_render_samples_only():
    graph_page = client.get(f"/viz/graph_viewer.html?sample={SAMPLE.name}")
    assert graph_page.status_code == 200
    assert '"nodes"' in graph_page.text

    tree_page = client.get(f"/viz/tree_viewer.html?sample={SAMPLE.name}")
    assert tree_page.status_code == 200
    assert '"raw_txt":' not in tree_page.text

    # Paths outside the sample directory are rejected (the page renders without data).
    bad = client.get("/viz/graph_viewer.html?sample=../main.py")
    assert bad.status_code == 200
    assert "const serverGraphData = null" in bad.text
