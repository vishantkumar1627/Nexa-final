import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from shared.config import settings
from services.storage_service import storage_service

router = APIRouter(prefix="/download", tags=["File Downloader"])

@router.get("/{folder}/{filename}")
async def download_file(folder: str, filename: str):
    """Safely retrieves generated architectural assets (PNG, SVG, DXF, GLTF, OBJ, BLEND)."""
    # 1. Directory traversal validation (Local File Inclusion protection)
    allowed_folders = ["floorplans", "models3d", "renders"]
    if folder not in allowed_folders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid folder category. Allowed: {allowed_folders}"
        )

    # 2. Get sanitized local path
    local_path = storage_service.get_local_path(folder, filename)
    
    # 3. Ensure the file actually exists
    if not local_path.exists() or not local_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested file does not exist in storage."
        )

    # 4. Resolve absolute paths to ensure LFI prevention
    storage_base_resolved = Path(settings.STORAGE_DIR).resolve()
    file_path_resolved = local_path.resolve()
    
    if not str(file_path_resolved).startswith(str(storage_base_resolved)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Directory traversal path detected."
        )

    # 5. Determine correct MIME Type for smooth client downloads
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".dxf": "application/dxf",
        ".gltf": "model/gltf+json",
        ".glb": "model/gltf-binary",
        ".obj": "model/obj",
        ".blend": "application/x-blender"
    }
    
    ext = local_path.suffix.lower()
    media_type = mime_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=local_path,
        media_type=media_type,
        filename=filename
    )
