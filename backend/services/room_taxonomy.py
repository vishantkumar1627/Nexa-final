"""
Dynamic Room Taxonomy Engine
============================
Metadata-driven room definitions. Every room carries:
  - zone         : public / private / service / utility / recreation / security
  - weight       : BSP layout weight (relative floor-space priority)
  - min_area     : minimum m² for layout scoring
  - color        : (R, G, B) fill for raster render
  - hex_color    : hex fill for SVG render
  - windows      : "full" | "partial" | "minimal" | "none"
  - furniture    : list of furniture items (used by SVG generator)
  - label        : human-readable display label
  - aliases      : NLP synonym list (lowercased)
  - is_dynamic   : True if this entry was synthesised at runtime
"""

import re
from typing import Dict, Any, List, Optional

# ─────────────────────────────────────────────────────────
# MASTER TAXONOMY
# ─────────────────────────────────────────────────────────
ROOM_TAXONOMY: Dict[str, Dict[str, Any]] = {

    # ── STANDARD RESIDENTIAL ──────────────────────────────
    "bedroom": {
        "zone": "private",
        "weight": 22.0,
        "min_area": 16.0,
        "color": [180, 220, 255],
        "hex_color": "#b4dcff",
        "windows": "full",
        "furniture": ["bed", "wardrobe", "side_table"],
        "label": "BEDROOM",
        "aliases": ["bedroom", "bed room", "bed", "sleeping room", "master bedroom",
                    "master bed", "guest bedroom", "kids room", "child room"],
    },
    "bathroom": {
        "zone": "private",
        "weight": 8.0,
        "min_area": 6.0,
        "color": [180, 255, 220],
        "hex_color": "#b4ffdc",
        "windows": "minimal",
        "furniture": ["toilet", "sink", "shower"],
        "label": "BATHROOM",
        "aliases": ["bathroom", "bath room", "bath", "restroom", "wc", "toilet",
                    "washroom", "lavatory", "powder room", "ensuite"],
    },
    "kitchen": {
        "zone": "service",
        "weight": 16.0,
        "min_area": 12.0,
        "color": [255, 255, 200],
        "hex_color": "#ffffc8",
        "windows": "full",
        "furniture": ["counter", "stove", "sink", "fridge"],
        "label": "KITCHEN",
        "aliases": ["kitchen", "cookhouse", "cook room", "galley", "kitchenette"],
    },
    "living_room": {
        "zone": "public",
        "weight": 35.0,
        "min_area": 20.0,
        "color": [255, 200, 200],
        "hex_color": "#ffc8c8",
        "windows": "full",
        "furniture": ["sofa", "coffee_table", "tv_unit"],
        "label": "LIVING ROOM",
        "aliases": ["living room", "living_room", "parlor", "salon", "lounge",
                    "sitting room", "family room", "drawing room", "reception"],
    },
    "dining_room": {
        "zone": "public",
        "weight": 14.0,
        "min_area": 12.0,
        "color": [235, 210, 255],
        "hex_color": "#ebd2ff",
        "windows": "partial",
        "furniture": ["dining_table", "chairs"],
        "label": "DINING ROOM",
        "aliases": ["dining room", "dining_room", "dining area", "eat-in", "breakfast room"],
    },
    "garage": {
        "zone": "utility",
        "weight": 26.0,
        "min_area": 18.0,
        "color": [230, 230, 230],
        "hex_color": "#e6e6e6",
        "windows": "minimal",
        "furniture": ["car"],
        "label": "GARAGE",
        "aliases": ["garage", "parking", "car park", "carport", "vehicle bay"],
    },
    "balcony": {
        "zone": "public",
        "weight": 8.0,
        "min_area": 5.0,
        "color": [255, 225, 180],
        "hex_color": "#ffe1b4",
        "windows": "full",
        "furniture": ["railing"],
        "label": "BALCONY",
        "aliases": ["balcony", "veranda", "porch", "terrace", "deck", "patio"],
    },
    "corridor": {
        "zone": "utility",
        "weight": 10.0,
        "min_area": 4.0,
        "color": [245, 245, 245],
        "hex_color": "#f5f5f5",
        "windows": "none",
        "furniture": [],
        "label": "CORRIDOR",
        "aliases": ["corridor", "hallway", "hall", "passage", "foyer", "entry"],
    },

    # ── WORK / PRODUCTIVITY ───────────────────────────────
    "office": {
        "zone": "public",
        "weight": 18.0,
        "min_area": 12.0,
        "color": [200, 230, 255],
        "hex_color": "#c8e6ff",
        "windows": "full",
        "furniture": ["desk", "chair", "bookshelf"],
        "label": "OFFICE",
        "aliases": ["office", "home office", "work room", "workspace",
                    "study", "work space", "workroom"],
    },
    "study_room": {
        "zone": "private",
        "weight": 14.0,
        "min_area": 10.0,
        "color": [210, 240, 220],
        "hex_color": "#d2f0dc",
        "windows": "partial",
        "furniture": ["desk", "chair", "bookshelf"],
        "label": "STUDY ROOM",
        "aliases": ["study room", "study_room", "reading room", "study area",
                    "homework room", "learning room"],
    },
    "library": {
        "zone": "private",
        "weight": 20.0,
        "min_area": 14.0,
        "color": [220, 200, 170],
        "hex_color": "#dcc8aa",
        "windows": "partial",
        "furniture": ["bookshelf", "armchair", "reading_lamp"],
        "label": "LIBRARY",
        "aliases": ["library", "book room", "reading room", "book lounge",
                    "personal library", "home library"],
    },

    # ── RECREATION / LEISURE ─────────────────────────────
    "gym": {
        "zone": "recreation",
        "weight": 28.0,
        "min_area": 20.0,
        "color": [255, 220, 180],
        "hex_color": "#ffdcb4",
        "windows": "full",
        "furniture": ["treadmill", "weights", "bench"],
        "label": "GYM",
        "aliases": ["gym", "gymnasium", "fitness room", "workout room",
                    "exercise room", "fitness center", "home gym", "workout space"],
    },
    "theater_room": {
        "zone": "recreation",
        "weight": 30.0,
        "min_area": 22.0,
        "color": [50, 50, 80],
        "hex_color": "#323250",
        "windows": "none",
        "furniture": ["projector", "screen", "theater_seats", "speakers"],
        "label": "THEATER ROOM",
        "aliases": ["theater room", "theatre room", "home theater", "home theatre",
                    "media room", "cinema room", "screening room", "movie room"],
    },
    "game_room": {
        "zone": "recreation",
        "weight": 22.0,
        "min_area": 16.0,
        "color": [180, 255, 180],
        "hex_color": "#b4ffb4",
        "windows": "partial",
        "furniture": ["game_console", "sofa", "tv_unit"],
        "label": "GAME ROOM",
        "aliases": ["game room", "gaming room", "games room", "playroom",
                    "recreation room", "rec room", "entertainment room"],
    },
    "art_studio": {
        "zone": "recreation",
        "weight": 20.0,
        "min_area": 14.0,
        "color": [255, 245, 200],
        "hex_color": "#fff5c8",
        "windows": "full",
        "furniture": ["easel", "work_table", "storage_cabinet"],
        "label": "ART STUDIO",
        "aliases": ["art studio", "studio", "art room", "craft room",
                    "painting room", "artist room", "creative room"],
    },

    # ── SECURITY / SPECIALTY ─────────────────────────────
    "panic_room": {
        "zone": "security",
        "weight": 12.0,
        "min_area": 8.0,
        "color": [100, 100, 120],
        "hex_color": "#646478",
        "windows": "none",
        "furniture": ["safe", "chair", "monitor"],
        "label": "PANIC ROOM",
        "aliases": ["panic room", "safe room", "security room", "bunker room",
                    "shelter room", "storm shelter", "vault room", "safe house"],
    },
    "server_room": {
        "zone": "utility",
        "weight": 10.0,
        "min_area": 8.0,
        "color": [180, 180, 220],
        "hex_color": "#b4b4dc",
        "windows": "none",
        "furniture": ["server_rack", "ups", "cooling_unit"],
        "label": "SERVER ROOM",
        "aliases": ["server room", "data room", "it room", "network room",
                    "tech room", "computer room"],
    },

    # ── WELLNESS / SPA ────────────────────────────────────
    "sauna": {
        "zone": "private",
        "weight": 10.0,
        "min_area": 6.0,
        "color": [200, 160, 120],
        "hex_color": "#c8a078",
        "windows": "minimal",
        "furniture": ["bench", "heater"],
        "label": "SAUNA",
        "aliases": ["sauna", "steam room", "sauna room", "steam bath", "spa room"],
    },
    "pool_room": {
        "zone": "recreation",
        "weight": 40.0,
        "min_area": 35.0,
        "color": [180, 230, 255],
        "hex_color": "#b4e6ff",
        "windows": "full",
        "furniture": ["pool", "lounge_chairs"],
        "label": "POOL ROOM",
        "aliases": ["pool room", "swimming pool", "indoor pool", "pool area",
                    "aquatic room", "pool hall"],
    },

    # ── UTILITY / SUPPORT ─────────────────────────────────
    "laundry_room": {
        "zone": "utility",
        "weight": 8.0,
        "min_area": 5.0,
        "color": [200, 220, 200],
        "hex_color": "#c8dcc8",
        "windows": "minimal",
        "furniture": ["washer", "dryer", "sink"],
        "label": "LAUNDRY ROOM",
        "aliases": ["laundry room", "laundry", "utility room", "wash room",
                    "laundry area", "laundry closet"],
    },
    "storage_room": {
        "zone": "utility",
        "weight": 8.0,
        "min_area": 4.0,
        "color": [200, 200, 185],
        "hex_color": "#c8c8b9",
        "windows": "none",
        "furniture": ["shelves"],
        "label": "STORAGE ROOM",
        "aliases": ["storage room", "store room", "storeroom", "storage",
                    "storage area", "cellar", "basement storage", "pantry room"],
    },
    "mudroom": {
        "zone": "utility",
        "weight": 8.0,
        "min_area": 5.0,
        "color": [215, 210, 200],
        "hex_color": "#d7d2c8",
        "windows": "minimal",
        "furniture": ["bench", "coat_rack", "shoe_rack"],
        "label": "MUDROOM",
        "aliases": ["mudroom", "mud room", "entry room", "boot room",
                    "entrance room", "drop zone"],
    },
    "pantry": {
        "zone": "service",
        "weight": 6.0,
        "min_area": 4.0,
        "color": [240, 235, 210],
        "hex_color": "#f0ebd2",
        "windows": "none",
        "furniture": ["shelves", "pantry_cabinet"],
        "label": "PANTRY",
        "aliases": ["pantry", "food storage", "walk-in pantry", "larder",
                    "pantry room", "food room"],
    },
    "home_office": {
        "zone": "public",
        "weight": 16.0,
        "min_area": 10.0,
        "color": [195, 225, 250],
        "hex_color": "#c3e1fa",
        "windows": "full",
        "furniture": ["desk", "chair", "monitor", "bookshelf"],
        "label": "HOME OFFICE",
        "aliases": ["home office", "remote office", "work from home", "wfh room"],
    },
}

# ─────────────────────────────────────────────────────────
# ZONE → BSP priority order and adjacency preferences
# ─────────────────────────────────────────────────────────
ZONE_ORDER = ["public", "private", "service", "utility", "recreation", "security"]

ZONE_ADJACENCY: Dict[str, List[str]] = {
    "public":     ["public", "service", "utility"],
    "private":    ["private", "utility"],
    "service":    ["public", "service", "utility"],
    "utility":    ["utility", "service", "public"],
    "recreation": ["public", "recreation"],
    "security":   ["private", "security"],
}

# Default colors/weights for truly unknown room types (runtime fallback)
FALLBACK_DEFAULTS: Dict[str, Any] = {
    "zone": "public",
    "weight": 16.0,
    "min_area": 12.0,
    "color": [210, 210, 210],
    "hex_color": "#d2d2d2",
    "windows": "partial",
    "furniture": [],
    "label": "",
    "aliases": [],
}


# ─────────────────────────────────────────────────────────
# BUILD ALIAS → CANONICAL MAP  (compiled once at import)
# ─────────────────────────────────────────────────────────
_ALIAS_MAP: Dict[str, str] = {}
for _canonical, _meta in ROOM_TAXONOMY.items():
    for _alias in _meta["aliases"]:
        _ALIAS_MAP[_alias.lower()] = _canonical


def resolve_room_type(raw_name: str) -> str:
    """
    Resolves any raw room name string to its canonical taxonomy key.
    Falls back to a sanitised version of the raw name for truly unknown types.
    """
    key = raw_name.lower().strip()

    # 1. Direct alias hit
    if key in _ALIAS_MAP:
        return _ALIAS_MAP[key]

    # 2. Canonical key direct hit
    if key in ROOM_TAXONOMY:
        return key

    # 3. Partial substring match (e.g. "master bedroom" → "bedroom")
    for alias, canonical in _ALIAS_MAP.items():
        if alias in key or key in alias:
            return canonical

    # 4. Unknown room – sanitise and return as-is (dynamic extension)
    return key.replace(" ", "_")


def get_room_meta(room_type: str) -> Dict[str, Any]:
    """
    Returns full metadata for a canonical room type.
    For unknown types, synthesises a sensible default and caches it.
    """
    if room_type in ROOM_TAXONOMY:
        return ROOM_TAXONOMY[room_type]

    # Synthesise a dynamic entry for the unknown room type
    meta = dict(FALLBACK_DEFAULTS)
    meta["label"] = room_type.replace("_", " ").upper()
    meta["aliases"] = [room_type.replace("_", " ")]

    # Cache it so the rest of the pipeline can reference it consistently
    ROOM_TAXONOMY[room_type] = meta
    _ALIAS_MAP[room_type.replace("_", " ")] = room_type

    return meta


# ─────────────────────────────────────────────────────────
# SEMANTIC INFERENCE  (for truly unknown rooms)
# ─────────────────────────────────────────────────────────

# Keyword → zone mapping
_ZONE_KEYWORDS: Dict[str, str] = {
    # Security
    "panic": "security", "safe": "security", "bunker": "security",
    "vault": "security", "shelter": "security",
    # Private
    "bed": "private", "sleep": "private", "dressing": "private",
    "meditation": "private", "prayer": "private", "nursery": "private",
    # Recreation
    "gym": "recreation", "game": "recreation", "play": "recreation",
    "cinema": "recreation", "theater": "recreation", "theatre": "recreation",
    "music": "recreation", "dance": "recreation", "yoga": "recreation",
    "sport": "recreation", "fitness": "recreation",
    # Service
    "kitchen": "service", "cook": "service", "laundry": "service",
    "pantry": "service", "utility": "utility", "storage": "utility",
    "server": "utility", "mechanical": "utility",
    # Public
    "office": "public", "study": "public", "library": "public",
    "lounge": "public", "hall": "public", "reception": "public",
    "meeting": "public", "conference": "public",
}

# Keyword → furniture hints
_FURNITURE_KEYWORDS: Dict[str, List[str]] = {
    "office": ["desk", "chair", "monitor"],
    "study": ["desk", "chair", "bookshelf"],
    "library": ["bookshelf", "armchair", "reading_lamp"],
    "meditation": ["mat", "cushion"],
    "yoga": ["mat", "mirror"],
    "gym": ["treadmill", "weights", "bench"],
    "music": ["instrument", "speaker", "stool"],
    "dance": ["mirror", "barre"],
    "prayer": ["mat", "altar"],
    "nursery": ["crib", "rocking_chair", "dresser"],
    "cinema": ["projector", "screen", "seats"],
    "theater": ["projector", "screen", "theater_seats"],
    "theatre": ["projector", "screen", "theater_seats"],
    "server": ["server_rack", "cooling_unit"],
    "meeting": ["conference_table", "chairs", "whiteboard"],
    "conference": ["conference_table", "chairs", "projector"],
    "panic": ["safe", "chair", "monitor"],
    "safe": ["safe", "chair"],
    "bunker": ["safe", "bunk_bed", "supplies"],
    "reception": ["reception_desk", "sofa", "counter"],
    "lounge": ["sofa", "coffee_table", "bar"],
    "dressing": ["mirror", "wardrobe", "vanity"],
}

# Keyword → window preference
_WINDOW_KEYWORDS: Dict[str, str] = {
    "panic": "none", "bunker": "none", "safe": "none",
    "shelter": "none", "server": "none", "theater": "none",
    "theatre": "none", "cinema": "none", "storage": "none",
    "vault": "none", "laundry": "minimal", "utility": "minimal",
    "prayer": "minimal", "sauna": "minimal",
}

# Deterministic palette generator from room name hash
def _palette_from_name(name: str) -> tuple:
    """Returns a deterministic (R,G,B) pastel colour from the room name."""
    h = hash(name) & 0xFFFFFF
    r = 160 + (h & 0x3F)          # 160–223
    g = 160 + ((h >> 6) & 0x3F)
    b = 160 + ((h >> 12) & 0x3F)
    return r, g, b


def synthesize_unknown_room(canonical: str, prompt_context: str = "") -> Dict[str, Any]:
    """
    Dynamically synthesises a full metadata entry for a room type that is not
    present in ROOM_TAXONOMY.  Inference is done via keyword matching on the
    canonical key and prompt context.

    The entry is cached in ROOM_TAXONOMY and _ALIAS_MAP so the rest of the
    pipeline (layout, rendering) can use it transparently.
    """
    if canonical in ROOM_TAXONOMY:
        return ROOM_TAXONOMY[canonical]

    name_words = canonical.replace("_", " ").lower()
    ctx = (name_words + " " + prompt_context.lower())

    # ── Zone inference ────────────────────────────────────
    zone = "public"  # default
    for kw, z in _ZONE_KEYWORDS.items():
        if kw in ctx:
            zone = z
            break

    # ── Weight (size priority) ───────────────────────────
    weight_by_zone = {
        "public": 18.0, "private": 14.0, "service": 12.0,
        "utility": 10.0, "recreation": 24.0, "security": 12.0,
    }
    weight = weight_by_zone.get(zone, 16.0)

    # ── min_area ─────────────────────────────────────────
    area_by_zone = {
        "public": 12.0, "private": 10.0, "service": 8.0,
        "utility": 6.0, "recreation": 18.0, "security": 8.0,
    }
    min_area = area_by_zone.get(zone, 12.0)

    # ── Furniture ─────────────────────────────────────────
    furniture: List[str] = []
    for kw, items in _FURNITURE_KEYWORDS.items():
        if kw in ctx:
            furniture = items
            break
    if not furniture:
        furniture = ["chair", "table"]  # generic default

    # ── Windows ───────────────────────────────────────────
    windows = "partial"
    for kw, w in _WINDOW_KEYWORDS.items():
        if kw in ctx:
            windows = w
            break

    # ── Colour ────────────────────────────────────────────
    r, g, b = _palette_from_name(canonical)
    hex_color = f"#{r:02x}{g:02x}{b:02x}"

    # ── Build entry ──────────────────────────────────────
    label = canonical.replace("_", " ").upper()
    aliases = [canonical.replace("_", " "), canonical]

    meta: Dict[str, Any] = {
        "zone": zone,
        "weight": weight,
        "min_area": min_area,
        "color": [r, g, b],
        "hex_color": hex_color,
        "windows": windows,
        "furniture": furniture,
        "label": label,
        "aliases": aliases,
        "is_dynamic": True,
    }

    # Cache
    ROOM_TAXONOMY[canonical] = meta
    for alias in aliases:
        _ALIAS_MAP[alias.lower()] = canonical

    print(f"[Taxonomy] Synthesised dynamic room: '{canonical}' -> zone={zone}, furniture={furniture}")
    return meta


def list_all_types() -> List[str]:
    """Returns all canonical room type keys (including dynamically added ones)."""
    return list(ROOM_TAXONOMY.keys())
