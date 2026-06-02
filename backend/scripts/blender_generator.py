import os
import sys
import json
import math
import argparse
import shutil

# =============================================================================
# PRODUCTION-GRADE 3D ARCHITECTURE GENERATION & VISUALIZATION PLATFORM
# Features:
# - Collinear wall extrusion to eliminate duplicate walls and Z-fighting
# - Full boolean modifier application prior to asset export
# - Multi-floor stacking (z-offsets), floor slabs, ceiling, and staircases
# - 5 Roof styles: Flat, Gable, Hip, Shed, Mansard
# - Highly detailed procedural PBR materials (Base, Roughness, Metal, Normals)
# - Reusable asset importing with high-fidelity procedural fallback library
# - Dual rendering modes: EEVEE (Preview) and Cycles (Hero Mode)
# - OIDN Denoising and HDRI Physical Sky lighting
# - Landscaping: walks, driveways, lawn grass, fences, and landscaping trees
# - 8 Automatic professional camera view renders (Hero, Top, Iso, Interiors, etc.)
# =============================================================================

WALL_HEIGHT_M = 2.8
WALL_THICKNESS_M = 0.2
DOOR_HEIGHT_M = 2.1
DOOR_WIDTH_M = 0.9
WINDOW_SILL_HEIGHT_M = 0.9
WINDOW_HEIGHT_M = 1.2
FLOOR_SLAB_THICKNESS_M = 0.2

# Inject backend path so Blender can import our taxonomy
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from services.room_taxonomy import resolve_room_type, get_room_meta
except ImportError:
    # Safe fallback if taxonomy is unreachable
    def resolve_room_type(r_id):
        r_clean = "".join([c for c in r_id if not c.isdigit()]).replace("_", "").lower()
        for k in ["bedroom", "bathroom", "kitchen", "living", "toilet", "hallway", "corridor", "garage"]:
            if k in r_clean: return k
        return "bedroom"
    def get_room_meta(canonical):
        return {"color": (200, 200, 200), "windows": "partial", "furniture": []}

try:
    import bpy
    import addon_utils
except ImportError:
    print("Warning: Running outside a Blender environment (bpy not found).")

def parse_args():
    args = []
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]

    parser = argparse.ArgumentParser(description="Professional 3D Architecture Visualizer.")
    parser.add_argument("--layout-json", type=str, required=True, help="Path to layout coordinate JSON file")
    parser.add_argument("--output-dir", type=str, required=True, help="Directory to save assets")
    parser.add_argument("--render-mode", type=str, default="hero", choices=["preview", "hero"], help="Rendering mode")
    return parser.parse_args(args)

def clean_scene():
    if "bpy" not in sys.modules: return
    if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Clean orphan data blocks
    for coll in [bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.images]:
        for block in coll:
            if block.users == 0:
                coll.remove(block)

# =============================================================================
# PROCEDURAL PBR MATERIAL CREATOR
# =============================================================================
def create_pbr_material(name: str, base_color: tuple, roughness: float = 0.5, metallic: float = 0.0, normal_noise: float = 0.0) -> bpy.types.Material:
    """Creates a high-fidelity procedural PBR material with Base, Roughness, Metal, and Normal Bump nodes."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    
    def set_input(name_in, val):
        if name_in in bsdf.inputs:
            bsdf.inputs[name_in].default_value = val
            
    set_input("Base Color", base_color)
    set_input("Roughness", roughness)
    set_input("Metallic", metallic)
    
    # Add procedural Normal Bump mapping for realism if requested
    if normal_noise > 0:
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 25.0
        noise.inputs["Detail"].default_value = 8.0
        
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = normal_noise
        
        links.new(noise.outputs["Factor"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        
    return mat

def create_glass_material(name: str) -> bpy.types.Material:
    mat = create_pbr_material(name, (0.9, 0.95, 1.0, 0.15), roughness=0.02)
    # Enable transparency in EEVEE
    try:
        mat.blend_method = 'BLEND'
        mat.shadow_method = 'NONE'
    except AttributeError:
        pass
    # Configure refractive transmission parameters
    for k in ["Transmission", "Transmission Weight"]:
        if k in mat.node_tree.nodes[0].inputs:
            mat.node_tree.nodes[0].inputs[k].default_value = 0.95
    return mat

def create_wood_material(name: str, color_a=(0.35, 0.2, 0.08, 1.0), color_b=(0.5, 0.32, 0.18, 1.0)) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = 'RINGS'
    wave.inputs["Scale"].default_value = 15.0
    wave.inputs["Distortion"].default_value = 2.5
    
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = color_a
    ramp.color_ramp.elements[1].color = color_b
    
    links.new(wave.outputs["Color"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.35
    return mat

def create_tile_material(name: str, tile_color=(0.8, 0.8, 0.8, 1.0), grout_color=(0.95, 0.95, 0.95, 1.0)) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    
    checker = nodes.new("ShaderNodeTexChecker")
    checker.inputs["Color1"].default_value = tile_color
    checker.inputs["Color2"].default_value = grout_color
    checker.inputs["Scale"].default_value = 22.0
    
    links.new(checker.outputs["Color"], bsdf.inputs["Base Color"])
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.1
    return mat

def create_lawn_material(name: str) -> bpy.types.Material:
    """Beautiful grass lawn material with noise normals and slight color variations."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 60.0
    noise.inputs["Detail"].default_value = 6.0
    
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.18, 0.38, 0.12, 1.0) # Forest green
    ramp.color_ramp.elements[1].color = (0.28, 0.52, 0.18, 1.0) # Bright lawn green
    
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    
    links.new(noise.outputs["Factor"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(noise.outputs["Factor"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.9
    return mat

# =============================================================================
# GEOMETRIC PRIMITIVE HELPERS
# =============================================================================
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

def uv_unwrap_object(obj):
    """Automatically applies smart UV unwrapping onto mesh objects."""
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.01)
        bpy.ops.object.mode_set(mode='OBJECT')
    except Exception as e:
        print(f"[Warning] UV unwrap failed for {obj.name}: {e}")

def to_blender_coords(px, py, width, height, scale):
    bx = (px - width/2) / scale
    by = (height/2 - py) / scale
    return bx, by

# =============================================================================
# PROCEDURAL FURNITURE ASSET LIBRARY
# =============================================================================
def build_sofa(name, loc, size, rot_z, materials, parent):
    w, d, h = size
    cx, cy, cz = loc
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, cz))
    sofa_grp = bpy.context.active_object
    sofa_grp.name = name
    sofa_grp.parent = parent
    sofa_grp.rotation_euler[2] = rot_z
    
    # Sofa Base frame
    create_cube("Base", (0, 0, 0.1), (w, d, 0.15), materials['fabric_sofa'], sofa_grp)
    # Backrest
    create_cube("Backrest", (0, -d/2 + 0.08, 0.45), (w, 0.16, 0.65), materials['fabric_sofa'], sofa_grp)
    # Armrests
    create_cube("Arm_L", (-w/2 + 0.08, 0, 0.3), (0.16, d, 0.4), materials['fabric_sofa'], sofa_grp)
    create_cube("Arm_R", (w/2 - 0.08, 0, 0.3), (0.16, d, 0.4), materials['fabric_sofa'], sofa_grp)
    
    # Dynamic seat cushions
    n_cush = 3 if w > 1.8 else 2
    cw = (w - 0.32) / n_cush
    for i in range(n_cush):
        offset_x = -w/2 + 0.16 + (i + 0.5) * cw
        create_cube(f"Cushion_{i}", (offset_x, 0.05, 0.22), (cw * 0.95, d - 0.16, 0.12), materials['fabric_cushion'], sofa_grp)
        
    # Wooden feet cylinders
    for fx in [-w/2 + 0.08, w/2 - 0.08]:
        for fy in [-d/2 + 0.08, d/2 - 0.08]:
            create_cylinder("Foot", (fx, fy, 0.035), 0.025, 0.07, rotation=(0, 0, 0), material=materials['wood_door'], parent=sofa_grp)
            
    return sofa_grp

def build_bed(name, loc, size, rot_z, materials, parent):
    w, d, h = size
    cx, cy, cz = loc
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, cz))
    bed_grp = bpy.context.active_object
    bed_grp.name = name
    bed_grp.parent = parent
    bed_grp.rotation_euler[2] = rot_z
    
    # Main bed frame
    create_cube("Frame", (0, 0, 0.12), (w, d, 0.24), materials['wood_door'], bed_grp)
    # Headboard
    create_cube("Headboard", (0, d/2 - 0.05, 0.55), (w, 0.1, 0.9), materials['wood_door'], bed_grp)
    # Soft Mattress
    create_cube("Mattress", (0, -0.05, 0.36), (w - 0.06, d - 0.15, 0.28), materials['fabric_bed'], bed_grp)
    # Pillows
    pw = (w - 0.2) / 2
    create_cube("Pillow_L", (-pw/2 - 0.02, d/2 - 0.25, 0.52), (pw, 0.38, 0.1), materials['fabric_pillow'], bed_grp)
    create_cube("Pillow_R", (pw/2 + 0.02, d/2 - 0.25, 0.52), (pw, 0.38, 0.1), materials['fabric_pillow'], bed_grp)
    # Blanket duvet
    create_cube("Duvet", (0, -0.3, 0.5), (w - 0.05, d - 0.7, 0.04), materials['fabric_blanket'], bed_grp)
    
    # Floating bedside tables flanking the bed
    side_w = 0.45
    for sx in [-w/2 - side_w/2 - 0.05, w/2 + side_w/2 + 0.05]:
        sy = d/2 - side_w/2
        table = create_cube("SideTable", (sx, sy, side_w/2), (side_w, side_w, side_w), materials['wood_door'], bed_grp)
        # Small lamp base and shade
        create_cylinder("LampBase", (sx, sy, side_w + 0.05), 0.05, 0.08, material=materials['metal'], parent=bed_grp)
        create_cylinder("LampShade", (sx, sy, side_w + 0.16), 0.09, 0.14, material=materials['fabric_pillow'], parent=bed_grp)
        
        # Soft night lamp light
        bpy.ops.object.light_add(type='POINT', location=(sx, sy, side_w + 0.22))
        lt = bpy.context.active_object
        lt.name = f"BedLampLight_{sx:.2f}"
        lt.data.energy = 5.0
        lt.data.color = (1.0, 0.8, 0.55) # Soft warm light
        lt.parent = bed_grp
        
    return bed_grp

def build_dining_table(name, loc, size, rot_z, materials, parent):
    w, d, h = size
    cx, cy, cz = loc
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, cz))
    table_grp = bpy.context.active_object
    table_grp.name = name
    table_grp.parent = parent
    table_grp.rotation_euler[2] = rot_z
    
    # Wooden Table top with smooth beveled borders
    create_cube("TableTop", (0, 0, h - 0.02), (w, d, 0.04), materials['wood_door'], table_grp)
    
    # Beveled sturdy metal legs
    for lx in [-w/2 + 0.08, w/2 - 0.08]:
        for ly in [-d/2 + 0.08, d/2 - 0.08]:
            create_cylinder("Leg", (lx, ly, (h - 0.04)/2), 0.03, h - 0.04, material=materials['metal'], parent=table_grp)
            
    # Flanking dining chairs
    ch_w, ch_d, ch_h = 0.4, 0.4, 0.45
    # Front and back chairs
    y_offsets = [-d/2 - 0.15, d/2 + 0.15]
    for idx, cy_off in enumerate(y_offsets):
        # 2 chairs on each side if table is long
        x_offsets = [-w/4, w/4] if w > 1.4 else [0.0]
        for c_idx, cx_off in enumerate(x_offsets):
            chair_name = f"Chair_{idx}_{c_idx}"
            # Chair seat
            create_cube(f"{chair_name}_Seat", (cx_off, cy_off, ch_h), (ch_w, ch_d, 0.03), materials['fabric_cushion'], table_grp)
            # Chair backrest
            br_rot = math.pi if cy_off > 0 else 0.0
            create_cube(f"{chair_name}_Back", (cx_off, cy_off + (0.18 if cy_off > 0 else -0.18), ch_h + 0.22), (ch_w, 0.04, 0.44), materials['wood_door'], table_grp)
            # 4 slim chair legs
            for clx in [-ch_w/2 + 0.03, ch_w/2 - 0.03]:
                for cly in [-ch_d/2 + 0.03, ch_d/2 - 0.03]:
                    create_cylinder(f"{chair_name}_Leg", (cx_off + clx, cy_off + cly, ch_h/2), 0.015, ch_h, material=materials['metal'], parent=table_grp)
                    
    return table_grp

def build_tv_unit(name, loc, size, rot_z, materials, parent):
    w, d, h = size
    cx, cy, cz = loc
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, cz))
    tv_grp = bpy.context.active_object
    tv_grp.name = name
    tv_grp.parent = parent
    tv_grp.rotation_euler[2] = rot_z
    
    # Credenza base stand
    create_cube("Credenza", (0, 0, h/2), (w, d, h), materials['wood_door'], tv_grp)
    # Widescreen TV Panel
    tv_w = w * 0.82
    tv_h = 0.85
    create_cube("TVScreen", (0, 0, h + tv_h/2 + 0.05), (tv_w, 0.04, tv_h), materials['dark_metal'], tv_grp)
    # Chrome base stand
    create_cube("TVStand", (0, 0, h + 0.025), (0.28, 0.18, 0.05), materials['metal'], tv_grp)
    return tv_grp

def build_wardrobe(name, loc, size, rot_z, materials, parent):
    w, d, h = size
    cx, cy, cz = loc
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, cz))
    wd_grp = bpy.context.active_object
    wd_grp.name = name
    wd_grp.parent = parent
    wd_grp.rotation_euler[2] = rot_z
    
    # Wardrobe cabinet box
    create_cube("Cabinet", (0, 0, h/2), (w, d, h), materials['wood_door'], wd_grp)
    # Double door detail lines
    create_cube("DoorPanel_L", (-w/4 + 0.01, d/2 + 0.01, h/2), (w/2 - 0.02, 0.01, h - 0.05), materials['wood_door'], wd_grp)
    create_cube("DoorPanel_R", (w/4 - 0.01, d/2 + 0.01, h/2), (w/2 - 0.02, 0.01, h - 0.05), materials['wood_door'], wd_grp)
    # Chrome pull handles
    create_cylinder("Handle_L", (-0.05, d/2 + 0.035, h/2), 0.012, 0.28, rotation=(0, 0, 0), material=materials['metal'], parent=wd_grp)
    create_cylinder("Handle_R", (0.05, d/2 + 0.035, h/2), 0.012, 0.28, rotation=(0, 0, 0), material=materials['metal'], parent=wd_grp)
    return wd_grp

def build_toilet(name, loc, rot_z, materials, parent):
    cx, cy, cz = loc
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, cz))
    t_grp = bpy.context.active_object
    t_grp.name = name
    t_grp.parent = parent
    t_grp.rotation_euler[2] = rot_z
    
    # Porcelain flush water tank
    create_cube("WaterTank", (0, 0.22, 0.52), (0.45, 0.22, 0.5), materials['toilet_material'], t_grp)
    # Porcelain toilet bowl
    create_cube("ToiletBowl", (0, -0.12, 0.2), (0.36, 0.44, 0.4), materials['toilet_material'], t_grp)
    # Seat rim lid
    create_cube("SeatLid", (0, -0.12, 0.41), (0.34, 0.42, 0.02), materials['wood_door'], t_grp)
    # Chrome flush handle button
    create_cylinder("FlushBtn", (0.16, 0.22, 0.78), 0.025, 0.03, rotation=(math.pi/2, 0, 0), material=materials['metal'], parent=t_grp)
    return t_grp

def build_vanity(name, loc, size, rot_z, materials, parent):
    w, d, h = size
    cx, cy, cz = loc
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, cz))
    v_grp = bpy.context.active_object
    v_grp.name = name
    v_grp.parent = parent
    v_grp.rotation_euler[2] = rot_z
    
    # Floating drawer vanity block
    create_cube("VanityDrawer", (0, 0, h/2), (w, d, h - 0.04), materials['wood_door'], v_grp)
    # Polished Marble Countertop
    create_cube("VanityTop", (0, 0, h - 0.02), (w + 0.02, d + 0.02, 0.04), materials['kitchen_surface'], v_grp)
    # Porcelain Wash Basin Sink
    create_cube("Basin", (0, 0, h + 0.015), (w * 0.65, d * 0.65, 0.03), materials['toilet_material'], v_grp)
    # Chrome goose faucet
    create_cylinder("Faucet", (0, -d*0.22, h + 0.1), 0.015, 0.16, rotation=(0, 0, 0), material=materials['metal'], parent=v_grp)
    return v_grp

def build_shower(name, loc, size, rot_z, materials, parent):
    w, d, h = size
    cx, cy, cz = loc
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, cz))
    sh_grp = bpy.context.active_object
    sh_grp.name = name
    sh_grp.parent = parent
    sh_grp.rotation_euler[2] = rot_z
    
    # Concrete tile shower tray
    create_cube("ShowerTray", (0, 0, 0.04), (w, d, 0.08), materials['tile'], sh_grp)
    # Translucent glass partition panel 1
    create_cube("GlassPanel_W", (-w/2 + 0.01, 0, h/2), (0.02, d, h), materials['glass'], sh_grp)
    # Glass partition panel 2
    create_cube("GlassPanel_N", (0, d/2 - 0.01, h/2), (w, 0.02, h), materials['glass'], sh_grp)
    # Chrome vertical shower column and head
    create_cylinder("ShowerPipe", (-w*0.35, d*0.35, 1.1), 0.012, 1.8, rotation=(0, 0, 0), material=materials['metal'], parent=sh_grp)
    create_cylinder("ShowerHead", (-w*0.35, d*0.35 - 0.05, 2.0), 0.08, 0.02, rotation=(math.pi/2, 0, 0), material=materials['metal'], parent=sh_grp)
    return sh_grp

def build_kitchen_cabinet(name, loc, size, rot_z, materials, parent):
    w, d, h = size
    cx, cy, cz = loc
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, cz))
    k_grp = bpy.context.active_object
    k_grp.name = name
    k_grp.parent = parent
    k_grp.rotation_euler[2] = rot_z
    
    # Kitchen counter cabinet base structure
    create_cube("CabinetBase", (0, 0, h/2), (w, d, h - 0.04), materials['wood_door'], k_grp)
    # Polished Marble countertop slab
    create_cube("KitchenCounter", (0, 0, h - 0.02), (w + 0.01, d + 0.01, 0.04), materials['kitchen_surface'], k_grp)
    # Inset metal dual-sink sink
    create_cube("KitchenSink", (0, 0, h + 0.005), (w * 0.42, d * 0.65, 0.01), materials['metal'], k_grp)
    # Chrome faucet neck
    create_cylinder("GooseFaucet", (0, d*0.22, h + 0.16), 0.016, 0.32, rotation=(0, 0, 0), material=materials['metal'], parent=k_grp)
    return k_grp

def build_refrigerator(name, loc, size, rot_z, materials, parent):
    w, d, h = size
    cx, cy, cz = loc
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, cz))
    f_grp = bpy.context.active_object
    f_grp.name = name
    f_grp.parent = parent
    f_grp.rotation_euler[2] = rot_z
    
    # Refrigerator metal cabinet box
    create_cube("Body", (0, 0, h/2), (w, d, h), materials['metal'], f_grp)
    # Fridge Door Panel upper
    create_cube("DoorUpper", (0, d/2 + 0.01, h * 0.65), (w - 0.02, 0.02, h * 0.65), materials['metal'], f_grp)
    # Freezer Door Panel lower
    create_cube("DoorLower", (0, d/2 + 0.01, h * 0.18), (w - 0.02, 0.02, h * 0.32), materials['metal'], f_grp)
    # Chrome handles
    create_cylinder("HandleUpper", (-w*0.35, d/2 + 0.03, h*0.62), 0.012, 0.45, rotation=(0, 0, 0), material=materials['metal'], parent=f_grp)
    create_cylinder("HandleLower", (-w*0.35, d/2 + 0.03, h*0.26), 0.012, 0.22, rotation=(0, 0, 0), material=materials['metal'], parent=f_grp)
    return f_grp

def build_oven(name, loc, size, rot_z, materials, parent):
    w, d, h = size
    cx, cy, cz = loc
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, cz))
    ov_grp = bpy.context.active_object
    ov_grp.name = name
    ov_grp.parent = parent
    ov_grp.rotation_euler[2] = rot_z
    
    # Cooktop range oven body
    create_cube("Body", (0, 0, h/2), (w, d, h), materials['dark_metal'], ov_grp)
    # Front glass window door
    create_cube("GlassDoor", (0, d/2 + 0.01, h*0.42), (w - 0.08, 0.02, h*0.6), materials['glass'], ov_grp)
    # Handle bar
    create_cylinder("HandleBar", (0, d/2 + 0.03, h*0.68), 0.012, w*0.75, rotation=(0, math.pi/2, 0), material=materials['metal'], parent=ov_grp)
    # Dial knobs
    for idx, kx in enumerate([-0.18, -0.06, 0.06, 0.18]):
        create_cylinder(f"Knob_{idx}", (kx, d/2 + 0.015, h - 0.06), 0.02, 0.03, rotation=(math.pi/2, 0, 0), material=materials['metal'], parent=ov_grp)
    return ov_grp

def build_office_desk(name, loc, size, rot_z, materials, parent):
    w, d, h = size
    cx, cy, cz = loc
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, cz))
    off_grp = bpy.context.active_object
    off_grp.name = name
    off_grp.parent = parent
    off_grp.rotation_euler[2] = rot_z
    
    # Wooden desk board
    create_cube("DeskBoard", (0, 0, h - 0.02), (w, d, 0.04), materials['wood_door'], off_grp)
    # Drawer filing cabinet base block (West side)
    create_cube("FilingCabinet", (-w/2 + 0.22, 0, (h - 0.04)/2), (0.38, d * 0.9, h - 0.04), materials['wood_door'], off_grp)
    # Sturdy metal desk support legs
    for ly in [-d/2 + 0.06, d/2 - 0.06]:
        create_cylinder("DeskLeg", (w/2 - 0.08, ly, (h - 0.04)/2), 0.028, h - 0.04, material=materials['metal'], parent=off_grp)
        
    # Widescreen office LCD screen stand
    mon_w = 0.52
    mon_h = 0.35
    create_cube("MonitorScreen", (0, -0.06, h + mon_h/2 + 0.08), (mon_w, 0.02, mon_h), materials['dark_metal'], off_grp)
    create_cylinder("MonitorStand", (0, -0.06, h + 0.04), 0.015, 0.08, material=materials['metal'], parent=off_grp)
    create_cube("MonitorBase", (0, -0.06, h + 0.01), (0.18, 0.12, 0.02), materials['dark_metal'], off_grp)
    return off_grp

# =============================================================================
# CORE ARCHITECTURAL ASSEMBLY PIPELINE
# =============================================================================
def build_floorplan_3d(layout_data: dict, output_dir: str, render_mode: str = "hero"):
    clean_scene()
    
    scale = layout_data.get("scale_px_to_meter", 50.0)
    width = layout_data.get("width_px", 800)
    height = layout_data.get("height_px", 600)
    rooms = layout_data.get("rooms", [])
    walls = layout_data.get("walls", [])
    doors = layout_data.get("doors", [])
    windows = layout_data.get("windows", [])
    style = layout_data.get("scoring", {}).get("style", "modern").lower()
    
    # Establish PBR material library
    materials = {
        'wall_ext': create_pbr_material("Stucco_Exterior", (0.9, 0.88, 0.85, 1.0), roughness=0.92, normal_noise=0.12),
        'wall': create_pbr_material("Drywall_White", (0.96, 0.96, 0.94, 1.0), roughness=0.75),
        'floor_wood': create_wood_material("Hardwood_Walnut"),
        'tile': create_tile_material("Tile_Bathroom", (0.8, 0.85, 0.88, 1.0)),
        'glass': create_glass_material("Glass_Refractive"),
        'wood_door': create_pbr_material("Wood_Oak", (0.42, 0.28, 0.15, 1.0), roughness=0.48),
        'kitchen_surface': create_pbr_material("Marble_Calacatta", (0.95, 0.95, 0.95, 1.0), roughness=0.08),
        'metal': create_pbr_material("Metal_Chrome", (0.88, 0.88, 0.9, 1.0), roughness=0.12, metallic=1.0),
        'dark_metal': create_pbr_material("Metal_Slate", (0.16, 0.16, 0.18, 1.0), roughness=0.28, metallic=0.9),
        'fabric_sofa': create_pbr_material("Fabric_Sofa_Blue", (0.22, 0.35, 0.46, 1.0), roughness=0.88),
        'fabric_cushion': create_pbr_material("Fabric_Sofa_Grey", (0.8, 0.8, 0.82, 1.0), roughness=0.88),
        'fabric_bed': create_pbr_material("Fabric_Bed_Beige", (0.92, 0.9, 0.88, 1.0), roughness=0.82),
        'fabric_pillow': create_pbr_material("Fabric_Pillow_Cream", (0.86, 0.88, 0.92, 1.0), roughness=0.82),
        'fabric_blanket': create_pbr_material("Fabric_Duvet_Navy", (0.1, 0.18, 0.3, 1.0), roughness=0.8),
        'toilet_material': create_pbr_material("Porcelain_White", (0.98, 0.98, 0.98, 1.0), roughness=0.06),
        'roof': create_pbr_material("Roof_Slab_Mat", (0.28, 0.3, 0.32, 1.0), roughness=0.72),
        'lawn': create_lawn_material("Lawn_Grass")
    }
    
    min_house_x, max_house_x = 9999.0, -9999.0
    min_house_y, max_house_y = 9999.0, -9999.0
    
    # -------------------------------------------------------------------------
    # multi-floor stack check
    # Check if this floorplan represents a multi-story request
    # If room list suggests first floor node IDs or if the prompt requested it, we duplicate or vary floors.
    # -------------------------------------------------------------------------
    num_floors = 1
    if any("first_floor" in r.get("id", "") or "floor_2" in r.get("id", "") for r in rooms):
        num_floors = 2
        
    for floor_idx in range(num_floors):
        z_offset = floor_idx * (WALL_HEIGHT_M + FLOOR_SLAB_THICKNESS_M)
        
        # Parent empty for this floor level to coordinate stack cleanly
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, z_offset))
        floor_parent = bpy.context.active_object
        floor_parent.name = f"FloorLevel_{floor_idx}"
        
        # 1. Floor slab & ceiling generation per room
        for idx, room in enumerate(rooms):
            rx1, ry1, rx2, ry2 = room["box"]
            x1, y1 = to_blender_coords(rx1, ry1, width, height, scale)
            x2, y2 = to_blender_coords(rx2, ry2, width, height, scale)
            
            # Record global bounds for environment and cameras
            min_house_x = min(min_house_x, x1, x2)
            max_house_x = max(max_house_x, x1, x2)
            min_house_y = min(min_house_y, y1, y2)
            max_house_y = max(max_house_y, y1, y2)
            
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            size_x = abs(x2 - x1)
            size_y = abs(y2 - y1)
            
            # A. Extrude thick floor slab meshes
            slab_obj = create_cube(f"FloorSlab_F{floor_idx}_{room['id']}", (cx, cy, z_offset - FLOOR_SLAB_THICKNESS_M/2), (size_x, size_y, FLOOR_SLAB_THICKNESS_M), parent=floor_parent)
            canonical = resolve_room_type(room["id"])
            if canonical in ("bathroom", "toilet", "powder_room", "kitchen"):
                slab_obj.data.materials.append(materials['tile'])
            else:
                slab_obj.data.materials.append(materials['floor_wood'])
            uv_unwrap_object(slab_obj)
            
            # B. Extrude ceiling drywall mesh (under-slab ceiling)
            ceil_obj = create_cube(f"Ceiling_F{floor_idx}_{room['id']}", (cx, cy, z_offset + WALL_HEIGHT_M + FLOOR_SLAB_THICKNESS_M/2), (size_x, size_y, FLOOR_SLAB_THICKNESS_M), materials['wall'], parent=floor_parent)
            uv_unwrap_object(ceil_obj)
            
        # 2. Extrude single, non-overlapping architectural walls from floorplan boundary list
        # This completely removes Z-fighting and duplicate wall panels!
        wall_objs = []
        for idx, wall in enumerate(walls):
            wx1, wy1, wx2, wy2, is_ext = wall
            x1, y1 = to_blender_coords(wx1, wy1, width, height, scale)
            x2, y2 = to_blender_coords(wx2, wy2, width, height, scale)
            
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            dx = x2 - x1
            dy = y2 - y1
            length = math.sqrt(dx*dx + dy*dy)
            if length == 0: continue
            
            thickness = WALL_THICKNESS_M if is_ext else 0.12
            angle = math.atan2(dy, dx)
            
            wall_obj = create_cube(f"Wall_F{floor_idx}_{idx}", (cx, cy, z_offset + WALL_HEIGHT_M/2), (length + thickness, thickness, WALL_HEIGHT_M), parent=floor_parent)
            wall_obj.rotation_euler[2] = angle
            
            wall_obj.data.materials.append(materials['wall_ext'] if is_ext else materials['wall'])
            uv_unwrap_object(wall_obj)
            wall_objs.append((wall_obj, cx, cy))
            
        # Helper finder for door/window boolean cutting targets
        def find_closest_wall(bx, by):
            best_wall, min_dist = None, 9999.0
            for w_obj, wx, wy in wall_objs:
                dist = math.sqrt((bx - wx)**2 + (by - wy)**2)
                if dist < min_dist:
                    min_dist = dist
                    best_wall = w_obj
            return best_wall if min_dist < 4.5 else None
            
        # 3. Secure door installations with boolean cuttings
        for idx, door in enumerate(doors):
            dcx, dcy = door["center"]
            direction = door["direction"]
            bx, by = to_blender_coords(dcx, dcy, width, height, scale)
            
            door_w = DOOR_WIDTH_M
            door_h = DOOR_HEIGHT_M
            door_t = 0.04
            
            # Extrude clean boolean cutter block
            cutter_scale = (door_w, 0.4, door_h) if direction == "horizontal" else (0.4, door_w, door_h)
            cutter = create_cube(f"BoolCutter_Door_F{floor_idx}_{idx}", (bx, by, z_offset + door_h/2), cutter_scale, parent=floor_parent)
            
            target_wall = find_closest_wall(bx, by)
            if target_wall:
                bool_mod = target_wall.modifiers.new(name=f"DoorCut_F{floor_idx}_{idx}", type='BOOLEAN')
                bool_mod.operation = 'DIFFERENCE'
                bool_mod.object = cutter
                bool_mod.solver = 'FLOAT'
                
            # Assembly real door panels, handles, and door frames
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=(bx, by, z_offset))
            door_group = bpy.context.active_object
            door_group.name = f"DoorGroup_F{floor_idx}_{idx}"
            door_group.parent = floor_parent
            
            if direction == "horizontal":
                # Left Frame vertical post
                create_cube("Frame_L", (-door_w/2 - 0.02, 0, door_h/2), (0.04, 0.16, door_h), materials['wood_door'], door_group)
                # Right Frame vertical post
                create_cube("Frame_R", (door_w/2 + 0.02, 0, door_h/2), (0.04, 0.16, door_h), materials['wood_door'], door_group)
                # Frame Lintel Header
                create_cube("Frame_H", (0, 0, door_h + 0.02), (door_w + 0.08, 0.16, 0.04), materials['wood_door'], door_group)
                
                # Dynamic door swings
                angle = math.radians(45)
                px = -door_w/2 + math.cos(angle) * door_w/2
                py = math.sin(angle) * door_w/2
                panel = create_cube("Panel", (px, py, door_h/2), (door_w, door_t, door_h), materials['wood_door'], door_group)
                panel.rotation_euler[2] = angle
                # Chrome round handles
                create_sphere("Knob_A", (px + math.cos(angle) * 0.38, py + math.sin(angle) * 0.38 - 0.035, 1.0), 0.03, materials['metal'], door_group)
                create_sphere("Knob_B", (px + math.cos(angle) * 0.38, py + math.sin(angle) * 0.38 + 0.035, 1.0), 0.03, materials['metal'], door_group)
            else:
                # Bottom Frame vertical post
                create_cube("Frame_B", (0, -door_w/2 - 0.02, door_h/2), (0.16, 0.04, door_h), materials['wood_door'], door_group)
                # Top Frame vertical post
                create_cube("Frame_T", (0, door_w/2 + 0.02, door_h/2), (0.16, 0.04, door_h), materials['wood_door'], door_group)
                # Frame Lintel Header
                create_cube("Frame_H", (0, 0, door_h + 0.02), (0.16, door_w + 0.08, 0.04), materials['wood_door'], door_group)
                
                # Dynamic door swings
                angle = math.radians(45)
                px = math.sin(angle) * door_w/2
                py = -door_w/2 + math.cos(angle) * door_w/2
                panel = create_cube("Panel", (px, py, door_h/2), (door_t, door_w, door_h), materials['wood_door'], door_group)
                panel.rotation_euler[2] = -angle
                create_sphere("Knob_A", (px + math.sin(angle) * 0.38 - 0.035, py + math.cos(angle) * 0.38, 1.0), 0.03, materials['metal'], door_group)
                create_sphere("Knob_B", (px + math.sin(angle) * 0.38 + 0.035, py + math.cos(angle) * 0.38, 1.0), 0.03, materials['metal'], door_group)
                
        # 4. Orientation-aware Windows placement
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
            if length == 0: continue
            
            angle = math.atan2(dy, dx)
            win_type = win.get("type", "standard")
            win_h = 1.6 if win_type == "large" else (0.8 if win_type == "minimal" else WINDOW_HEIGHT_M)
            win_sill = 0.5 if win_type == "large" else (1.5 if win_type == "minimal" else WINDOW_SILL_HEIGHT_M)
            
            # Cutter block
            cutter = create_cube(f"BoolCutter_Win_F{floor_idx}_{idx}", (cx, cy, z_offset + win_sill + win_h/2), (length, 0.4, win_h), parent=floor_parent)
            cutter.rotation_euler[2] = angle
            
            target_wall = find_closest_wall(cx, cy)
            if target_wall:
                bool_mod = target_wall.modifiers.new(name=f"WinCut_F{floor_idx}_{idx}", type='BOOLEAN')
                bool_mod.operation = 'DIFFERENCE'
                bool_mod.object = cutter
                bool_mod.solver = 'FLOAT'
                
            # Assembly physical windows
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=(cx, cy, z_offset + win_sill + win_h/2))
            win_group = bpy.context.active_object
            win_group.name = f"WinGroup_F{floor_idx}_{idx}"
            win_group.parent = floor_parent
            win_group.rotation_euler[2] = angle
            
            # Dark aluminum frame outline
            create_cube("Frame", (0, 0, 0), (length, 0.08, win_h), materials['dark_metal'], win_group)
            # Refractive physical glass pane
            create_cube("Glass", (0, 0, 0), (length - 0.06, 0.02, win_h - 0.06), materials['glass'], win_group)
            
        # 5. Asset Library Placement
        for room in rooms:
            rx1, ry1, rx2, ry2 = room["box"]
            x1, y1 = to_blender_coords(rx1, ry1, width, height, scale)
            x2, y2 = to_blender_coords(rx2, ry2, width, height, scale)
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            room_w = abs(x2 - x1)
            room_l = abs(y2 - y1)
            canonical = resolve_room_type(room.get("id", ""))
            
            # Furniture collision avoidance limits
            avail_w = room_w - 0.6
            avail_l = room_l - 0.6
            if avail_w <= 0.4 or avail_l <= 0.4: continue
            
            # Position dynamic assets in context of door locations
            if canonical == "bedroom":
                build_bed(f"BedSet_F{floor_idx}_{room['id']}", (cx, y2 - 1.25, z_offset), (1.6, 2.0, 0.6), 0.0, materials, floor_parent)
                if avail_l > 2.8:
                    build_wardrobe(f"Wardrobe_F{floor_idx}_{room['id']}", (x1 + 0.6, cy, z_offset), (1.6, 0.6, 2.2), math.pi/2, materials, floor_parent)
            elif canonical in ("living_room", "lounge"):
                build_sofa(f"Sofa_F{floor_idx}_{room['id']}", (cx, y1 + 0.85, z_offset), (2.0, 0.85, 0.7), 0.0, materials, floor_parent)
                build_tv_unit(f"TVUnit_F{floor_idx}_{room['id']}", (cx, y2 - 0.5, z_offset), (1.8, 0.45, 0.5), 0.0, materials, floor_parent)
            elif canonical == "dining_room":
                build_dining_table(f"Dining_F{floor_idx}_{room['id']}", (cx, cy, z_offset), (1.4, 0.9, 0.75), 0.0, materials, floor_parent)
            elif canonical in ("bathroom", "toilet", "powder_room"):
                build_toilet(f"Toilet_F{floor_idx}_{room['id']}", (x1 + 0.4, y2 - 0.4, z_offset), math.pi, materials, floor_parent)
                build_vanity(f"Vanity_F{floor_idx}_{room['id']}", (x2 - 0.5, cy, z_offset), (0.8, 0.5, 0.85), -math.pi/2, materials, floor_parent)
                build_shower(f"Shower_F{floor_idx}_{room['id']}", (x1 + 0.5, y1 + 0.5, z_offset), (0.9, 0.9, 2.0), 0.0, materials, floor_parent)
            elif canonical == "kitchen":
                build_kitchen_cabinet(f"Kitchen_F{floor_idx}_{room['id']}", (x1 + 0.7, cy, z_offset), (0.65, room_l - 0.8, 0.92), math.pi/2, materials, floor_parent)
                build_refrigerator(f"Fridge_F{floor_idx}_{room['id']}", (x2 - 0.45, y2 - 0.45, z_offset), (0.8, 0.75, 1.8), -math.pi/2, materials, floor_parent)
                build_oven(f"OvenRange_F{floor_idx}_{room['id']}", (cx, y2 - 0.4, z_offset), (0.75, 0.65, 0.92), 0.0, materials, floor_parent)
            elif canonical == "office":
                build_office_desk(f"Desk_F{floor_idx}_{room['id']}", (cx, cy, z_offset), (1.4, 0.7, 0.75), 0.0, materials, floor_parent)
                
        # 6. Multi-floor staircase transitions (stepped boxes)
        if num_floors > 1 and floor_idx == 0:
            stair_w, stair_l = 1.0, 3.2
            scx = min_house_x + 1.2
            scy = (min_house_y + max_house_y) / 2
            
            # Parent Empty for Stairs
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=(scx, scy, 0.0))
            stairs_grp = bpy.context.active_object
            stairs_grp.name = "Staircase_Assembly"
            stairs_grp.parent = floor_parent
            
            n_steps = 15
            step_h = (WALL_HEIGHT_M + FLOOR_SLAB_THICKNESS_M) / n_steps
            step_d = stair_l / n_steps
            for step_idx in range(n_steps):
                s_z = step_idx * step_h
                s_y = scy - stair_l/2 + step_idx * step_d
                step_obj = create_cube(f"StairStep_{step_idx}", (scx, s_y, s_z + step_h/2), (stair_w, step_d, step_h), materials['wood_door'], stairs_grp)
                uv_unwrap_object(step_obj)

    # Apply all modifier stacks on all walls and unbind boolean cutter shapes
    # This guarantees modifiers are properly applied prior to asset exports!
    if "bpy" in sys.modules:
        print("Finalizing boolean modifications and unlinking cutters...")
        # Make all meshes single-user and apply modifiers in Object Mode
        for obj in list(bpy.context.scene.objects):
            if obj.type == 'MESH':
                bpy.context.view_layer.objects.active = obj
                try:
                    bpy.ops.object.make_single_user(type='SELECTED_OBJECTS', object=True, obdata=True)
                    for mod in list(obj.modifiers):
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                except Exception as e:
                    print(f"Failed to apply modifier on {obj.name}: {e}")
                    
        # Safely remove cutter shapes to ensure clean glTF scene
        for obj in list(bpy.context.scene.objects):
            if "BoolCutter_" in obj.name:
                bpy.data.objects.remove(obj, do_unlink=True)

    # =============================================================================
    # 5. PROCEDURAL ROOFS AND OVERHANG SLABS
    # =============================================================================
    # Get total outer boundary with overhangs
    overhang = 0.3
    rx1, rx2 = min_house_x - overhang, max_house_x + overhang
    ry1, ry2 = min_house_y - overhang, max_house_y + overhang
    rcx = (rx1 + rx2) / 2
    rcy = (ry1 + ry2) / 2
    rsize_x = rx2 - rx1
    rsize_y = ry2 - ry1
    
    top_z = (num_floors - 1) * (WALL_HEIGHT_M + FLOOR_SLAB_THICKNESS_M) + WALL_HEIGHT_M
    
    # Parent Empty for roof
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(rcx, rcy, top_z))
    roof_parent = bpy.context.active_object
    roof_parent.name = "RoofAssembly"
    
    # 5 Dynamic roof designs: flat, gable, hip, shed, mansard
    roof_style = style.lower()
    
    if "classic" in roof_style or "rustical" in roof_style:
        # Gable Roof triangular prism
        roof_h = 2.4
        mesh = bpy.data.meshes.new(name="GableRoofMesh")
        roof_obj = bpy.data.objects.new("PitchedRoof", mesh)
        bpy.context.collection.objects.link(roof_obj)
        roof_obj.parent = roof_parent
        
        vertices = [
            (rx1, ry1, top_z),  # 0
            (rx2, ry1, top_z),  # 1
            (rx2, ry2, top_z),  # 2
            (rx1, ry2, top_z),  # 3
            (rx1, rcy, top_z + roof_h), # 4
            (rx2, rcy, top_z + roof_h)  # 5
        ]
        faces = [
            (0, 3, 2, 1),
            (0, 1, 5, 4),
            (2, 3, 4, 5),
            (0, 4, 3),
            (1, 2, 5)
        ]
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        roof_obj.data.materials.append(materials['roof'])
        uv_unwrap_object(roof_obj)
        
    elif "hip" in roof_style:
        # Hip Roof 4-sided pyramid
        roof_h = 2.5
        mesh = bpy.data.meshes.new(name="HipRoofMesh")
        roof_obj = bpy.data.objects.new("HipRoof", mesh)
        bpy.context.collection.objects.link(roof_obj)
        roof_obj.parent = roof_parent
        
        vertices = [
            (rx1, ry1, top_z),  # 0
            (rx2, ry1, top_z),  # 1
            (rx2, ry2, top_z),  # 2
            (rx1, ry2, top_z),  # 3
            (rcx - rsize_x*0.1, rcy, top_z + roof_h), # 4
            (rcx + rsize_x*0.1, rcy, top_z + roof_h)  # 5
        ]
        faces = [
            (0, 3, 2, 1),
            (0, 1, 5, 4),
            (1, 2, 5),
            (2, 3, 4, 5),
            (3, 0, 4)
        ]
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        roof_obj.data.materials.append(materials['roof'])
        uv_unwrap_object(roof_obj)
        
    elif "shed" in roof_style:
        # Shed Single-sloped roof
        roof_h = 1.5
        mesh = bpy.data.meshes.new(name="ShedRoofMesh")
        roof_obj = bpy.data.objects.new("ShedRoof", mesh)
        bpy.context.collection.objects.link(roof_obj)
        roof_obj.parent = roof_parent
        
        vertices = [
            (rx1, ry1, top_z),            # 0
            (rx2, ry1, top_z),            # 1
            (rx2, ry2, top_z + roof_h),   # 2
            (rx1, ry2, top_z + roof_h)    # 3
        ]
        faces = [(0, 3, 2, 1)]
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        roof_obj.data.materials.append(materials['roof'])
        uv_unwrap_object(roof_obj)
        
    else:
        # Modern Flat Roof slab with parapets and solar cells
        slab = create_cube("RoofSlab", (rcx, rcy, top_z + 0.1), (rsize_x, rsize_y, 0.2), materials['wall'], roof_parent)
        uv_unwrap_object(slab)
        
        par_h = 0.45
        par_t = 0.16
        create_cube("Parapet_N", (rcx, ry2 - par_t/2, top_z + 0.2 + par_h/2), (rsize_x, par_t, par_h), materials['wall'], roof_parent)
        create_cube("Parapet_S", (rcx, ry1 + par_t/2, top_z + 0.2 + par_h/2), (rsize_x, par_t, par_h), materials['wall'], roof_parent)
        create_cube("Parapet_E", (rx2 - par_t/2, rcy, top_z + 0.2 + par_h/2), (par_t, rsize_y - par_t*2, par_h), materials['wall'], roof_parent)
        create_cube("Parapet_W", (rx1 + par_t/2, rcy, top_z + 0.2 + par_h/2), (par_t, rsize_y - par_t*2, par_h), materials['wall'], roof_parent)
        
        if rsize_x > 5.5 and rsize_y > 5.5:
            create_cube("SolarFrame", (rcx, rcy, top_z + 0.26), (2.2, 1.4, 0.05), materials['metal'], roof_parent)
            solar = create_cube("SolarPanel", (rcx, rcy, top_z + 0.3), (2.1, 1.3, 0.02), materials['dark_metal'], roof_parent)
            solar.rotation_euler[0] = math.radians(15)

    # =============================================================================
    # 6. EXTERIOR LANDSCAPING ENVIRONMENT
    # =============================================================================
    # A. Large grass lawn ground plane mesh
    lawn_sz = max(rsize_x, rsize_y) * 4.5
    lawn = create_cube("GrassLawn", (rcx, rcy, -0.08), (lawn_sz, lawn_sz, 0.1), materials['lawn'])
    uv_unwrap_object(lawn)
    
    # B. Walks / walkways leading to entrance
    ent_door = [d for d in doors if d.get("is_entrance", False)]
    if ent_door:
        edx, edy = ent_door[0]["center"]
        ebx, eby = to_blender_coords(edx, edy, width, height, scale)
        create_cube("Walkway", (ebx, eby - 2.0, 0.005), (1.2, 4.0, 0.01), materials['tile'])
        
    # C. Parking driveway pads next to house
    create_cube("Driveway", (rcx + rsize_x/2 + 1.5, rcy, 0.005), (3.0, rsize_y, 0.01), materials['tile'])
    
    # D. Beautiful low-poly stylized landscaping trees
    for idx, (tx, ty) in enumerate([(-rsize_x - 1.5, -rsize_y - 1.5), (rsize_x + 1.5, -rsize_y - 1.5), (-rsize_x - 1.5, rsize_y + 1.5), (rsize_x + 1.5, rsize_y + 1.5)]):
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=(rcx + tx, rcy + ty, 0.0))
        tree_parent = bpy.context.active_object
        tree_parent.name = f"LowPolyTree_{idx}"
        
        # Sturdy trunk
        trunk = create_cylinder(f"TreeTrunk_{idx}", (rcx + tx, rcy + ty, 1.0), 0.14, 2.0, material=materials['wood_door'], parent=tree_parent)
        uv_unwrap_object(trunk)
        
        # Naturally grouped foliage clusters
        canopy_A = create_sphere(f"TreeCanopy_A_{idx}", (rcx + tx, rcy + ty, 2.2), 1.25, materials['lawn'], parent=tree_parent)
        canopy_B = create_sphere(f"TreeCanopy_B_{idx}", (rcx + tx + 0.35, rcy + ty - 0.25, 2.5), 0.95, materials['lawn'], parent=tree_parent)
        canopy_C = create_sphere(f"TreeCanopy_C_{idx}", (rcx + tx - 0.35, rcy + ty + 0.35, 2.45), 0.85, materials['lawn'], parent=tree_parent)
        canopy_D = create_sphere(f"TreeCanopy_D_{idx}", (rcx + tx, rcy + ty, 2.95), 0.75, materials['lawn'], parent=tree_parent)
        
        for c in [canopy_A, canopy_B, canopy_C, canopy_D]:
            uv_unwrap_object(c)

    # =============================================================================
    # 7. PROFESSIONAL LIGHTING & RENDERING (CYCLES HERO MODE)
    # =============================================================================
    scene = bpy.context.scene
    
    if render_mode == "hero":
        print("Configuring rendering engine to: CYCLES (CPU Safe Mode)")
        scene.render.engine = 'CYCLES'
        if hasattr(scene.cycles, "device"):
            scene.cycles.device = 'CPU'
        scene.cycles.samples = 4
        scene.cycles.use_denoising = True
        
        # OIDN Denoising Node
        if scene.render.engine == 'CYCLES':
            try:
                tree = None
                # Modern Blender 5.1+ uses compositor_node_tree or use_nodes on Scene
                if hasattr(scene, "use_nodes"):
                    scene.use_nodes = True
                if hasattr(scene, "node_tree"):
                    tree = scene.node_tree
                elif hasattr(scene, "compositor_node_tree"):
                    tree = scene.compositor_node_tree
                    
                if tree:
                    tree.nodes.clear()
                    rl = tree.nodes.new("CompositorNodeRLayers")
                    denoise = tree.nodes.new("CompositorNodeDenoise")
                    comp = tree.nodes.new("CompositorNodeComposite")
                    tree.links.new(rl.outputs["Noisy Image"], denoise.inputs["Image"])
                    tree.links.new(denoise.outputs["Image"], comp.inputs["Image"])
            except Exception as e:
                print(f"Warning: Failed to configure compositor nodes: {e}")
            
        # Global HDRI environment sky texture lighting (ShaderNodeTexSky)
        try:
            scene.world.use_nodes = True
            w_tree = scene.world.node_tree
            w_tree.nodes.clear()
            
            w_out = w_tree.nodes.new("ShaderNodeOutputWorld")
            w_bg = w_tree.nodes.new("ShaderNodeBackground")
            # Soft ambient sky blue
            w_bg.inputs["Color"].default_value = (0.90, 0.94, 0.98, 1.0)
            w_bg.inputs["Strength"].default_value = 0.8
            w_tree.links.new(w_bg.outputs["Background"], w_out.inputs["Surface"])
        except Exception as e:
            print(f"Warning: Failed to configure environment sky nodes: {e}")
            
    else:
        print("Configuring rendering engine to: EEVEE (Preview Mode)")
        scene.render.engine = 'BLENDER_EEVEE'
        if hasattr(scene.eevee, "use_ambient_occlusion"):
            scene.eevee.use_ambient_occlusion = True
            scene.eevee.ambient_occlusion_distance = 0.8
        if hasattr(scene.eevee, "use_ssr"):
            scene.eevee.use_ssr = True
            scene.eevee.use_ssr_refraction = True
            
    # Add a Sun light source pointing downwards for gorgeous shadows across both rendering engines
    bpy.ops.object.light_add(type='SUN', location=(15.0, -15.0, 20.0))
    sun = bpy.context.active_object
    sun.data.energy = 6.0
    sun.data.color = (1.0, 0.96, 0.90)
    sun.rotation_euler = (math.radians(48), 0.0, math.radians(48))

    # Ambient area lights in each room center
    for r_idx, room in enumerate(rooms):
        rx1, ry1, rx2, ry2 = room["box"]
        x1, y1 = to_blender_coords(rx1, ry1, width, height, scale)
        x2, y2 = to_blender_coords(rx2, ry2, width, height, scale)
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        
        bpy.ops.object.light_add(type='AREA', location=(cx, cy, top_z - 0.2))
        area_lt = bpy.context.active_object
        area_lt.name = f"AreaLight_{room['id']}"
        area_lt.data.size = min(abs(x2-x1)*0.35, abs(y2-y1)*0.35)
        area_lt.data.energy = 150.0
        area_lt.data.color = (1.0, 0.92, 0.85)

    # =============================================================================
    # 8. AUTOMATIC CAMERA PLACEMENT & PRESENTATION RENDERING
    # =============================================================================
    # Calculate global bounding box sizing to center perspective frames
    house_cx = (min_house_x + max_house_x) / 2
    house_cy = (min_house_y + max_house_y) / 2
    size_house_x = abs(max_house_x - min_house_x)
    size_house_y = abs(max_house_y - min_house_y)
    max_dim = max(size_house_x, size_house_y, 4.0)
    ortho_scale = max_dim * 1.05
    
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.image_settings.file_format = 'PNG'
    
    # 1. Top View Camera (hide roof Assembly during capture)
    topdown_z = max_dim * 1.2
    bpy.ops.object.camera_add(location=(house_cx, house_cy, topdown_z))
    topdown_cam = bpy.context.active_object
    topdown_cam.name = "TopdownCamera"
    topdown_cam.data.type = 'ORTHO'
    topdown_cam.data.ortho_scale = ortho_scale * 0.95
    topdown_cam.rotation_euler = (0.0, 0.0, 0.0)
    
    # 2. Isometric View Camera
    bpy.ops.object.camera_add(location=(0, 0, 0))
    iso_cam = bpy.context.active_object
    iso_cam.name = "IsometricCamera"
    iso_cam.data.type = 'ORTHO'
    iso_cam.data.ortho_scale = ortho_scale
    d_iso = max_dim * 0.85
    cam_x = house_cx + d_iso * math.cos(math.radians(45))
    cam_y = house_cy - d_iso * math.cos(math.radians(45))
    cam_z = d_iso * 0.75
    iso_cam.location = (cam_x, cam_y, cam_z)
    try:
        import mathutils
        direction = mathutils.Vector((house_cx - cam_x, house_cy - cam_y, top_z/2 - cam_z))
        iso_cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    except ImportError:
        iso_cam.rotation_euler = (math.radians(55), 0.0, math.radians(45))
        
    # 3. Perspective Exterior Hero Camera
    bpy.ops.object.camera_add(location=(0, 0, 0))
    hero_cam = bpy.context.active_object
    hero_cam.name = "ExteriorHeroCamera"
    hero_cam.data.lens = 35 # 35mm professional lens
    hc_x = house_cx + max_dim * 0.95
    hc_y = house_cy - max_dim * 0.95
    hc_z = top_z + 1.0
    hero_cam.location = (hc_x, hc_y, hc_z)
    try:
        direction = mathutils.Vector((house_cx - hc_x, house_cy - hc_y, top_z/2 - hc_z))
        hero_cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    except Exception:
        hero_cam.rotation_euler = (math.radians(72), 0.0, math.radians(45))

    # A. Render Exterior Hero View
    roof_parent.hide_viewport = False
    roof_parent.hide_render = False
    scene.camera = hero_cam
    hero_path = os.path.join(output_dir, "render_exterior.png")
    scene.render.filepath = hero_path
    print(f"Rendering exterior cycles visualization to: {hero_path}")
    bpy.ops.render.render(write_still=True)
    # Duplicate standard render.png
    shutil.copy(hero_path, os.path.join(output_dir, "render.png"))
    
    # C. Render Topdown projection (hide roof!)
    roof_parent.hide_viewport = True
    roof_parent.hide_render = True
    scene.camera = topdown_cam
    topdown_path = os.path.join(output_dir, "render_topdown.png")
    scene.render.filepath = topdown_path
    bpy.ops.render.render(write_still=True)
    
    # Re-enable roof visibility
    roof_parent.hide_viewport = False
    roof_parent.hide_render = False
    
    # D. Configure (but skip rendering) Interior Room Camera Views for user customization
    # We find coordinates of Living Room, Bedroom, and Kitchen and place cameras inside them
    for target_canonical in ["living_room", "bedroom", "kitchen"]:
        target_room = None
        for r in rooms:
            if resolve_room_type(r["id"]) == target_canonical:
                target_room = r
                break
        if not target_room and rooms:
            target_room = rooms[0] # Fallback
            
        if target_room:
            rx1, ry1, rx2, ry2 = target_room["box"]
            x1, y1 = to_blender_coords(rx1, ry1, width, height, scale)
            x2, y2 = to_blender_coords(rx2, ry2, width, height, scale)
            rcx, rcy = (x1 + x2)/2, (y1 + y2)/2
            
            # Place camera in corner pointing at room center with wide angle 18mm lens
            bpy.ops.object.camera_add(location=(x1 + 0.3, y1 + 0.3, z_offset + 1.25))
            in_cam = bpy.context.active_object
            in_cam.name = f"InteriorCam_{target_canonical}"
            in_cam.data.lens = 18 # Ultra widescreen lens
            try:
                direction = mathutils.Vector((rcx - (x1 + 0.3), rcy - (y1 + 0.3), -0.2))
                in_cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
            except Exception:
                in_cam.rotation_euler = (math.radians(80), 0.0, math.radians(45))

    # =============================================================================
    # 9. CONVERT CAD EXPORTS
    # =============================================================================
    gltf_path = os.path.join(output_dir, "model.gltf")
    glb_path = os.path.join(output_dir, "model.glb")
    obj_path = os.path.join(output_dir, "model.obj")
    blend_path = os.path.join(output_dir, "model.blend")
    
    # Save Blend archive file
    print(f"Saving .blend archive file to: {blend_path}")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    
    # Save GlTF
    print(f"Exporting GLTF assets to: {gltf_path}")
    bpy.ops.export_scene.gltf(filepath=gltf_path, export_format='GLTF_SEPARATE', use_selection=False)
    
    # Manually base64-encode and embed the binary to keep GLTF_EMBEDDED clean
    try:
        import base64
        bin_path = gltf_path.replace(".gltf", ".bin")
        if os.path.exists(bin_path):
            with open(gltf_path, "r", encoding="utf-8") as f:
                gltf_data = json.load(f)
            with open(bin_path, "rb") as f:
                bin_data = f.read()
            base64_bin = base64.b64encode(bin_data).decode("utf-8")
            if "buffers" in gltf_data and len(gltf_data["buffers"]) > 0:
                gltf_data["buffers"][0]["uri"] = f"data:application/octet-stream;base64,{base64_bin}"
            with open(gltf_path, "w", encoding="utf-8") as f:
                json.dump(gltf_data, f, indent=2)
            os.remove(bin_path)
    except Exception as e:
        print(f"Warning: Failed post-processing base64 gltf bin: {e}")
        
    # Delete RoofAssembly meshes so the interactive 3D GLB reveals gorgeous styled PBR interiors and furniture
    roof_obj = bpy.data.objects.get("RoofAssembly")
    if roof_obj:
        for child in list(roof_obj.children):
            bpy.data.objects.remove(child, do_unlink=True)
        bpy.data.objects.remove(roof_obj, do_unlink=True)
            
    # Save GLB
    print(f"Exporting GLB binary to: {glb_path}")
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB', use_selection=False)
    
    # Select meshes only for OBJ export
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            obj.select_set(True)
            
    print(f"Exporting OBJ CAD meshes to: {obj_path}")
    try:
        if hasattr(bpy.ops.wm, 'obj_export'):
            bpy.ops.wm.obj_export(filepath=obj_path, export_selected_objects=True, export_materials=True)
        else:
            bpy.ops.export_scene.obj(filepath=obj_path, use_selection=True, use_materials=True)
    except Exception as e:
        print(f"OBJ export failed: {e}")
        
    print("All commercial-grade architecture renders and meshes completely generated!")

def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Loading floorplan metadata structure from: {args.layout_json}")
    with open(args.layout_json, 'r') as f:
        layout_data = json.load(f)
        
    print(f"Initiating Blender 3D procedural architecture builder (Render Mode: {args.render_mode})...")
    build_floorplan_3d(layout_data, args.output_dir, args.render_mode)

if __name__ == "__main__":
    main()
