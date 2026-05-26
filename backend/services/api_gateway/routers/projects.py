import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.database import get_async_db
from shared.models import User, Project, FloorPlan, Model3D
from shared.schemas import ProjectCreate, ProjectOut, ProjectDetailsOut
from shared.security import get_current_user

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.post("/create", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate, 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Creates a new architectural project with text prompt guidelines."""
    new_project = Project(
        user_id=current_user.id,
        name=project_in.name,
        prompt=project_in.prompt,
        style=project_in.style
    )
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    return new_project

@router.get("/", response_model=List[ProjectOut])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Fetch all architectural projects belonging to the active user."""
    result = await db.execute(
        select(Project)
        .filter(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    return result.scalars().all()

@router.get("/{project_id}", response_model=ProjectDetailsOut)
async def get_project_details(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieves deep-dive layout metrics and all linked visual/3D assets for a project."""
    # Query project and eagerly load nested floorplans and 3D models + renders
    result = await db.execute(
        select(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .options(
            selectinload(Project.floorplans),
            selectinload(Project.models_3d).selectinload(Model3D.renders)
        )
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied."
        )

    return project

