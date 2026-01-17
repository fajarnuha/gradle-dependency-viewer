import json
import argparse
from collections import defaultdict, deque
from utils import get_root_key_and_nodes

def traverse_tree(nodes, parent_id=None, graph_nodes=None, edges=None):
    """
    Recursively traverse the dependency tree and build graph representation.
    """
    if graph_nodes is None:
        graph_nodes = {}
    if edges is None:
        edges = defaultdict(set)
    
    for node in nodes:
        # Create unique node ID from module and version
        module = node.get('module', '')
        version = node.get('version', '')
        node_id = f"{module}:{version}" if version else module
        
        # If this node doesn't exist yet, create it
        if node_id not in graph_nodes:
            graph_nodes[node_id] = {
                'id': node_id,
                'module': module,
                'version': version,
                'resolution': node.get('resolution', ''),
                'full': node.get('full', ''),
                'parents': set(),
                'children': set()
            }
        
        # Add parent relationship if this node has a parent
        if parent_id:
            graph_nodes[node_id]['parents'].add(parent_id)
            graph_nodes[parent_id]['children'].add(node_id)
            edges[parent_id].add(node_id)
        
        # Recursively process children
        if 'children' in node and node['children']:
            traverse_tree(node['children'], node_id, graph_nodes, edges)
    
    return graph_nodes, edges

def convert_to_graph_format(graph_nodes, edges):
    """
    Convert internal graph representation to final JSON format.
    """
    # Convert to final node format (excluding parents/children since we have edges)
    nodes_list = []
    for node_id, node_data in graph_nodes.items():
        node_copy = {
            'id': node_data['id'],
            'module': node_data['module'],
            'version': node_data['version'],
            'resolution': node_data['resolution'],
            'full': node_data['full']
        }
        nodes_list.append(node_copy)
    
    # Convert edges to list format
    edges_list = []
    for parent, children in edges.items():
        for child in children:
            edges_list.append({
                'source': parent,
                'target': child
            })
    
    return {
        'nodes': nodes_list,
        'edges': edges_list,
        'metadata': {
            'total_nodes': len(nodes_list),
            'total_edges': len(edges_list)
        }
    }

def filter_graph_by_exclude(graph_nodes, edges, exclude_keyword):
    """
    Filter out nodes whose ID contains the exclude keyword and remove their edges.
    """
    if not exclude_keyword:
        return graph_nodes, edges
    
    # Find nodes to exclude
    nodes_to_exclude = set()
    for node_id in graph_nodes:
        if exclude_keyword in node_id:
            nodes_to_exclude.add(node_id)
    
    if not nodes_to_exclude:
        return graph_nodes, edges
    
    # Create new graph without excluded nodes
    filtered_nodes = {}
    filtered_edges = defaultdict(set)
    
    # Copy nodes that are not excluded
    for node_id, node_data in graph_nodes.items():
        if node_id not in nodes_to_exclude:
            # Create a copy of the node data
            filtered_node = {
                'id': node_data['id'],
                'module': node_data['module'],
                'version': node_data['version'],
                'resolution': node_data['resolution'],
                'full': node_data['full'],
                'parents': set(),
                'children': set()
            }
            
            # Update parent/child relationships, excluding removed nodes
            for parent in node_data['parents']:
                if parent not in nodes_to_exclude:
                    filtered_node['parents'].add(parent)
            
            for child in node_data['children']:
                if child not in nodes_to_exclude:
                    filtered_node['children'].add(child)
            
            filtered_nodes[node_id] = filtered_node
    
    # Copy edges that don't involve excluded nodes
    for source, targets in edges.items():
        if source not in nodes_to_exclude:
            for target in targets:
                if target not in nodes_to_exclude:
                    filtered_edges[source].add(target)
    
    return filtered_nodes, filtered_edges

def filter_graph_by_distance(graph_nodes, edges, max_distance):
    """
    Filter the graph to include only nodes within max_distance steps from the root.
    """
    root_id = "root:"
    if root_id not in graph_nodes:
        print("Warning: Root node not found in graph.")
        return graph_nodes, edges
    
    # BFS to calculate distances from root
    distances = {root_id: 0}
    queue = deque([root_id])
    
    while queue:
        current_node = queue.popleft()
        current_distance = distances[current_node]
        
        if current_distance < max_distance:
            # Add children to queue if within distance limit
            for child in graph_nodes[current_node]['children']:
                if child not in distances:
                    distances[child] = current_distance + 1
                    queue.append(child)
    
    # Filter nodes and edges based on distance
    filtered_nodes = {node_id: node_data for node_id, node_data in graph_nodes.items() 
                     if node_id in distances}
    
    filtered_edges = defaultdict(set)
    for parent, children in edges.items():
        if parent in distances:
            for child in children:
                if child in distances:
                    filtered_edges[parent].add(child)
    
    return filtered_nodes, filtered_edges

def process_data(dependency_data, distance=None, exclude=None):
    """
    Process dependency tree data into graph format with optional filtering.
    """
    # Extract root nodes
    _, root_nodes = get_root_key_and_nodes(dependency_data)
    if not root_nodes:
        return None
    
    # Build graph representation
    graph_nodes, edges = traverse_tree(root_nodes)
    
    # Add the single root node and connect it to first-level dependencies
    root_id = "root:"
    graph_nodes[root_id] = {
        'id': root_id,
        'module': 'root',
        'version': '',
        'resolution': '',
        'full': 'root',
        'parents': set(),
        'children': set()
    }
    
    # Connect root to all first-level nodes
    first_level_nodes = []
    for node_id, node_data in graph_nodes.items():
        if node_id != root_id and len(node_data['parents']) == 0:
            first_level_nodes.append(node_id)
    
    for node_id in first_level_nodes:
        graph_nodes[root_id]['children'].add(node_id)
        graph_nodes[node_id]['parents'].add(root_id)
        edges[root_id].add(node_id)
    
    # Apply exclude filtering
    if exclude:
        graph_nodes, edges = filter_graph_by_exclude(graph_nodes, edges, exclude)
    
    # Apply distance filtering
    if distance is not None:
        graph_nodes, edges = filter_graph_by_distance(graph_nodes, edges, distance)
    
    # Convert to final format
    return convert_to_graph_format(graph_nodes, edges)

def main():
    """Main function to convert dependency tree to graph representation."""
    parser = argparse.ArgumentParser(description='Convert dependency tree JSON to graph representation')
    parser.add_argument('input_file', help='Path to the input dependency JSON file')
    parser.add_argument('-o', '--output', help='Output graph JSON file path (default: input_file_graph.json)')
    parser.add_argument('-d', '--distance', type=int, help='Maximum distance from root to include nodes (default: no limit)')
    parser.add_argument('-e', '--exclude', help='Exclude nodes whose ID contains this keyword')
    args = parser.parse_args()
    
    # Determine output file path
    if args.output:
        output_path = args.output
    else:
        base_name = args.input_file.rsplit('.', 1)[0]
        output_path = f"{base_name}_graph.json"
    
    # Read input JSON file
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            dependency_data = json.load(f)
    except Exception as e:
        print(f"Error reading {args.input_file}: {e}")
        return
    
    print(f"Converting dependency tree to graph representation...")
    
    graph_data = process_data(dependency_data, distance=args.distance, exclude=args.exclude)
    
    if not graph_data:
        print("Warning: No graph data generated.")
        return
    
    # Write output file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, indent=2)
        
        print(f"Successfully converted to graph representation:")
        print(f"  - Total unique nodes: {graph_data['metadata']['total_nodes']}")
        print(f"  - Total edges: {graph_data['metadata']['total_edges']}")
        print(f"  - Output written to: {output_path}")
        
    except Exception as e:
        print(f"Error writing to {output_path}: {e}")
        return

if __name__ == "__main__":
    main()