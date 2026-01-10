from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent
PARSE_SCRIPT = REPO_ROOT / "parse.py"
CONVERT_SCRIPT = REPO_ROOT / "convert_to_graph.py"

app = FastAPI()

templates = Jinja2Templates(directory=[
    str(APP_ROOT / "templates"),
    str(APP_ROOT / "viz")
])


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/viz/graph_viewer.html", response_class=HTMLResponse)
async def graph_viewer(request: Request) -> HTMLResponse:
    dep_json_path = REPO_ROOT / "dependencies.json"
    graph_data = None
    
    if dep_json_path.exists():
        try:
            # Add REPO_ROOT to sys.path to import convert_to_graph
            if str(REPO_ROOT) not in sys.path:
                sys.path.append(str(REPO_ROOT))
            
            import convert_to_graph
            
            # Read the dependency data
            with open(dep_json_path, 'r', encoding='utf-8') as f:
                dependency_data = json.load(f)
            
            # Process directly in-process
            graph_data = convert_to_graph.process_data(dependency_data)
        except Exception as e:
            print(f"Error converting graph in-process: {e}")

    return templates.TemplateResponse("graph_viewer.html", {
        "request": request,
        "graph_data": graph_data
    })


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


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported.")

    data = await file.read()
    
    # Try common encodings to be more robust (e.g. for Windows outputs)
    txt_content = None
    for encoding in ["utf-8-sig", "utf-16", "cp1252"]:
        try:
            txt_content = data.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if txt_content is None:
        # Final fallback to latin-1 which should always succeed but might have incorrect characters
        try:
            txt_content = data.decode("latin-1")
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="TXT file could not be decoded. Please ensure it is UTF-8 or UTF-16 encoded."
            ) from exc

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(data)

    try:
        parsed_json = _run_parser(temp_path)
        
        # Save to repo root so it can be used by other visualizers/scripts
        dep_json_path = REPO_ROOT / "dependencies.json"
        with open(dep_json_path, 'w', encoding='utf-8') as f:
            json.dump(parsed_json, f, indent=2)
            
    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "job_id": str(uuid.uuid4()),
        "txt": txt_content,
        "json": parsed_json,
    }
