"""
Project management routes: CRUD for projects, roadmaps, and tasks.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import PaginationParams, get_current_user
from app.models.idea import GeneratedIdea
from app.models.project import Project, Roadmap, Task
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    RoadmapGenerateRequest,
    RoadmapResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.services import ai_service

router = APIRouter(prefix="/projects", tags=["Projects"])
logger = logging.getLogger(__name__)


# ── Projects CRUD ─────────────────────────────────────────────────────────────

@router.get("", response_model=ProjectListResponse)
async def list_projects(
    current_user: User = Depends(get_current_user),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    total = (
        db.query(func.count(Project.id))
        .filter(Project.owner_id == current_user.id)
        .scalar()
    )
    items = (
        db.query(Project)
        .filter(Project.owner_id == current_user.id)
        .order_by(Project.updated_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
        .all()
    )
    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in items],
        total=total,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    generated_idea_id = _get_owned_generated_idea(
        payload.generated_idea_id, current_user.id, db
    )
    project = Project(
        owner_id=current_user.id,
        title=payload.title,
        description=payload.description,
        domain=payload.domain,
        tech_stack=json.dumps(payload.tech_stack or []),
        team_size=payload.team_size,
        budget=payload.budget,
        duration_weeks=payload.duration_weeks,
        generated_idea_id=generated_idea_id,
        is_public=payload.is_public,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_owned_project(project_id, current_user.id, db)
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_owned_project(project_id, current_user.id, db)

    if payload.title is not None:
        project.title = payload.title
    if payload.description is not None:
        project.description = payload.description
    if payload.domain is not None:
        project.domain = payload.domain
    if payload.status is not None:
        project.status = payload.status
    if payload.tech_stack is not None:
        project.tech_stack = json.dumps(payload.tech_stack)
    if payload.team_size is not None:
        project.team_size = payload.team_size
    if payload.budget is not None:
        project.budget = payload.budget
    if payload.duration_weeks is not None:
        project.duration_weeks = payload.duration_weeks
    if payload.is_public is not None:
        project.is_public = payload.is_public

    # Recalculate progress
    project.progress_pct = _calculate_progress(project, db)

    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_owned_project(project_id, current_user.id, db)
    db.delete(project)
    db.commit()


# ── Roadmaps ──────────────────────────────────────────────────────────────────

@router.post("/{project_id}/roadmap/generate", response_model=RoadmapResponse)
async def generate_roadmap(
    project_id: int,
    payload: RoadmapGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_owned_project(project_id, current_user.id, db)

    project_dict = {
        "title": project.title,
        "description": project.description or "",
        "domain": project.domain or "",
        "duration_weeks": project.duration_weeks or 4,
        "tech_stack": json.loads(project.tech_stack or "[]"),
        "team_size": project.team_size,
    }

    try:
        roadmap_data = await ai_service.generate_roadmap(project_dict)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    roadmap = Roadmap(
        project_id=project_id,
        title=payload.title or roadmap_data.get("title", f"{project.title} Roadmap"),
        description=payload.description or roadmap_data.get("description"),
        total_weeks=roadmap_data.get("total_weeks", project.duration_weeks or 4),
        technologies=json.dumps(roadmap_data.get("technologies", [])),
        learning_resources=json.dumps(roadmap_data.get("learning_resources", [])),
    )
    db.add(roadmap)
    db.flush()

    tasks_data = roadmap_data.get("tasks", [])
    for idx, task_dict in enumerate(tasks_data):
        task = Task(
            roadmap_id=roadmap.id,
            title=task_dict.get("title", f"Task {idx + 1}"),
            description=task_dict.get("description"),
            week_number=task_dict.get("week_number", 1),
            order_index=task_dict.get("order_index", idx),
            phase=task_dict.get("phase"),
            estimated_hours=task_dict.get("estimated_hours"),
            technologies=json.dumps(task_dict.get("technologies", [])),
            is_milestone=task_dict.get("is_milestone", False),
        )
        db.add(task)

    db.commit()
    db.refresh(roadmap)
    return RoadmapResponse.model_validate(roadmap)


@router.get("/roadmaps/{roadmap_id}", response_model=RoadmapResponse)
async def get_roadmap(
    roadmap_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    roadmap = db.get(Roadmap, roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    _get_owned_project(roadmap.project_id, current_user.id, db)
    return RoadmapResponse.model_validate(roadmap)


# ── Tasks ─────────────────────────────────────────────────────────────────────

@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    roadmap = db.get(Roadmap, payload.roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    _get_owned_project(roadmap.project_id, current_user.id, db)

    task = Task(
        roadmap_id=payload.roadmap_id,
        title=payload.title,
        description=payload.description,
        week_number=payload.week_number,
        order_index=payload.order_index,
        estimated_hours=payload.estimated_hours,
        phase=payload.phase,
        technologies=json.dumps(payload.technologies or []),
        is_milestone=payload.is_milestone,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return TaskResponse.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    roadmap = db.get(Roadmap, task.roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    _get_owned_project(roadmap.project_id, current_user.id, db)

    if payload.title is not None:
        task.title = payload.title
    if payload.description is not None:
        task.description = payload.description
    if payload.status is not None:
        task.status = payload.status
        if payload.status == "completed" and not task.completed_at:
            task.completed_at = datetime.now(timezone.utc)
        elif payload.status != "completed":
            task.completed_at = None
    if payload.week_number is not None:
        task.week_number = payload.week_number
    if payload.order_index is not None:
        task.order_index = payload.order_index
    if payload.estimated_hours is not None:
        task.estimated_hours = payload.estimated_hours
    if payload.phase is not None:
        task.phase = payload.phase
    if payload.is_milestone is not None:
        task.is_milestone = payload.is_milestone

    db.commit()

    # Update project progress
    project = db.get(Project, roadmap.project_id)
    if project:
        project.progress_pct = _calculate_progress(project, db)
        db.commit()

    db.refresh(task)
    return TaskResponse.model_validate(task)

    
@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Find task
    task = db.get(Task, task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Find roadmap
    roadmap = db.get(Roadmap, task.roadmap_id)

    if not roadmap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Roadmap not found"
        )

    # Verify project ownership
    project = _get_owned_project(
        roadmap.project_id,
        current_user.id,
        db
    )

    # Delete task
    db.delete(task)
    db.flush()

    # Recalculate project progress
    remaining_tasks = (
        db.query(Task)
        .join(Roadmap, Task.roadmap_id == Roadmap.id)
        .filter(Roadmap.project_id == project.id)
        .all()
    )

    total = len(remaining_tasks)
    completed = sum(
        task.status == "completed"
        for task in remaining_tasks
    )

    project.progress_pct = (
        round(completed / total * 100, 1) if total else 0.0
    )

    db.commit()   


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_owned_generated_idea(
    generated_idea_id: Optional[int], user_id: int, db: Session
) -> Optional[int]:
    if generated_idea_id is None:
        return None
    idea = db.get(GeneratedIdea, generated_idea_id)
    if not idea or idea.user_id != user_id:
        raise HTTPException(status_code=404, detail="Generated idea not found")
    return idea.id


def _get_owned_project(project_id: int, user_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this project",
        )
    return project


def _calculate_progress(project: Project, db: Session) -> float:
    """Calculate project completion percentage from task statuses."""
    total = 0
    completed = 0
    for roadmap in project.roadmaps:
        for task in roadmap.tasks:
            total += 1
            if task.status == "completed":
                completed += 1
    return round((completed / total * 100) if total > 0 else 0.0, 1)
