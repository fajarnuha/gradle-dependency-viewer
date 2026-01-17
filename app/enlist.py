import json
import yaml
import argparse
import os
from utils import get_root_key_and_nodes

def collect_dependencies(node, dependencies_set):
    """Recursively collect all dependencies from the JSON structure."""
    if not isinstance(node, dict):
        return
    
    # If this node has module and version, add it to the set
    if 'module' in node and 'version' in node and node['version']:
        # Concatenate module and version to create unique dependency identifier
        dependency = f"{node['module']}:{node['version']}"
        dependencies_set.add(dependency)
    
    # Recursively process children
    if 'children' in node and isinstance(node['children'], list):
        for child in node['children']:
            collect_dependencies(child, dependencies_set)

def extract_dependencies_from_json(json_data):
    """Extract all unique dependencies from the JSON structure."""
    dependencies_set = set()
    
    # Process root nodes
    _, root_nodes = get_root_key_and_nodes(json_data)
    for root_node in root_nodes:
        collect_dependencies(root_node, dependencies_set)
    
    return sorted(list(dependencies_set))

def main():
    """Main function to read JSON and output YAML."""
    parser = argparse.ArgumentParser(description='Extract dependencies from JSON and output to YAML')
    parser.add_argument('json_file', help='Path to the input JSON file')
    parser.add_argument('-o', '--output', help='Output YAML file path (default: dependencies.yaml)', 
                       default='dependencies.yaml')
    args = parser.parse_args()
    
    # Read JSON file
    try:
        with open(args.json_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {args.json_file} not found.")
        return
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return
    except Exception as e:
        print(f"Error reading {args.json_file}: {e}")
        return
    
    # Extract dependencies
    dependencies = extract_dependencies_from_json(json_data)
    
    # Create YAML structure
    yaml_data = {
        'dependencies': dependencies,
        'total_count': len(dependencies)
    }
    
    # Write to YAML file
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
        
        print(f"Successfully extracted {len(dependencies)} unique dependencies")
        print(f"Output written to: {args.output}")
        
    except Exception as e:
        print(f"Error writing to {args.output}: {e}")
        return

if __name__ == "__main__":
    main()