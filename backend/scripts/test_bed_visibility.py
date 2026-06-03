"""
DEEP MATERIAL & GEOMETRY DIAGNOSTIC
=====================================
Figure out WHY the bed mesh is invisible despite having 354 verts / 342 faces.
"""
import bpy
import os
import sys
import math
import mathutils

script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)
furniture_dir = os.path.join(backend_dir, "assets", "furniture")

# Clear
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for col in list(bpy.data.collections):
    bpy.data.collections.remove(col)

# Import
bed_path = os.path.join(furniture_dir, "Bed_King.fbx")
bpy.ops.import_scene.fbx(filepath=bed_path)
bed = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]

print(f"\n=== OBJECT: {bed.name} ===")
print(f"Vertices: {len(bed.data.vertices)}")
print(f"Edges: {len(bed.data.edges)}")
print(f"Polygons: {len(bed.data.polygons)}")
print(f"Location: {bed.location[:]}")
print(f"Scale: {bed.scale[:]}")
print(f"Dimensions: {bed.dimensions[:]}")

# Check normals
print(f"\n=== NORMALS ===")
if bed.data.polygons:
    sample = list(bed.data.polygons)[:5]
    for p in sample:
        print(f"  Face {p.index}: normal={p.normal[:]}  area={p.area:.6f}  center={p.center[:]}")
    areas = [p.area for p in bed.data.polygons]
    print(f"  Total faces: {len(areas)}")
    print(f"  Min area: {min(areas):.6f}")
    print(f"  Max area: {max(areas):.6f}")
    print(f"  Zero-area faces: {sum(1 for a in areas if a < 1e-8)}")

# Check materials deeply
print(f"\n=== MATERIALS ({len(bed.data.materials)} total) ===")
for i, mat in enumerate(bed.data.materials):
    if not mat:
        print(f"  Slot {i}: None")
        continue
    print(f"\n  Material '{mat.name}':")
    print(f"    use_nodes: {mat.use_nodes}")
    print(f"    blend_method: {mat.blend_method if hasattr(mat, 'blend_method') else 'N/A'}")
    
    if mat.node_tree:
        print(f"    Nodes ({len(mat.node_tree.nodes)}):")
        for node in mat.node_tree.nodes:
            print(f"      [{node.type}] '{node.name}'")
            if node.type == 'BSDF_PRINCIPLED':
                base_col = node.inputs.get('Base Color')
                if base_col:
                    print(f"        Base Color: {base_col.default_value[:]}")
                alpha = node.inputs.get('Alpha')
                if alpha:
                    print(f"        Alpha: {alpha.default_value}")
                    if alpha.default_value < 0.01:
                        print(f"        *** WARNING: Alpha is ZERO! Object will be INVISIBLE! ***")
            elif node.type == 'OUTPUT_MATERIAL':
                print(f"        is_active_output: {node.is_active_output}")
        
        print(f"    Links ({len(mat.node_tree.links)}):")
        for link in mat.node_tree.links:
            print(f"      {link.from_node.name}.{link.from_socket.name} -> {link.to_node.name}.{link.to_socket.name}")
    else:
        print(f"    node_tree: None")
    
    # Check how many faces use this material
    face_count = sum(1 for p in bed.data.polygons if p.material_index == i)
    print(f"    Faces using this material: {face_count}")

# Check if mesh has any vertex colors or UVs
print(f"\n=== UV MAPS ===")
if bed.data.uv_layers:
    for uv in bed.data.uv_layers:
        print(f"  UV Map: '{uv.name}' active={uv.active}")
else:
    print("  No UV maps")

print(f"\n=== VERTEX COLORS ===")
if bed.data.color_attributes:
    for vc in bed.data.color_attributes:
        print(f"  Color attr: '{vc.name}' domain={vc.domain} type={vc.data_type}")
else:
    print("  No vertex colors")

# Check the EEVEE rendering - try with a simple override material
print(f"\n=== TESTING: Override all materials with solid red ===")
for i, mat in enumerate(bed.data.materials):
    if mat and mat.node_tree:
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                node.inputs['Base Color'].default_value = (1, 0, 0, 1)
                alpha_input = node.inputs.get('Alpha')
                if alpha_input:
                    alpha_input.default_value = 1.0
                    print(f"  Fixed Alpha to 1.0 on material '{mat.name}'")

# Force scene collection
scene_col = bpy.context.scene.collection
for o in bpy.context.scene.objects:
    if o.type == 'MESH':
        if o.name not in scene_col.objects:
            scene_col.objects.link(o)
        o.hide_viewport = False
        o.hide_render = False

bpy.context.view_layer.update()

# Camera
bpy.ops.object.camera_add(location=(0, 0, 9))
cam = bpy.context.active_object
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 6
cam.data.clip_end = 30
cam.rotation_euler = (0, 0, 0)
bpy.context.scene.camera = cam

# Sun
bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))
sun = bpy.context.active_object
sun.data.energy = 5.0

# World
world = bpy.data.worlds.new("W")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.85, 0.88, 0.92, 1.0)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 800
scene.render.resolution_y = 800

# Render with red override
red_path = os.path.join(backend_dir, "outputs", "test_bed_red.png")
scene.render.filepath = red_path
print(f"\nRendering red-override top-down...")
bpy.ops.render.render(write_still=True)
print(f"Red override render: {os.path.getsize(red_path):,} bytes")

# Also try CYCLES
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 16
cycles_path = os.path.join(backend_dir, "outputs", "test_bed_cycles.png")
scene.render.filepath = cycles_path
print(f"\nRendering with CYCLES engine...")
bpy.ops.render.render(write_still=True)
print(f"Cycles render: {os.path.getsize(cycles_path):,} bytes")

print("\nDONE")
