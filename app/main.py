from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from . import convert_to_graph
from . import enlist as enlist_module
from . import filter as filter_module
from .utils import get_root_key_and_nodes

APP_ROOT = Path(__file__).resolve().parent
PARSE_SCRIPT = APP_ROOT / "parse.py"
SAMPLE_DIR = APP_ROOT / "static" / "sample"

# The app is stateless: it never writes dependency data to disk. Pages are rendered either from
# the pre-compiled samples in SAMPLE_DIR or from data the browser sends along with the request
# (an ad-hoc upload is only kept in the user's browser tab).
app = FastAPI()

templates = Jinja2Templates(
    directory=[str(APP_ROOT / "templates"), str(APP_ROOT / "viz")]
)


class ViewRequest(BaseModel):
    data: dict
    filter: str | None = None
    project_only: bool = False


class EnlistRequest(BaseModel):
    data: dict


def _sample_path(filename: str) -> Path:
    # Security check: only plain file names of existing samples are accepted
    if Path(filename).name != filename or not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid sample name.")
    path = SAMPLE_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Sample not found.")
    return path


def _load_sample(filename: str) -> dict:
    with open(_sample_path(filename), "r", encoding="utf-8") as f:
        return json.load(f)


def _apply_filters(dependency_data: dict, filter: str | None, project_only: bool) -> dict:
    root_key, root_nodes = get_root_key_and_nodes(dependency_data)
    if root_key is None:
        return dependency_data

    keywords = [k.strip() for k in (filter or "").split(",") if k.strip()]
    if project_only:
        dependency_data[root_key] = filter_module.filter_project_only(root_nodes)
    elif keywords:
        kept_nodes = set()
        filter_module.find_matches_and_relatives(root_nodes, keywords, kept_nodes, [])
        dependency_data[root_key] = filter_module.rebuild_tree(root_nodes, kept_nodes)
    return dependency_data


def _to_graph(dependency_data: dict) -> dict:
    graph = convert_to_graph.process_data(dependency_data)
    return graph or {"nodes": [], "edges": [], "metadata": {"total_nodes": 0, "total_edges": 0}}


@lru_cache(maxsize=32)
def _sample_summary(filename: str, mtime: float) -> dict:
    """Entry and unique-module counts of a sample (cached per file modification time)."""
    data = _load_sample(filename)
    _, root_nodes = get_root_key_and_nodes(data)
    modules = set()
    entries = 0
    stack = list(root_nodes or [])
    while stack:
        node = stack.pop()
        entries += 1
        modules.add(node.get("module", ""))
        stack.extend(node.get("children") or [])
    return {"entries": entries, "modules": len(modules)}


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/viz/graph_viewer.html", response_class=HTMLResponse)
async def graph_viewer(
    request: Request, sample: str = None, filter: str = None, project_only: bool = False
) -> HTMLResponse:
    # Without a sample the page renders empty and loads the user's upload from the browser.
    graph_data = None
    if sample:
        try:
            graph_data = _to_graph(_apply_filters(_load_sample(sample), filter, project_only))
        except HTTPException as e:
            print(f"Sample not available: {e.detail}")
        except Exception as e:
            print(f"Error converting graph in-process: {e}")
            import traceback

            traceback.print_exc()

    return templates.TemplateResponse(
        request=request,
        name="graph_viewer.html",
        context={"graph_data": graph_data, "file_name": sample},
    )


@app.get("/viz/tree_viewer.html", response_class=HTMLResponse)
async def tree_viewer(
    request: Request, sample: str = None, filter: str = None, project_only: bool = False
) -> HTMLResponse:
    # Without a sample the page renders empty and loads the user's upload from the browser.
    tree_data = None
    if sample:
        try:
            tree_data = _apply_filters(_load_sample(sample), filter, project_only)
            # The raw TXT is not used by the tree viewer; don't inline it into the page.
            tree_data.pop("raw_txt", None)
        except HTTPException as e:
            print(f"Sample not available: {e.detail}")
        except Exception as e:
            print(f"Error processing tree data: {e}")

    return templates.TemplateResponse(
        request=request,
        name="tree_viewer.html",
        context={"tree_data": tree_data, "file_name": sample},
    )


app.mount("/static", StaticFiles(directory=APP_ROOT / "static"), name="static")
app.mount("/viz", StaticFiles(directory=APP_ROOT / "viz"), name="viz")


def _run_parser(input_path: Path) -> dict:
    if not PARSE_SCRIPT.exists():
        raise HTTPException(status_code=500, detail="parse.py not found.")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        temp_input = temp_dir_path / input_path.name
        temp_input.write_bytes(input_path.read_bytes())

        result = subprocess.run(
            [sys.executable, str(PARSE_SCRIPT), str(temp_input)],
            capture_output=True,
            text=True,
            cwd=temp_dir,
            check=False,
        )

        stdout = result.stdout.strip()
        if stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                pass

        candidate_files = [
            temp_input.with_suffix(".json"),
            temp_dir_path / "output.json",
            temp_dir_path / "result.json",
        ]

        json_path = next((path for path in candidate_files if path.exists()), None)
        if json_path is None:
            json_files = sorted(temp_dir_path.glob("*.json"))
            json_path = json_files[0] if json_files else None

        if json_path and json_path.exists():
            try:
                return json.loads(json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to read JSON output: {exc}",
                ) from exc

        stderr = result.stderr.strip()
        if stderr:
            stderr = stderr[:4000]
        raise HTTPException(
            status_code=500,
            detail=f"Parser failed to produce JSON output. stderr: {stderr or 'No stderr output.'}",
        )


@app.get("/api/samples")
async def list_samples():
    samples = []
    for f in sorted(SAMPLE_DIR.glob("*.json")):
        # Expecting filename format: {project}_ddMMhh.json
        project_name = f.stem.split("_")[0]
        samples.append(
            {
                "name": project_name,
                "filename": f.name,
                "path": f"/static/sample/{f.name}",
                **_sample_summary(f.name, f.stat().st_mtime),
            }
        )
    return samples


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    """Parse an uploaded TXT and return the result. Nothing is persisted."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported.")

    data = await file.read()

    # Try common encodings
    txt_content = None
    for encoding in ["utf-8-sig", "utf-16", "cp1252"]:
        try:
            txt_content = data.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if txt_content is None:
        try:
            txt_content = data.decode("latin-1")
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="TXT file could not be decoded. Please ensure it is UTF-8 or UTF-16 encoded.",
            ) from exc

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(data)

    try:
        parsed_json = _run_parser(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "name": Path(file.filename).stem,
        "txt": txt_content,
        "json": parsed_json,
    }


@app.post("/api/graph")
async def graph(request: ViewRequest):
    """Filter dependency data sent by the browser and convert it to the graph format."""
    try:
        return _to_graph(_apply_filters(request.data, request.filter, request.project_only))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid dependency data: {e}")


@app.post("/api/tree")
async def tree(request: ViewRequest):
    """Filter dependency data sent by the browser for the tree viewer."""
    try:
        tree_data = _apply_filters(request.data, request.filter, request.project_only)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid dependency data: {e}")
    tree_data.pop("raw_txt", None)
    return tree_data


@app.post("/api/enlist")
async def enlist(request: EnlistRequest):
    try:
        dependencies = enlist_module.extract_dependencies_from_json(request.data)
        yaml_data = {"dependencies": dependencies, "total_count": len(dependencies)}

        yaml_content = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)

        return Response(
            content=yaml_content, media_type="application/x-yaml", headers={}
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
