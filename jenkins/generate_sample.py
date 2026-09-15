"""Helpers for jenkins/generate-sample.Jenkinsfile, which turns a public GitHub Android project into a
pre-compiled sample in app/static/sample/. Standard library only, so any agent with python3 runs it.

Values meant for the pipeline are printed to stdout as KEY=value lines; logs go to stderr.

  repo-info <url> [--ref REF] [--name NAME]  check the GitHub URL, resolve the commit, name the sample
  validate <dir> [--command CMD]             check it is a Gradle project with a wrapper, and check CMD
  run-gradle <dir> --command CMD --out FILE  run the Gradle command without a shell, output into FILE
  convert <txt> --name NAME [--out-dir DIR]  parse the Gradle output into a sample JSON
  check-access --repo OWNER/REPO             check the GitHub token in GH_TOKEN can push to the repo
  open-pr --repo OWNER/REPO --branch B ...   open the pull request (GitHub token in GH_TOKEN)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
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
EXAMPLE_COMMAND = "./gradlew app:dependencies --configuration debugRuntimeClasspath"
# GRADLE_COMMAND is not run by a shell, so redirects, pipes, separators and substitutions would only
# reach Gradle as bogus arguments; they are rejected with a clear message instead.
SHELL_SYNTAX = re.compile(r"[|&;<>`]|\$\(")
BUILD_FILES = ("build.gradle", "build.gradle.kts")
SETTINGS_FILES = ("settings.gradle", "settings.gradle.kts")


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


def validate(path: Path, command: str | None = None) -> dict:
    project = find_project_dir(path)
    if not any((project / f).is_file() for f in SETTINGS_FILES):
        fail(f"{project.name} has no settings.gradle(.kts), so it is not a Gradle project.")
    if not (project / "gradlew").is_file():
        fail(f"{project.name} has no Gradle wrapper (gradlew), so its Gradle version is unknown.")
    if command is not None:
        gradle_command(command)
    return {"PROJECT_DIR": str(project)}


# --- run-gradle ---


def gradle_command(command: str) -> list[str]:
    """Splits GRADLE_COMMAND into arguments like a shell would, without running one. Only the
    project's wrapper may run, so the parameter cannot start any other program."""
    try:
        argv = shlex.split(command)
    except ValueError as e:
        fail(f"GRADLE_COMMAND cannot be parsed: {e}.")
    if len(argv) < 2 or argv[0] != "./gradlew":
        fail(f"GRADLE_COMMAND must be ./gradlew followed by tasks and options, e.g. {EXAMPLE_COMMAND}; got '{command}'.")
    shell = [a for a in argv if SHELL_SYNTAX.search(a)]
    if shell:
        fail(
            f"GRADLE_COMMAND is not run by a shell, so it cannot use {' '.join(shell)}. "
            "The job saves Gradle's output itself."
        )
    return argv


def run_gradle(project: Path, command: str, out: Path, gradle_args: str = "") -> dict:
    argv = gradle_command(command) + shlex.split(gradle_args)
    log(f"Running {shlex.join(argv)}")
    with out.open("wb") as output:
        result = subprocess.run(argv, cwd=project, stdout=output, check=False)
    if result.returncode != 0:
        fail(f"Gradle exited with code {result.returncode}; see its output above.")
    return {}


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
            f"| Gradle command | `{args.gradle_command}` |",
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

    # --command is stored as gradle_command, because args.command names the subcommand.
    p = commands.add_parser("validate")
    p.add_argument("path", type=Path)
    p.add_argument("--command", dest="gradle_command")

    p = commands.add_parser("run-gradle")
    p.add_argument("path", type=Path)
    p.add_argument("--command", dest="gradle_command", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--gradle-args", default="")

    p = commands.add_parser("convert")
    p.add_argument("txt", type=Path)
    p.add_argument("--name", required=True)
    p.add_argument("--out-dir", type=Path, default=SAMPLE_DIR)

    p = commands.add_parser("check-access")
    p.add_argument("--repo", required=True)

    p = commands.add_parser("open-pr")
    for option in ("--repo", "--branch", "--base", "--sample", "--source", "--sha"):
        p.add_argument(option, required=True)
    p.add_argument("--command", dest="gradle_command", required=True)
    p.add_argument("--replaces", default="")

    args = parser.parse_args(argv)
    if args.command == "repo-info":
        result = repo_info(args.url, args.ref, args.name or None)
    elif args.command == "validate":
        result = validate(args.path, args.gradle_command)
    elif args.command == "run-gradle":
        result = run_gradle(args.path, args.gradle_command, args.out, args.gradle_args)
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
