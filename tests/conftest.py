import os
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = ROOT / "app"
SAMPLE_DIR = APP_ROOT / "static/sample"
CLI = ROOT / "server/build/install/gradle-dependency-viewer/bin/gradle-dependency-viewer"


@pytest.fixture(scope="session", autouse=True)
def server(tmp_path_factory):
    if not CLI.is_file():
        pytest.fail("Build the Ktor distribution first: ./gradlew :server:installDist")
    log_path = tmp_path_factory.mktemp("ktor") / "server.log"
    with log_path.open("w") as log:
        proc = subprocess.Popen([str(CLI)], cwd=ROOT, env={**os.environ, "PORT": "8003", "HOST": "127.0.0.1"},
                                stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    pytest.fail(log_path.read_text())
                try:
                    with urllib.request.urlopen("http://127.0.0.1:8003/healthz", timeout=1) as response:
                        if response.read() == b"ok":
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                pytest.fail(f"Ktor did not start: {log_path.read_text()}")
            yield
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
