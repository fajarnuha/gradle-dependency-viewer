# Gradle Dependency Viewer

Visualize Gradle dependency reports as interactive graphs and trees. Upload the output of the Gradle `dependencies` task saved as a text file.

The backend uses Kotlin and Ktor. The parser, filters, graph conversion, summaries and dependency export live in the `core` Kotlin Multiplatform module, using the Kotlin standard library and `kotlinx.serialization`. The frontend uses static JavaScript, CSS and D3 7.9.0.

![Graph Viewer](screenshot/graph_viewer.png)

## Getting started

### Prerequisites

- JDK 21 for development and CI. The Gradle wrapper is included.
- Node.js 22 to run the core tests on JavaScript.
- Python 3.12 and [uv](https://github.com/astral-sh/uv) for the optional browser and automation test suite. Python is not required to build or run the Kotlin application.

### Running the web application

To start the server from source:

```bash
./gradlew :server:run
```

Access the UI at [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Usage guide

### 1. Generate a dependency report

Run the following command in your Gradle project root to generate a text file of your dependencies.

**Note:** The configuration name (e.g., `debugRuntimeClasspath`) varies depending on your project's build variants and flavors. Check your available configurations by running `./gradlew app:dependencies` without arguments first to decide which one you want to visualize.

```bash
./gradlew app:dependencies --configuration debugRuntimeClasspath > my_app.txt
```

### 2. Upload and visualize

1. Open the web app in your browser.
2. Drag and drop or click to upload your `my_app.txt`.
3. Once parsing finishes, choose **Graph Viewer** or **Tree Viewer** from the result card.

### 3. Explore dependencies

- **Bundled samples**: The landing page lists dependency reports from open source Android projects in `app/static/sample/`.
- **Stateless uploads**: The server parses reports in memory without saving them. Results stay in the browser tab's `sessionStorage`.
- **Tree Viewer**: Browse the dependency hierarchy and expand individual branches.
- **Graph Viewer**: Explore connections and transitive dependencies in an interactive graph.
- **Search and filters**: Find dependencies by keyword, such as `androidx` or `:module-name`, and highlight their connections.

![Tree Viewer](screenshot/tree_viewer.png)

## Development

### Project structure

- `core/`: Kotlin Multiplatform logic and shared tests, targeting JVM and JavaScript.
- `server/`: Ktor server, JVM file and charset handling, CLI and server tests.
- `app/`: Static frontend, HTML templates and bundled JSON samples, packaged as server resources.
- `tests/`: Python tests for Chromium browser flows, accessibility, screenshots, Jenkins automation and the release script. These run against the Kotlin distribution in CI.
- `jenkins/` and `scripts/`: Python standard-library automation for sample generation and releases. Dependency parsing uses the Kotlin CLI.

### Build and test

```bash
./gradlew :core:allTests :server:test :server:installDist
```

To run the browser and automation tests after building the distribution:

```bash
uv sync --frozen --dev
uv run playwright install chromium
uv run pytest
```

The shared core logic and tests live in `commonMain` and `commonTest`. JavaScript is a core test target; the frontend is maintained separately in `app/`. `pyproject.toml` and `uv.lock` manage test dependencies only.

### CLI

The installed distribution can run the server or the CLI, without Gradle:

```bash
server/build/install/gradle-dependency-viewer/bin/gradle-dependency-viewer
server/build/install/gradle-dependency-viewer/bin/gradle-dependency-viewer parse my_app.txt --output my_app.json
server/build/install/gradle-dependency-viewer/bin/gradle-dependency-viewer tree my_app.json --filter androidx --output filtered.json
server/build/install/gradle-dependency-viewer/bin/gradle-dependency-viewer tree my_app.json --project-only
server/build/install/gradle-dependency-viewer/bin/gradle-dependency-viewer graph my_app.json --distance 2 --exclude kotlin --output graph.json
server/build/install/gradle-dependency-viewer/bin/gradle-dependency-viewer enlist my_app.json --output dependencies.yaml
```

CLI commands print to stdout unless `--output` is supplied. `summary FILE` prints entry counts and validated sample metadata as JSON.

### Docker and deployment

```bash
docker build -t gradle-dependency-viewer .
docker run --rm -p 8000:8000 gradle-dependency-viewer
```

Docker builds and tests the JVM code, then copies the installed distribution into a Temurin 21 JRE image. It runs as UID 10001 and checks `/healthz`. Static assets and samples are packaged in the application resources. The server remains stateless and needs no data volume.

The server accepts these environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | HTTP port |
| `HOST` | `0.0.0.0` | Listen address |
| `JAVA_OPTS` | `-XX:MaxRAMPercentage=75.0 -XX:+ExitOnOutOfMemoryError` in Docker | JVM options; adjust alongside the container memory limit |

Rebuild and restart after changing bundled samples or frontend files. CSS and JS URLs include content hashes for cache invalidation. Ktor uses a 50 MiB multipart file limit; for larger reports, adjust `receiveMultipart` in `server/src/main/kotlin/dev/gradleviewer/Main.kt` and the reverse proxy upload limit together. The Docker host needs no Java or Python installation.

The deployment workflow runs on `v*` tags. It tests the Kotlin JVM code, publishes the image to GHCR, replaces the production container over SSH and waits for it to become healthy. Configure `SSH_HOST`, `SSH_USERNAME` and `SSH_KEY` in GitHub Actions secrets; registry access uses `GITHUB_TOKEN`.

The release version lives in `gradle.properties`. After committing application changes, run `python3 scripts/up_version.py` from the repository root to increment the patch version, commit it, create a `v*` tag and push the current branch and tag. Pushing the tag triggers production deployment.

### Generating a bundled sample (Jenkins)

`jenkins/generate-sample.Jenkinsfile` turns a public GitHub Android repository into a new sample in `app/static/sample/` and opens a pull request with it. It checks out the commit with git (without history, since some builds run git while Gradle configures them), checks that it is a Gradle project with a wrapper, works out the Gradle command to run (or takes it from `GRADLE_COMMAND`), runs it, converts the output to JSON, and deletes the downloaded project when it finishes. The sample's `meta` entry records the source repository and commit, and the app's launcher icon (a PNG or WebP bitmap from the app module, when it has one); the home page shows them with the sample. A new dump of a project replaces that project's older sample.

To set it up, create a Pipeline job ("Pipeline script from SCM") on this repository with the script path `jenkins/generate-sample.Jenkinsfile`, and add a "Username with password" credential with the ID `github-credentials` whose password is a GitHub token that can push branches and open pull requests (a non-dry run checks this before anything else runs). The job runs on the agent labelled `self` (an x86 machine), which needs `git`, `python3`, a JDK (21 or newer) and the [Antigravity](https://antigravity.google) CLI at `/home/fajar/.local/bin/agy` (the `AGY` variable in the Jenkinsfile), signed in for non-interactive use. Gradle runs directly on the agent, without Docker; the Android SDK is optional, because recent Android Gradle plugins can dump dependencies without it. Building a downloaded project runs its code as the Jenkins user, so use an agent you are comfortable running untrusted builds on.

| Parameter | Default | Purpose |
|---|---|---|
| `REPO_URL` | | e.g. `https://github.com/android/architecture-samples` |
| `GIT_REF` | `HEAD` | Branch, tag or commit |
| `SAMPLE_NAME` | repository name | Name shown on the home page |
| `GRADLE_COMMAND` | worked out from the Gradle files | Command whose output becomes the sample, e.g. `./gradlew app:dependencies --configuration debugRuntimeClasspath`. It must start with `./gradlew` and runs without a shell, so no redirects or pipes |
| `BASE_BRANCH` | `main` | Branch the pull request targets |
| `CACHE_GRADLE` | `true` | Keep Gradle's downloads on the agent between builds |
| `DRY_RUN` | `false` | Only build and archive the JSON |

With `CACHE_GRADLE` on, the Gradle distribution and dependencies stay in `~/.cache/gradle-dependency-viewer/gradle` on the agent, so only the first build of a project downloads everything. Builds run one at a time because they share that cache. To start over, delete that directory on the agent.

When `GRADLE_COMMAND` is blank, the job sends the project's Gradle files (`settings.gradle(.kts)`, `build.gradle(.kts)`, `gradle.properties`) to the Antigravity CLI and asks which module and debug runtime classpath configuration to dump, so no Gradle run is needed to find them. The CLI gets no tools and cannot run commands; its answer must still be a `./gradlew` command or the build fails. If it answers `UNKNOWN`, the build stops and names the reason, and you can re-run it with `GRADLE_COMMAND` set.

The orchestration steps are in `jenkins/generate_sample.py` and use the Python standard library. The pipeline builds the Kotlin CLI for parsing and summaries. Build it with `./gradlew :server:installDist` before running `convert` or `open-pr` locally, or set `VIEWER_CLI` to another installed distribution. Repository inspection works directly, for example `python3 jenkins/generate_sample.py validate path/to/project`.
