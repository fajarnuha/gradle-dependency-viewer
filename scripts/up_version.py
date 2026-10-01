import re
import subprocess
import sys
from pathlib import Path

def run_command(command):
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        sys.exit(1)

def main():
    version_path = Path("gradle.properties")
    if not version_path.exists():
        print("gradle.properties not found.")
        sys.exit(1)

    content = version_path.read_text(encoding="utf-8")
    
    match = re.search(r'^version=(\d+)\.(\d+)\.(\d+)$', content, re.MULTILINE)
    if not match:
        print("Could not find version in gradle.properties")
        sys.exit(1)

    major, minor, patch = map(int, match.groups())
    
    # Increment patch version (default behavior)
    new_version = f"{major}.{minor}.{patch + 1}"
    
    new_content = re.sub(r'^version=\d+\.\d+\.\d+$', f'version={new_version}', content, flags=re.MULTILINE)
    version_path.write_text(new_content, encoding="utf-8")
    
    print(f"Bumped version from {major}.{minor}.{patch} to {new_version}")

    # Git operations
    run_command(['git', 'add', 'gradle.properties'])
    run_command(['git', 'commit', '-m', f'Bump version to v{new_version}'])
    run_command(['git', 'tag', f'v{new_version}'])
    
    print("Pushing to remote...")
    run_command(['git', 'push'])
    run_command(['git', 'push', 'origin', f'v{new_version}'])
    
    print("Done!")

if __name__ == "__main__":
    main()
