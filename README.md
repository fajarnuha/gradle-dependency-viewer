# Gradle Dependency Viewer

A simple tool to visualize gradle dependencies.

## Usage

1.  **Generate dependency tree:**

    ```bash
    ./gradlew dependencies > dependencies.txt
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

    Open `viewer.html` in your web browser to see the dependency graph as horizontal tree
  
5. **Vew the result as neural graph**

    Open 'graph_viewer.html` in your web vrowser to see the more flexible neural graph for a larger dependencies
