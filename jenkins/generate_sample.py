"""Helpers for jenkins/generate-sample.Jenkinsfile, which turns a public GitHub Android project into a
pre-compiled sample in app/static/sample/. Standard library only, so any agent with python3 runs it.

Values meant for the pipeline are printed to stdout as KEY=value lines; logs go to stderr.

  repo-info <url> [--ref REF] [--name NAME]  check the GitHub URL, resolve the commit, name the sample
  validate <dir> [--module :app]             check it is an Android Gradle project, find the app module
  pick-config [--configuration NAME] < out   choose what to dump from the init script's listing
  convert <txt> --name NAME [--out-dir DIR]  parse the Gradle output into a sample JSON
  check-access --repo OWNER/REPO             check the GitHub token in GH_TOKEN can push to the repo
  open-pr --repo OWNER/REPO --branch B ...   open the pull request (GitHub token in GH_TOKEN)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "app"
SAMPLE_DIR = APP_DIR / "static" / "sample"

# app/parse.py is a script that imports its sibling module as `utils`.
sys.path.insert(0, str(APP_DIR))
import parse  # noqa: E402
from utils import get_root_key_and_nodes  # noqa: E402

GITHUB_URL = re.compile(r"^https://github\.com/([A-Za-z0-9][A-Za-z0-9-]{0,38})/([A-Za-z0-9._-]{1,100}?)(?:\.git)?/?$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
MODULE_PATH = re.compile(r"^:$|^(?::[A-Za-z0-9._-]+)+$")
CONFIGURATION_NAME = re.compile(r"^[A-Za-z0-9_]+$")
APPLICATION_PLUGIN = re.compile(r"com\.android\.application|android[._-]?application", re.IGNORECASE)
ANDROID_MARKER = re.compile(r"com\.android\.|plugins\.android|^\s*android\s*\{", re.MULTILINE)
APPLY_FALSE = re.compile(r"apply\s*\(?\s*false")
BUILD_FILES = ("build.gradle", "build.gradle.kts")
SETTINGS_FILES = ("settings.gradle", "settings.gradle.kts")
# Never the app module: build output, and build logic whose convention plugins mention the
# application plugin without being an app. Hidden directories (.git, .gradle, ...) are skipped too.
SKIP_DIRS = {"build", "buildSrc", "build-logic", "node_modules"}
MAX_DEPTH = 4


def fail(message: str):
    raise SystemExit(f"error: {message}")


def log(message: str) -> None:
    print(message, file=sys.stderr)


def sample_slug(name: str) -> str:
    """File-name-safe sample name; the home page shows the part of the file name before '_'."""
    slug = re.sub(r"[^a-z0-9.-]+", "-", name.strip().lower()).strip("-.")
    if not slug:
        fail(f"'{name}' cannot be used as a sample name.")
    return slug


# --- repo-info ---


def parse_github_url(url: str) -> tuple[str, str]:
    match = GITHUB_URL.match(url.strip())
    if not match or set(match.group(2)) == {"."}:
        fail(f"'{url}' is not a GitHub repository URL like https://github.com/owner/repo.")
    return match.group(1), match.group(2)


def pick_sha(ls_remote_output: str, ref: str) -> str | None:
    """Commit of `ref` in `git ls-remote` output, preferring exact refs and peeled tags."""
    refs = {}
    for line in ls_remote_output.splitlines():
        sha, _, name = line.partition("\t")
        if sha and name:
            refs[name] = sha
    for name in (ref, f"refs/heads/{ref}", f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}"):
        if name in refs:
            return refs[name]
    return None


def resolve_ref(owner: str, repo: str, ref: str) -> str:
    if COMMIT_SHA.match(ref):
        return ref
    result = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{owner}/{repo}.git", ref, f"{ref}^{{}}"],
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        check=False,
    )
    if result.returncode != 0:
        fail(f"github.com/{owner}/{repo} was not found or is not public.")
    sha = pick_sha(result.stdout, ref)
    if sha is None:
        fail(f"'{ref}' is not a branch, tag or HEAD of github.com/{owner}/{repo}.")
    return sha


def repo_info(url: str, ref: str = "HEAD", name: str | None = None) -> dict:
    owner, repo = parse_github_url(url)
    sha = resolve_ref(owner, repo, ref.strip() or "HEAD")
    log(f"github.com/{owner}/{repo} @ {ref or 'HEAD'} is {sha}")
    return {"REPO_OWNER": owner, "REPO_NAME": repo, "REPO_SHA": sha, "SAMPLE_SLUG": sample_slug(name or repo)}


# --- validate ---


def find_project_dir(path: Path) -> Path:
    """Accepts the project itself or the folder the archive was extracted into (one top-level dir)."""
    if not path.is_dir():
        fail(f"{path} is not a directory.")
    if not any((path / f).is_file() for f in SETTINGS_FILES + BUILD_FILES):
        children = [p for p in path.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))]
        if len(children) == 1:
            return children[0]
    return path


def gradle_modules(root: Path):
    """Yields (module dir, build file) for the modules of the root build, skipping included builds."""
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        depth = len(current.relative_to(root).parts)
        if current != root and any(f in filenames for f in SETTINGS_FILES):
            dirnames.clear()
            continue
        dirnames[:] = [
            d for d in sorted(dirnames) if d not in SKIP_DIRS and not d.startswith(".")
        ] if depth < MAX_DEPTH else []
        build_file = next((current / f for f in BUILD_FILES if f in filenames), None)
        if build_file:
            yield current, build_file


def applies_application_plugin(build_file: Path) -> bool:
    for line in build_file.read_text(encoding="utf-8", errors="replace").splitlines():
        code = line.split("//", 1)[0]
        if APPLICATION_PLUGIN.search(code) and not APPLY_FALSE.search(code):
            return True
    return False


def validate(path: Path, module: str | None = None) -> dict:
    project = find_project_dir(path)
    if not any((project / f).is_file() for f in SETTINGS_FILES):
        fail(f"{project.name} has no settings.gradle(.kts), so it is not a Gradle project.")
    if not (project / "gradlew").is_file():
        fail(f"{project.name} has no Gradle wrapper (gradlew), so its Gradle version is unknown.")

    modules = list(gradle_modules(project))
    apps = [d for d, build_file in modules if applies_application_plugin(build_file)]

    if module:
        module = module.strip()
        module = module if module.startswith(":") else f":{module}"
        if not MODULE_PATH.match(module):
            fail(f"'{module}' is not a Gradle module path like :app.")
        is_android = apps or any(
            ANDROID_MARKER.search(f.read_text(encoding="utf-8", errors="replace")) for _, f in modules
        )
        if not is_android:
            fail(f"{project.name} does not use the Android Gradle plugin.")
        selector = f"-Pgdv.module={module}"
        log(f"Using module {module} as requested.")
    else:
        if not apps:
            fail(
                f"No module of {project.name} applies the Android application plugin, so it does not look "
                "like an Android app. Set MODULE to the Gradle path of the app module if it is set up differently."
            )
        app = min(
            apps,
            key=lambda d: (
                not (d / "src" / "main" / "AndroidManifest.xml").is_file(),
                d.name != "app",
                len(d.relative_to(project).parts),
                str(d),
            ),
        )
        module_dir = app.relative_to(project).as_posix() or "."
        selector = f"-Pgdv.moduleDir={module_dir}"
        others = [d.relative_to(project).as_posix() or "." for d in apps if d != app]
        log(f"App module directory: {module_dir}" + (f" (also found: {', '.join(others)}; set MODULE to pick one)" if others else ""))

    return {"PROJECT_DIR": str(project), "GRADLE_MODULE_SELECTOR": selector}


# --- pick-config ---


def pick_configuration(names: list[str], requested: str | None = None) -> str:
    """The requested configuration, or the shortest release runtime classpath that is not for tests."""
    if requested:
        if not CONFIGURATION_NAME.match(requested):
            fail(f"'{requested}' is not a configuration name.")
        if requested not in names:
            fail(f"Configuration {requested} does not exist. Available: {', '.join(names) or 'none'}.")
        return requested
    candidates = [n for n in names if "test" not in n.lower()]
    if not candidates:
        fail(f"The module has no runtime classpath configuration to dump. Found: {', '.join(names) or 'none'}.")
    return min(candidates, key=lambda n: (not n.endswith("ReleaseRuntimeClasspath") and n != "releaseRuntimeClasspath", len(n), n))


def pick_config(listing: str, requested: str | None = None) -> dict:
    values = [line.strip().partition("=") for line in listing.splitlines() if line.startswith("GDV_")]
    module = next((v for k, _, v in values if k == "GDV_MODULE"), None)
    if module is None:
        fail("The configuration listing is empty; check the Gradle output above.")
    names = [v for k, _, v in values if k == "GDV_CONFIGURATION"]
    configuration = pick_configuration(names, (requested or "").strip() or None)
    log(f"Dumping {module} {configuration} (available: {', '.join(names)})")
    return {"GRADLE_MODULE": module, "GRADLE_CONFIGURATION": configuration}


# --- convert ---


def convert(txt_path: Path, name: str, out_dir: Path = SAMPLE_DIR, now: datetime | None = None) -> dict:
    # Decoded from bytes so raw_txt keeps the original line endings.
    text = txt_path.read_bytes().decode("utf-8", errors="replace")
    lines = text.splitlines()
    nodes = parse.parse_dependencies(lines)
    if not nodes:
        fail(f"No dependencies found in {txt_path}; check the Gradle output above.")

    slug = sample_slug(name)
    out_dir.mkdir(parents=True, exist_ok=True)
    # One sample per project: a newer dump replaces the older one.
    replaced = sorted(out_dir.glob(f"{slug}_*.json"))
    for old in replaced:
        log(f"Replacing {old.name}")
        old.unlink()

    path = out_dir / f"{slug}_{(now or datetime.now()):%d%H%M}.json"
    data = {parse.extract_project_name(lines): nodes, "raw_txt": text}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log(f"Wrote {path} ({len(nodes)} top-level dependencies)")
    return {"SAMPLE_FILE": path.name, "REPLACED_SAMPLES": ",".join(p.name for p in replaced)}


# --- GitHub API (check-access, open-pr) ---


def github_api(path: str, payload: dict | None = None) -> dict:
    """Calls the GitHub REST API with the token in GH_TOKEN; raises urllib.error.HTTPError on refusal."""
    token = os.environ.get("GH_TOKEN")
    if not token:
        fail("GH_TOKEN is not set.")
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "gradle-dependency-viewer-generate-sample",
        },
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def check_access(repo: str) -> dict:
    """Fails fast, before Gradle runs, when the credential cannot push to `repo`."""
    try:
        repository = github_api(f"/repos/{repo}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            fail(
                "GitHub rejected the credential. Its password must be a GitHub token; "
                "GitHub does not accept account passwords."
            )
        if e.code == 404:
            fail(f"The credential's token cannot see {repo}.")
        fail(f"GitHub refused to show {repo} ({e.code}): {e.read().decode(errors='replace')[:300]}")
    if not repository.get("permissions", {}).get("push"):
        fail(f"The credential's token can read {repo} but cannot push to it.")
    log(f"The credential can push to {repo}.")
    return {}


# --- open-pr ---


def summarize(data: dict) -> tuple[int, int]:
    """Entry and unique-module counts, as shown on the home page."""
    _, root_nodes = get_root_key_and_nodes(data)
    modules = set()
    entries = 0
    stack = list(root_nodes or [])
    while stack:
        node = stack.pop()
        entries += 1
        modules.add(node.get("module", ""))
        stack.extend(node.get("children") or [])
    return entries, len(modules)


def open_pull_request(args) -> dict:
    sample = Path(args.sample)
    slug = sample.stem.split("_")[0]
    entries, modules = summarize(json.loads(sample.read_text(encoding="utf-8")))
    replaced = [r for r in (args.replaces or "").split(",") if r]
    title = f"{'Update' if replaced else 'Add'} {slug} dependency sample"
    body = "\n".join(
        [
            "Pre-compiled dependency sample generated by the `generate-sample` Jenkins job.",
            "",
            "| | |",
            "|---|---|",
            f"| Source | {args.source} @ `{args.sha[:12]}` |",
            f"| Module | `{args.module}` |",
            f"| Configuration | `{args.configuration}` |",
            f"| Entries | {entries:,} |",
            f"| Unique modules | {modules:,} |",
            f"| File | `{sample.as_posix()}` |",
        ]
        + ([f"| Replaces | {', '.join(f'`{r}`' for r in replaced)} |"] if replaced else [])
    )
    try:
        pull = github_api(
            f"/repos/{args.repo}/pulls",
            {"title": title, "head": args.branch, "base": args.base, "body": body},
        )
    except urllib.error.HTTPError as e:
        fail(f"GitHub refused the pull request ({e.code}): {e.read().decode(errors='replace')[:500]}")
    log(f"Opened {pull['html_url']}")
    return {"PR_URL": pull["html_url"]}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("repo-info")
    p.add_argument("url")
    p.add_argument("--ref", default="HEAD")
    p.add_argument("--name", default="")

    p = commands.add_parser("validate")
    p.add_argument("path", type=Path)
    p.add_argument("--module", default="")

    p = commands.add_parser("pick-config")
    p.add_argument("--configuration", default="")

    p = commands.add_parser("convert")
    p.add_argument("txt", type=Path)
    p.add_argument("--name", required=True)
    p.add_argument("--out-dir", type=Path, default=SAMPLE_DIR)

    p = commands.add_parser("check-access")
    p.add_argument("--repo", required=True)

    p = commands.add_parser("open-pr")
    for option in ("--repo", "--branch", "--base", "--sample", "--source", "--sha", "--module", "--configuration"):
        p.add_argument(option, required=True)
    p.add_argument("--replaces", default="")

    args = parser.parse_args(argv)
    if args.command == "repo-info":
        result = repo_info(args.url, args.ref, args.name or None)
    elif args.command == "validate":
        result = validate(args.path, args.module or None)
    elif args.command == "pick-config":
        result = pick_config(sys.stdin.read(), args.configuration)
    elif args.command == "convert":
        result = convert(args.txt, args.name, args.out_dir)
    elif args.command == "check-access":
        result = check_access(args.repo)
    else:
        result = open_pull_request(args)

    for key, value in result.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
