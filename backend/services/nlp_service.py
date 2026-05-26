import re
from typing import Dict, Any, List
from transformers import AutoTokenizer

class NLPService:
    def __init__(self):
        # Proactively load a tiny tokenizer locally for realistic pipeline feel
        try:
            self.tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased", local_files_only=True)
        except Exception as e:
            print(f"HuggingFace offline or unavailable, tokenizing locally with simple regex fallback: {e}")
            self.tokenizer = None

    def extract_architecture_details(self, prompt: str) -> Dict[str, Any]:
        """Parses a natural language prompt and extracts rooms, connections, constraints and styles."""
        # Baseline structure
        result = {
            "rooms": [],
            "relationships": [],
            "constraints": [],
            "dimensions": {"width": 12.0, "height": 10.0, "area": 120.0},
            "style": "modern"
        }

        # 1. Tokenize prompt to simulate BERT model intake
        if self.tokenizer:
            try:
                tokens = self.tokenizer.tokenize(prompt)
                # In real code, we would run a BERT NER model over the tokens:
                # model(tokens) -> extract labels like B-ROOM, I-ROOM, etc.
            except Exception:
                pass

        # 2. Extract Style
        prompt_lower = prompt.lower()
        styles = ["modern", "minimalist", "classic", "scandinavian", "industrial", "rustical", "victorian"]
        for style in styles:
            if style in prompt_lower:
                result["style"] = style
                break

        # 3. Extract Rooms with sensible heuristics
        # Standard rooms mapping
        target_types = {
            "bedroom": ["bedroom", "bed room", "bed"],
            "bathroom": ["bathroom", "bath room", "bath", "restroom", "wc"],
            "kitchen": ["kitchen", "cookhouse"],
            "living_room": ["living room", "living_room", "parlor", "salon", "lounge"],
            "garage": ["garage", "parking"],
            "balcony": ["balcony", "veranda"],
            "corridor": ["corridor", "hallway"],
            "dining_room": ["dining room", "dining_room"]
        }
        
        rooms_to_add = []
        
        # Color mapping for beautiful architectural aesthetics
        color_map = {
            "bedroom": [180, 220, 255],      # Soft Blue
            "bathroom": [180, 255, 220],     # Soft Green
            "kitchen": [255, 255, 200],      # Soft Yellow
            "living_room": [255, 200, 200],  # Soft Red/Coral
            "garage": [230, 230, 230],       # Soft Grey
            "balcony": [255, 225, 180],      # Soft Orange
            "corridor": [245, 245, 245],     # Very light grey
            "dining_room": [235, 210, 255]   # Soft Purple
        }

        area_map = {
            "bedroom": 16.0,
            "bathroom": 8.0,
            "kitchen": 15.0,
            "living_room": 25.0,
            "garage": 18.0,
            "balcony": 8.0,
            "corridor": 6.0,
            "dining_room": 12.0
        }

        for room_type, syns in target_types.items():
            count = 0
            found = False
            for syn in syns:
                match = re.search(rf"(\d+)\s*-?\s*{syn}s?\b", prompt_lower)
                if match:
                    count = max(count, int(match.group(1)))
                    found = True
                elif syn in prompt_lower:
                    found = True
            
            # If a synonym is matched in the prompt but without a leading digit, default is 1
            if found and count == 0:
                count = 1
                
            for i in range(count):
                name = f"{room_type}_{i+1}" if count > 1 else room_type
                rooms_to_add.append({
                    "id": name,
                    "type": room_type,
                    "min_area": area_map[room_type],
                    "color": color_map[room_type]
                })

        # Core fallback: if list is empty, put standard house set
        if not rooms_to_add:
            rooms_to_add = [
                {"id": "living_room", "type": "living_room", "min_area": 25.0, "color": [255, 200, 200]},
                {"id": "kitchen", "type": "kitchen", "min_area": 15.0, "color": [255, 255, 200]},
                {"id": "bedroom", "type": "bedroom", "min_area": 16.0, "color": [180, 220, 255]},
                {"id": "bathroom", "type": "bathroom", "min_area": 8.0, "color": [180, 255, 220]},
                {"id": "corridor", "type": "corridor", "min_area": 6.0, "color": [240, 240, 240]}
            ]

        result["rooms"] = rooms_to_add

        # 4. Generate Spatial Adjacency Relationships
        # Build logical connections between rooms (e.g. kitchen adjacent to dining, corridor to rooms)
        rooms_list = [r["id"] for r in rooms_to_add]
        
        # Connect everything through a central corridor if it exists
        has_corridor = "corridor" in rooms_list
        corridor_id = "corridor" if has_corridor else rooms_list[0]
        
        relationships = []
        for r_id in rooms_list:
            if r_id != corridor_id:
                relationships.append([corridor_id, r_id])
                
        # Additional logical connection: Kitchen to Living Room
        if "kitchen" in rooms_list and "living_room" in rooms_list:
            relationships.append(["kitchen", "living_room"])

        result["relationships"] = relationships

        # 5. Dimensions Heuristics
        # If user specified something like "150 sq meters"
        area_match = re.search(r"(\d+)\s*(sq\s*m|sqm|square\s*feet|sq\s*ft|sqft)", prompt_lower)
        if area_match:
            val = float(area_match.group(1))
            if "feet" in area_match.group(2) or "ft" in area_match.group(2):
                val = val * 0.092903  # Convert to square meters
            result["dimensions"]["area"] = val
            # Adjust width and height based on square root ratio
            import math
            side = math.sqrt(val)
            result["dimensions"]["width"] = round(side * 1.2, 1)
            result["dimensions"]["height"] = round(side / 1.2, 1)

        return result

nlp_service = NLPService()
