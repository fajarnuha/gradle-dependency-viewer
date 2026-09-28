# Gradle Dependency Viewer

A powerful and intuitive tool to visualize Gradle dependencies as interactive graphs. **This tool requires the output of the Gradle `dependencies` task saved as a text file.**

![Graph Viewer](screenshot/graph_viewer.png)

## Getting Started

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) (recommended for dependency management)

### Running the Web Application

To start the server in development mode:

```bash
uv run uvicorn app.main:app --reload
```

Access the UI at [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Usage Guide

### 1. Generate Dependency File
Run the following command in your Gradle project root to generate a text file of your dependencies.

**Note:** The configuration name (e.g., `debugRuntimeClasspath`) varies depending on your project's build variants and flavors. Check your available configurations by running `./gradlew app:dependencies` without arguments first to decide which one you want to visualize.

```bash
./gradlew app:dependencies --configuration debugRuntimeClasspath > my_app.txt
```

### 2. Upload and Visualize
1. Open the web app in your browser.
2. Drag and drop or click to upload your `my_app.txt`.
3. The app will automatically parse the file and redirect you to the visualization.

### 3. Navigation and Features
- **Pre-Compiled Open Source Projects**: The landing page lists ready-to-explore dependency trees of open source Android projects (from `app/static/sample/`), so you can try the viewers without uploading anything.
- **Stateless**: The app never stores your data. An uploaded TXT is parsed on the fly and the result is kept only in your browser tab (`sessionStorage`); closing the tab discards it.
- **Tree Viewer**: Provides a hierarchical view of dependencies, perfect for understanding the structure of your project.
  ![Tree Viewer](screenshot/tree_viewer.png)
- **Graph Viewer**: Offers a flexible, interactive neural graph visualization. Great for identifying complex relationship webs and transitive dependencies.
- **Search and Filter**: Both viewers support filtering. Enter a keyword (e.g., `androidx`, `:module-name`) to highlight matching nodes and their connections, making it easy to trace specific dependencies.

## Development

### Manual CLI Parsing (Optional)
While the web app handles parsing automatically, you can still use the core scripts manually:

```bash
uv run python app/parse.py path/to/my_app.txt
```

### Generating a Pre-Compiled Sample (Jenkins)
`jenkins/generate-sample.Jenkinsfile` turns a public GitHub Android repository into a new sample in `app/static/sample/` and opens a pull request with it. It checks out the commit with git (without history, since some builds run git while Gradle configures them), checks that it is a Gradle project with a wrapper, works out the Gradle command to run (or takes it from `GRADLE_COMMAND`), runs it, converts the output to JSON, and deletes the downloaded project when it finishes. The sample's `meta` entry records the source repository and commit, and the app's launcher icon (a PNG or WebP bitmap from the app module, when it has one); the home page shows them with the sample. A new dump of a project replaces that project's older sample.

To set it up, create a Pipeline job ("Pipeline script from SCM") on this repository with the script path `jenkins/generate-sample.Jenkinsfile`, and add a "Username with password" credential with the ID `github-credentials` whose password is a GitHub token that can push branches and open pull requests (a non-dry run checks this before anything else runs). The job runs on the agent labelled `self` (an x86 machine), which needs `git`, `python3`, a JDK (17 or newer) and the [Antigravity](https://antigravity.google) CLI at `/home/fajar/.local/bin/agy` (the `AGY` variable in the Jenkinsfile), signed in for non-interactive use. Gradle runs directly on the agent, without Docker; the Android SDK is optional, because recent Android Gradle plugins can dump dependencies without it. Building a downloaded project runs its code as the Jenkins user, so use an agent you are comfortable running untrusted builds on.

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

The steps are in `jenkins/generate_sample.py` (standard library only), so you can run them locally too, e.g. `python3 jenkins/generate_sample.py validate path/to/project`.
