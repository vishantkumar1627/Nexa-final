"""
Building Code Validator — IS 962 / IBC Chapter 12 compliance checks.
Runs after layout generation and returns a list of violation dicts.
"""
from typing import Dict, Any, List
from services.room_taxonomy import resolve_room_type


# Minimum areas in square metres (IS 962 / IBC Chapter 12)
_MIN_AREAS: Dict[str, Dict[str, Any]] = {
    "bedroom":     {"min_sqm": 9.5,  "level": "warning"},
    "living_room": {"min_sqm": 12.0, "level": "warning"},
    "kitchen":     {"min_sqm": 5.0,  "level": "warning"},
    "bathroom":    {"min_sqm": 2.5,  "level": "error"},
}

# Minimum clear door width in metres
_MIN_DOOR_WIDTH_M = 0.81

# Minimum corridor clear width in metres
_MIN_CORRIDOR_WIDTH_M = 1.0

# Total floor area threshold above which two egress doors are required
_TWO_EGRESS_THRESHOLD_SQM = 80.0


class BuildingCodeValidator:
    """Validates a layout JSON dict against basic residential building codes."""

    def validate(self, layout_data: Dict[str, Any], dimensions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Checks the layout dict and returns violation dicts with keys:
          level (error|warning), code, message, room_id (or None).
        """
        violations: List[Dict[str, Any]] = []
        scale = layout_data.get("scale_px_to_meter", 50)
        rooms = layout_data.get("rooms", [])
        doors = layout_data.get("doors", [])

        # --- 1. Minimum room areas ---
        for room in rooms:
            canonical = resolve_room_type(room.get("id", ""))
            rule = _MIN_AREAS.get(canonical)
            if not rule:
                continue
            box = room.get("box", [0, 0, 0, 0])
            w_m = (box[2] - box[0]) / scale
            h_m = (box[3] - box[1]) / scale
            area_sqm = w_m * h_m
            if area_sqm < rule["min_sqm"]:
                violations.append({
                    "level": rule["level"],
                    "code": f"MIN_AREA_{canonical.upper()}",
                    "message": (
                        f"{canonical.replace('_', ' ').title()} '{room.get('id')}' "
                        f"is {area_sqm:.1f} m² — minimum is {rule['min_sqm']} m²."
                    ),
                    "room_id": room.get("id"),
                })

        # --- 2. Minimum corridor width ---
        for room in rooms:
            canonical = resolve_room_type(room.get("id", ""))
            if canonical not in ("corridor", "hallway"):
                continue
            box = room.get("box", [0, 0, 0, 0])
            w_m = (box[2] - box[0]) / scale
            h_m = (box[3] - box[1]) / scale
            min_dim_m = min(w_m, h_m)
            if min_dim_m < _MIN_CORRIDOR_WIDTH_M:
                violations.append({
                    "level": "error",
                    "code": "MIN_CORRIDOR_WIDTH",
                    "message": (
                        f"Corridor '{room.get('id')}' has clear width {min_dim_m:.2f} m "
                        f"— minimum is {_MIN_CORRIDOR_WIDTH_M} m."
                    ),
                    "room_id": room.get("id"),
                })

        # --- 3. Minimum door clear width ---
        for door in doors:
            door_width_m = door.get("width_m", DOOR_WIDTH_M if "DOOR_WIDTH_M" in dir() else 0.9)
            if door_width_m < _MIN_DOOR_WIDTH_M:
                violations.append({
                    "level": "warning",
                    "code": "MIN_DOOR_WIDTH",
                    "message": (
                        f"Door for room '{door.get('room_id')}' is {door_width_m:.2f} m wide "
                        f"— minimum clear width is {_MIN_DOOR_WIDTH_M} m."
                    ),
                    "room_id": door.get("room_id"),
                })

        # --- 4. Two-egress rule ---
        total_area = dimensions.get("area", 0.0)
        if total_area == 0.0:
            # Estimate from layout
            if rooms:
                all_x2 = max(r["box"][2] for r in rooms)
                all_x1 = min(r["box"][0] for r in rooms)
                all_y2 = max(r["box"][3] for r in rooms)
                all_y1 = min(r["box"][1] for r in rooms)
                total_area = ((all_x2 - all_x1) / scale) * ((all_y2 - all_y1) / scale)

        if total_area > _TWO_EGRESS_THRESHOLD_SQM:
            exterior_doors = [d for d in doors if d.get("is_entrance", False)]
            if len(exterior_doors) < 2:
                violations.append({
                    "level": "warning",
                    "code": "TWO_EGRESS_RULE",
                    "message": (
                        f"Floor area is {total_area:.0f} m² (> {_TWO_EGRESS_THRESHOLD_SQM} m²) "
                        f"but only {len(exterior_doors)} exterior egress door(s) found — 2 required."
                    ),
                    "room_id": None,
                })

        # --- 5. Room count sanity (from NLP-derived expected counts) ---
        expected_bedrooms = dimensions.get("bedroom_count", 0)
        actual_bedrooms = sum(
            1 for r in rooms if resolve_room_type(r.get("id", "")) == "bedroom"
        )
        if expected_bedrooms > 0 and actual_bedrooms == 0:
            violations.append({
                "level": "error",
                "code": "MISSING_BEDROOMS",
                "message": (
                    f"NLP requested {expected_bedrooms} bedroom(s) but none appear in the layout."
                ),
                "room_id": None,
            })

        return violations


code_validator = BuildingCodeValidator()
