import networkx as nx
from typing import Dict, Any, List, Tuple

from services.room_taxonomy import resolve_room_type, get_room_meta

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
            canonical = resolve_room_type(node_id)
            meta = get_room_meta(canonical)
            graph_nodes.append({
                "id": node_id,
                "type": canonical,
                "zone": meta.get("zone", "public"),
                "min_area": data.get("min_area", meta.get("min_area", 10.0)),
                "weight": meta.get("weight", 16.0),
                "color": data.get("color", meta.get("color", [200, 200, 200])),
                "hex_color": meta.get("hex_color", "#c8c8c8"),
                "label": meta.get("label", canonical.replace("_", " ").upper()),
                "furniture": meta.get("furniture", []),
                "windows": meta.get("windows", "partial"),
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
        """
        Validates architecture layout constraints using taxonomy zone data.
        Accepts any valid room combination, not just standard bedroom/bathroom layouts.
        """
        errors = []
        warnings = []
        nodes = graph_data.get("nodes", [])
        is_planar = graph_data.get("is_planar", True)

        if not is_planar:
            warnings.append("Layout graph is non-planar; intersecting room paths might exist.")

        # Collect zones and canonical types
        zones_present = {n.get("zone", "public") for n in nodes}
        types_present = {resolve_room_type(n["type"]) for n in nodes}

        # Warn (not error) if standard zones are fully absent
        if "private" not in zones_present:
            warnings.append("No private zone rooms (e.g. bedroom). Plan may lack sleeping areas.")
        if "public" not in zones_present and "service" not in zones_present:
            warnings.append("No public or service zone rooms detected.")

        # Minimum room count
        if len(nodes) < 1:
            errors.append("No rooms defined in the layout.")

        all_messages = errors + warnings
        return len(errors) == 0, all_messages

graph_service = SpatialGraphService()
