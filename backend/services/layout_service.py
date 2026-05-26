import math
import random
import io
import json
from typing import Dict, Any, List, Tuple
import numpy as np

class LayoutGenerationService:
    ROOM_WEIGHTS = {
        "living_room": 35.0,
        "bedroom": 22.0,
        "dining_room": 16.0,
        "kitchen": 16.0,
        "garage": 26.0,
        "bathroom": 8.0,
        "balcony": 8.0,
        "corridor": 10.0,
        "hallway": 10.0,
        "entrance": 8.0
    }

    def _get_base_type(self, room_id: str) -> str:
        """Helper to extract general room category from identifier."""
        room_id_lower = room_id.lower()
        for key in ["bedroom", "bathroom", "kitchen", "living_room", "dining_room", "garage", "balcony", "corridor", "hallway", "entrance"]:
            if key in room_id_lower:
                return key
        return "bedroom"

    def _classify_zoning(self, nodes: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Classifies rooms into Architectural Zones (Public, Private, Service)."""
        zones = {"public": [], "private": [], "service": []}
        for node in nodes:
            base_type = self._get_base_type(node.get("id", "bedroom"))
            if base_type in ["bedroom", "balcony"]:
                zones["private"].append(node)
            elif base_type in ["bathroom"]:
                # If there are multiple bathrooms, allocate the first as common (service) and others as private (ensuite).
                # If only one bathroom, classify as private so it clusters with bedrooms.
                existing_bathrooms = [n for n in nodes if self._get_base_type(n.get("id", "")) == "bathroom"]
                if len(existing_bathrooms) > 1 and node == existing_bathrooms[0]:
                    zones["service"].append(node)
                else:
                    zones["private"].append(node)
            elif base_type in ["kitchen"]:
                zones["service"].append(node)
            elif base_type in ["living_room", "dining_room", "garage", "entrance"]:
                zones["public"].append(node)
            else:
                zones["public"].append(node)
        return zones

    def _partition_rooms(self, rooms_list: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Greedily balances rooms into two lists of roughly equal weights for balanced BSP partitioning."""
        sorted_rooms = sorted(rooms_list, key=lambda r: self.ROOM_WEIGHTS.get(self._get_base_type(r.get("id", "")), 16.0), reverse=True)
        g1, g2 = [], []
        w1, w2 = 0.0, 0.0
        for r in sorted_rooms:
            weight = self.ROOM_WEIGHTS.get(self._get_base_type(r.get("id", "")), 16.0)
            if w1 <= w2:
                g1.append(r)
                w1 += weight
            else:
                g2.append(r)
                w2 += weight
        return g1, g2

    def _get_safe_split_pos(self, start: int, end: int, ratio: float, min_dim: int = 75) -> int:
        """Returns a split position constrained by a minimum dimension threshold to prevent too narrow rooms."""
        total_dim = end - start
        if total_dim <= 2 * min_dim:
            return start + total_dim // 2
        split_pos = start + int(total_dim * ratio)
        if split_pos - start < min_dim:
            split_pos = start + min_dim
        elif end - split_pos < min_dim:
            split_pos = end - min_dim
        return split_pos

    def _subdivide(self, box: List[int], rooms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Recursive Binary Space Partitioning (BSP) subdivisions for room cells."""
        if not rooms:
            return []
            
        if len(rooms) == 1:
            room = rooms[0].copy()
            room["box"] = box
            return [room]
            
        g1, g2 = self._partition_rooms(rooms)
        if not g1:
            return self._subdivide(box, g2)
        if not g2:
            return self._subdivide(box, g1)
            
        w = box[2] - box[0]
        h = box[3] - box[1]
        
        w1 = sum(self.ROOM_WEIGHTS.get(self._get_base_type(r.get("id", "")), 16.0) for r in g1)
        w2 = sum(self.ROOM_WEIGHTS.get(self._get_base_type(r.get("id", "")), 16.0) for r in g2)
        ratio = w1 / (w1 + w2) if (w1 + w2) > 0 else 0.5
        ratio = max(0.3, min(0.7, ratio))
        
        # Decide if we should inject a corridor slice for circulation (only for large groups)
        insert_corridor = len(rooms) >= 3 and min(w, h) > 160
        
        if insert_corridor:
            corr_size = 45  # ~0.9 meters
            if w > h:
                # Horizontal corridor running perpendicular through vertical room slices
                corr_box = [box[0], box[1] + (h - corr_size) // 2, box[2], box[1] + (h - corr_size) // 2 + corr_size]
                box_top = [box[0], box[1], box[2], corr_box[1]]
                box_bottom = [box[0], corr_box[3], box[2], box[3]]
                
                # Check for explicit corridor in rooms
                corridor_node = None
                for r in rooms:
                    if self._get_base_type(r.get("id", "")) in ["corridor", "hallway"]:
                        corridor_node = r.copy()
                        rooms.remove(r)
                        g1, g2 = self._partition_rooms(rooms)
                        break
                        
                if not corridor_node:
                    corridor_node = {
                        "id": f"corridor_{random.randint(100, 999)}",
                        "type": "corridor",
                        "color": [245, 245, 245]
                    }
                corridor_node["box"] = corr_box
                
                res = [corridor_node]
                if g1:
                    res.extend(self._subdivide(box_top, g1))
                if g2:
                    res.extend(self._subdivide(box_bottom, g2))
                return res
            else:
                # Vertical corridor split
                corr_box = [box[0] + (w - corr_size) // 2, box[1], box[0] + (w - corr_size) // 2 + corr_size, box[3]]
                box_left = [box[0], box[1], corr_box[0], box[3]]
                box_right = [corr_box[2], box[1], box[2], box[3]]
                
                corridor_node = None
                for r in rooms:
                    if self._get_base_type(r.get("id", "")) in ["corridor", "hallway"]:
                        corridor_node = r.copy()
                        rooms.remove(r)
                        g1, g2 = self._partition_rooms(rooms)
                        break
                        
                if not corridor_node:
                    corridor_node = {
                        "id": f"corridor_{random.randint(100, 999)}",
                        "type": "corridor",
                        "color": [245, 245, 245]
                    }
                corridor_node["box"] = corr_box
                
                res = [corridor_node]
                if g1:
                    res.extend(self._subdivide(box_left, g1))
                if g2:
                    res.extend(self._subdivide(box_right, g2))
                return res
        else:
            # Standard split without corridor
            if w > h:
                split_x = self._get_safe_split_pos(box[0], box[2], ratio, min_dim=75)
                box1 = [box[0], box[1], split_x, box[3]]
                box2 = [split_x, box[1], box[2], box[3]]
                return self._subdivide(box1, g1) + self._subdivide(box2, g2)
            else:
                split_y = self._get_safe_split_pos(box[1], box[3], ratio, min_dim=75)
                box1 = [box[0], box[1], box[2], split_y]
                box2 = [box[0], split_y, box[2], box[3]]
                return self._subdivide(box1, g1) + self._subdivide(box2, g2)

    def _subdivide_zone(self, box: List[int], rooms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Subdivides a specific architectural zone boundary into its constituent rooms."""
        if not rooms:
            return []
        return self._subdivide(box, rooms)

    def _merge_segments(self, segments: List[Tuple[int, int, int, bool]]) -> List[Tuple[int, int, int, bool]]:
        """Merges collinear overlapping or touching wall intervals into clean continuous lines."""
        if not segments:
            return []
        by_coord = {}
        for coord, min_val, max_val, is_ext in segments:
            by_coord.setdefault(coord, []).append((min_val, max_val, is_ext))
            
        merged = []
        for coord, intervals in by_coord.items():
            intervals.sort(key=lambda x: x[0])
            curr_start, curr_end, curr_ext = intervals[0]
            for start, end, is_ext in intervals[1:]:
                if start <= curr_end:
                    curr_end = max(curr_end, end)
                    curr_ext = curr_ext or is_ext
                else:
                    merged.append((coord, curr_start, curr_end, curr_ext))
                    curr_start, curr_end, curr_ext = start, end, is_ext
            merged.append((coord, curr_start, curr_end, curr_ext))
        return merged

    def _generate_candidate(self, nodes: List[Dict[str, Any]], relationships: List[Any], prompt_style: str, seed: int) -> Dict[str, Any]:
        """Generates a high-quality coordinate layout candidate using Binary Space Partitioning and zoning."""
        random.seed(seed)
        np.random.seed(seed)
        
        # 1. Zoning
        zones = self._classify_zoning(nodes)
        
        active_zones = {}
        for zone_name, zone_nodes in zones.items():
            if zone_nodes:
                weight_sum = sum(self.ROOM_WEIGHTS.get(self._get_base_type(n.get("id", "")), 16.0) for n in zone_nodes)
                active_zones[zone_name] = {
                    "nodes": zone_nodes,
                    "weight": weight_sum
                }
                
        # 2. Outer Building boundary settings
        master_width = 800
        master_height = 600
        scale = 50
        
        margin_x = random.randint(70, 95)
        margin_y = random.randint(70, 95)
        bx1 = margin_x
        by1 = margin_y
        bx2 = master_width - margin_x
        by2 = master_height - margin_y
        
        total_active_weight = sum(info["weight"] for info in active_zones.values())
        if total_active_weight == 0:
            total_active_weight = 1.0
            
        # 3. First-Level Subdivision
        zone_boxes = {}
        remaining_box = [bx1, by1, bx2, by2]
        sorted_zone_names = [z for z in ["public", "private", "service"] if z in active_zones]
        
        for idx, zone_name in enumerate(sorted_zone_names):
            if idx == len(sorted_zone_names) - 1:
                zone_boxes[zone_name] = remaining_box
            else:
                w = remaining_box[2] - remaining_box[0]
                h = remaining_box[3] - remaining_box[1]
                
                zone_w = active_zones[zone_name]["weight"]
                rem_w = sum(active_zones[zn]["weight"] for zn in sorted_zone_names[idx:])
                ratio = zone_w / rem_w if rem_w > 0 else 0.5
                
                ratio *= random.uniform(0.92, 1.08)
                ratio = max(0.25, min(0.75, ratio))
                
                if w > h:
                    split_x = self._get_safe_split_pos(remaining_box[0], remaining_box[2], ratio, min_dim=90)
                    zone_boxes[zone_name] = [remaining_box[0], remaining_box[1], split_x, remaining_box[3]]
                    remaining_box = [split_x, remaining_box[1], remaining_box[2], remaining_box[3]]
                else:
                    split_y = self._get_safe_split_pos(remaining_box[1], remaining_box[3], ratio, min_dim=90)
                    zone_boxes[zone_name] = [remaining_box[0], remaining_box[1], remaining_box[2], split_y]
                    remaining_box = [remaining_box[0], split_y, remaining_box[2], remaining_box[3]]
                    
        # 4. Recursively subdivide zones into rooms
        rooms_layout = []
        for zone_name, zone_info in active_zones.items():
            zbox = zone_boxes[zone_name]
            znodes = zone_info["nodes"]
            placed_rooms = self._subdivide_zone(zbox, znodes)
            rooms_layout.extend(placed_rooms)
            
        node_lookup = {n["id"]: n for n in nodes}
        for room in rooms_layout:
            n_id = room["id"]
            if n_id in node_lookup:
                room["type"] = node_lookup[n_id].get("type", room.get("type", "bedroom"))
                room["color"] = node_lookup[n_id].get("color", room.get("color", [200, 200, 200]))
            else:
                room["type"] = "corridor"
                room["color"] = [245, 245, 245]
                
        # 5. Build walls and deduplicate collinear intervals
        walls = []
        horiz_walls = []
        vert_walls = []
        
        for room in rooms_layout:
            x1, y1, x2, y2 = room["box"]
            horiz_walls.append((y1, x1, x2, abs(y1 - by1) < 5))
            horiz_walls.append((y2, x1, x2, abs(y2 - by2) < 5))
            vert_walls.append((x1, y1, y2, abs(x1 - bx1) < 5))
            vert_walls.append((x2, y1, y2, abs(x2 - bx2) < 5))
            
        merged_horiz = self._merge_segments(horiz_walls)
        merged_vert = self._merge_segments(vert_walls)
        
        for y, x1, x2, is_ext in merged_horiz:
            walls.append([x1, y, x2, y, is_ext])
        for x, y1, y2, is_ext in merged_vert:
            walls.append([x, y1, x, y2, is_ext])
            
        # 6. Door placement & circulation flows
        doors = []
        connected_pairs = set()
        shared_segments = []
        
        for i, r1 in enumerate(rooms_layout):
            for j, r2 in enumerate(rooms_layout):
                if i < j:
                    b1, b2 = r1["box"], r2["box"]
                    # Horizontal shared boundaries
                    if abs(b1[3] - b2[1]) < 3:
                        overlap_x1 = max(b1[0], b2[0])
                        overlap_x2 = min(b1[2], b2[2])
                        if overlap_x2 - overlap_x1 >= 40:
                            shared_segments.append({
                                "r1": r1, "r2": r2, "direction": "horizontal", "coord": b1[3], "span": [overlap_x1, overlap_x2]
                            })
                    elif abs(b1[1] - b2[3]) < 3:
                        overlap_x1 = max(b1[0], b2[0])
                        overlap_x2 = min(b1[2], b2[2])
                        if overlap_x2 - overlap_x1 >= 40:
                            shared_segments.append({
                                "r1": r1, "r2": r2, "direction": "horizontal", "coord": b1[1], "span": [overlap_x1, overlap_x2]
                            })
                    # Vertical shared boundaries
                    if abs(b1[2] - b2[0]) < 3:
                        overlap_y1 = max(b1[1], b2[1])
                        overlap_y2 = min(b1[3], b2[3])
                        if overlap_y2 - overlap_y1 >= 40:
                            shared_segments.append({
                                "r1": r1, "r2": r2, "direction": "vertical", "coord": b1[2], "span": [overlap_y1, overlap_y2]
                            })
                    elif abs(b1[0] - b2[2]) < 3:
                        overlap_y1 = max(b1[1], b2[1])
                        overlap_y2 = min(b1[3], b2[3])
                        if overlap_y2 - overlap_y1 >= 40:
                            shared_segments.append({
                                "r1": r1, "r2": r2, "direction": "vertical", "coord": b1[0], "span": [overlap_y1, overlap_y2]
                            })
                            
        rooms_with_doors = set()
        
        # Connect corridor hallway cells to neighbors
        for seg in shared_segments:
            t1 = self._get_base_type(seg["r1"]["id"])
            t2 = self._get_base_type(seg["r2"]["id"])
            if t1 in ["corridor", "hallway"] or t2 in ["corridor", "hallway"]:
                if t1 in ["corridor", "hallway"] and t2 in ["corridor", "hallway", "balcony"]:
                    continue
                if t2 in ["corridor", "hallway"] and t1 in ["corridor", "hallway", "balcony"]:
                    continue
                mid = (seg["span"][0] + seg["span"][1]) // 2
                doors.append({
                    "room_id": seg["r1"]["id"] if t1 != "corridor" else seg["r2"]["id"],
                    "center": [mid, seg["coord"]] if seg["direction"] == "horizontal" else [seg["coord"], mid],
                    "direction": seg["direction"]
                })
                rooms_with_doors.add(seg["r1"]["id"])
                rooms_with_doors.add(seg["r2"]["id"])
                connected_pairs.add((seg["r1"]["id"], seg["r2"]["id"]))
                connected_pairs.add((seg["r2"]["id"], seg["r1"]["id"]))
                
        # Connect remaining unconnected cells
        for r in rooms_layout:
            r_id = r["id"]
            r_type = self._get_base_type(r_id)
            if r_type in ["corridor", "hallway", "balcony"]:
                continue
            if r_id not in rooms_with_doors:
                for seg in shared_segments:
                    if seg["r1"]["id"] == r_id or seg["r2"]["id"] == r_id:
                        other = seg["r2"] if seg["r1"]["id"] == r_id else seg["r1"]
                        other_type = self._get_base_type(other["id"])
                        if r_type == "bathroom" and other_type == "kitchen":
                            continue
                        mid = (seg["span"][0] + seg["span"][1]) // 2
                        doors.append({
                            "room_id": r_id,
                            "center": [mid, seg["coord"]] if seg["direction"] == "horizontal" else [seg["coord"], mid],
                            "direction": seg["direction"]
                        })
                        rooms_with_doors.add(r_id)
                        rooms_with_doors.add(other["id"])
                        connected_pairs.add((seg["r1"]["id"], seg["r2"]["id"]))
                        connected_pairs.add((seg["r2"]["id"], seg["r1"]["id"]))
                        break
                        
        # Main entrance door selection (Public exterior boundary preferred)
        entrance_placed = False
        public_rooms = [r for r in rooms_layout if self._get_base_type(r["id"]) in ["living_room", "entrance", "dining_room"]]
        if not public_rooms:
            public_rooms = rooms_layout
            
        for pr in public_rooms:
            box = pr["box"]
            if abs(box[3] - by2) < 5:
                mid = (box[0] + box[2]) // 2
                doors.append({
                    "room_id": pr["id"],
                    "center": [mid, by2],
                    "direction": "horizontal",
                    "is_entrance": True
                })
                entrance_placed = True
                break
            if abs(box[0] - bx1) < 5:
                mid = (box[1] + box[3]) // 2
                doors.append({
                    "room_id": pr["id"],
                    "center": [bx1, mid],
                    "direction": "vertical",
                    "is_entrance": True
                })
                entrance_placed = True
                break
            if abs(box[2] - bx2) < 5:
                mid = (box[1] + box[3]) // 2
                doors.append({
                    "room_id": pr["id"],
                    "center": [bx2, mid],
                    "direction": "vertical",
                    "is_entrance": True
                })
                entrance_placed = True
                break
            if abs(box[1] - by1) < 5:
                mid = (box[0] + box[2]) // 2
                doors.append({
                    "room_id": pr["id"],
                    "center": [mid, by1],
                    "direction": "horizontal",
                    "is_entrance": True
                })
                entrance_placed = True
                break
                
        if not entrance_placed:
            box = public_rooms[0]["box"]
            doors.append({
                "room_id": public_rooms[0]["id"],
                "center": [(box[0] + box[2]) // 2, box[3]],
                "direction": "horizontal",
                "is_entrance": True
            })
            
        # 7. Exterior Windows placement only
        windows = []
        for room in rooms_layout:
            r_id = room["id"]
            r_type = self._get_base_type(r_id)
            if r_type in ["corridor", "hallway", "garage"]:
                continue
                
            x1, y1, x2, y2 = room["box"]
            if abs(y1 - by1) < 5:
                windows.append({
                    "room_id": r_id,
                    "start": [x1 + int((x2 - x1) * 0.25), y1],
                    "end": [x1 + int((x2 - x1) * 0.75), y1]
                })
            if abs(y2 - by2) < 5:
                windows.append({
                    "room_id": r_id,
                    "start": [x1 + int((x2 - x1) * 0.25), y2],
                    "end": [x1 + int((x2 - x1) * 0.75), y2]
                })
            if abs(x1 - bx1) < 5:
                windows.append({
                    "room_id": r_id,
                    "start": [bx1, y1 + int((y2 - y1) * 0.25)],
                    "end": [bx1, y1 + int((y2 - y1) * 0.75)]
                })
            if abs(x2 - bx2) < 5:
                windows.append({
                    "room_id": r_id,
                    "start": [bx2, y1 + int((y2 - y1) * 0.25)],
                    "end": [bx2, y1 + int((y2 - y1) * 0.75)]
                })
                
        # 8. Multi-Criteria Architecture scoring engine
        score = 100.0
        
        # Aspect ratios check
        for room in rooms_layout:
            x1, y1, x2, y2 = room["box"]
            w = x2 - x1
            h = y2 - y1
            aspect = max(w, h) / max(1, min(w, h))
            if aspect > 2.5:
                score -= 15.0
            elif aspect > 2.0:
                score -= 5.0
            elif aspect < 1.3:
                score += 2.0
                
        # Private bathrooms near bedrooms
        bedrooms = [r for r in rooms_layout if self._get_base_type(r["id"]) == "bedroom"]
        bathrooms = [r for r in rooms_layout if self._get_base_type(r["id"]) == "bathroom"]
        for bed in bedrooms:
            bx1, by1, bx2, by2 = bed["box"]
            bcx = (bx1 + bx2)/2
            bcy = (by1 + by2)/2
            
            min_dist = 9999.0
            shares_wall = False
            for bath in bathrooms:
                bax1, bay1, bax2, bay2 = bath["box"]
                bacx = (bax1 + bax2)/2
                bacy = (bay1 + bay2)/2
                dist = math.sqrt((bcx - bacx)**2 + (bcy - bacy)**2)
                min_dist = min(min_dist, dist)
                if (bed["id"], bath["id"]) in connected_pairs:
                    shares_wall = True
                    
            if shares_wall:
                score += 10.0
            elif min_dist < 150.0:
                score += 5.0
            elif min_dist > 300.0:
                score -= 8.0
                
        # Kitchen near dining/living room
        kitchens = [r for r in rooms_layout if self._get_base_type(r["id"]) == "kitchen"]
        public_areas = [r for r in rooms_layout if self._get_base_type(r["id"]) in ["living_room", "dining_room"]]
        for kit in kitchens:
            kx1, ky1, kx2, ky2 = kit["box"]
            kcx = (kx1 + kx2)/2
            kcy = (ky1 + ky2)/2
            shares_wall = False
            min_dist = 9999.0
            for pub in public_areas:
                pcx = (pub["box"][0] + pub["box"][2])/2
                pcy = (pub["box"][1] + pub["box"][3])/2
                dist = math.sqrt((kcx - pcx)**2 + (kcy - pcy)**2)
                min_dist = min(min_dist, dist)
                if (kit["id"], pub["id"]) in connected_pairs:
                    shares_wall = True
                    
            if shares_wall:
                score += 10.0
            elif min_dist < 150.0:
                score += 5.0
            elif min_dist > 250.0:
                score -= 8.0

        # Bathroom away from entrance
        ent_door = [d for d in doors if d.get("is_entrance", False)]
        if ent_door:
            edx, edy = ent_door[0]["center"]
            for bath in bathrooms:
                bacx = (bath["box"][0] + bath["box"][2])/2
                bacy = (bath["box"][1] + bath["box"][3])/2
                dist = math.sqrt((edx - bacx)**2 + (edy - bacy)**2)
                if dist < 120.0:
                    score -= 10.0
                else:
                    score += 5.0

        # Garage/Parking close to entrance
        garages = [r for r in rooms_layout if self._get_base_type(r["id"]) == "garage"]
        if garages and ent_door:
            edx, edy = ent_door[0]["center"]
            for gar in garages:
                gcx = (gar["box"][0] + gar["box"][2])/2
                gcy = (gar["box"][1] + gar["box"][3])/2
                dist = math.sqrt((edx - gcx)**2 + (edy - gcy)**2)
                if dist < 180.0:
                    score += 8.0

        all_x1 = [r["box"][0] for r in rooms_layout]
        all_y1 = [r["box"][1] for r in rooms_layout]
        all_x2 = [r["box"][2] for r in rooms_layout]
        all_y2 = [r["box"][3] for r in rooms_layout]
        env_width = max(all_x2) - min(all_x1) if all_x1 else 800
        env_height = max(all_y2) - min(all_y1) if all_y1 else 600
        tightness = (env_width * env_height) / (master_width * master_height)
        
        return {
            "rooms": rooms_layout,
            "walls": walls,
            "doors": doors,
            "windows": windows,
            "score": score,
            "aesthetic_score": min(0.98, max(0.40, score / 100.0)),
            "env_bounds": [min(all_x1) if all_x1 else 50, min(all_y1) if all_y1 else 50, max(all_x2) if all_x2 else 750, max(all_y2) if all_y2 else 550],
            "tightness": tightness
        }

    def generate_layout(self, graph_data: Dict[str, Any], prompt_style: str) -> Dict[str, Any]:
        """Core endpoint. Generates candidates, selects the best plan, and renders blueprint image bytes."""
        nodes = graph_data.get("nodes", [])
        relationships = graph_data.get("edges", [])
        
        # 1. MULTI-LAYOUT GENERATION (Create 3 candidate floor plans via seeds)
        candidates = []
        seeds = [42, 108, 999]
        for seed in seeds:
            try:
                candidate = self._generate_candidate(nodes, relationships, prompt_style, seed)
                candidates.append(candidate)
            except Exception as e:
                print(f"[Warning] Failed candidate seed {seed}: {e}")

        if not candidates:
            raise ValueError("Failed to generate any valid architectural candidates.")

        best = max(candidates, key=lambda c: c["score"])
        
        # 2. Render Blueprint via PIL
        master_width = 800
        master_height = 600
        scale = 50
        
        zoning_colors = {
            "bedroom": (173, 216, 230, 95),       # Elegant Soft Blue
            "bathroom": (152, 251, 152, 95),      # Elegant Soft Green
            "kitchen": (255, 250, 205, 95),       # Elegant Soft Cream
            "living_room": (255, 228, 225, 95),   # Elegant Soft Coral
            "dining_room": (230, 230, 250, 95),   # Elegant Lavender
            "garage": (240, 240, 240, 95),        # Sleek Soft Grey
            "balcony": (255, 218, 185, 95),       # Warm Peach
            "corridor": (245, 245, 245, 95),      # Elegant White
            "hallway": (245, 245, 245, 95)
        }

        # Clean blueprint white background
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (master_width, master_height), (250, 248, 245, 255))
        draw = ImageDraw.Draw(img)

        # A. Fill zoned rooms
        for room in best["rooms"]:
            x1, y1, x2, y2 = room["box"]
            base_t = self._get_base_type(room["id"])
            color_fill = zoning_colors.get(base_t, (255, 255, 255, 90))
            draw.rectangle([x1, y1, x2, y2], fill=color_fill, outline=None)

        # B. Draw Grid Lines
        for x in range(0, master_width, scale):
            draw.line([x, 0, x, master_height], fill=(230, 230, 230, 100), width=1)
        for y in range(0, master_height, scale):
            draw.line([0, y, master_width, y], fill=(230, 230, 230, 100), width=1)

        # C. Draw Thick CAD Drafting Walls (Thick exterior, slightly thinner interior)
        for wall in best["walls"]:
            x1, y1, x2, y2, is_ext = wall
            width = 8 if is_ext else 4
            draw.line([x1, y1, x2, y2], fill=(26, 32, 44, 255), width=width)

        # D. Draw Windows (Cyan lines on exterior walls only)
        for win in best["windows"]:
            wx1, wy1 = win["start"]
            wx2, wy2 = win["end"]
            if wx1 == wx2: # Vertical window
                draw.rectangle([wx1 - 3, wy1, wx1 + 3, wy2], fill=(0, 191, 255, 255))
                draw.line([wx1, wy1, wx1, wy2], fill=(255, 255, 255), width=1)
            else: # Horizontal window
                draw.rectangle([wx1, wy1 - 3, wx2, wy1 + 3], fill=(0, 191, 255, 255))
                draw.line([wx1, wy1, wx2, wy1], fill=(255, 255, 255), width=1)

        # E. Draw Doors with clean swing arcs
        for door in best["doors"]:
            dcx, dcy = door["center"]
            is_entrance = door.get("is_entrance", False)
            stroke_color = (40, 167, 69, 255) if is_entrance else (229, 62, 62, 255)
            
            # Clear wall path under door
            draw.ellipse([dcx - 11, dcy - 11, dcx + 11, dcy + 11], fill=(250, 248, 245, 255))
            
            if door["direction"] == "horizontal":
                draw.arc([dcx - 15, dcy - 15, dcx + 15, dcy + 15], start=0, end=90, fill=stroke_color, width=2)
                draw.line([dcx, dcy, dcx, dcy - 15], fill=stroke_color, width=3)
            else:
                draw.arc([dcx - 15, dcy - 15, dcx + 15, dcy + 15], start=90, end=180, fill=stroke_color, width=2)
                draw.line([dcx, dcy, dcx + 15, dcy], fill=stroke_color, width=3)

            if is_entrance:
                draw.polygon([dcx - 8, dcy + 22, dcx + 8, dcy + 22, dcx, dcy + 10], fill=(40, 167, 69, 255))
                draw.text((dcx - 28, dcy + 25), "ENTRANCE", fill=(40, 167, 69, 255), stroke_width=1, stroke_fill=(255, 255, 255))

        # F. Annotate Room Details
        for room in best["rooms"]:
            x1, y1, x2, y2 = room["box"]
            rx, ry = (x1 + x2) / 2, (y1 + y2) / 2
            
            label = room["id"].replace("_", " ").upper()
            w_m = (x2 - x1) / scale
            h_m = (y2 - y1) / scale
            w_ft = int(w_m * 3.28084)
            h_ft = int(h_m * 3.28084)
            dims_text = f"{w_ft}'-0\" X {h_ft}'-0\""
            
            draw.text((rx - 38, ry - 12), label, fill=(26, 32, 44), stroke_width=2, stroke_fill=(255, 255, 255))
            draw.text((rx - 30, ry + 6), dims_text, fill=(74, 85, 104), stroke_width=2, stroke_fill=(255, 255, 255))

        # G. Render Gorgeous North Arrow Symbol (Compass)
        comp_cx, comp_cy = 730, 80
        draw.ellipse([comp_cx - 20, comp_cy - 20, comp_cx + 20, comp_cy + 20], fill=None, outline=(26, 32, 44), width=2)
        draw.line([comp_cx, comp_cy - 25, comp_cx, comp_cy + 25], fill=(74, 85, 104), width=1)
        draw.line([comp_cx - 25, comp_cy, comp_cx + 25, comp_cy], fill=(74, 85, 104), width=1)
        draw.polygon([comp_cx, comp_cy - 22, comp_cx + 5, comp_cy, comp_cx - 5, comp_cy], fill=(26, 32, 44, 255))
        draw.polygon([comp_cx, comp_cy + 22, comp_cx + 5, comp_cy, comp_cx - 5, comp_cy], fill=(160, 174, 192, 255))
        draw.text((comp_cx - 3, comp_cy - 34), "N", fill=(26, 32, 44), stroke_width=1, stroke_fill=(255, 255, 255))

        # Convert to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format="PNG")
        img_bytes = img_byte_arr.getvalue()

        # Build output metadata packet
        return {
            "image_bytes": img_bytes,
            "metadata": {
                "width_px": master_width,
                "height_px": master_height,
                "scale_px_to_meter": scale,
                "rooms": best["rooms"],
                "walls": best["walls"],
                "doors": best["doors"],
                "windows": best["windows"],
                "scoring": {
                    "aesthetic_score": best["aesthetic_score"],
                    "candidate_score": best["score"],
                    "overlaps_minimization_pct": 100.0,
                    "unused_space_tightness_ratio": float(best["tightness"])
                }
            }
        }

layout_service = LayoutGenerationService()
