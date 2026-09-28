import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest

from app.main import SAMPLE_DIR

SCRIPT = Path(__file__).resolve().parent.parent / "jenkins" / "generate_sample.py"
spec = importlib.util.spec_from_file_location("generate_sample", SCRIPT)
gs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gs)


def make_project(root: Path, files: dict[str, str]) -> Path:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


ANDROID_PROJECT = {
    "settings.gradle.kts": 'include(":app")\n',
    "gradlew": "#!/bin/sh\n",
    "app/build.gradle.kts": "plugins {\n    alias(libs.plugins.android.application)\n}\n",
}


# --- repo-info ---


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://github.com/android/architecture-samples", ("android", "architecture-samples")),
        ("https://github.com/signalapp/Signal-Android.git", ("signalapp", "Signal-Android")),
        ("https://github.com/home-assistant/android/", ("home-assistant", "android")),
    ],
)
def test_parse_github_url(url, expected):
    assert gs.parse_github_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",
        "https://gitlab.com/a/b",
        "https://github.com/a/b/tree/main",
        "https://github.com/a/b;rm -rf /",
        "https://github.com/a/..",
        "git@github.com:a/b.git",
    ],
)
def test_parse_github_url_rejects_other_urls(url):
    with pytest.raises(SystemExit):
        gs.parse_github_url(url)


def test_pick_sha_prefers_exact_refs_and_peeled_tags():
    output = "\n".join(
        [
            "1" * 40 + "\tHEAD",
            "2" * 40 + "\trefs/heads/main",
            "3" * 40 + "\trefs/heads/feature/main",
            "4" * 40 + "\trefs/tags/v1.0",
            "5" * 40 + "\trefs/tags/v1.0^{}",
        ]
    )
    assert gs.pick_sha(output, "HEAD") == "1" * 40
    assert gs.pick_sha(output, "main") == "2" * 40
    assert gs.pick_sha(output, "v1.0") == "5" * 40
    assert gs.pick_sha(output, "missing") is None


@pytest.mark.parametrize(
    "name, slug",
    [("Signal-Android", "signal-android"), ("my_app", "my-app"), (" Now in Android ", "now-in-android")],
)
def test_sample_slug_has_no_underscore(name, slug):
    assert gs.sample_slug(name) == slug


# --- validate ---


def test_validate_finds_the_project_in_an_extracted_archive(tmp_path):
    make_project(tmp_path / "architecture-samples-abc123", ANDROID_PROJECT)
    result = gs.validate(tmp_path, gs.EXAMPLE_COMMAND)
    assert result == {"PROJECT_DIR": str(tmp_path / "architecture-samples-abc123")}


@pytest.mark.parametrize(
    "files, command",
    [
        ({"README.md": ""}, None),  # not a Gradle project
        ({"settings.gradle": "", "app/build.gradle": ""}, None),  # no wrapper
        (ANDROID_PROJECT, "gradle app:dependencies"),  # not the wrapper
    ],
)
def test_validate_rejects(tmp_path, files, command):
    make_project(tmp_path, files)
    with pytest.raises(SystemExit):
        gs.validate(tmp_path, command)


# --- choose-command ---


def fake_agy(tmp_path: Path, stdout: str, exit_code: int = 0) -> str:
    """A stand-in for the Antigravity CLI that prints `stdout` whatever it is asked."""
    script = tmp_path / "agy"
    script.write_text(f"#!/bin/sh\ncat <<'JSON'\n{stdout}\nJSON\nexit {exit_code}\n", encoding="utf-8")
    script.chmod(0o755)
    return str(script)


def envelope(**fields) -> str:
    return json.dumps({"conversation_id": "test", "status": "SUCCESS", "response": "", **fields})


def test_collect_gradle_files_reads_the_build_files(tmp_path):
    make_project(
        tmp_path,
        {
            **ANDROID_PROJECT,
            "gradle.properties": "android.useAndroidX=true\n",
            "app/src/main/java/App.kt": "class App",  # not a Gradle file
            "build/generated/build.gradle.kts": "// build output",  # skipped
        },
    )
    assert [path for path, _ in gs.collect_gradle_files(tmp_path)] == [
        "gradle.properties",
        "settings.gradle.kts",
        "app/build.gradle.kts",
    ]
    assert "android.application" in dict(gs.collect_gradle_files(tmp_path))["app/build.gradle.kts"]


def test_choose_command_takes_the_structured_answer(tmp_path):
    make_project(tmp_path, ANDROID_PROJECT)
    command = "./gradlew :Signal-Android:dependencies --configuration playProdDebugRuntimeClasspath"
    agy = fake_agy(tmp_path, envelope(structured_output={"command": command, "reason": "flavors"}))
    assert gs.choose_command(tmp_path, agy) == {"GRADLE_CMD": command}


def test_choose_command_reads_the_answer_from_fenced_json(tmp_path):
    make_project(tmp_path, ANDROID_PROJECT)
    answer = json.dumps({"command": gs.EXAMPLE_COMMAND})
    agy = fake_agy(tmp_path, envelope(response=f"```json\n{answer}\n```\n{answer}\n"))
    assert gs.choose_command(tmp_path, agy) == {"GRADLE_CMD": gs.EXAMPLE_COMMAND}


@pytest.mark.parametrize(
    "stdout, exit_code",
    [
        (envelope(structured_output={"command": "UNKNOWN", "reason": "no app module"}), 0),
        (envelope(structured_output={"command": "rm -rf /"}), 0),  # not the wrapper
        (envelope(response="I could not work it out."), 0),  # no JSON answer
        ("not json at all", 0),
        (envelope(structured_output={"command": gs.EXAMPLE_COMMAND}), 1),  # the CLI failed
    ],
)
def test_choose_command_rejects(tmp_path, stdout, exit_code):
    make_project(tmp_path, ANDROID_PROJECT)
    with pytest.raises(SystemExit):
        gs.choose_command(tmp_path, fake_agy(tmp_path, stdout, exit_code))


def test_choose_command_without_the_cli_installed(tmp_path):
    make_project(tmp_path, ANDROID_PROJECT)
    with pytest.raises(SystemExit):
        gs.choose_command(tmp_path, str(tmp_path / "missing-agy"))


# --- run-gradle ---


def test_gradle_command_splits_like_a_shell():
    assert gs.gradle_command("./gradlew :app:dependencies --configuration 'play Release' -Pa=\"b c\"") == [
        "./gradlew",
        ":app:dependencies",
        "--configuration",
        "play Release",
        "-Pa=b c",
    ]


@pytest.mark.parametrize(
    "command",
    [
        "",
        "./gradlew",
        "gradle app:dependencies",
        "sh -c './gradlew help'",
        "./gradlew app:dependencies > dependencies.txt",
        "./gradlew help; rm -rf /",
        "./gradlew help && curl example.com",
        "./gradlew $(id)",
        "./gradlew `id`",
        "./gradlew 'unbalanced",
    ],
)
def test_gradle_command_rejects(command):
    with pytest.raises(SystemExit):
        gs.gradle_command(command)


def test_run_gradle_runs_the_wrapper_without_a_shell(tmp_path):
    make_project(tmp_path, {"gradlew": '#!/bin/sh\necho "args: $*"\n'})
    (tmp_path / "gradlew").chmod(0o755)
    out = tmp_path / "dependencies.txt"
    gs.run_gradle(tmp_path, "./gradlew app:dependencies --configuration 'a b'", out, "--no-daemon --console=plain")
    assert out.read_text() == "args: app:dependencies --configuration a b --no-daemon --console=plain\n"


def test_run_gradle_fails_when_gradle_fails(tmp_path):
    make_project(tmp_path, {"gradlew": "#!/bin/sh\nexit 3\n"})
    (tmp_path / "gradlew").chmod(0o755)
    with pytest.raises(SystemExit) as exc:
        gs.run_gradle(tmp_path, gs.EXAMPLE_COMMAND, tmp_path / "dependencies.txt")
    assert "code 3" in str(exc.value)


# --- convert ---


def test_convert_writes_a_sample_like_the_bundled_ones(tmp_path):
    bundled = json.loads(sorted(SAMPLE_DIR.glob("*.json"))[0].read_text(encoding="utf-8"))
    txt = tmp_path / "dependencies.txt"
    txt.write_text(bundled["raw_txt"], encoding="utf-8")
    out_dir = tmp_path / "sample"
    make_project(out_dir, {"demo_010101.json": "{}", "demo-extra_010101.json": "{}"})

    meta = {"repository": "https://github.com/owner/demo", "commit": "a" * 40}
    result = gs.convert(txt, "Demo", out_dir, now=datetime(2026, 9, 13, 8, 5), meta=meta)

    assert result == {"SAMPLE_FILE": "demo_130805.json", "REPLACED_SAMPLES": "demo_010101.json"}
    assert sorted(p.name for p in out_dir.iterdir()) == ["demo-extra_010101.json", "demo_130805.json"]
    written = json.loads((out_dir / "demo_130805.json").read_text(encoding="utf-8"))
    assert list(written)[0] == "meta" and written["meta"] == meta
    assert {k: v for k, v in written.items() if k != "meta"} == {k: v for k, v in bundled.items() if k != "meta"}
    assert gs.summarize(written)[0] > 100


PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16
WEBP = b"RIFF\0\0\0\0WEBPVP8 " + b"\0" * 16
MANIFEST = '<manifest><application android:label="Demo"\n    android:icon="@mipmap/app_icon"></application></manifest>'


def write_bytes(root: Path, files: dict[str, bytes]) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


@pytest.mark.parametrize(
    ("command", "module"),
    [
        ("./gradlew app:dependencies --configuration debugRuntimeClasspath", "app"),
        ("./gradlew :apps:phone:dependencies", "apps/phone"),
        ("./gradlew dependencies --configuration debugRuntimeClasspath", ""),
    ],
)
def test_gradle_module(command, module):
    assert gs.gradle_module(command) == module


def test_app_icon_prefers_the_main_source_set_and_a_sharp_density(tmp_path):
    make_project(tmp_path, {**ANDROID_PROJECT, "app/src/main/AndroidManifest.xml": MANIFEST})
    write_bytes(
        tmp_path / "app/src",
        {
            "main/res/mipmap-hdpi/app_icon.png": PNG + b"hdpi",
            "main/res/mipmap-xxhdpi-v4/app_icon.webp": WEBP,
            "main/res/mipmap-xxxhdpi/ic_launcher.png": PNG,
            "free/res/mipmap-xxhdpi/app_icon.png": PNG + b"free",
        },
    )
    icon = gs.app_icon(tmp_path, "./gradlew app:dependencies")
    assert icon == "data:image/webp;base64," + gs.base64.b64encode(WEBP).decode()


def test_app_icon_finds_the_app_module_when_the_gradle_path_differs_from_its_directory(tmp_path):
    # Like Signal-Android, whose :Signal-Android project lives in app/.
    make_project(
        tmp_path,
        {
            "settings.gradle.kts": 'include(":Signal-Android", ":lib")\n',
            "app/build.gradle.kts": 'plugins { id("com.android.application") }\n',
            "app/src/main/AndroidManifest.xml": "<manifest><application/></manifest>",
            "lib/build.gradle.kts": 'plugins { id("com.android.library") }\n',
            "lib/src/main/AndroidManifest.xml": MANIFEST,
        },
    )
    write_bytes(tmp_path, {"app/src/main/res/mipmap-xhdpi/ic_launcher.png": PNG, "lib/src/main/res/mipmap-xxhdpi/app_icon.png": PNG + b"lib"})
    icon = gs.app_icon(tmp_path, "./gradlew :Signal-Android:dependencies")
    assert icon == "data:image/png;base64," + gs.base64.b64encode(PNG).decode()


@pytest.mark.parametrize(
    "files",
    [
        {"app/src/main/res/mipmap-anydpi-v26/app_icon.xml": b"<adaptive-icon/>"},
        {"app/src/main/res/mipmap-xxhdpi/app_icon.png": b"<svg onload=alert(1)>"},
        {"app/src/main/res/mipmap-xxhdpi/app_icon.png": PNG + b"\0" * gs.MAX_ICON_BYTES},
    ],
    ids=["xml only", "not an image", "too large"],
)
def test_app_icon_skips_what_cannot_be_embedded(tmp_path, files):
    make_project(tmp_path, {**ANDROID_PROJECT, "app/src/main/AndroidManifest.xml": MANIFEST})
    write_bytes(tmp_path, files)
    assert gs.app_icon(tmp_path, "./gradlew app:dependencies") is None


def test_app_icon_ignores_files_outside_the_project(tmp_path):
    project = make_project(tmp_path / "project", {**ANDROID_PROJECT, "app/src/main/AndroidManifest.xml": MANIFEST})
    write_bytes(tmp_path, {"outside.png": PNG})
    (project / "app/src/main/res/mipmap-xxhdpi").mkdir(parents=True)
    (project / "app/src/main/res/mipmap-xxhdpi/app_icon.png").symlink_to(tmp_path / "outside.png")
    assert gs.app_icon(project, "./gradlew app:dependencies") is None


def test_sample_meta(tmp_path):
    make_project(tmp_path, {**ANDROID_PROJECT, "app/src/main/AndroidManifest.xml": MANIFEST})
    write_bytes(tmp_path, {"app/src/main/res/mipmap-xxhdpi/app_icon.png": PNG})
    meta = gs.sample_meta("https://github.com/owner/demo.git", "b" * 40, tmp_path, "./gradlew app:dependencies")
    assert meta["repository"] == "https://github.com/owner/demo"
    assert meta["commit"] == "b" * 40
    assert meta["icon"].startswith("data:image/png;base64,")
    assert gs.sample_meta() == {}
    with pytest.raises(SystemExit):
        gs.sample_meta(commit="main")


@pytest.fixture
def github(monkeypatch):
    """Fakes GitHub's REST API: set `github.response` to a dict, or to an HTTP status code to fail."""
    import io
    import urllib.error

    class FakeGitHub:
        response = {}
        requests = []

        def urlopen(self, request, timeout):
            self.requests.append(request)
            if isinstance(self.response, int):
                raise urllib.error.HTTPError(request.full_url, self.response, "error", {}, io.BytesIO(b"{}"))
            return io.BytesIO(json.dumps(self.response).encode())

    fake = FakeGitHub()
    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setattr(gs.urllib.request, "urlopen", fake.urlopen)
    return fake


def test_check_access_accepts_a_token_that_can_push(github):
    github.response = {"permissions": {"pull": True, "push": True}}
    assert gs.check_access("fajarnuha/gradle-dependency-viewer") == {}
    request = github.requests[0]
    assert request.full_url == "https://api.github.com/repos/fajarnuha/gradle-dependency-viewer"
    assert request.get_header("Authorization") == "Bearer test-token"


@pytest.mark.parametrize(
    "response, message",
    [
        ({"permissions": {"pull": True, "push": False}}, "cannot push"),
        (401, "must be a GitHub token"),
        (404, "cannot see"),
    ],
)
def test_check_access_rejects_credentials_that_cannot_push(github, capsys, response, message):
    github.response = response
    with pytest.raises(SystemExit) as exc:
        gs.check_access("fajarnuha/gradle-dependency-viewer")
    assert message in str(exc.value)


def test_check_access_needs_a_token(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        gs.check_access("fajarnuha/gradle-dependency-viewer")


def test_convert_rejects_output_without_dependencies(tmp_path):
    txt = tmp_path / "dependencies.txt"
    txt.write_text("FAILURE: Build failed with an exception.\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        gs.convert(txt, "demo", tmp_path / "sample")
    assert not (tmp_path / "sample").exists() or not any((tmp_path / "sample").iterdir())
