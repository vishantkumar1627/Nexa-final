import os
import sys
import json
import math
import argparse

# =============================================================================
# PROCEDURAL 3D ARCHITECTURE GENERATOR
# Pipeline: Geometry -> Materials -> Procedural Furniture -> Lighting -> Eevee Render
# =============================================================================

# Inject backend path so Blender can import our taxonomy
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.room_taxonomy import resolve_room_type, get_room_meta


# Since this script runs inside Blender's Python shell, we import bpy safely
try:
    import bpy
    import addon_utils
except ImportError:
    # Fail-safe print if executed outside Blender environment
    print("Warning: This script is intended to be run inside a Blender environment (bpy module not found).")

def parse_args():
    """Parses standard command line arguments passed to Blender python."""
    args = []
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]

    parser = argparse.ArgumentParser(description="Procedural 3D Architecture Generator.")
    parser.add_argument("--layout-json", type=str, required=True, help="Path to layout coordinate JSON file")
    parser.add_argument("--output-dir", type=str, required=True, help="Directory to save gltf, obj, blend, and renders")
    return parser.parse_args()

def clean_scene():
    """Purges the standard default startup scene cubes, cameras, and lights."""
    if "bpy" not in sys.modules:
        return
    if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Purge orphan data
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in bpy.data.cameras:
        if block.users == 0:
            bpy.data.cameras.remove(block)
    for block in bpy.data.lights:
        if block.users == 0:
            bpy.data.lights.remove(block)

def create_principled_material(name: str, base_color: tuple, roughness: float = 0.5, specular: float = 0.5, metallic: float = 0.0, transmission: float = 0.0) -> bpy.types.Material:
    """Procedurally creates a material using Blender's Principled BSDF shader nodes."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    mat.node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    
    # Set inputs safely (handles both Blender 3.x and 4.x)
    def set_input(name, val):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = val

    set_input("Base Color", base_color)
    set_input("Roughness", roughness)
    set_input("Metallic", metallic)
    
    if "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = specular
    elif "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = specular
        
    if transmission > 0:
        if "Transmission" in bsdf.inputs:
            bsdf.inputs["Transmission"].default_value = transmission
        elif "Transmission Weight" in bsdf.inputs:
            bsdf.inputs["Transmission Weight"].default_value = transmission
            
    return mat

def create_wood_material(name: str, dark_color: tuple = (0.35, 0.2, 0.08, 1.0), light_color: tuple = (0.5, 0.32, 0.18, 1.0)) -> bpy.types.Material:
    """Creates a beautiful procedural wood texture with rings and grain using shader nodes."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    mat.node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    
    # Wave texture for wood rings
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = 'RINGS'
    wave.inputs["Scale"].default_value = 12.0
    wave.inputs["Distortion"].default_value = 2.0
    wave.inputs["Detail"].default_value = 3.0
    
    # Color Ramp
    color_ramp = nodes.new("ShaderNodeValToRGB")
    color_ramp.color_ramp.elements[0].color = dark_color
    color_ramp.color_ramp.elements[1].color = light_color
    
    mat.node_tree.links.new(wave.outputs["Color"], color_ramp.inputs["Fac"])
    mat.node_tree.links.new(color_ramp.outputs["Color"], bsdf.inputs["Base Color"])
    
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.4
        
    return mat

def create_tile_material(name: str, base_color: tuple, grout_color: tuple = (0.9, 0.9, 0.9, 1.0)) -> bpy.types.Material:
    """Creates a procedural checker tile texture using shader nodes."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    mat.node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    
    # Checker texture
    checker = nodes.new("ShaderNodeTexChecker")
    checker.inputs["Color1"].default_value = base_color
    checker.inputs["Color2"].default_value = grout_color
    checker.inputs["Scale"].default_value = 16.0
    
    mat.node_tree.links.new(checker.outputs["Color"], bsdf.inputs["Base Color"])
    
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.15  # Glossy tiles
        
    return mat

def create_marble_material(name: str, base_color: tuple = (0.95, 0.95, 0.95, 1.0), vein_color: tuple = (0.4, 0.4, 0.4, 1.0)) -> bpy.types.Material:
    """Creates a procedural polished marble texture with noise."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    mat.node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    
    # Noise texture
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 18.0
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Distortion"].default_value = 2.5
    
    # Color Ramp
    color_ramp = nodes.new("ShaderNodeValToRGB")
    color_ramp.color_ramp.elements[0].color = base_color
    color_ramp.color_ramp.elements[1].color = vein_color
    color_ramp.color_ramp.elements[0].position = 0.42
    color_ramp.color_ramp.elements[1].position = 0.58
    
    mat.node_tree.links.new(noise.outputs["Factor"], color_ramp.inputs["Fac"])
    mat.node_tree.links.new(color_ramp.outputs["Color"], bsdf.inputs["Base Color"])
    
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.12  # Highly reflective
        
    return mat

def create_glass_material(name: str) -> bpy.types.Material:
    """Creates a transparent/refractive glass material."""
    mat = create_principled_material(name, (0.85, 0.95, 1.0, 0.2), roughness=0.05, specular=1.0, transmission=1.0)
    mat.blend_method = 'BLEND'
    mat.shadow_method = 'NONE'
    return mat

# Geometry primitive helpers
def create_cube(name, location, scale, material=None, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    if material:
        obj.data.materials.append(material)
    if parent:
        obj.parent = parent
    return obj

def create_cylinder(name, location, radius, depth, rotation=(0, 0, 0), material=None, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    if parent:
        obj.parent = parent
    return obj

def create_sphere(name, location, radius, material=None, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=location)
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    if parent:
        obj.parent = parent
    return obj

# Coordinate Conversion Helper
def to_blender_coords(px, py, width, height, scale):
    bx = (px - width/2) / scale
    by = (height/2 - py) / scale
    return bx, by

def build_floorplan_3d(layout_data: dict, output_dir: str):
    """Procedurally constructs professional 3D interiors, furniture, materials, roofs and lights."""
    clean_scene()

    scale = layout_data.get("scale_px_to_meter", 50)
    width = layout_data.get("width_px", 800)
    height = layout_data.get("height_px", 600)
    rooms = layout_data.get("rooms", [])
    walls = layout_data.get("walls", [])
    doors = layout_data.get("doors", [])
    windows = layout_data.get("windows", [])
    style = layout_data.get("scoring", {}).get("style", "modern").lower()

    # Create Material Palette
    materials = {
        'wall': create_principled_material("Drywall_White", (0.95, 0.95, 0.93, 1.0), roughness=0.8),
        'floor_wood': create_wood_material("Hardwood_Brown"),
        'tile': create_tile_material("Tile_Bathroom", (0.75, 0.85, 0.85, 1.0)),
        'glass': create_glass_material("Glass_Translucent"),
        'wood_door': create_principled_material("Wood_Oak", (0.4, 0.25, 0.12, 1.0), roughness=0.55),
        'kitchen_surface': create_marble_material("Marble_Countertop"),
        'metal': create_principled_material("Metal_Chrome", (0.9, 0.9, 0.92, 1.0), roughness=0.15, specular=0.9, metallic=1.0),
        'dark_metal': create_principled_material("Metal_Slate", (0.15, 0.15, 0.17, 1.0), roughness=0.3, specular=0.5, metallic=0.9),
        'fabric_sofa': create_principled_material("Fabric_Sofa", (0.3, 0.45, 0.55, 1.0), roughness=0.9),
        'fabric_cushion': create_principled_material("Fabric_Cushion", (0.85, 0.75, 0.65, 1.0), roughness=0.85),
        'fabric_bed': create_principled_material("Fabric_Bed", (0.9, 0.9, 0.9, 1.0), roughness=0.8),
        'fabric_pillow': create_principled_material("Fabric_Pillow", (0.8, 0.82, 0.88, 1.0), roughness=0.8),
        'fabric_blanket': create_principled_material("Fabric_Blanket", (0.5, 0.25, 0.28, 1.0), roughness=0.85),
        'toilet_material': create_principled_material("Porcelain_White", (0.98, 0.98, 0.98, 1.0), roughness=0.08, specular=0.8),
        'roof': create_principled_material("Roof_Slab_Mat", (0.3, 0.32, 0.35, 1.0), roughness=0.7)
    }

    # Bounding box track for whole house (to place roof and position camera)
    min_house_x = 999.0
    max_house_x = -999.0
    min_house_y = 999.0
    max_house_y = -999.0

    # ==========================================
    # 1. GENERATE ROOM-BY-ROOM ARCHITECTURE (Floor, Ceiling, 4 Walls)
    # ==========================================
    wall_height = 2.8
    wall_thickness = 0.2
    wall_objs = []  # Keep tracks to apply boolean cuts later

    for idx, room in enumerate(rooms):
        rx1, ry1, rx2, ry2 = room["box"]
        x1, y1 = to_blender_coords(rx1, ry1, width, height, scale)
        x2, y2 = to_blender_coords(rx2, ry2, width, height, scale)
        
        # Track bounds
        min_house_x = min(min_house_x, x1, x2)
        max_house_x = max(max_house_x, x1, x2)
        min_house_y = min(min_house_y, y1, y2)
        max_house_y = max(max_house_y, y1, y2)

        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        size_x = abs(x2 - x1)
        size_y = abs(y2 - y1)
        floor_thickness = 0.05
        
        # 1. Floor mesh
        floor_obj = create_cube(f"Floor_{room['id']}", (cx, cy, -floor_thickness/2), (size_x, size_y, floor_thickness))
        if "bathroom" in room["id"].lower():
            floor_obj.data.materials.append(materials['tile'])
        else:
            floor_obj.data.materials.append(materials['floor_wood'])
            
        # 2. Ceiling mesh
        ceiling_obj = create_cube(f"Ceiling_{room['id']}", (cx, cy, wall_height + floor_thickness/2), (size_x, size_y, floor_thickness), materials['wall'])

        # 3. Left wall (West)
        wall_w = create_cube(f"Wall_W_{room['id']}", (x1, cy, wall_height/2), (wall_thickness, size_y + wall_thickness, wall_height), materials['wall'])
        wall_objs.append((wall_w, x1, cy))
        
        # 4. Right wall (East)
        wall_e = create_cube(f"Wall_E_{room['id']}", (x2, cy, wall_height/2), (wall_thickness, size_y + wall_thickness, wall_height), materials['wall'])
        wall_objs.append((wall_e, x2, cy))
        
        # 5. Top wall (North)
        wall_n = create_cube(f"Wall_N_{room['id']}", (cx, y2, wall_height/2), (size_x + wall_thickness, wall_thickness, wall_height), materials['wall'])
        wall_objs.append((wall_n, cx, y2))
        
        # 6. Bottom wall (South)
        wall_s = create_cube(f"Wall_S_{room['id']}", (cx, y1, wall_height/2), (size_x + wall_thickness, wall_thickness, wall_height), materials['wall'])
        wall_objs.append((wall_s, cx, y1))

    # Helper function to find closest wall to place Boolean openings
    def find_closest_wall(cx, cy):
        best_wall = None
        min_dist = 999.0
        for wall_obj, wx, wy in wall_objs:
            dist = math.sqrt((cx - wx)**2 + (cy - wy)**2)
            if dist < min_dist:
                min_dist = dist
                best_wall = wall_obj
        return best_wall if min_dist < 4.0 else None

    # ==========================================
    # 3. DOORS & WINDOWS WITH BOOLEAN CUTS
    # ==========================================
    # 3A. Draw Doors
    for idx, door in enumerate(doors):
        dcx, dcy = door["center"]
        direction = door["direction"]
        bx, by = to_blender_coords(dcx, dcy, width, height, scale)
        
        door_w = 0.9
        door_h = 2.1
        door_t = 0.04
        
        # Create Boolean Cutter object
        cutter_scale = (door_w, 0.35, door_h) if direction == "horizontal" else (0.35, door_w, door_h)
        cutter = create_cube(f"DoorCutter_{idx}", (bx, by, door_h/2), cutter_scale)
        
        # Apply subtraction to closest wall
        target_wall = find_closest_wall(bx, by)
        if target_wall:
            bool_mod = target_wall.modifiers.new(name=f"DoorCut_{idx}", type='BOOLEAN')
            bool_mod.operation = 'DIFFERENCE'
            bool_mod.object = cutter
            # Hide cutter from renders
            cutter.hide_viewport = True
            cutter.hide_render = True
            
        # Draw physical door frame and panel
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=(bx, by, 0.0))
        door_group = bpy.context.active_object
        door_group.name = f"DoorGroup_{idx}"
        
        if direction == "horizontal":
            # Left Frame Post
            create_cube("Frame_L", (bx - door_w/2 - 0.02, by, door_h/2), (0.04, 0.15, door_h), materials['wood_door'], door_group)
            # Right Frame Post
            create_cube("Frame_R", (bx + door_w/2 + 0.02, by, door_h/2), (0.04, 0.15, door_h), materials['wood_door'], door_group)
            # Header Frame
            create_cube("Frame_H", (bx, by, door_h + 0.02), (door_w + 0.08, 0.15, 0.04), materials['wood_door'], door_group)
            # Ajar Door panel
            angle = math.radians(40)
            px = bx - door_w/2 + math.cos(angle) * door_w/2
            py = by + math.sin(angle) * door_w/2
            panel = create_cube("DoorPanel", (px, py, door_h/2), (door_w, door_t, door_h), materials['wood_door'], door_group)
            panel.rotation_euler[2] = angle
            # Door Handle knob
            create_sphere("Handle_L", (px + math.cos(angle) * 0.35, py + math.sin(angle) * 0.35, 1.0), 0.035, materials['metal'], door_group)
        else:
            # Bottom Frame Post
            create_cube("Frame_B", (bx, by - door_w/2 - 0.02, door_h/2), (0.15, 0.04, door_h), materials['wood_door'], door_group)
            # Top Frame Post
            create_cube("Frame_T", (bx, by + door_w/2 + 0.02, door_h/2), (0.15, 0.04, door_h), materials['wood_door'], door_group)
            # Header Frame
            create_cube("Frame_H", (bx, by, door_h + 0.02), (0.15, door_w + 0.08, 0.04), materials['wood_door'], door_group)
            # Ajar Door panel
            angle = math.radians(40)
            px = bx + math.sin(angle) * door_w/2
            py = by - door_w/2 + math.cos(angle) * door_w/2
            panel = create_cube("DoorPanel", (px, py, door_h/2), (door_t, door_w, door_h), materials['wood_door'], door_group)
            panel.rotation_euler[2] = -angle
            create_sphere("Handle_V", (px + math.sin(angle) * 0.35, py + math.cos(angle) * 0.35, 1.0), 0.035, materials['metal'], door_group)

    # 3B. Draw Windows
    for idx, win in enumerate(windows):
        wx1, wy1 = win["start"]
        wx2, wy2 = win["end"]
        x1, y1 = to_blender_coords(wx1, wy1, width, height, scale)
        x2, y2 = to_blender_coords(wx2, wy2, width, height, scale)
        
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy)
        if length == 0:
            continue
        
        angle = math.atan2(dy, dx)
        win_h = 1.4
        win_z = 0.9  # 90cm sill height
        
        # Cutter object
        cutter = create_cube(f"WinCutter_{idx}", (cx, cy, win_z + win_h/2), (length, 0.35, win_h))
        cutter.rotation_euler[2] = angle
        
        target_wall = find_closest_wall(cx, cy)
        if target_wall:
            bool_mod = target_wall.modifiers.new(name=f"WinCut_{idx}", type='BOOLEAN')
            bool_mod.operation = 'DIFFERENCE'
            bool_mod.object = cutter
            cutter.hide_viewport = True
            cutter.hide_render = True
            
        # Draw physical window assembly
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, win_z + win_h/2))
        win_group = bpy.context.active_object
        win_group.name = f"WinGroup_{idx}"
        
        # Metal Frame
        frame = create_cube("WinFrame", (cx, cy, win_z + win_h/2), (length, 0.08, win_h), materials['dark_metal'], win_group)
        frame.rotation_euler[2] = angle
        # Glass Panel
        glass = create_cube("WinGlass", (cx, cy, win_z + win_h/2), (length - 0.06, 0.02, win_h - 0.06), materials['glass'], win_group)
        glass.rotation_euler[2] = angle

    # ==========================================
    # 4. PROCEDURAL ROOM FURNITURE GENERATION
    # ==========================================
    for room in rooms:
        rx1, ry1, rx2, ry2 = room["box"]
        x1, y1 = to_blender_coords(rx1, ry1, width, height, scale)
        x2, y2 = to_blender_coords(rx2, ry2, width, height, scale)
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        room_w = abs(x2 - x1)
        room_l = abs(y2 - y1)
        room_type = room["id"].lower()
        
        if "bedroom" in room_type:
            # Queen Bed + Bedside tables + Lamps
            bed_w = 1.6
            bed_l = 2.0
            
            # Snap head of bed to North wall (y2)
            bed_x = cx
            bed_y = y2 - wall_thickness - bed_l/2
            
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=(bed_x, bed_y, 0.0))
            bed_parent = bpy.context.active_object
            bed_parent.name = f"BedSet_{room['id']}"
            
            # 1. Wooden frame
            create_cube("BedFrame", (bed_x, bed_y, 0.15), (bed_w, bed_l, 0.3), materials['wood_door'], bed_parent)
            # Headboard
            create_cube("Headboard", (bed_x, bed_y + bed_l/2 - 0.05, 0.5), (bed_w, 0.1, 1.0), materials['wood_door'], bed_parent)
            # Mattress
            create_cube("Mattress", (bed_x, bed_y - 0.05, 0.45), (bed_w - 0.08, bed_l - 0.15, 0.32), materials['fabric_bed'], bed_parent)
            # Pillows
            pw = (bed_w - 0.25) / 2
            create_cube("Pillow_L", (bed_x - pw/2 - 0.04, bed_y + bed_l/2 - 0.22, 0.65), (pw, 0.38, 0.12), materials['fabric_pillow'], bed_parent)
            create_cube("Pillow_R", (bed_x + pw/2 + 0.04, bed_y + bed_l/2 - 0.22, 0.65), (pw, 0.38, 0.12), materials['fabric_pillow'], bed_parent)
            # Blanket fold
            create_cube("Blanket", (bed_x, bed_y - 0.35, 0.63), (bed_w - 0.07, 1.2, 0.05), materials['fabric_blanket'], bed_parent)
            
            # Bedside tables (left/right)
            table_size = 0.42
            tx_l = bed_x - bed_w/2 - table_size/2 - 0.05
            tx_r = bed_x + bed_w/2 + table_size/2 + 0.05
            ty = y2 - wall_thickness - table_size/2
            
            if tx_l > x1 + wall_thickness + 0.1:
                create_cube("SideTable_L", (tx_l, ty, table_size/2), (table_size, table_size, table_size), materials['wood_door'], bed_parent)
                # Table lamp
                create_cylinder("LampBase_L", (tx_l, ty, table_size + 0.05), 0.08, 0.1, material=materials['metal'], parent=bed_parent)
                create_cylinder("LampShade_L", (tx_l, ty, table_size + 0.18), 0.1, 0.18, material=materials['fabric_pillow'], parent=bed_parent)
                # Soft light cast
                bpy.ops.object.light_add(type='POINT', location=(tx_l, ty, table_size + 0.25))
                lamp_lt = bpy.context.active_object
                lamp_lt.name = f"BedLight_L_{room['id']}"
                lamp_lt.data.energy = 8.0
                lamp_lt.data.color = (1.0, 0.75, 0.45) # Cozy warm yellow
                lamp_lt.parent = bed_parent
                
            if tx_r < x2 - wall_thickness - 0.1:
                create_cube("SideTable_R", (tx_r, ty, table_size/2), (table_size, table_size, table_size), materials['wood_door'], bed_parent)
                create_cylinder("LampBase_R", (tx_r, ty, table_size + 0.05), 0.08, 0.1, material=materials['metal'], parent=bed_parent)
                create_cylinder("LampShade_R", (tx_r, ty, table_size + 0.18), 0.1, 0.18, material=materials['fabric_pillow'], parent=bed_parent)
                bpy.ops.object.light_add(type='POINT', location=(tx_r, ty, table_size + 0.25))
                lamp_lt = bpy.context.active_object
                lamp_lt.name = f"BedLight_R_{room['id']}"
                lamp_lt.data.energy = 8.0
                lamp_lt.data.color = (1.0, 0.75, 0.45)
                lamp_lt.parent = bed_parent
                
            # Wardrobe cupboard against West wall (x1)
            ward_w = 1.6
            ward_d = 0.6
            ward_h = 2.2
            if room_l > ward_w + 0.8:
                create_cube("Wardrobe", (x1 + wall_thickness + ward_d/2, cy, ward_h/2), (ward_d, ward_w, ward_h), materials['wood_door'], bed_parent)

        elif "living" in room_type or "drawing" in room_type:
            # Sofa Couch + Coffee Table + TV Unit stand
            sofa_w = min(2.4, room_w - 1.2)
            sofa_d = 0.85
            
            # Position Sofa facing North
            sofa_x = cx
            sofa_y = y1 + wall_thickness + sofa_d/2 + 0.6
            
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=(sofa_x, sofa_y, 0.0))
            sofa_parent = bpy.context.active_object
            sofa_parent.name = f"LivingSet_{room['id']}"
            
            # Sofa base, frame & cushions
            create_cube("SofaBase", (sofa_x, sofa_y, 0.12), (sofa_w, sofa_d, 0.22), materials['fabric_sofa'], sofa_parent)
            create_cube("SofaBack", (sofa_x, sofa_y - sofa_d/2 + 0.08, 0.58), (sofa_w, 0.16, 0.72), materials['fabric_sofa'], sofa_parent)
            # Cushions
            cw = (sofa_w - 0.25) / 3
            create_cube("SofaCushion_1", (sofa_x - cw - 0.03, sofa_y + 0.04, 0.26), (cw, sofa_d - 0.12, 0.15), materials['fabric_cushion'], sofa_parent)
            create_cube("SofaCushion_2", (sofa_x, sofa_y + 0.04, 0.26), (cw, sofa_d - 0.12, 0.15), materials['fabric_cushion'], sofa_parent)
            create_cube("SofaCushion_3", (sofa_x + cw + 0.03, sofa_y + 0.04, 0.26), (cw, sofa_d - 0.12, 0.15), materials['fabric_cushion'], sofa_parent)
            # Armrests
            create_cube("SofaArm_L", (sofa_x - sofa_w/2 + 0.08, sofa_y, 0.38), (0.16, sofa_d, 0.52), materials['fabric_sofa'], sofa_parent)
            create_cube("SofaArm_R", (sofa_x + sofa_w/2 - 0.08, sofa_y, 0.38), (0.16, sofa_d, 0.52), materials['fabric_sofa'], sofa_parent)
            
            # Coffee Table
            ct_w = sofa_w * 0.55
            ct_d = 0.65
            ct_h = 0.42
            ct_y = sofa_y + sofa_d/2 + ct_d/2 + 0.75
            create_cube("CoffeeTable_Top", (cx, ct_y, ct_h), (ct_w, ct_d, 0.05), materials['glass'], sofa_parent)
            # Metallic legs
            for lx in [-ct_w/2 + 0.05, ct_w/2 - 0.05]:
                for ly in [-ct_d/2 + 0.05, ct_d/2 - 0.05]:
                    create_cylinder("TableLeg", (cx + lx, ct_y + ly, ct_h/2), 0.02, ct_h, material=materials['metal'], parent=sofa_parent)
                    
            # TV Credenza / Stand
            stand_w = min(2.0, room_w - 1.0)
            stand_d = 0.42
            stand_h = 0.52
            stand_y = y2 - wall_thickness - stand_d/2 - 0.1
            create_cube("TV_Console", (cx, stand_y, stand_h/2), (stand_w, stand_d, stand_h), materials['wood_door'], sofa_parent)
            
            # Big screen TV
            tv_w = stand_w * 0.88
            tv_h = 0.85
            create_cube("TV_Screen", (cx, stand_y, stand_h + tv_h/2 + 0.04), (tv_w, 0.05, tv_h), materials['dark_metal'], sofa_parent)
            create_cube("TV_Base", (cx, stand_y, stand_h + 0.02), (0.35, 0.22, 0.04), materials['metal'], sofa_parent)

        elif "kitchen" in room_type:
            # L-shaped kitchen system
            counter_w = 0.65
            counter_h = 0.92
            
            # Counter running along West wall (x1)
            west_len = room_l - wall_thickness * 2
            if west_len > 1.6:
                create_cube("KitchenCounter_West", (x1 + wall_thickness + counter_w/2, cy, counter_h/2), (counter_w, west_len, counter_h), materials['kitchen_surface'], None)
                # Built-in Sink
                create_cube("Sink", (x1 + wall_thickness + counter_w/2, cy - 0.3, counter_h + 0.01), (counter_w - 0.12, 0.55, 0.02), materials['metal'], None)
                # Goose neck faucet
                create_cylinder("Faucet", (x1 + wall_thickness + counter_w/2 - 0.16, cy - 0.3, counter_h + 0.16), 0.018, 0.3, rotation=(0, 0, 0), material=materials['metal'])
                
            # Counter along North wall (y2)
            north_len = room_w - wall_thickness * 2 - counter_w
            if north_len > 1.6:
                create_cube("KitchenCounter_North", (cx + counter_w/2, y2 - wall_thickness - counter_w/2, counter_h/2), (north_len, counter_w, counter_h), materials['kitchen_surface'], None)
                # Cooking stove
                create_cube("Stove", (cx + counter_w/2, y2 - wall_thickness - counter_w/2, counter_h + 0.01), (0.75, 0.52, 0.02), materials['dark_metal'], None)
                # 4 burner grids
                for bx in [-0.22, 0.22]:
                    for by in [-0.14, 0.14]:
                        create_cylinder("BurnerRing", (cx + counter_w/2 + bx, y2 - wall_thickness - counter_w/2 + by, counter_h + 0.025), 0.08, 0.012, material=materials['metal'])

        elif "bathroom" in room_type:
            # Toilet + Basin/Cabinet vanity + Glass shower
            # 1. Shower tray at corner
            shower_w = min(1.0, room_w * 0.45)
            shower_d = min(1.0, room_l * 0.45)
            create_cube("ShowerTray", (x1 + wall_thickness + shower_w/2, y1 + wall_thickness + shower_d/2, 0.04), (shower_w, shower_d, 0.08), materials['tile'], None)
            create_cube("ShowerGlass_E", (x1 + wall_thickness + shower_w, y1 + wall_thickness + shower_d/2, 1.0), (0.02, shower_d, 2.0), materials['glass'], None)
            create_cube("ShowerGlass_N", (x1 + wall_thickness + shower_w/2, y1 + wall_thickness + shower_d, 1.0), (shower_w, 0.02, 2.0), materials['glass'], None)
            
            # 2. Toilet bowl & tank
            toilet_x = x1 + wall_thickness + 0.22
            toilet_y = y2 - wall_thickness - 0.24
            create_cube("ToiletTank", (toilet_x, toilet_y, 0.5), (0.42, 0.22, 0.58), materials['toilet_material'], None)
            create_cube("ToiletBowl", (toilet_x, toilet_y - 0.32, 0.2), (0.36, 0.42, 0.4), materials['toilet_material'], None)
            
            # 3. Sink Basin vanity cabinet
            vanity_w = min(0.85, room_w * 0.45)
            vanity_d = 0.5
            vanity_h = 0.86
            vanity_x = x2 - wall_thickness - vanity_w/2
            create_cube("VanityCabinet", (vanity_x, cy, vanity_h/2), (vanity_w, vanity_d, vanity_h), materials['kitchen_surface'], None)
            create_cube("VanitySink", (vanity_x, cy, vanity_h + 0.01), (vanity_w - 0.1, vanity_d - 0.1, 0.04), materials['toilet_material'], None)
            
        else:
            # DYNAMIC CUSTOM ROOM TYPE: Generic procedural furniture blocks based on taxonomy
            canonical = resolve_room_type(room_type)
            meta = get_room_meta(canonical)
            furniture_list = meta.get("furniture", [])
            
            if furniture_list:
                bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, 0.0))
                room_group = bpy.context.active_object
                room_group.name = f"DynamicSet_{room['id']}"
                
                n = len(furniture_list)
                cols = min(n, 3)
                rows = (n + cols - 1) // cols
                
                cell_w = (room_w - wall_thickness * 2) / (cols + 1)
                cell_l = (room_l - wall_thickness * 2) / (rows + 1)
                
                # Create a generic material based on the room's hex color
                hex_color = meta.get("hex_color", "#e2e8f0").lstrip('#')
                r, g, b = tuple(int(hex_color[i:i+2], 16)/255.0 for i in (0, 2, 4))
                gen_mat = create_principled_material(f"Mat_{canonical}", (r, g, b, 1.0), roughness=0.6)
                
                for idx, item in enumerate(furniture_list):
                    col = idx % cols
                    row = idx // cols
                    
                    fx = x1 + wall_thickness + (col + 0.5) * cell_w
                    fy = y1 + wall_thickness + (row + 0.5) * cell_l
                    
                    fw = min(0.8, cell_w * 0.6)
                    fl = min(0.8, cell_l * 0.6)
                    fh = 0.6 # default generic height
                    
                    create_cube(f"Item_{item}", (fx, fy, fh/2), (fw, fl, fh), gen_mat, room_group)

    # ==========================================
    # 5. PROCEDURAL ROOF GENERATION
    # ==========================================
    roof_obj = None
    if min_house_x < 900.0:
        overhang = 0.25
        rx1 = min_house_x - overhang
        rx2 = max_house_x + overhang
        ry1 = min_house_y - overhang
        ry2 = max_house_y + overhang
        
        # Calculate centers
        rcx = (rx1 + rx2) / 2
        rcy = (ry1 + ry2) / 2
        rsize_x = rx2 - rx1
        rsize_y = ry2 - ry1
        
        if style in ["classic", "rustical", "scandinavian"]:
            # Pitched Gable Roof runs E-W
            roof_h = 2.2
            
            mesh = bpy.data.meshes.new(name="PitchedRoofMesh")
            roof_obj = bpy.data.objects.new("Roof", mesh)
            bpy.context.collection.objects.link(roof_obj)
            
            # 6 Vertices for triangular prism
            vertices = [
                (rx1, ry1, wall_height),  # 0: SW
                (rx2, ry1, wall_height),  # 1: SE
                (rx2, ry2, wall_height),  # 2: NE
                (rx1, ry2, wall_height),  # 3: NW
                (rx1, rcy, wall_height + roof_h), # 4: West Ridge
                (rx2, rcy, wall_height + roof_h), # 5: East Ridge
            ]
            faces = [
                (0, 3, 2, 1),      # Bottom
                (0, 1, 5, 4),      # South slope
                (2, 3, 4, 5),      # North slope
                (0, 4, 3),         # West gable
                (1, 2, 5)          # East gable
            ]
            mesh.from_pydata(vertices, [], faces)
            mesh.update()
            roof_obj.data.materials.append(materials['roof'])
            
        else:
            # Modern flat roof slab + parapet wall borders + solar panels
            # Main roof parent empty
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=(rcx, rcy, wall_height))
            roof_obj = bpy.context.active_object
            roof_obj.name = "ModernRoofGroup"
            
            # Roof slab
            slab = create_cube("RoofSlab", (rcx, rcy, wall_height + 0.1), (rsize_x, rsize_y, 0.2), materials['wall'], roof_obj)
            
            # Parapet walls
            parapet_h = 0.45
            parapet_t = 0.16
            create_cube("Parapet_N", (rcx, ry2 - parapet_t/2, wall_height + 0.2 + parapet_h/2), (rsize_x, parapet_t, parapet_h), materials['wall'], roof_obj)
            create_cube("Parapet_S", (rcx, ry1 + parapet_t/2, wall_height + 0.2 + parapet_h/2), (rsize_x, parapet_t, parapet_h), materials['wall'], roof_obj)
            create_cube("Parapet_E", (rx2 - parapet_t/2, rcy, wall_height + 0.2 + parapet_h/2), (parapet_t, rsize_y - parapet_t * 2, parapet_h), materials['wall'], roof_obj)
            create_cube("Parapet_W", (rx1 + parapet_t/2, rcy, wall_height + 0.2 + parapet_h/2), (parapet_t, rsize_y - parapet_t * 2, parapet_h), materials['wall'], roof_obj)
            
            # Solar Panel details for pro AI visualizer look
            if rsize_x > 5.0 and rsize_y > 5.0:
                sp_x = rcx
                sp_y = rcy
                sp_z = wall_height + 0.26
                create_cube("Solar_Frame", (sp_x, sp_y, sp_z), (2.2, 1.4, 0.06), materials['metal'], roof_obj)
                solar_p = create_cube("Solar_Cells", (sp_x, sp_y, sp_z + 0.035), (2.1, 1.3, 0.02), materials['dark_metal'], roof_obj)
                solar_p.rotation_euler[0] = math.radians(16)  # tilted

    # ==========================================
    # 6. LIGHTING & ENVIRONMENT
    # ==========================================
    # Global soft sunlight
    # Global soft sunlight for realistic architectural shadows
    bpy.ops.object.light_add(type='SUN', location=(15.0, -15.0, 20.0))
    sun = bpy.context.active_object
    sun.name = "Sunlight"
    sun.data.energy = 5.0  # Increased for brighter, professional look
    sun.data.color = (1.0, 0.96, 0.90)  # Enhanced soft warm afternoon sun
    sun.data.angle = math.radians(10.0) # Softer shadow edges
    sun.rotation_euler = (math.radians(45), 0.0, math.radians(45))
    if hasattr(sun.data, "use_shadow"):
        sun.data.use_shadow = True
        
    # Ambient fill area lights in each room center
    for room in rooms:
        rx1, ry1, rx2, ry2 = room["box"]
        x1, y1 = to_blender_coords(rx1, ry1, width, height, scale)
        x2, y2 = to_blender_coords(rx2, ry2, width, height, scale)
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        size_x = abs(x2 - x1)
        size_y = abs(y2 - y1)
        
        # Soft indoor area lights
        bpy.ops.object.light_add(type='AREA', location=(cx, cy, 2.7))
        area_lt = bpy.context.active_object
        area_lt.name = f"AreaLight_{room['id']}"
        area_lt.data.size = min(size_x * 0.4, size_y * 0.4)
        
        # Power & Colors
        if "bedroom" in room['id'].lower() or "living" in room['id'].lower():
            area_lt.data.energy = 100.0  # Warm ambient glow
            area_lt.data.color = (1.0, 0.92, 0.85)
        else:
            area_lt.data.energy = 120.0  # Clean bright glow
            area_lt.data.color = (0.9, 0.95, 1.0)

    # ==========================================
    # 7. CAMERA SETUP & RENDERING (EEVEE)
    # ==========================================
    # Setup rendering engine parameters
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 768
    scene.render.image_settings.file_format = 'PNG'
    
    # Eevee graphics polishing settings
    if hasattr(scene.eevee, "use_ambient_occlusion"):
        scene.eevee.use_ambient_occlusion = True
        scene.eevee.ambient_occlusion_distance = 0.6
    if hasattr(scene.eevee, "use_bloom"):
        scene.eevee.use_bloom = True
    if hasattr(scene.eevee, "use_ssr"):
        scene.eevee.use_ssr = True
        scene.eevee.use_ssr_refraction = True

    # Bounding centers
    house_cx = (min_house_x + max_house_x) / 2
    house_cy = (min_house_y + max_house_y) / 2
    size_house_x = abs(max_house_x - min_house_x)
    size_house_y = abs(max_house_y - min_house_y)
    max_dim = max(size_house_x, size_house_y)
    ortho_scale = max_dim * 1.6

    # Create Isometric Camera
    bpy.ops.object.camera_add(location=(12.0, -12.0, 10.0))
    iso_cam = bpy.context.active_object
    iso_cam.name = "IsometricCamera"
    iso_cam.data.type = 'ORTHOGRAPHIC'
    iso_cam.data.ortho_scale = ortho_scale
    iso_cam.rotation_euler = (math.radians(55), 0.0, math.radians(45))

    # Create Top-down Camera
    bpy.ops.object.camera_add(location=(house_cx, house_cy, 18.0))
    topdown_cam = bpy.context.active_object
    topdown_cam.name = "TopdownCamera"
    topdown_cam.data.type = 'ORTHOGRAPHIC'
    topdown_cam.data.ortho_scale = ortho_scale * 1.15
    topdown_cam.rotation_euler = (0.0, 0.0, 0.0)

    # A. Render Exterior View (with roof shown)
    if roof_obj:
        roof_obj.hide_viewport = False
        roof_obj.hide_render = False

    scene.camera = iso_cam
    render_ext_path = os.path.join(output_dir, "render_exterior.png")
    scene.render.filepath = render_ext_path
    print(f"Rendering exterior isometric visualization to: {render_ext_path}")
    bpy.ops.render.render(write_still=True)
    
    # Save a generic render.png copy as requested
    import shutil
    shutil.copy(render_ext_path, os.path.join(output_dir, "render.png"))

    # B. Render Topdown Layout View (hide roof!)
    if roof_obj:
        roof_obj.hide_viewport = True
        roof_obj.hide_render = True

    scene.camera = topdown_cam
    render_td_path = os.path.join(output_dir, "render_topdown.png")
    scene.render.filepath = render_td_path
    print(f"Rendering topdown layout projection to: {render_td_path}")
    bpy.ops.render.render(write_still=True)

    # Make roof visible again for final blend & GLTF files
    if roof_obj:
        roof_obj.hide_viewport = False
        roof_obj.hide_render = False

    # ==========================================
    # 8. EXPORT CAD MULTI-FORMATS
    # ==========================================
    gltf_path = os.path.join(output_dir, "model.gltf")
    glb_path = os.path.join(output_dir, "model.glb")
    obj_path = os.path.join(output_dir, "model.obj")
    blend_path = os.path.join(output_dir, "model.blend")

    # 8A. Save native Blend file
    print(f"Saving .blend archive file to: {blend_path}")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    # 8B. Export GLTF and GLB
    print(f"Exporting GLTF to: {gltf_path}")
    bpy.ops.export_scene.gltf(
        filepath=gltf_path,
        export_format='GLTF_EMBEDDED',
        use_selection=False
    )
    
    print(f"Exporting binary GLB to: {glb_path}")
    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format='GLB',
        use_selection=False
    )

    # 8C. Export OBJ Mesh
    # Select all meshes
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            obj.select_set(True)
            
    print(f"Exporting CAD/OBJ mesh to: {obj_path}")
    if hasattr(bpy.ops.export_scene, 'obj'):
        bpy.ops.export_scene.obj(filepath=obj_path, use_selection=True)
    else:
        bpy.ops.wm.obj_export(filepath=obj_path, export_selected_objects=True)

    print("Procedural Blender 3D pipeline execution completely successful!")

def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Loading floorplan metadata structure from: {args.layout_json}")
    with open(args.layout_json, 'r') as f:
        layout_data = json.load(f)
        
    print("Initiating Blender 3D procedural architecture builder...")
    build_floorplan_3d(layout_data, args.output_dir)

if __name__ == "__main__":
    main()
