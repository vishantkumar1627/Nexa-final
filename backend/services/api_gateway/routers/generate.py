import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_async_db
from shared.models import User, Project, GenerationJob
from shared.schemas import GenerateRequest, JobStatusResponse
from shared.security import get_current_user
from workers.tasks import execute_architecture_pipeline

router = APIRouter(prefix="/generate", tags=["AI Generation"])

@router.post("/floorplan", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def generate_architecture_pipeline(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Triggers the full Text-to-2D floorplan and 3D Model Celery pipeline asynchronously."""
    # 1. Verify target project exists and belongs to current user
    result = await db.execute(
        select(Project).filter(Project.id == req.project_id, Project.user_id == current_user.id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied."
        )

    # 2. Check if a job is already processing to prevent double queues
    job_check = await db.execute(
        select(GenerationJob)
        .filter(GenerationJob.project_id == req.project_id, GenerationJob.status == "PROCESSING")
    )
    existing_job = job_check.scalars().first()
    if existing_job:
        return {
            "message": "A generation pipeline is already running for this project.",
            "job_id": existing_job.id,
            "status": existing_job.status
        }

    # 3. Create Generation Job row
    new_job = GenerationJob(
        project_id=project.id,
        status="PENDING",
        progress_percent=0,
        current_stage="Queue Enqueued"
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    # 4. Trigger Asynchronous Job
    # Check if Redis is online to choose between Celery and native BackgroundTasks
    try:
        import redis
        from shared.config import settings
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        r.ping()
        # Redis is online, run via Celery worker
        execute_architecture_pipeline.delay(str(new_job.id))
        print("Enqueued pipeline task in Celery worker.")
    except Exception as e:
        # Redis is offline! Fall back to running natively in FastAPI BackgroundTasks thread pool
        print(f"Redis is offline/unavailable ({e}). Running task natively inside FastAPI BackgroundTasks!")
        background_tasks.add_task(execute_architecture_pipeline, str(new_job.id))

    return {
        "message": "AI Text-to-3D Generation pipeline successfully enqueued.",
        "job_id": new_job.id,
        "status": "PENDING"
    }

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_generation_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Poll the status, progress percent, and current processing stage of a running job."""
    result = await db.execute(
        select(GenerationJob).filter(GenerationJob.id == job_id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation job not found."
        )
        
    # Verify owner of the project associated with the job
    proj_result = await db.execute(
        select(Project).filter(Project.id == job.project_id, Project.user_id == current_user.id)
    )
    project = proj_result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to job records denied."
        )

    return job
