import json
import re

def parse_dependency_line(line):
    """Parses a single line of gradle dependency output, extracting the node and its level."""
    # The level is determined by the indentation and tree structure.
    # A common pattern is '|    ' or '     ' (5 spaces) per level.
    # We find the start of the dependency text itself.
    
    level = 0
    for i, char in enumerate(line):
        if char not in ' |\+-':
            level = i
            break
    
    # The actual dependency string starts after the tree markers
    match = re.search(r'--- (.*)', line)
    if not match:
        return None, -1

    full_dependency = match.group(1).strip()

    module = ""
    version = ""

    # Check for version change '->'
    if ' -> ' in full_dependency:
        parts = full_dependency.split(' -> ')
        module_part = parts[0]
        version_part = parts[1]

        # Module is the part before the arrow, stripped of any version info it might have
        module_parts = module_part.split(':')
        if len(module_parts) > 2:
            module = f"{module_parts[0]}:{module_parts[1]}"
        else:
            module = module_part
        
        # Version is the part after the arrow
        version_match = re.search(r'([\d\.\-a-zA-Z]+)', version_part)
        if version_match:
            version = version_match.group(1)
    else:
        # No version change
        parts = full_dependency.split(':')
        if len(parts) > 2:
            module = f"{parts[0]}:{parts[1]}"
            version_part = parts[2]
            version_match = re.search(r'([\d\.\-a-zA-Z]+)', version_part)
            if version_match:
                version = version_match.group(1)
        else:
            # This could be a module without a version, or something else.
            module = full_dependency

    resolution = ""
    resolution_match = re.search(r'\(([*+c])\)', full_dependency)
    if resolution_match:
        resolution = resolution_match.group(1)

    node = {
        "module": module,
        "version": version,
        "resolution": resolution,
        "full": full_dependency,
        "children": []
    }
    return node, level


def parse_dependencies(lines):
    """Parses the dependency tree and returns a list of root nodes."""
    root_nodes = []
    node_stack = []  # Stack to keep track of (node, level)

    parsing = False
    for line in lines:
        line = line.rstrip()
        if 'compileClasspath'.lower() in line.lower():
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
    try:
        with open('dependencies.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        try:
            with open('dependencies.txt', 'r', encoding='utf-16') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading dependencies.txt with utf-16: {e}")
            return
    except FileNotFoundError:
        print("Error: dependencies.txt not found.")
        return
    except Exception as e:
        print(f"Error reading dependencies.txt: {e}")
        return

    root_nodes = parse_dependencies(lines)

    dependency_graph = {"root": root_nodes}

    with open('dependencies.json', 'w', encoding='utf-8') as f:
        json.dump(dependency_graph, f, indent=2)

    print("Successfully parsed dependencies.txt and created dependencies.json")

if __name__ == "__main__":
    main()