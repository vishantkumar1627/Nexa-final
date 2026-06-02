import re
import os
import math
from typing import Dict, Any, List

from services.room_taxonomy import (
    ROOM_TAXONOMY,
    ZONE_ADJACENCY,
    resolve_room_type,
    get_room_meta,
    list_all_types,
    synthesize_unknown_room,
)

# Controls room extraction strategy. Options: regex (default), openai, anthropic
LLM_PROVIDER_MODE = os.getenv("LLM_PROVIDER_MODE", "regex")


class NLPService:
    """
    Semantic NLP parser that converts a natural-language architectural prompt into
    a structured room graph, using the dynamic room taxonomy engine.

    Supports:
    - All rooms defined in ROOM_TAXONOMY (30+ types)
    - Semantic aliases  (e.g. 'safe room' → panic_room)
    - Plural counts    (e.g. '3 bedrooms')
    - Fully unknown rooms (e.g. 'meditation room') → synthesised dynamically
    - Area/dimension heuristics
    - Style extraction
    - Optional LLM-backed extraction (set LLM_PROVIDER_MODE=openai|anthropic)
    """

    def __init__(self):
        pass  # No heavy tokenizer loading; LLM calls are made lazily per-request

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_style(self, prompt_lower: str) -> str:
        styles = [
            "modern", "minimalist", "classic", "scandinavian",
            "industrial", "rustic", "victorian", "contemporary",
            "art deco", "mediterranean",
        ]
        for style in styles:
            if style in prompt_lower:
                return style
        return "modern"

    def _extract_dimensions(self, prompt_lower: str) -> Dict[str, float]:
        dims = {"width": 12.0, "height": 10.0, "area": 120.0}
        area_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(sq\s*m|sqm|square\s*meters?|square\s*feet|sq\s*ft|sqft)",
            prompt_lower,
        )
        if area_match:
            val = float(area_match.group(1))
            unit = area_match.group(2)
            if "feet" in unit or "ft" in unit:
                val *= 0.092903
            dims["area"] = val
            side = math.sqrt(val)
            dims["width"] = round(side * 1.2, 1)
            dims["height"] = round(side / 1.2, 1)
        return dims

    # ── Core: dynamic room detection ─────────────────────────────────────────

    def _detect_rooms(self, prompt_lower: str) -> Dict[str, int]:
        """
        Phase 1 – taxonomy alias scan.
        For every canonical room type, scan all its aliases for mentions.
        Supports leading digit counts (e.g. '3 bedrooms').
        """
        found: Dict[str, int] = {}   # canonical_type → count

        for canonical, meta in ROOM_TAXONOMY.items():
            aliases = sorted(meta["aliases"], key=len, reverse=True)  # longest first
            for alias in aliases:
                # Try "N alias(s)" pattern first
                pattern = rf"(\d+)\s*-?\s*{re.escape(alias)}s?\b"
                match = re.search(pattern, prompt_lower)
                if match:
                    cnt = int(match.group(1))
                    found[canonical] = max(found.get(canonical, 0), cnt)
                    break
                elif alias in prompt_lower:
                    found[canonical] = max(found.get(canonical, 0), 1)
                    break

        return found

    def _detect_unknown_rooms(self, prompt_lower: str, already_found: Dict[str, int]) -> Dict[str, int]:
        """
        Phase 2 – catch custom/unknown room names not in taxonomy.
        Heuristic: look for '<word(s)> room' or 'room for <purpose>' patterns.
        """
        extra: Dict[str, int] = {}

        _STOP = {
            "a", "an", "the", "this", "that", "my", "our", "some", "with",
            "and", "or", "build", "create", "design", "add", "house", "home",
        }
        # Pattern A: 1-3 word prefix before "room"
        matches = re.findall(r"\b(\w+(?:\s+\w+){0,2})\s+room\b", prompt_lower)
        for raw in matches:
            raw = raw.strip()
            if any(tok in _STOP for tok in raw.split()):
                continue
            canonical = resolve_room_type(raw + " room")
            if canonical not in already_found and canonical not in ROOM_TAXONOMY:
                synthesize_unknown_room(canonical, prompt_lower)
                extra[canonical] = 1

        # Pattern B: digit + 1-2 word noun + "room(s)"
        matches2 = re.findall(r"(\d+)\s+(\w+(?:\s+\w+)?)\s+rooms?\b", prompt_lower)
        for cnt_str, raw in matches2:
            raw = raw.strip()
            canonical = resolve_room_type(raw + " room")
            if canonical not in already_found and canonical not in ROOM_TAXONOMY:
                synthesize_unknown_room(canonical, prompt_lower)
                extra[canonical] = max(extra.get(canonical, 0), int(cnt_str))

        return extra

    def _build_room_list(self, found: Dict[str, int]) -> List[Dict[str, Any]]:
        """Convert found dict → list of room node dicts with full taxonomy metadata."""
        rooms = []
        for canonical, count in found.items():
            meta = get_room_meta(canonical)
            for i in range(count):
                node_id = f"{canonical}_{i + 1}" if count > 1 else canonical
                rooms.append({
                    "id": node_id,
                    "type": canonical,
                    "zone": meta["zone"],
                    "min_area": meta["min_area"],
                    "weight": meta["weight"],
                    "color": meta["color"],
                    "hex_color": meta["hex_color"],
                    "label": meta["label"],
                    "windows": meta["windows"],
                    "furniture": meta["furniture"],
                })
        return rooms

    def _build_relationships(self, rooms: List[Dict[str, Any]]) -> List[List[str]]:
        """
        Build spatial adjacency edges driven by ZONE_ADJACENCY rules:
        - Rooms in compatible zones are connected.
        - Corridor acts as a hub if present.
        - Kitchen always adjacent to living/dining.
        """
        relationships: List[List[str]] = []
        ids = [r["id"] for r in rooms]

        # Find corridor hub
        corridor_ids = [r["id"] for r in rooms if r["type"] in ("corridor", "hallway")]
        hub = corridor_ids[0] if corridor_ids else None

        # Zone-driven connections
        connected = set()

        for i, r1 in enumerate(rooms):
            for j, r2 in enumerate(rooms):
                if i >= j:
                    continue
                pair = (r1["id"], r2["id"])
                if pair in connected:
                    continue

                z1 = r1["zone"]
                z2 = r2["zone"]
                compatible = z2 in ZONE_ADJACENCY.get(z1, []) or z1 in ZONE_ADJACENCY.get(z2, [])

                # Corridor connects to everything
                if r1["type"] in ("corridor", "hallway") or r2["type"] in ("corridor", "hallway"):
                    compatible = True

                if compatible:
                    relationships.append([r1["id"], r2["id"]])
                    connected.add(pair)

        # Guarantee kitchen ↔ dining/living connections
        kitchen_ids = [r["id"] for r in rooms if r["type"] == "kitchen"]
        social_ids = [r["id"] for r in rooms if r["type"] in ("living_room", "dining_room")]
        for k in kitchen_ids:
            for s in social_ids:
                pair = tuple(sorted([k, s]))
                if pair not in connected:
                    relationships.append([k, s])
                    connected.add(pair)

        # Panic/security rooms connect only to private/corridor
        for r in rooms:
            if r["zone"] == "security":
                for r2 in rooms:
                    if r2["zone"] in ("private",) or r2["type"] in ("corridor", "hallway"):
                        pair = tuple(sorted([r["id"], r2["id"]]))
                        if pair not in connected:
                            relationships.append([r["id"], r2["id"]])
                            connected.add(pair)

        return relationships

    # ── LLM-backed extraction ─────────────────────────────────────────────────

    def _extract_rooms_via_llm(self, prompt: str) -> Dict[str, Any]:
        """
        Calls OpenAI or Anthropic to extract rooms, style, floors, and dimensions.
        Returns an empty dict on failure so the caller can fall back to regex.
        """
        tool_schema = {
            "name": "extract_floor_plan",
            "description": "Extract architectural floor plan requirements from a user prompt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rooms": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "count": {"type": "integer"},
                                "special_requirements": {"type": "string"}
                            },
                            "required": ["type", "count"]
                        }
                    },
                    "style": {"type": "string"},
                    "num_floors": {"type": "integer"},
                    "dimensions": {
                        "type": "object",
                        "properties": {
                            "width": {"type": "number"},
                            "height": {"type": "number"},
                            "area": {"type": "number"}
                        }
                    }
                },
                "required": ["rooms"]
            }
        }

        try:
            if LLM_PROVIDER_MODE == "openai":
                import openai
                import json
                api_key = os.getenv("OPENAI_API_KEY", "")
                client = openai.OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    tools=[{"type": "function", "function": tool_schema}],
                    tool_choice={"type": "function", "function": {"name": "extract_floor_plan"}}
                )
                args = response.choices[0].message.tool_calls[0].function.arguments
                return json.loads(args)

            elif LLM_PROVIDER_MODE == "anthropic":
                import anthropic, json
                api_key = os.getenv("CLAUDE_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
                client = anthropic.Anthropic(api_key=api_key)
                response = client.messages.create(
                    model="claude-sonnet-4-6",   # confirmed available 2026-06
                    max_tokens=1024,
                    tools=[{
                        "name": tool_schema["name"],
                        "description": tool_schema["description"],
                        "input_schema": tool_schema["parameters"]
                    }],
                    messages=[{"role": "user", "content": prompt}]
                )
                for block in response.content:
                    if block.type == "tool_use":
                        return block.input

            elif LLM_PROVIDER_MODE == "gemini":
                import json, urllib.request, urllib.parse
                api_key = os.getenv("GEMINI_API_KEY", "")
                system_msg = (
                    "You are an architectural assistant. Given a free-text description of a house, "
                    "return ONLY a valid JSON object matching this schema (no markdown, no explanation):\n"
                    f"{json.dumps(tool_schema['parameters'], indent=2)}"
                )
                payload = {
                    "contents": [{"parts": [{"text": f"{system_msg}\n\nPrompt: {prompt}"}]}],
                    "generationConfig": {"responseMimeType": "application/json"}
                }
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/"
                    f"models/gemini-2.5-flash:generateContent?key={api_key}"
                )
                req = urllib.request.Request(
                    url, data=json.dumps(payload).encode(), method="POST",
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = json.loads(resp.read())
                text = body["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)

        except Exception as e:
            print(f"[NLP] LLM extraction failed ({LLM_PROVIDER_MODE}): {e}. Falling back to regex.")

        return {}

    # ── Public API ────────────────────────────────────────────────────────────

    def extract_architecture_details(self, prompt: str) -> Dict[str, Any]:
        """
        Parses a natural-language prompt and returns structured architectural data
        with full support for dynamic/custom room types via the taxonomy engine.
        """
        prompt_lower = prompt.lower()

        # 1. Style
        style = self._extract_style(prompt_lower)

        # 2. Dimensions (regex always runs; LLM result may override)
        dimensions = self._extract_dimensions(prompt_lower)

        # 3. Room detection
        if LLM_PROVIDER_MODE != "regex":
            llm_result = self._extract_rooms_via_llm(prompt)
            if llm_result.get("rooms"):
                found: Dict[str, int] = {}
                for room_entry in llm_result["rooms"]:
                    canonical = resolve_room_type(room_entry.get("type", ""))
                    count = max(1, int(room_entry.get("count", 1)))
                    found[canonical] = max(found.get(canonical, 0), count)
                style = llm_result.get("style", style) or style
                if llm_result.get("dimensions"):
                    for k, v in llm_result["dimensions"].items():
                        if v:
                            dimensions[k] = v
            else:
                # LLM failed — fall through to regex
                found = self._detect_rooms(prompt_lower)
                extra = self._detect_unknown_rooms(prompt_lower, found)
                found.update(extra)
        else:
            # Phase 1: taxonomy-driven regex scan
            found = self._detect_rooms(prompt_lower)
            # Phase 2: unknown/custom rooms
            extra = self._detect_unknown_rooms(prompt_lower, found)
            found.update(extra)

        # 4. Fallback: no rooms detected → standard house
        if not found:
            found = {
                "living_room": 1,
                "kitchen": 1,
                "bedroom": 1,
                "bathroom": 1,
                "corridor": 1,
            }

        # 5. Build node list
        rooms = self._build_room_list(found)

        # 6. Spatial adjacency graph
        relationships = self._build_relationships(rooms)

        return {
            "rooms": rooms,
            "relationships": relationships,
            "constraints": [],
            "dimensions": dimensions,
            "style": style,
        }


nlp_service = NLPService()
