import copy
import json
import argparse

def find_matches_and_relatives(nodes, keywords, kept_nodes, ancestors):
    """
    Recursively traverses the tree to find nodes that match the keyword,
    and adds them, their ancestors, and their direct children to the kept_nodes set.
    """
    for node in nodes:
        current_path = ancestors + [node]
        if any(keyword.lower() in node.get('module', '').lower() for keyword in keywords):
            for n in current_path:
                kept_nodes.add(n['full'])
            for child in node.get('children', []):
                kept_nodes.add(child['full'])
        
        find_matches_and_relatives(node.get('children', []), keywords, kept_nodes, current_path)

def rebuild_tree(nodes, kept_nodes):
    """
    Recursively rebuilds the tree, only including nodes whose 'full' identifier
    is in the kept_nodes set.
    """
    new_tree = []
    for node in nodes:
        if node['full'] in kept_nodes:
            new_node = copy.deepcopy(node)
            new_node['children'] = rebuild_tree(node.get('children', []), kept_nodes)
            new_tree.append(new_node)
    return new_tree

def filter_dependencies(root_nodes, keywords):
    """
    Filters the dependency tree based on a list of keywords.
    """
    kept_nodes = set()
    find_matches_and_relatives(root_nodes, keywords, kept_nodes, [])
    return rebuild_tree(root_nodes, kept_nodes)

def filter_project_only(nodes):
    """
    Filters the dependency tree to only include project dependencies.
    Project dependencies start with 'project'.
    Recursively removes all external dependencies from children.
    """
    project_nodes = []
    for node in nodes:
        if node.get('module', '').startswith('project '):
            # Create a deep copy and recursively filter children
            project_node = copy.deepcopy(node)
            project_node['children'] = filter_project_only(node.get('children', []))
            project_nodes.append(project_node)
    return project_nodes

def main():
    """Main function to read, filter, and write dependencies."""
    parser = argparse.ArgumentParser(description='Filter a dependency JSON file.')
    parser.add_argument('--file', type=str, required=True, help='The path to the dependency JSON file.')
    parser.add_argument('--filter', type=str, help='A comma-separated list of keywords to filter the dependency tree.')
    parser.add_argument('--project-only', '-p', action='store_true', help='Filter to show only project dependencies.')
    args = parser.parse_args()
    
    if not args.filter and not args.project_only:
        parser.error('Either --filter or --project-only must be specified.')

    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            dependency_graph = json.load(f)
    except FileNotFoundError:
        print(f"Error: {args.file} not found.")
        return
    except Exception as e:
        print(f"Error reading {args.file}: {e}")
        return

    root_nodes = dependency_graph.get('root', [])
    
    if args.project_only:
        print("Filtering dependencies to show only project dependencies")
        filtered_nodes = filter_project_only(root_nodes)
        base_name = args.file.rsplit('.', 1)[0]
        output_filename = f"{base_name}_project-only.json"
    else:
        keywords = [k.strip() for k in args.filter.split(',')]
        print(f"Filtering dependencies with keywords: {keywords}")
        filtered_nodes = filter_dependencies(root_nodes, keywords)
        base_name = args.file.rsplit('.', 1)[0]
        filter_name = args.filter.replace(',', '_')
        output_filename = f"{base_name}_{filter_name}.json"
    
    dependency_graph['root'] = filtered_nodes

    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(dependency_graph, f, indent=2)

    print(f"Successfully created filtered file: {output_filename}")

if __name__ == "__main__":
    main()