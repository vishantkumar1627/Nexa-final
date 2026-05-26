import cv2
import numpy as np
from typing import Dict, Any, List, Tuple

class FloorplanVectorizationService:
    def _draw_furniture_svg(self, room_type: str, box: List[int]) -> List[str]:
        """Procedurally constructs gorgeous detailed vector SVG elements for furniture, stairs, cars, and fixtures."""
        x1, y1, x2, y2 = box
        w = x2 - x1
        h = y2 - y1
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        
        lines = []
        room_type = room_type.lower()
        
        # Style tokens
        furniture_color = "#4a5568"
        furniture_fill = "#f7fafc"
        wood_color = "#cbd5e0"
        bed_accent = "#e2e8f0"
        
        if "bedroom" in room_type:
            # 1. DRAW A GORGEOUS BED (with pillows, sheets, and side tables!)
            bed_w = w * 0.55
            bed_h = h * 0.65
            bx1 = cx - bed_w / 2
            by1 = y1 + 12  # Snapped near top wall
            
            # Bed frame outline
            lines.append(f'  <rect x="{bx1}" y="{by1}" width="{bed_w}" height="{bed_h}" rx="3" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="2" />')
            
            # Mattress indent
            lines.append(f'  <rect x="{bx1 + 3}" y="{by1 + 3}" width="{bed_w - 6}" height="{bed_h - 6}" rx="1" fill="none" stroke="{furniture_color}" stroke-width="0.75" />')
            
            # Pillows
            pillow_w = bed_w * 0.38
            pillow_h = bed_h * 0.18
            px1 = bx1 + bed_w * 0.08
            px2 = bx1 + bed_w * 0.54
            py = by1 + bed_h * 0.06
            lines.append(f'  <rect x="{px1}" y="{py}" width="{pillow_w}" height="{pillow_h}" rx="2" fill="#ffffff" stroke="{furniture_color}" stroke-width="1" />')
            lines.append(f'  <rect x="{px2}" y="{py}" width="{pillow_w}" height="{pillow_h}" rx="2" fill="#ffffff" stroke="{furniture_color}" stroke-width="1" />')
            
            # Duvet fold
            dy = by1 + bed_h * 0.32
            lines.append(f'  <line x1="{bx1}" y1="{dy}" x2="{bx1 + bed_w}" y2="{dy}" stroke="{furniture_color}" stroke-width="1" />')
            lines.append(f'  <path d="M {bx1} {dy} L {bx1 + 8} {dy - 4} L {bx1 + bed_w - 8} {dy - 4} L {bx1 + bed_w} {dy}" fill="none" stroke="{furniture_color}" stroke-width="1" />')
            
            # Side tables
            table_size = min(w * 0.12, 20)
            tx1 = bx1 - table_size - 4
            tx2 = bx1 + bed_w + 4
            ty = by1 + 2
            lines.append(f'  <rect x="{tx1}" y="{ty}" width="{table_size}" height="{table_size}" rx="2" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="1" />')
            lines.append(f'  <rect x="{tx2}" y="{ty}" width="{table_size}" height="{table_size}" rx="2" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="1" />')
            # Table lamps
            lines.append(f'  <circle cx="{tx1 + table_size/2}" cy="{ty + table_size/2}" r="{table_size * 0.3}" fill="#ffeb3b" fill-opacity="0.3" stroke="{furniture_color}" stroke-width="0.75" />')
            lines.append(f'  <circle cx="{tx2 + table_size/2}" cy="{ty + table_size/2}" r="{table_size * 0.3}" fill="#ffeb3b" fill-opacity="0.3" stroke="{furniture_color}" stroke-width="0.75" />')
            
            # 2. DRAW A WARDROBE
            ward_w = w * 0.65
            ward_h = min(h * 0.14, 22)
            wx = cx - ward_w / 2
            wy = y2 - ward_h - 6
            lines.append(f'  <rect x="{wx}" y="{wy}" width="{ward_w}" height="{ward_h}" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="1.5" />')
            lines.append(f'  <text x="{cx}" y="{wy + ward_h/2 + 3}" font-family="Inter, sans-serif" font-weight="600" font-size="8px" fill="{furniture_color}" text-anchor="middle" letter-spacing="1">WARDROBE</text>')
            # Hanger lines inside wardrobe
            for hx in np.linspace(wx + 8, wx + ward_w - 8, 6):
                lines.append(f'  <line x1="{hx - 2}" y1="{wy + 3}" x2="{hx + 2}" y2="{wy + 3}" stroke="{wood_color}" stroke-width="0.75" />')
                lines.append(f'  <line x1="{hx}" y1="{wy + 3}" x2="{hx}" y2="{wy + ward_h - 3}" stroke="{wood_color}" stroke-width="0.75" />')
                
        elif "living" in room_type or "drawing" in room_type:
            # 1. DRAW A GORGEOUS SOFA SET & COFFEE TABLE
            sofa_w = w * 0.70
            sofa_h = min(h * 0.20, 32)
            sx = cx - sofa_w / 2
            sy = y1 + 10
            
            # Sofa base
            lines.append(f'  <rect x="{sx}" y="{sy}" width="{sofa_w}" height="{sofa_h}" rx="3" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="2" />')
            # Armrests
            lines.append(f'  <rect x="{sx}" y="{sy}" width="6" height="{sofa_h}" rx="1" fill="#ffffff" stroke="{furniture_color}" stroke-width="1" />')
            lines.append(f'  <rect x="{sx + sofa_w - 6}" y="{sy}" width="6" height="{sofa_h}" rx="1" fill="#ffffff" stroke="{furniture_color}" stroke-width="1" />')
            # Cushions
            c_w = (sofa_w - 12) / 3
            for ci in range(3):
                cx1 = sx + 6 + ci * c_w
                lines.append(f'  <rect x="{cx1 + 1}" y="{sy + 4}" width="{c_w - 2}" height="{sofa_h - 8}" rx="1" fill="#ffffff" stroke="{furniture_color}" stroke-width="1" />')
                
            # Sofa opposite chair or secondary seats
            lines.append(f'  <rect x="{sx}" y="{y2 - sofa_h - 10}" width="{sofa_w}" height="{sofa_h}" rx="3" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="2" />')
            for ci in range(3):
                cx1 = sx + 6 + ci * c_w
                lines.append(f'  <rect x="{cx1 + 1}" y="{y2 - sofa_h - 10 + 4}" width="{c_w - 2}" height="{sofa_h - 8}" rx="1" fill="#ffffff" stroke="{furniture_color}" stroke-width="1" />')
            
            # 2. DRAW COFFEE TABLE
            table_w = sofa_w * 0.38
            table_h = min(h * 0.14, 22)
            tx = cx - table_w / 2
            ty = cy - table_h / 2
            lines.append(f'  <rect x="{tx}" y="{ty}" width="{table_w}" height="{table_h}" rx="2" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="1" stroke-dasharray="2,2" />')
            lines.append(f'  <line x1="{tx}" y1="{ty}" x2="{tx+table_w}" y2="{ty+table_h}" stroke="{wood_color}" stroke-width="0.5" />')
            lines.append(f'  <line x1="{tx}" y1="{ty+table_h}" x2="{tx+table_w}" y2="{ty}" stroke="{wood_color}" stroke-width="0.5" />')
            
            # 3. DRAW T.V. UNIT
            tv_w = w * 0.40
            tv_h = 8
            lines.append(f'  <rect x="{cx - tv_w/2}" y="{y1 + 1}" width="{tv_w}" height="{tv_h}" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="1" />')
            lines.append(f'  <text x="{cx}" y="{y1 + 7}" font-family="Inter, sans-serif" font-weight="600" font-size="6px" fill="{furniture_color}" text-anchor="middle">T.V. UNIT</text>')
            
        elif "bathroom" in room_type or "toilet" in room_type:
            # 1. DRAW A DETAILED TOILET BOWL
            toilet_w = min(w * 0.20, 20)
            toilet_h = min(h * 0.30, 28)
            tox = x2 - toilet_w - 12
            toy = y1 + 12
            lines.append(f'  <rect x="{tox}" y="{toy}" width="{toilet_w}" height="6" rx="1" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="1.5" />')
            lines.append(f'  <path d="M {tox + 2} {toy + 6} Q {tox + toilet_w/2} {toy + toilet_h}, {tox + toilet_w - 2} {toy + 6} Z" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="1.5" />')
            lines.append(f'  <ellipse cx="{tox + toilet_w/2}" cy="{toy + 14}" rx="{toilet_w/2 - 3}" ry="5" fill="#ffffff" stroke="{furniture_color}" stroke-width="0.75" />')
            
            # 2. DRAW WASH BASIN SINK
            basin_w = min(w * 0.22, 22)
            basin_h = min(h * 0.20, 18)
            bax = x1 + 12
            bay = y1 + 12
            lines.append(f'  <rect x="{bax}" y="{bay}" width="{basin_w}" height="{basin_h}" rx="2" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="1.5" />')
            lines.append(f'  <ellipse cx="{bax + basin_w/2}" cy="{bay + basin_h/2}" rx="{basin_w/2 - 3}" ry="{basin_h/2 - 3}" fill="#ffffff" stroke="{furniture_color}" stroke-width="0.75" />')
            lines.append(f'  <line x1="{bax + basin_w/2}" y1="{bay}" x2="{bax + basin_w/2}" y2="{bay + 3}" stroke="{furniture_color}" stroke-width="1" />')
            
            # 3. SHOWER AREA WITH TILE HATCH
            show_w = min(w * 0.38, 40)
            show_h = min(h * 0.38, 40)
            shx = x1 + 12
            shy = y2 - show_h - 12
            lines.append(f'  <rect x="{shx}" y="{shy}" width="{show_w}" height="{show_h}" fill="none" stroke="{furniture_color}" stroke-width="1" stroke-dasharray="2,2" />')
            lines.append(f'  <circle cx="{shx + show_w/2}" cy="{shy + show_h/2}" r="2" fill="none" stroke="{furniture_color}" stroke-width="1" />')
            lines.append(f'  <line x1="{shx}" y1="{shy}" x2="{shx + show_w}" y2="{shy + show_h}" stroke="{furniture_color}" stroke-width="0.5" stroke-dasharray="2,2" />')
            lines.append(f'  <line x1="{shx + show_w}" y1="{shy}" x2="{shx}" y2="{shy + show_h}" stroke="{furniture_color}" stroke-width="0.5" stroke-dasharray="2,2" />')

        elif "kitchen" in room_type:
            # 1. DRAW L-SHAPED KITCHEN COUNTER
            cnt_d = min(w * 0.20, 24)
            lines.append(f'  <rect x="{x1 + 8}" y="{y1 + 8}" width="{w - 16}" height="{cnt_d}" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="1.5" />')
            lines.append(f'  <rect x="{x1 + 8}" y="{y1 + 8}" width="{cnt_d}" height="{h - 16}" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="1.5" />')
            
            # 2. DRAW COOKTOP STOVE
            stove_w = 35
            stove_h = 20
            stx = x1 + cnt_d + 12
            sty = y1 + 10
            lines.append(f'  <rect x="{stx}" y="{sty}" width="{stove_w}" height="{stove_h}" rx="2" fill="#ffffff" stroke="{furniture_color}" stroke-width="1.25" />')
            lines.append(f'  <circle cx="{stx + 9}" cy="{sty + 5}" r="3" fill="none" stroke="{furniture_color}" stroke-width="1" />')
            lines.append(f'  <circle cx="{stx + 26}" cy="{sty + 5}" r="3" fill="none" stroke="{furniture_color}" stroke-width="1" />')
            lines.append(f'  <circle cx="{stx + 9}" cy="{sty + 15}" r="3" fill="none" stroke="{furniture_color}" stroke-width="1" />')
            lines.append(f'  <circle cx="{stx + 26}" cy="{sty + 15}" r="3" fill="none" stroke="{furniture_color}" stroke-width="1" />')
            
            # 3. DRAW KITCHEN SINK
            sink_w = 28
            sink_h = 16
            six = x1 + 10
            siy = y1 + h/2 - sink_h/2
            lines.append(f'  <rect x="{six}" y="{siy}" width="{sink_w}" height="{sink_h}" rx="2" fill="#ffffff" stroke="{furniture_color}" stroke-width="1.25" />')
            lines.append(f'  <rect x="{six + 2}" y="{siy + 2}" width="{sink_w - 4}" height="{sink_h - 4}" rx="1" fill="none" stroke="{furniture_color}" stroke-width="0.75" />')
            lines.append(f'  <circle cx="{six + sink_w - 3}" cy="{siy + sink_h/2}" r="1" fill="{furniture_color}" />')
            lines.append(f'  <line x1="{six + sink_w - 3}" y1="{siy + sink_h/2}" x2="{six + sink_w - 8}" y2="{siy + sink_h/2}" stroke="{furniture_color}" stroke-width="1" />')

        elif "garage" in room_type or "parking" in room_type:
            # 1. DRAW A GORGEOUS DETAILED CAR VECTOR
            car_w = w * 0.45
            car_h = h * 0.75
            cx1 = cx - car_w / 2
            cy1 = cy - car_h / 2
            
            # Car body outline
            lines.append(f'  <rect x="{cx1}" y="{cy1}" width="{car_w}" height="{car_h}" rx="12" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="2" />')
            # Windshields
            lines.append(f'  <path d="M {cx1 + 5} {cy1 + car_h * 0.28} Q {cx} {cy1 + car_h * 0.22}, {cx1 + car_w - 5} {cy1 + car_h * 0.28} L {cx1 + car_w - 8} {cy1 + car_h * 0.38} Q {cx} {cy1 + car_h * 0.35}, {cx1 + 8} {cy1 + car_h * 0.38} Z" fill="#ffffff" stroke="{furniture_color}" stroke-width="1" />')
            lines.append(f'  <path d="M {cx1 + 6} {cy1 + car_h * 0.78} Q {cx} {cy1 + car_h * 0.82}, {cx1 + car_w - 6} {cy1 + car_h * 0.78} L {cx1 + car_w - 10} {cy1 + car_h * 0.70} Q {cx} {cy1 + car_h * 0.72}, {cx1 + 10} {cy1 + car_h * 0.70} Z" fill="#ffffff" stroke="{furniture_color}" stroke-width="1" />')
            # Mirrors
            lines.append(f'  <rect x="{cx1 - 3}" y="{cy1 + car_h * 0.22}" width="3" height="6" rx="1" fill="{furniture_color}" />')
            lines.append(f'  <rect x="{cx1 + car_w}" y="{cy1 + car_h * 0.22}" width="3" height="6" rx="1" fill="{furniture_color}" />')
            # Steering wheel & seats
            lines.append(f'  <circle cx="{cx1 + 12}" cy="{cy1 + car_h * 0.45}" r="4" fill="none" stroke="{furniture_color}" stroke-width="1.25" />')
            lines.append(f'  <rect x="{cx1 + 6}" y="{cy1 + car_h * 0.48}" width="{car_w/2 - 8}" height="12" rx="2" fill="none" stroke="{furniture_color}" stroke-width="1.25" />')
            lines.append(f'  <rect x="{cx + 2}" y="{cy1 + car_h * 0.48}" width="{car_w/2 - 8}" height="12" rx="2" fill="none" stroke="{furniture_color}" stroke-width="1.25" />')
            # Tires
            lines.append(f'  <rect x="{cx1 - 2}" y="{cy1 + 10}" width="2" height="12" rx="1" fill="{furniture_color}" />')
            lines.append(f'  <rect x="{cx1 + car_w}" y="{cy1 + 10}" width="2" height="12" rx="1" fill="{furniture_color}" />')
            lines.append(f'  <rect x="{cx1 - 2}" y="{cy1 + car_h - 22}" width="2" height="12" rx="1" fill="{furniture_color}" />')
            lines.append(f'  <rect x="{cx1 + car_w}" y="{cy1 + car_h - 22}" width="2" height="12" rx="1" fill="{furniture_color}" />')

        elif "balcony" in room_type:
            lines.append(f'  <rect x="{x1}" y="{y1}" width="{w}" height="{h}" fill="none" stroke="{furniture_color}" stroke-width="1" />')
            # Railing balusters
            for bx in range(x1 + 6, x2, 10):
                lines.append(f'  <line x1="{bx}" y1="{y1}" x2="{bx}" y2="{y2}" stroke="{wood_color}" stroke-width="0.5" stroke-dasharray="2,2" />')
            # Railing borders
            lines.append(f'  <line x1="{x1}" y1="{y1 + 3}" x2="{x2}" y2="{y1 + 3}" stroke="{furniture_color}" stroke-width="2" />')
            lines.append(f'  <line x1="{x1}" y1="{y2 - 3}" x2="{x2}" y2="{y2 - 3}" stroke="{furniture_color}" stroke-width="2" />')

        elif "wash" in room_type or "stair" in room_type:
            # DRAW A BEAUTIFUL STAIR BLOCK
            st_w = w * 0.80
            st_h = h * 0.70
            stx = cx - st_w / 2
            sty = cy - st_h / 2
            # Stair outline
            lines.append(f'  <rect x="{stx}" y="{sty}" width="{st_w}" height="{st_h}" fill="{furniture_fill}" stroke="{furniture_color}" stroke-width="2" />')
            # Steps lines
            num_steps = 7
            for step in range(1, num_steps):
                step_x = stx + (st_w / num_steps) * step
                lines.append(f'  <line x1="{step_x}" y1="{sty}" x2="{step_x}" y2="{sty + st_h}" stroke="{furniture_color}" stroke-width="1.5" />')
            # Directional arrow
            lines.append(f'  <line x1="{stx + 10}" y1="{cy}" x2="{stx + st_w - 10}" y2="{cy}" stroke="{furniture_color}" stroke-width="1.5" />')
            lines.append(f'  <path d="M {stx + st_w - 16} {cy - 4} L {stx + st_w - 10} {cy} L {stx + st_w - 16} {cy + 4}" fill="none" stroke="{furniture_color}" stroke-width="1.5" />')

        return lines

    def vectorize_layout(self, layout_metadata: Dict[str, Any], image_bytes: bytes) -> Tuple[str, str, Dict[str, Any]]:
        """Vectorizes a raster floor plan using coordinate metadata and OpenCV contours, returning SVG, DXF, and Vector JSON."""
        
        # 1. Simulate OpenCV contour extraction
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            contours, hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            extracted_polygons = []
            for cnt in contours:
                epsilon = 0.02 * cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, epsilon, True)
                if len(approx) >= 4:
                    extracted_polygons.append(approx.tolist())
        except Exception as e:
            print(f"Warning: OpenCV analysis fallback activated: {e}")
            extracted_polygons = []

        # Parse coordinate metadata
        rooms = layout_metadata.get("rooms", [])
        walls = layout_metadata.get("walls", [])
        doors = layout_metadata.get("doors", [])
        windows = layout_metadata.get("windows", [])
        scale = layout_metadata.get("scale_px_to_meter", 50)
        width = layout_metadata.get("width_px", 800)
        height = layout_metadata.get("height_px", 600)

        # Calculate bounding envelope of all rooms for structural walls & dimensions
        all_x1 = [r["box"][0] for r in rooms]
        all_y1 = [r["box"][1] for r in rooms]
        all_x2 = [r["box"][2] for r in rooms]
        all_y2 = [r["box"][3] for r in rooms]
        
        min_x = min(all_x1) if all_x1 else 80
        min_y = min(all_y1) if all_y1 else 80
        max_x = max(all_x2) if all_x2 else 720
        max_y = max(all_y2) if all_y2 else 520

        # ==========================================
        # 2. GENERATE GORGEOUS SVG (Architectural Blueprint Style)
        # ==========================================
        svg_lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background-color: #faf8f5;">',
            '  <!-- Floorplan styling definitions -->',
            '  <style>',
            '    .room { stroke: #cbd5e0; stroke-width: 1; fill-opacity: 0.15; }',
            '    .wall { stroke: #1a202c; stroke-width: 4; stroke-linecap: round; }',
            '    .outer-wall { stroke: #1a202c; stroke-width: 8; stroke-linejoin: round; fill: none; }',
            '    .window { stroke: #3182ce; stroke-width: 6; stroke-linecap: round; }',
            '    .door-swing { stroke: #e53e3e; stroke-width: 1; fill: none; stroke-dasharray: 3,3; }',
            '    .door-panel { stroke: #e53e3e; stroke-width: 2.5; }',
            '    .label { font-family: "Outfit", "Inter", sans-serif; font-weight: 700; font-size: 13px; fill: #1a202c; text-anchor: middle; letter-spacing: 0.5px; }',
            '    .dims { font-family: "Inter", sans-serif; font-weight: 500; font-size: 9px; fill: #4a5568; text-anchor: middle; }',
            '    .dim-line { stroke: #718096; stroke-width: 0.75; }',
            '    .dim-tick { stroke: #2d3748; stroke-width: 1.5; }',
            '    .dim-text { font-family: "Outfit", "Inter", sans-serif; font-weight: 700; font-size: 14px; fill: #1a202c; text-anchor: middle; }',
            '    .legend-title { font-family: "Outfit", "Inter", sans-serif; font-weight: 800; font-size: 16px; fill: #1a202c; letter-spacing: 1px; }',
            '    .legend-sub { font-family: "Inter", sans-serif; font-weight: 400; font-size: 9px; fill: #718096; }',
            '  </style>'
        ]

        # Draw Rooms
        for room in rooms:
            x1, y1, x2, y2 = room["box"]
            color = room["color"]
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            svg_lines.append(f'  <rect class="room" x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" fill="{hex_color}" />')

        # Draw Procedural Furniture vectors inside rooms
        for room in rooms:
            svg_lines.extend(self._draw_furniture_svg(room["id"], room["box"]))

        # Draw Walls
        for wall in walls:
            x1, y1, x2, y2, _ = wall
            svg_lines.append(f'  <line class="wall" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" />')

        # Draw a bold Outer Building Wall Envelope (double-line look)
        svg_lines.append(f'  <rect class="outer-wall" x="{min_x}" y="{min_y}" width="{max_x - min_x}" height="{max_y - min_y}" />')

        # Draw Windows
        for win in windows:
            wx1, wy1 = win["start"]
            wx2, wy2 = win["end"]
            svg_lines.append(f'  <line class="window" x1="{wx1}" y1="{wy1}" x2="{wx2}" y2="{wy2}" />')

        # Draw Doors
        for door in doors:
            dcx, dcy = door["center"]
            svg_lines.append(f'  <path class="door-swing" d="M {dcx} {dcy-12} A 12 12 0 0 1 {dcx+12} {dcy}" />')
            svg_lines.append(f'  <line class="door-panel" x1="{dcx}" y1="{dcy}" x2="{dcx}" y2="{dcy-12}" />')

        # Draw Room Annotation Text Labels
        for room in rooms:
            x1, y1, x2, y2 = room["box"]
            rx, ry = (x1 + x2) / 2, (y1 + y2) / 2
            
            # Avoid labels overlapping centered beds/furniture by shifting them slightly down
            label_y = ry + 22 if "bedroom" in room["id"].lower() else (ry + 18 if "living" in room["id"].lower() or "drawing" in room["id"].lower() else ry)
            
            label = room["id"].replace("_", " ").upper()
            w_m = (x2 - x1) / scale
            h_m = (y2 - y1) / scale
            # Convert to feet/inches for professional CAD look
            w_ft = w_m * 3.28084
            h_ft = h_m * 3.28084
            dims_txt = f"{int(w_ft)}'-0\" X {int(h_ft)}'-0\""
            
            svg_lines.append(f'  <text class="label" x="{rx}" y="{label_y}">{label}</text>')
            svg_lines.append(f'  <text class="dims" x="{rx}" y="{label_y+13}">{dims_txt}</text>')

        # ==========================================
        # DRAW BLUEPRINT DIMENSIONS (Top and Right)
        # ==========================================
        width_m = (max_x - min_x) / scale
        height_m = (max_y - min_y) / scale
        width_ft = int(width_m * 3.28084)
        height_ft = int(height_m * 3.28084)

        # Count bedrooms to determine BHK dynamically
        bed_count = sum(1 for r in rooms if "bedroom" in r["id"].lower())
        bhk_str = f"{bed_count}BHK" if bed_count > 0 else "STUDIO"

        # 1. TOP DIMENSION
        dim_y = min_y - 25
        svg_lines.extend([
            f'  <!-- Top Dimension -->',
            f'  <line class="dim-line" x1="{min_x}" y1="{dim_y}" x2="{max_x}" y2="{dim_y}" />',
            f'  <line class="dim-line" x1="{min_x}" y1="{min_y}" x2="{min_x}" y2="{dim_y - 8}" />',
            f'  <line class="dim-line" x1="{max_x}" y1="{min_y}" x2="{max_x}" y2="{dim_y - 8}" />',
            f'  <!-- Slanted architectural ticks -->',
            f'  <line class="dim-tick" x1="{min_x - 5}" y1="{dim_y + 5}" x2="{min_x + 5}" y2="{dim_y - 5}" />',
            f'  <line class="dim-tick" x1="{max_x - 5}" y1="{dim_y + 5}" x2="{max_x + 5}" y2="{dim_y - 5}" />',
            f'  <rect x="{(min_x+max_x)/2 - 25}" y="{dim_y - 12}" width="50" height="18" fill="#faf8f5" />',
            f'  <text class="dim-text" x="{(min_x+max_x)/2}" y="{dim_y + 2}">{width_ft}\'</text>'
        ])

        # 2. RIGHT DIMENSION
        dim_x = max_x + 25
        svg_lines.extend([
            f'  <!-- Right Dimension -->',
            f'  <line class="dim-line" x1="{dim_x}" y1="{min_y}" x2="{dim_x}" y2="{max_y}" />',
            f'  <line class="dim-line" x1="{max_x}" y1="{min_y}" x2="{dim_x + 8}" y2="{min_y}" />',
            f'  <line class="dim-line" x1="{max_x}" y1="{max_y}" x2="{dim_x + 8}" y2="{max_y}" />',
            f'  <!-- Slanted architectural ticks -->',
            f'  <line class="dim-tick" x1="{dim_x - 5}" y1="{min_y + 5}" x2="{dim_x + 5}" y2="{min_y - 5}" />',
            f'  <line class="dim-tick" x1="{dim_x - 5}" y1="{max_y + 5}" x2="{dim_x + 5}" y2="{max_y - 5}" />',
            f'  <rect x="{dim_x - 12}" y="{(min_y+max_y)/2 - 12}" width="24" height="24" fill="#faf8f5" />',
            f'  <text class="dim-text" x="{dim_x}" y="{(min_y+max_y)/2 + 5}">{height_ft}\'</text>'
        ])

        # ==========================================
        # DRAW PROFESSIONAL TITLE LEGEND BLOCK
        # ==========================================
        legend_y = 535
        # Legend frame
        svg_lines.extend([
            f'  <!-- Legend Border Frame -->',
            f'  <rect x="40" y="{legend_y}" width="{width - 80}" height="50" fill="#ffffff" stroke="#1a202c" stroke-width="1.5" />',
            f'  <line x1="280" y1="{legend_y}" x2="280" y2="{legend_y + 50}" stroke="#1a202c" stroke-width="1" />',
            f'  <line x1="560" y1="{legend_y}" x2="560" y2="{legend_y + 50}" stroke="#1a202c" stroke-width="1" />',
            
            f'  <!-- Column 1: Compass -->',
            f'  <circle cx="80" cy="{legend_y + 25}" r="15" fill="none" stroke="#2d3748" stroke-width="1" />',
            f'  <path d="M 80 {legend_y + 10} L 80 {legend_y + 40} M 65 {legend_y + 25} L 95 {legend_y + 25}" stroke="#cbd5e0" stroke-width="0.5" />',
            f'  <path d="M 80 {legend_y + 10} L 83 {legend_y + 25} L 77 {legend_y + 25} Z" fill="#1a202c" />',
            f'  <path d="M 80 {legend_y + 40} L 83 {legend_y + 25} L 77 {legend_y + 25} Z" fill="#718096" />',
            f'  <text x="80" y="{legend_y + 8}" font-family="Inter" font-weight="700" font-size="7px" fill="#1a202c" text-anchor="middle">N</text>',
            
            f'  <!-- Column 2: Logo -->',
            f'  <text class="legend-title" x="420" y="{legend_y + 22}" text-anchor="middle">2D HOUSE PLAN</text>',
            f'  <text class="legend-sub" x="420" y="{legend_y + 36}" text-anchor="middle">Procedurally generated by Nex Architecture AI</text>',
            
            f'  <!-- Column 3: Metrics Info -->',
            f'  <text x="580" y="{legend_y + 22}" font-family="Outfit, Inter" font-weight="700" font-size="12px" fill="#1a202c">{width_ft}\'-0\" X {height_ft}\'-0\", {bhk_str}</text>',
            f'  <text x="580" y="{legend_y + 38}" font-family="Inter" font-weight="700" font-size="11px" fill="#718096" letter-spacing="1">GROUND FLOOR PLAN</text>'
        ])

        svg_lines.append('</svg>')
        svg_content = "\n".join(svg_lines)

        # ==========================================
        # 3. GENERATE CAD-COMPATIBLE DXF
        # ==========================================
        # DXF is a clean text format. Let's write standard elements in ENTITIES section.
        dxf_lines = [
            "  0", "SECTION",
            "  2", "HEADER",
            "  0", "ENDSEC",
            "  0", "SECTION",
            "  2", "TABLES",
            "  0", "ENDSEC",
            "  0", "SECTION",
            "  2", "BLOCKS",
            "  0", "ENDSEC",
            "  0", "SECTION",
            "  2", "ENTITIES"
        ]

        # Draw rooms (represented as closed 2D polylines)
        for room in rooms:
            x1, y1, x2, y2 = room["box"]
            # In CAD, coordinates usually have inverted Y axis (Y pointing UP)
            # We scale from pixels to meters
            mx1, my1 = x1 / scale, (height - y1) / scale
            mx2, my2 = x2 / scale, (height - y2) / scale

            # Add a closed polyline
            dxf_lines.extend([
                "  0", "POLYLINE",
                "  8", "ROOMS",
                " 66", "1",
                " 70", "1", # Closed
                "  0", "VERTEX",
                "  8", "ROOMS",
                " 10", f"{mx1:.3f}", " 20", f"{my1:.3f}",
                "  0", "VERTEX",
                "  8", "ROOMS",
                " 10", f"{mx2:.3f}", " 20", f"{my1:.3f}",
                "  0", "VERTEX",
                "  8", "ROOMS",
                " 10", f"{mx2:.3f}", " 20", f"{my2:.3f}",
                "  0", "VERTEX",
                "  8", "ROOMS",
                " 10", f"{mx1:.3f}", " 20", f"{my2:.3f}",
                "  0", "SEQEND"
            ])

        # Draw structural walls (heavy lines in CAD layer WALLS)
        for wall in walls:
            x1, y1, x2, y2, _ = wall
            mx1, my1 = x1 / scale, (height - y1) / scale
            mx2, my2 = x2 / scale, (height - y2) / scale
            dxf_lines.extend([
                "  0", "LINE",
                "  8", "WALLS",
                " 10", f"{mx1:.3f}", " 20", f"{my1:.3f}", " 30", "0.0",
                " 11", f"{mx2:.3f}", " 21", f"{my2:.3f}", " 31", "0.0"
            ])

        # Draw window objects (layer WINDOWS)
        for win in windows:
            wx1, wy1 = win["start"]
            wx2, wy2 = win["end"]
            mx1, my1 = wx1 / scale, (height - wy1) / scale
            mx2, my2 = wx2 / scale, (height - wy2) / scale
            dxf_lines.extend([
                "  0", "LINE",
                "  8", "WINDOWS",
                " 10", f"{mx1:.3f}", " 20", f"{my1:.3f}", " 30", "0.0",
                " 11", f"{mx2:.3f}", " 21", f"{my2:.3f}", " 31", "0.0"
            ])

        dxf_lines.extend([
            "  0", "ENDSEC",
            "  0", "EOF"
        ])
        dxf_content = "\n".join(dxf_lines)

        # ==========================================
        # 4. GENERATE VECTOR JSON
        # ==========================================
        # High fidelity geometrical payload
        vector_json = {
            "canvas": {
                "width_px": width,
                "height_px": height,
                "width_meters": width / scale,
                "height_meters": height / scale,
                "scale": scale
            },
            "polygons": extracted_polygons,
            "rooms": [
                {
                    "name": room["id"],
                    "corners": [
                        [room["box"][0]/scale, (height-room["box"][1])/scale],
                        [room["box"][2]/scale, (height-room["box"][1])/scale],
                        [room["box"][2]/scale, (height-room["box"][3])/scale],
                        [room["box"][0]/scale, (height-room["box"][3])/scale]
                    ]
                }
                for room in rooms
            ],
            "structural_vectors": {
                "walls": [[w[0]/scale, (height-w[1])/scale, w[2]/scale, (height-w[3])/scale] for w in walls],
                "windows": [[wi["start"][0]/scale, (height-wi["start"][1])/scale, wi["end"][0]/scale, (height-wi["end"][1])/scale] for wi in windows]
            }
        }

        return svg_content, dxf_content, vector_json

floorplan_service = FloorplanVectorizationService()
