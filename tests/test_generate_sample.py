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
    "settings.gradle.kts": 'include(":app", ":core")\n',
    "gradlew": "#!/bin/sh\n",
    "build.gradle.kts": "plugins {\n    alias(libs.plugins.android.application) apply false\n}\n",
    "app/build.gradle.kts": "plugins {\n    alias(libs.plugins.android.application)\n}\n",
    "app/src/main/AndroidManifest.xml": "<manifest/>",
    "core/build.gradle.kts": "plugins {\n    alias(libs.plugins.android.library)\n}\n",
    # Convention plugins mention the application plugin but are not an app module
    "build-logic/settings.gradle.kts": "",
    "build-logic/convention/build.gradle.kts": 'gradlePlugin { plugins { register("androidApplication") } }\n',
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


def test_validate_finds_app_module_in_extracted_archive(tmp_path):
    make_project(tmp_path / "architecture-samples-abc123", ANDROID_PROJECT)
    result = gs.validate(tmp_path)
    assert result["PROJECT_DIR"] == str(tmp_path / "architecture-samples-abc123")
    assert result["GRADLE_MODULE_SELECTOR"] == "-Pgdv.moduleDir=app"


def test_validate_prefers_the_app_directory(tmp_path):
    make_project(
        tmp_path,
        {
            **ANDROID_PROJECT,
            "wear/build.gradle": "apply plugin: 'com.android.application'\n",
            "wear/src/main/AndroidManifest.xml": "<manifest/>",
        },
    )
    assert gs.validate(tmp_path)["GRADLE_MODULE_SELECTOR"] == "-Pgdv.moduleDir=app"


def test_validate_finds_a_differently_named_app_module(tmp_path):
    make_project(
        tmp_path,
        {
            "settings.gradle": "include ':mobile'\n",
            "gradlew": "",
            "mobile/build.gradle": 'plugins {\n    id "com.android.application"\n}\n',
        },
    )
    assert gs.validate(tmp_path)["GRADLE_MODULE_SELECTOR"] == "-Pgdv.moduleDir=mobile"


def test_validate_accepts_an_explicit_module(tmp_path):
    make_project(tmp_path, ANDROID_PROJECT)
    assert gs.validate(tmp_path, "core")["GRADLE_MODULE_SELECTOR"] == "-Pgdv.module=:core"


@pytest.mark.parametrize(
    "files, module",
    [
        ({"README.md": ""}, None),  # not a Gradle project
        ({"settings.gradle": "", "app/build.gradle": "apply plugin: 'com.android.application'"}, None),  # no wrapper
        ({"settings.gradle": "", "gradlew": "", "build.gradle": "plugins { id 'java' }"}, None),  # not Android
        ({"settings.gradle": "", "gradlew": "", "build.gradle": "plugins { id 'java' }"}, ":app"),
        (ANDROID_PROJECT, "--init-script=evil.gradle"),
    ],
)
def test_validate_rejects(tmp_path, files, module):
    make_project(tmp_path, files)
    with pytest.raises(SystemExit):
        gs.validate(tmp_path, module)


# --- pick-config ---


@pytest.mark.parametrize(
    "names, expected",
    [
        (["debugRuntimeClasspath", "releaseRuntimeClasspath", "releaseUnitTestRuntimeClasspath"], "releaseRuntimeClasspath"),
        (["fullDebugRuntimeClasspath", "fullReleaseRuntimeClasspath", "minimalReleaseRuntimeClasspath"], "fullReleaseRuntimeClasspath"),
        (
            ["playProdReleaseRuntimeClasspath", "playStagingReleaseRuntimeClasspath", "websiteProdReleaseRuntimeClasspath"],
            "playProdReleaseRuntimeClasspath",
        ),
        (["debugRuntimeClasspath", "debugAndroidTestRuntimeClasspath"], "debugRuntimeClasspath"),
    ],
)
def test_pick_configuration(names, expected):
    assert gs.pick_configuration(names) == expected


def test_pick_config_reads_the_init_script_listing():
    listing = "\n".join(
        [
            "> Task :help",
            "GDV_MODULE=:Signal-Android",
            "GDV_CONFIGURATION=playProdDebugRuntimeClasspath",
            "GDV_CONFIGURATION=playProdReleaseRuntimeClasspath",
            "BUILD SUCCESSFUL in 3s",
        ]
    )
    assert gs.pick_config(listing) == {
        "GRADLE_MODULE": ":Signal-Android",
        "GRADLE_CONFIGURATION": "playProdReleaseRuntimeClasspath",
    }
    assert gs.pick_config(listing, "playProdDebugRuntimeClasspath")["GRADLE_CONFIGURATION"] == "playProdDebugRuntimeClasspath"


@pytest.mark.parametrize("requested", ["missingRuntimeClasspath", "release; rm -rf /"])
def test_pick_config_rejects_unknown_configurations(requested):
    with pytest.raises(SystemExit):
        gs.pick_config("GDV_MODULE=:app\nGDV_CONFIGURATION=releaseRuntimeClasspath", requested)


def test_pick_config_rejects_empty_listing():
    with pytest.raises(SystemExit):
        gs.pick_config("FAILURE: Build failed with an exception.")


# --- convert ---


def test_convert_writes_a_sample_like_the_bundled_ones(tmp_path):
    bundled = json.loads(sorted(SAMPLE_DIR.glob("*.json"))[0].read_text(encoding="utf-8"))
    txt = tmp_path / "dependencies.txt"
    txt.write_text(bundled["raw_txt"], encoding="utf-8")
    out_dir = tmp_path / "sample"
    make_project(out_dir, {"demo_010101.json": "{}", "demo-extra_010101.json": "{}"})

    result = gs.convert(txt, "Demo", out_dir, now=datetime(2026, 9, 13, 8, 5))

    assert result == {"SAMPLE_FILE": "demo_130805.json", "REPLACED_SAMPLES": "demo_010101.json"}
    assert sorted(p.name for p in out_dir.iterdir()) == ["demo-extra_010101.json", "demo_130805.json"]
    written = json.loads((out_dir / "demo_130805.json").read_text(encoding="utf-8"))
    assert written == bundled
    assert gs.summarize(written)[0] > 100


def test_convert_rejects_output_without_dependencies(tmp_path):
    txt = tmp_path / "dependencies.txt"
    txt.write_text("FAILURE: Build failed with an exception.\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        gs.convert(txt, "demo", tmp_path / "sample")
    assert not (tmp_path / "sample").exists() or not any((tmp_path / "sample").iterdir())
