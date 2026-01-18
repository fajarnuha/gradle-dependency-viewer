from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent
PARSE_SCRIPT = APP_ROOT / "parse.py"
CONVERT_SCRIPT = APP_ROOT / "convert_to_graph.py"
DATA_DIR = APP_ROOT / "static" / "data"
SAMPLE_DIR = APP_ROOT / "static" / "sample"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()

templates = Jinja2Templates(
    directory=[str(APP_ROOT / "templates"), str(APP_ROOT / "viz")]
)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    deps_history = os.environ.get("DEPS_HISTORY", "0")
    return templates.TemplateResponse(
        "index.html", {"request": request, "deps_history": deps_history}
    )


@app.get("/viz/graph_viewer.html", response_class=HTMLResponse)
async def graph_viewer(
    request: Request, file: str = None, filter: str = None, project_only: bool = False
) -> HTMLResponse:
    graph_data = None

    if file:
        dep_json_path = DATA_DIR / file
    else:
        # Fallback for backward compatibility
        dep_json_path = REPO_ROOT / "dependencies.json"

    if dep_json_path.exists():
        try:
            from . import convert_to_graph
            from . import filter as filter_module
            from .utils import get_root_key_and_nodes

            # Read the dependency data
            with open(dep_json_path, "r", encoding="utf-8") as f:
                dependency_data = json.load(f)

            root_key, root_nodes = get_root_key_and_nodes(dependency_data)

            # Apply filtering if requested
            if project_only:
                print("Filtering: Project Only")
                dependency_data[root_key] = filter_module.filter_project_only(
                    root_nodes
                )
            elif filter:
                keywords = [k.strip() for k in filter.split(",")]
                print(f"Filtering keywords: {keywords}")
                kept_nodes = set()
                filter_module.find_matches_and_relatives(
                    root_nodes, keywords, kept_nodes, []
                )
                dependency_data[root_key] = filter_module.rebuild_tree(
                    root_nodes, kept_nodes
                )

            # Process directly in-process
            graph_data = convert_to_graph.process_data(dependency_data)
        except Exception as e:
            print(f"Error converting graph in-process: {e}")
            import traceback

            traceback.print_exc()

    return templates.TemplateResponse(
        "graph_viewer.html",
        {"request": request, "graph_data": graph_data, "file_name": file},
    )


@app.get("/viz/tree_viewer.html", response_class=HTMLResponse)
async def tree_viewer(
    request: Request, file: str = None, filter: str = None, project_only: bool = False
) -> HTMLResponse:
    tree_data = None

    if file:
        dep_json_path = DATA_DIR / file
        if dep_json_path.exists():
            try:
                from . import filter as filter_module
                from .utils import get_root_key_and_nodes

                with open(dep_json_path, "r", encoding="utf-8") as f:
                    dependency_data = json.load(f)

                root_key, root_nodes = get_root_key_and_nodes(dependency_data)

                # Apply filtering if requested
                if project_only:
                    dependency_data[root_key] = filter_module.filter_project_only(
                        root_nodes
                    )
                elif filter:
                    keywords = [k.strip() for k in filter.split(",")]
                    kept_nodes = set()
                    filter_module.find_matches_and_relatives(
                        root_nodes, keywords, kept_nodes, []
                    )
                    dependency_data[root_key] = filter_module.rebuild_tree(
                        root_nodes, kept_nodes
                    )

                tree_data = dependency_data

            except Exception as e:
                print(f"Error processing tree data: {e}")

    return templates.TemplateResponse(
        "tree_viewer.html",
        {"request": request, "tree_data": tree_data, "file_name": file},
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
    # List .json files in the sample directory
    for f in SAMPLE_DIR.glob("*.json"):
        # Expecting filename format: {project}_ddMMhh.json
        parts = f.stem.split('_')
        project_name = parts[0] if len(parts) > 0 else f.stem
        
        samples.append({
            "name": project_name,
            "filename": f.name,
            "path": f"/static/sample/{f.name}"
        })
    return samples


@app.post("/api/samples/{filename}/process")
async def process_sample(filename: str):
    sample_path = SAMPLE_DIR / filename
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample file not found.")
    
    # Generate timestamped filename for the data directory to avoid conflicts/overwrites
    # and to match the upload behavior (sort of)
    timestamp = datetime.now().strftime("%d%H%M")
    original_stem = sample_path.stem.split('_')[0] # keep project name part
    dest_filename = f"{original_stem}_sample_{timestamp}.json"
    dest_path = DATA_DIR / dest_filename
    
    try:
        dest_path.write_bytes(sample_path.read_bytes())
        
        # Cleanup old files (keep max 20) logic duplicate - could be refactored but ok for now
        json_files = sorted(DATA_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
        while len(json_files) > 20:
            file_to_remove = json_files.pop(0)
            try:
                file_to_remove.unlink()
            except Exception:
                pass
                
        return {"filename": dest_filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process sample: {e}")


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
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

        # Save to static/data directory with the same name as txt file (but .json)
        # Embed the original TXT content for persistence
        parsed_json["raw_txt"] = txt_content

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%d%H%M")
        original_stem = Path(file.filename).stem
        json_filename = f"{original_stem}_{timestamp}.json"
        dest_path = DATA_DIR / json_filename

        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(parsed_json, f, indent=2)

        # Cleanup old files (keep max 20)
        json_files = sorted(DATA_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
        while len(json_files) > 20:
            file_to_remove = json_files.pop(0)
            try:
                file_to_remove.unlink()
                print(f"Removed old file: {file_to_remove.name}")
            except Exception as e:
                print(f"Error removing file {file_to_remove.name}: {e}")

    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "filename": json_filename,
        "txt": txt_content,
        "json": parsed_json,
    }


@app.get("/api/files")
async def list_files():
    files = []
    for f in DATA_DIR.glob("*.json"):
        files.append(
            {"name": f.name, "size": f.stat().st_size, "modified": f.stat().st_mtime}
        )
    # Sort by modification time (newest first)
    files.sort(key=lambda x: x["modified"], reverse=True)
    return files


@app.delete("/api/files/{filename}")
async def delete_file(filename: str):
    file_path = DATA_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    # Security check: ensure it's just a filename and not a path
    if Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path.unlink()
    return {"message": f"File {filename} deleted."}


@app.get("/api/enlist/{filename}")
async def enlist(filename: str):
    file_path = DATA_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    # Security check: ensure it's just a filename and not a path
    if Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    try:
        from . import enlist as enlist_module

        with open(file_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        dependencies = enlist_module.extract_dependencies_from_json(json_data)
        yaml_data = {"dependencies": dependencies, "total_count": len(dependencies)}

        yaml_content = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)

        return Response(
            content=yaml_content, media_type="application/x-yaml", headers={}
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
