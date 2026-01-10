# Gradle Dependency Viewer

A powerful and intuitive tool to visualize Gradle dependencies as interactive graphs.

## App Architecture

The project is structured to separate the core logic from the web application interface:

- `app/`: The main application package.
  - `main.py`: FastAPI application and API endpoints.
  - `parse.py`: Core logic for parsing Gradle dependency output (`.txt`).
  - `convert_to_graph.py`: Logic for transforming parsed data into graph formats.
  - `utils.py`: Shared utility functions.
  - `static/`: Static assets (JS, CSS, images).
  - `templates/`: Jinja2 HTML templates.
  - `viz/`: HTML-based visualization components.
- `tests/`: Automated test suite for both CLI logic and API endpoints.
- `.github/workflows/`: CI/CD pipeline configuration.
- `Dockerfile`: Containerization configuration using `uv`.

## Getting Started

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) (recommended for dependency management)

### Running the Web Application

#### Using uv (Recommended)

To start the server in development mode:

```bash
uv run uvicorn app.main:app --reload
```

#### Using Docker

Build and run the container:

```bash
docker build -t gradle-dependency-viewer .
docker run -p 8000:8000 gradle-dependency-viewer
```

Access the UI at [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Usage Guide

### 1. Generate Dependency File
Run the following command in your Gradle project root to generate a text file of your dependencies:

```bash
./gradlew app:dependencies > dependencies.txt
```

### 2. Upload and Visualize
1. Open the web app in your browser.
2. Drag and drop or click to upload your `dependencies.txt`.
3. The app will automatically parse the file and redirect you to the visualization.

### 3. Navigation and Features
- **File History**: The landing page shows a history of uploaded files. You can revisit any previous visualization or delete old files.
- **Tree Viewer**: Provides a hierarchical view of dependencies, perfect for understanding the structure of your project.
- **Graph Viewer**: Offers a flexible, interactive neural graph visualization. Great for identifying complex relationship webs and transitive dependencies.
- **Search and Filter**: Both viewers support filtering to find specific artifacts or groups.

## Development

### Running Tests
To run the full test suite:

```bash
uv run pytest
```

### Manual CLI Parsing (Optional)
While the web app handles parsing automatically, you can still use the core scripts manually:

```bash
uv run python app/parse.py path/to/dependencies.txt
```
