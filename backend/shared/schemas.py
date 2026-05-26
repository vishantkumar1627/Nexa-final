from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

# ==========================================
# AUTHENTICATION & USER SCHEMAS
# ==========================================

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters long")

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None

class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ==========================================
# PROJECT SCHEMAS
# ==========================================

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    prompt: str = Field(..., min_length=5, description="Natural language prompt for floor plan generation")
    style: str = Field("modern", description="Architectural style, e.g. modern, minimalist, classic, scandinavian")

class ProjectOut(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    prompt: str
    style: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ==========================================
# AI GENERATION SCHEMAS
# ==========================================

class GenerateRequest(BaseModel):
    project_id: UUID
    prompt: Optional[str] = None
    style: Optional[str] = None

class JobStatusResponse(BaseModel):
    id: UUID
    project_id: UUID
    status: str
    progress_percent: int
    current_stage: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ==========================================
# RESOURCE OUT SCHEMAS
# ==========================================

class FloorPlanOut(BaseModel):
    id: UUID
    project_id: UUID
    image_url: Optional[str] = None
    vector_svg_url: Optional[str] = None
    vector_dxf_url: Optional[str] = None
    room_layout_json: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class RenderOutputOut(BaseModel):
    id: UUID
    model_3d_id: UUID
    image_url: str
    view_type: str
    created_at: datetime

    class Config:
        from_attributes = True

class Model3DOut(BaseModel):
    id: UUID
    project_id: UUID
    gltf_url: Optional[str] = None
    obj_url: Optional[str] = None
    blend_url: Optional[str] = None
    renders: List[RenderOutputOut] = []
    created_at: datetime

    class Config:
        from_attributes = True

# ==========================================
# API KEYS & WEBSOCKETS
# ==========================================

class APIKeyCreate(BaseModel):
    name: str = Field("Default API Key", max_length=50)

class APIKeyOut(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True

class APIKeyFullOut(APIKeyOut):
    key: str  # Plain-text API key (only returned once upon creation)

class ProjectDetailsOut(BaseModel):
    id: UUID
    name: str
    prompt: str
    style: str
    created_at: datetime
    floorplans: List[FloorPlanOut] = []
    models_3d: List[Model3DOut] = []

    class Config:
        from_attributes = True

