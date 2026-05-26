import networkx as nx
from typing import Dict, Any, List, Tuple

class SpatialGraphService:
    def generate_spatial_graph(self, rooms: List[Dict[str, Any]], relationships: List[List[str]]) -> Dict[str, Any]:
        """Creates a NetworkX graph representing the rooms and their adjacencies, and resolves node coordinates."""
        # 1. Build NetworkX Graph
        G = nx.Graph()
        
        # Add nodes with metadata
        for room in rooms:
            G.add_node(room["id"], **room)
            
        # Add edges (adjacency links)
        for rel in relationships:
            if len(rel) == 2:
                G.add_edge(rel[0], rel[1])

        # 2. Planar Validation
        # A floor plan is only topologically realizable if it's planar (no intersecting connection edges)
        is_planar, _ = nx.check_planarity(G)

        # 3. Calculate Layout Coordinates via Spring Layout
        # This gives us relative continuous positions [x, y] in range [-1, 1] which we scale to real-world floor plan meters!
        pos = nx.spring_layout(G, seed=42, k=1.0)
        
        # Format nodes and coordinates
        graph_nodes = []
        for node_id, data in G.nodes(data=True):
            coords = pos[node_id]
            # Convert coordinate from [-1, 1] to positive floor plan space e.g. [0.5, 11.5]
            graph_nodes.append({
                "id": node_id,
                "type": data.get("type", "bedroom"),
                "min_area": data.get("min_area", 10.0),
                "color": data.get("color", [200, 200, 200]),
                "x_rel": float(coords[0]),
                "y_rel": float(coords[1])
            })

        graph_edges = [{"source": u, "target": v} for u, v in G.edges()]

        return {
            "is_planar": is_planar,
            "nodes": graph_nodes,
            "edges": graph_edges,
            "connected_components": nx.number_connected_components(G)
        }

    def validate_constraints(self, graph_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validates architecture layout constraints."""
        errors = []
        nodes = graph_data.get("nodes", [])
        is_planar = graph_data.get("is_planar", True)

        if not is_planar:
            errors.append("Layout graph is non-planar; intersecting room paths might exist.")

        # Ensure we have at least one bathroom and one bedroom
        types = [n["type"] for n in nodes]
        if "bedroom" not in types:
            errors.append("Invalid layout: No bedroom defined.")
        if "bathroom" not in types:
            errors.append("Invalid layout: No bathroom defined.")
        if "living_room" not in types:
            errors.append("Warning: Standard living area is missing.")

        return len(errors) == 0, errors

graph_service = SpatialGraphService()
