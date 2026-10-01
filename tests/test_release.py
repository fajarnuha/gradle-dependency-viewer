import runpy
from pathlib import Path


def test_release_bumps_gradle_version_and_pushes_only_its_tag(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parent.parent / "scripts/up_version.py"
    properties = tmp_path / "gradle.properties"
    properties.write_text("version=0.1.9\norg.gradle.jvmargs=-Xmx1g\n")
    commands = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("subprocess.run", lambda command, **kwargs: commands.append(command))
    runpy.run_path(str(script), run_name="__main__")
    assert properties.read_text() == "version=0.1.10\norg.gradle.jvmargs=-Xmx1g\n"
    assert commands == [
        ["git", "add", "gradle.properties"],
        ["git", "commit", "-m", "Bump version to v0.1.10"],
        ["git", "tag", "v0.1.10"],
        ["git", "push"],
        ["git", "push", "origin", "v0.1.10"],
    ]
