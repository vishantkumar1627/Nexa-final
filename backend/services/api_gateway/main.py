import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from shared.config import settings
from shared.database import async_engine, Base
from services.api_gateway.routers import auth, projects, generate, files

# Setup logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("gateway_main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for startup and shutdown procedures, bootstrapping DB tables."""
    logger.info("Initializing Gateway startup operations...")
    
    # Auto-bootstrap DB tables for seamless run out-of-the-box
    try:
        async with async_engine.begin() as conn:
            logger.info("Connecting to database engine to bootstrap tables...")
            # Automatically imports and maps shared schemas/models
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables successfully bootstrapped!")
    except Exception as e:
        logger.error(f"Error during startup database bootstrapping: {e}")
        
    yield
    logger.info("Shutting down Gateway operations...")

# Initialize FastAPI App
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Text-to-2D floorplans and 3D architectural asset generation backend.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Policy configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Sub-Routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(generate.router)
app.include_router(files.router)

class CustomStaticFiles(StaticFiles):
    def get_mime_type(self, path: str) -> str:
        if path.endswith(".glb"):
            return "model/gltf-binary"
        elif path.endswith(".gltf"):
            return "model/gltf+json"
        return super().get_mime_type(path)

# Mount outputs static directory for local downloads
try:
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    # Ensure nested subdirectories are present
    os.makedirs(os.path.join(settings.STORAGE_DIR, "floorplans"), exist_ok=True)
    os.makedirs(os.path.join(settings.STORAGE_DIR, "models3d"), exist_ok=True)
    os.makedirs(os.path.join(settings.STORAGE_DIR, "renders"), exist_ok=True)
    
    app.mount("/outputs", CustomStaticFiles(directory=settings.STORAGE_DIR), name="outputs")
    logger.info(f"Successfully mounted local static folder: {settings.STORAGE_DIR}")
except Exception as e:
    logger.error(f"Failed to mount local static folder: {e}")

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the premium, high-fidelity Nex AI Web Portal Dashboard."""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse(content="<h1>Nex AI Architectural Template Not Found!</h1>", status_code=404)

@app.get("/health")
async def gateway_health_check():
    """Endpoint for verifying server and internal configs are operational."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "debug_mode": settings.DEBUG,
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.api_gateway.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)

