import os
import sys
import json
import tempfile
import subprocess

# Set up paths
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)
furniture_dir = os.path.join(backend_dir, "assets", "furniture")
output_dir = os.path.join(backend_dir, "outputs", "models3d", "debug_run")

print("==================================================")
print("             NEXA FURNITURE TESTING SUITE         ")
print("==================================================")

# 1. & 2. Verify and Print Discovered Furniture Assets
print(f"Checking assets directory: {furniture_dir}")
fbx_files = []
if os.path.exists(furniture_dir):
    fbx_files = [f for f in os.listdir(furniture_dir) if f.lower().endswith(".fbx")]

print(f"Number of assets found: {len(fbx_files)}")
print("Discovered assets:")
for f in sorted(fbx_files):
    print(f"  - {f}")

# 3. Create a Mock Layout JSON that contains Bedroom, Living Room, Bathroom, Kitchen
mock_layout = {
  "width_px": 800,
  "height_px": 600,
  "scale_px_to_meter": 50,
  "rooms": [
    {
      "id": "bedroom_1",
      "type": "bedroom",
      "zone": "private",
      "box": [100, 100, 300, 300],  # 4m x 4m
      "label": "BEDROOM"
    },
    {
      "id": "living_room_1",
      "type": "living_room",
      "zone": "public",
      "box": [300, 100, 550, 300],  # 5m x 4m
      "label": "LIVING ROOM"
    },
    {
      "id": "bathroom_1",
      "type": "bathroom",
      "zone": "private",
      "box": [100, 300, 250, 450],  # 3m x 3m
      "label": "BATHROOM"
    },
    {
      "id": "kitchen_1",
      "type": "kitchen",
      "zone": "service",
      "box": [250, 300, 450, 450],  # 4m x 3m
      "label": "KITCHEN"
    }
  ],
  "walls": [
    # Exterior boundaries
    [100, 100, 550, 100, True],
    [550, 100, 550, 300, True],
    [550, 300, 450, 300, True],
    [450, 300, 450, 450, True],
    [450, 450, 100, 450, True],
    [100, 450, 100, 100, True],
    # Interior partitions
    [300, 100, 300, 300, False],
    [100, 300, 300, 300, False],
    [250, 300, 250, 450, False]
  ],
  "doors": [
    {
      "room_id": "bedroom_1",
      "center": [300, 200],
      "direction": "vertical"
    },
    {
      "room_id": "bathroom_1",
      "center": [175, 300],
      "direction": "horizontal"
    },
    {
      "room_id": "kitchen_1",
      "center": [350, 300],
      "direction": "horizontal"
    }
  ],
  "windows": [
    {
      "room_id": "bedroom_1",
      "start": [100, 150],
      "end": [100, 250]
    },
    {
      "room_id": "living_room_1",
      "start": [400, 100],
      "end": [450, 100]
    }
  ]
}

temp_json_path = os.path.join(tempfile.gettempdir(), "debug_layout.json")
with open(temp_json_path, "w") as f:
    json.dump(mock_layout, f)

print(f"\nCreated debug layout file at: {temp_json_path}")
print("Executing Blender generation pipeline to build rooms and place furniture assets...")

generator_script = os.path.join(script_dir, "blender_generator.py")
blender_cmd = [
    "blender",
    "--background",
    "--python", generator_script,
    "--",
    "--layout-json", temp_json_path,
    "--output-dir", output_dir
]

result = subprocess.run(blender_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
if result.returncode != 0:
    print(f"[-] Blender generation failed! Exit code: {result.returncode}")
    print(f"Stdout:\n{result.stdout}")
    print(f"Stderr:\n{result.stderr}")
    sys.exit(1)

print("[+] Blender generation completed successfully!")

# Run verification in Blender context
print("\nLoading generated .blend file to verify furniture positions and orientations...")
blend_file = os.path.join(output_dir, "model.blend")

verify_script = """
import bpy
import os

print("\\n" + "="*50)
print("       BLENDER INTERNAL GEOMETRY VERIFICATION")
print("="*50)

# Rooms and their target boundaries in Blender units
# Box pixel bounds converted: bx = (px - 400) / 50, by = (300 - py) / 50
# bedroom_1: box=[100, 100, 300, 300] => X=[-6.0, -2.0], Y=[0.0, 4.0]
# living_room_1: box=[300, 100, 550, 300] => X=[-2.0, 3.0], Y=[0.0, 4.0]
# bathroom_1: box=[100, 300, 250, 450] => X=[-6.0, -3.0], Y=[-3.0, 0.0]
# kitchen_1: box=[250, 300, 450, 450] => X=[-3.0, 1.0], Y=[-3.0, 0.0]

room_bounds = {
    "bedroom": {"min_x": -6.0, "max_x": -2.0, "min_y": 0.0, "max_y": 4.0},
    "living_room": {"min_x": -2.0, "max_x": 3.0, "min_y": 0.0, "max_y": 4.0},
    "bathroom": {"min_x": -6.0, "max_x": -3.0, "min_y": -3.0, "max_y": 0.0},
    "kitchen": {"min_x": -3.0, "max_x": 1.0, "min_y": -3.0, "max_y": 0.0}
}

active_collection = bpy.context.view_layer.active_layer_collection.collection

print("Scanning objects in scene...")
assets_placed = []
failures = []

for o in bpy.context.scene.objects:
    if o.name.startswith("Asset_"):
        assets_placed.append(o)
        
        # 5. Verify linked to active collection
        is_linked = o.name in active_collection.objects
        # 6. Verify not hidden
        is_hidden = o.hide_viewport or o.hide_render
        # 7. Verify not placed below the floor (Z >= 0)
        z_height = o.matrix_world.translation.z
        is_below_floor = z_height < -0.01
        # 8. Verify scale is not zero
        scale = o.scale
        is_zero_scale = scale.x < 0.01 or scale.y < 0.01 or scale.z < 0.01
        
        # Determine which room bounds to check
        room_type = None
        for key in room_bounds:
            if key in o.name.lower() or (o.parent and key in o.parent.name.lower()):
                room_type = key
                break
                
        is_inside = True
        loc = o.matrix_world.translation
        if room_type:
            bounds = room_bounds[room_type]
            # Give a small tolerance margin of 0.2m for wall offset alignment
            if not (bounds["min_x"] - 0.2 <= loc.x <= bounds["max_x"] + 0.2) or not (bounds["min_y"] - 0.2 <= loc.y <= bounds["max_y"] + 0.2):
                is_inside = False
                
        print(f"\\n[*] Furniture placement check: {o.name}")
        print(f"    - Location: {loc}")
        print(f"    - Scale: {scale}")
        print(f"    - Linked to scene collection: {is_linked}")
        print(f"    - Hidden: {is_hidden}")
        print(f"    - Placed Z height >= 0: {not is_below_floor} (z={z_height:.3f})")
        print(f"    - Inside room bounds: {is_inside} (room={room_type})")
        
        if not is_linked: failures.append(f"{o.name} is NOT linked to collection")
        if is_hidden: failures.append(f"{o.name} is hidden")
        if is_below_floor: failures.append(f"{o.name} is placed below floor (z={z_height:.3f})")
        if is_zero_scale: failures.append(f"{o.name} has zero scale")
        if not is_inside: failures.append(f"{o.name} is outside room bounds")

print("\\n" + "="*50)
print("             VERIFICATION SUMMARY")
print("="*50)
print(f"Total assets placed in scene: {len(assets_placed)}")
print(f"Total validation failures: {len(failures)}")
if failures:
    for fail in failures:
        print(f"  [-] {fail}")
else:
    print("  [+] ALL 10 DEBUG CHECKS PASSED SUCCESSFULLY!")

print("="*50)
"""

verify_script_path = os.path.join(tempfile.gettempdir(), "verify_blend.py")
with open(verify_script_path, "w") as f:
    f.write(verify_script)

verify_cmd = [
    "blender",
    blend_file,
    "--background",
    "--python", verify_script_path
]

verify_result = subprocess.run(verify_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
print(verify_result.stdout)

# Copy the final render outputs to the brain artifacts folder to be visible
shutil_ok = True
try:
    import shutil
    shutil.copy(os.path.join(output_dir, "render_isometric.png"), "C:\\Users\\Vishant Kumar\\.gemini\\antigravity\\brain\\816d724d-f6a8-45a2-9dc7-f798bfe9a34c\\artifacts\\render_isometric.png")
    shutil.copy(os.path.join(output_dir, "render_topdown.png"), "C:\\Users\\Vishant Kumar\\.gemini\\antigravity\\brain\\816d724d-f6a8-45a2-9dc7-f798bfe9a34c\\artifacts\\render_topdown.png")
    print("[+] Render outputs copied to artifacts!")
except Exception as e:
    print(f"[-] Failed to copy renders: {e}")
