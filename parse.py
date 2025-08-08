import json
import argparse
import os
from utils import parse_dependency_line




def parse_dependencies(lines):
    """Parses the dependency tree and returns a list of root nodes."""
    root_nodes = []
    node_stack = []  # Stack to keep track of (node, level)

    parsing = False
    for line in lines:
        line = line.rstrip()
        if 'compileclasspath' in line.lower() or 'runtimeclasspath' in line.lower():
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
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        try:
            with open(input_path, 'r', encoding='utf-16') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading {input_path} with utf-16: {e}")
            return
    except FileNotFoundError:
        print(f"Error: {input_path} not found.")
        return
    except Exception as e:
        print(f"Error reading {input_path}: {e}")
        return

    root_nodes = parse_dependencies(lines)

    dependency_graph = {"root": root_nodes}

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dependency_graph, f, indent=2)

    print(f"Successfully parsed {input_path} and created {output_path}")

if __name__ == "__main__":
    main()