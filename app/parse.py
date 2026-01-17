import json
import argparse
import os
import re
from utils import parse_dependency_line




def extract_project_name(lines):
    """Extracts the project name from the lines (e.g., Project ':app' -> 'app')."""
    for line in lines:
        match = re.search(r"^Project ':([^']+)'", line.strip())
        if match:
            return match.group(1)
    return "root"


def parse_dependencies(lines):
    """Parses the dependency tree and returns a list of root nodes."""
    root_nodes = []
    node_stack = []  # Stack to keep track of (node, level)

    parsing = False
    for line in lines:
        line = line.rstrip()
        if re.match(r'^\w+(Runtime|Compile)Classpath', line):
            parsing = True
            continue

        if not parsing or not line.strip() or '---' not in line:
            continue

        node, level = parse_dependency_line(line)
        if not node:
            continue

        # Pop from stack until we find the correct parent for the current node's level
        while node_stack and node_stack[-1][1] >= level:
            node_stack.pop()

        if not node_stack:
            # This is a root node
            root_nodes.append(node)
        else:
            # This is a child of the last node left on the stack
            parent_node = node_stack[-1][0]
            parent_node['children'].append(node)

        # Push the current node onto the stack to be a potential parent
        node_stack.append((node, level))

    return root_nodes



def main():
    """Main function to read, parse, and write dependencies."""
    parser = argparse.ArgumentParser(description='Parse Gradle dependency tree from text file')
    parser.add_argument('file_path', help='Path to the input file (txt or no extension)')
    args = parser.parse_args()
    
    input_path = args.file_path
    
    # Determine output path: same path and filename with .json suffix
    base_path = os.path.splitext(input_path)[0]
    output_path = base_path + '.json'
    
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    encodings = ["utf-8-sig", "utf-16", "cp1252", "latin-1"]
    lines = None
    for encoding in encodings:
        try:
            with open(input_path, 'r', encoding=encoding) as f:
                lines = f.readlines()
            break
        except (UnicodeDecodeError, LookupError):
            continue
        except Exception as e:
            print(f"Error reading {input_path} with {encoding}: {e}")
            return

    if lines is None:
        print(f"Error: Could not decode {input_path} with common encodings.")
        return

    project_name = extract_project_name(lines)
    root_nodes = parse_dependencies(lines)

    dependency_graph = {project_name: root_nodes}

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dependency_graph, f, indent=2)

    print(f"Successfully parsed {input_path} and created {output_path}")

if __name__ == "__main__":
    main()