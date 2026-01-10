# Gradle Dependency Viewer

A simple tool to visualize gradle dependencies.

## Usage

1.  **Generate dependency tree:**

    ```bash
    ./gradlew app:dependencies > dependencies.txt
    ```

2.  **Parse the dependency file:**

    ```bash
    python parse.py
    ```

    This will create a `dependencies.json` file.

3.  **Filter the dependencies (optional):**

    ```bash
    python filter.py --file dependencies.json --filter <your-keywords>
    ```

    Replace `<your-keywords>` with a comma-separated list of keywords to filter by (e.g., `spring,google`).

4.  **View the result as horizontal tree graph:**

    Open `viewer.html` in your web browser to see the dependency graph as horizontal tree. (Requires the `.json` file from step 2).
  
5. **View the result as neural graph:**

    Open `graph_viewer.html` in your web browser to see the more flexible neural graph for larger dependencies. (Requires the `.json` file from step 2).

## Web Application

For a more interactive experience, you can run the FastAPI web server:

1.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the application (from the project root):**

    ```bash
    fastapi dev app/main.py
    ```

    *Note: If you don't have the `fastapi` CLI, you can use:*
    ```bash
    uvicorn app.main:app --reload
    ```

    *To run specifically from the `app` directory:*
    ```bash
    cd app
    uvicorn main:app --reload
    ```

3.  **Access the UI:**

    Go to [http://127.0.0.1:8000](http://127.0.0.1:8000). You can upload your `dependencies.txt` file here to visualize it without manual parsing.
