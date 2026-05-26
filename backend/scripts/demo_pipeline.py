import time
import httpx

BASE_URL = "http://127.0.0.1:8000"

def run_demo():
    print("==================================================================")
    print("      NEXUS AI ARCHITECTURE GENERATION - LIVE SYSTEM DEMO")
    print("==================================================================\n")

    client = httpx.Client(timeout=30.0)

    # 1. Register User
    email = "architect_demo@nex.ai"
    password = "securepassword123"
    print(f"[*] Step 1: Registering new account '{email}'...")
    try:
        reg_res = client.post(f"{BASE_URL}/auth/register", json={"email": email, "password": password})
        if reg_res.status_code == 201:
            print("[+] Account successfully created!")
        elif reg_res.status_code == 400:
            print("[*] Account already exists, proceeding to login...")
        else:
            print(f"[-] Registration failed: {reg_res.text}")
            return
    except Exception as e:
        print(f"[-] Could not connect to API Gateway: {e}")
        return

    # 2. Login
    print("\n[*] Step 2: Logging in to acquire secure JWT token...")
    login_res = client.post(f"{BASE_URL}/auth/login", data={"username": email, "password": password})
    if login_res.status_code != 200:
        print(f"[-] Login failed: {login_res.text}")
        return
    
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[+] JWT Token successfully acquired!")

    # 3. Create Project
    print("\n[*] Step 3: Creating a new Architectural Project...")
    project_payload = {
        "name": "Sleek Modernist Villa",
        "prompt": "Design a modern 3-bedroom house with garage, spacious living room, open kitchen, and classic front balcony",
        "style": "minimalist"
    }
    proj_res = client.post(f"{BASE_URL}/projects/create", json=project_payload, headers=headers)
    if proj_res.status_code != 201:
        print(f"[-] Project creation failed: {proj_res.text}")
        return
    
    project_data = proj_res.json()
    project_id = project_data["id"]
    print(f"[+] Project created successfully! ID: {project_id}")

    # 4. Trigger Generation Pipeline
    print("\n[*] Step 4: Triggering Asynchronous CAD & 3D Generation Pipeline...")
    gen_res = client.post(f"{BASE_URL}/generate/floorplan", json={"project_id": project_id}, headers=headers)
    if gen_res.status_code != 202:
        print(f"[-] Triggering pipeline failed: {gen_res.text}")
        return
    
    job_id = gen_res.json()["job_id"]
    print(f"[+] Generation pipeline successfully enqueued! Job ID: {job_id}")

    # 5. Poll Job Status
    print("\n[*] Step 5: Polling Generation Job Status...")
    while True:
        status_res = client.get(f"{BASE_URL}/generate/status/{job_id}", headers=headers)
        if status_res.status_code != 200:
            print(f"[-] Status retrieval failed: {status_res.text}")
            break
        
        job_info = status_res.json()
        status_state = job_info["status"]
        progress = job_info["progress_percent"]
        stage = job_info["current_stage"]
        
        print(f"    [Job Status]: Status: {status_state.upper()} | Progress: {progress}% | Stage: {stage}")
        
        if status_state in ["COMPLETED", "SUCCESS"]:
            print("\n[+] AI GENERATION WORKFLOW COMPLETED SUCCESSFULLY!")
            break
        elif status_state == "FAILED":
            print(f"\n[-] Job failed: {job_info.get('error_message')}")
            break
            
        time.sleep(2.0)

    # 6. Fetch Generated Project Assets
    print("\n[*] Step 6: Fetching Generated CAD & 3D Assets...")
    get_proj_res = client.get(f"{BASE_URL}/projects/{project_id}", headers=headers)
    if get_proj_res.status_code != 200:
        print(f"[-] Failed to retrieve project assets: {get_proj_res.text}")
        return
    
    assets = get_proj_res.json()
    print("==================================================================")
    print("               GENERATED CAD & 3D ASSETS DOWNLOAD LINKS")
    print("==================================================================")
    
    floorplans = assets.get("floorplans", [])
    models = assets.get("models_3d", [])
    
    if floorplans:
        fp = floorplans[0]
        print(f"    [Floorplan PNG] : {BASE_URL}{fp.get('image_url')}")
        print(f"    [Vector SVG]    : {BASE_URL}{fp.get('vector_svg_url')}")
        print(f"    [CAD DXF File]  : {BASE_URL}{fp.get('vector_dxf_url')}")
    
    if models:
        md = models[0]
        print(f"    [3D GLTF Mesh]  : {BASE_URL}{md.get('gltf_url')}")
        print(f"    [AutoCAD OBJ]   : {BASE_URL}{md.get('obj_url')}")
        print(f"    [3D Rendering]  : {BASE_URL}{md.get('renders')[0].get('image_url') if md.get('renders') else 'N/A'}")
        
    print("\n==================================================================")
    print("      ALL CAD ASSETS HAVE BEEN SUCCESSFULLY SAVED TO STORAGE!")
    print("==================================================================")

if __name__ == "__main__":
    run_demo()
