import os
import sys
import uuid
import json

# Add backend directory to path
backend_path = os.path.dirname(os.path.dirname(__file__))
sys.path.append(backend_path)

from shared.database import get_sync_db, sync_engine, Base
from shared.models import User, Project, GenerationJob, FloorPlan, Model3D, RenderOutput
from shared.security import get_password_hash
from workers.tasks import execute_architecture_pipeline

def run_local_pipeline():
    print("==================================================================")
    print("   NEXUS AI ARCHITECTURE GENERATION - SYNC LOCAL PIPELINE RUN")
    print("==================================================================\n")

    # 1. Bootstrap SQLite database tables
    print("[*] Bootstrapping SQLite database schemas...")
    Base.metadata.create_all(bind=sync_engine)
    print("[+] Database bootstrapped successfully!\n")

    db_gen = get_sync_db()
    db = next(db_gen)

    try:
        # 2. Register / Fetch User
        email = "architect_demo@nex.ai"
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"[*] Creating user account '{email}'...")
            user = User(
                email=email,
                hashed_password=get_password_hash("securepassword123"),
                role="user",
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print("[+] Account created successfully!")
        else:
            print(f"[+] Found existing account: {email}")

        # 3. Create Project
        print("\n[*] Creating a new Architectural Project...")
        project = Project(
            user_id=user.id,
            name="Sleek Modernist Villa",
            prompt="Design a modern 3-bedroom house with garage, spacious living room, open kitchen, and classic front balcony",
            style="modern"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        print(f"[+] Project created! ID: {project.id}")

        # 4. Enqueue Generation Job
        print("\n[*] Initializing generation job...")
        job = GenerationJob(
            project_id=project.id,
            status="PENDING",
            progress_percent=0,
            current_stage="Created"
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        print(f"[+] Job initialized! ID: {job.id}")

        # 5. Execute Pipeline Synchronously
        print("\n[*] Starting End-to-End Architectural Pipeline Execution...")
        print("    (Running stages: NLP Parsing -> Graph Gen -> Our new BSP Layout -> Vectorization -> 3D Mesh)")
        print("------------------------------------------------------------------")
        
        success = execute_architecture_pipeline(str(job.id))
        
        print("------------------------------------------------------------------")
        if success:
            print("[+] Synchronous Pipeline Completed Successfully!")
            
            # Refresh DB objects
            db.refresh(job)
            floorplan = db.query(FloorPlan).filter(FloorPlan.project_id == project.id).first()
            model = db.query(Model3D).filter(Model3D.project_id == project.id).first()
            
            print("\n==================================================================")
            print("               GENERATED CAD & 3D ASSETS LOCAL PATHS")
            print("==================================================================")
            if floorplan:
                print(f"    [Floorplan PNG] : {floorplan.image_url}")
                print(f"    [Vector SVG]    : {floorplan.vector_svg_url}")
                print(f"    [CAD DXF File]  : {floorplan.vector_dxf_url}")
                print(f"    [Layout JSON]   : (Saved in database)")
                
            if model:
                print(f"    [3D GLTF Mesh]  : {model.gltf_url}")
                print(f"    [AutoCAD OBJ]   : {model.obj_url}")
                renders = db.query(RenderOutput).filter(RenderOutput.model_3d_id == model.id).all()
                for idx, render in enumerate(renders):
                    print(f"    [Render {render.view_type.upper()}] : {render.image_url}")
            
            print("\n==================================================================")
            print("      ALL CAD ASSETS HAVE BEEN SUCCESSFULLY SAVED TO STORAGE!")
            print("==================================================================")
        else:
            db.refresh(job)
            print(f"[-] Pipeline execution failed: {job.error_message}")

    except Exception as e:
        import traceback
        print(f"[-] Error during demo run: {e}")
        traceback.print_exc()
    finally:
        db_gen.close()

if __name__ == "__main__":
    run_local_pipeline()
