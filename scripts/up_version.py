import re
import subprocess
import sys
from pathlib import Path

def run_command(command):
    try:
        subprocess.run(command, check=True, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        sys.exit(1)

def main():
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("pyproject.toml not found.")
        sys.exit(1)

    content = pyproject_path.read_text(encoding="utf-8")
    
    # Regex to find version = "x.y.z"
    match = re.search(r'^version = "(\d+)\.(\d+)\.(\d+)"', content, re.MULTILINE)
    if not match:
        print("Could not find version in pyproject.toml")
        sys.exit(1)

    major, minor, patch = map(int, match.groups())
    
    # Increment patch version (default behavior)
    new_version = f"{major}.{minor}.{patch + 1}"
    
    new_content = content.replace(f'version = "{major}.{minor}.{patch}"', f'version = "{new_version}"')
    pyproject_path.write_text(new_content, encoding="utf-8")
    
    print(f"Bumped version from {major}.{minor}.{patch} to {new_version}")

    # Git operations
    run_command(f'git add pyproject.toml')
    run_command(f'git commit -m "Bump version to v{new_version}"')
    run_command(f'git tag v{new_version}')
    
    print("Pushing to remote...")
    run_command('git push')
    run_command('git push --tags')
    
    print("Done!")

if __name__ == "__main__":
    main()
