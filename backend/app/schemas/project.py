"""
Project, Roadmap, and Task Pydantic schemas.
"""
import json
from datetime import datetime
from typing import Any, List, Optional, Literal


from pydantic import BaseModel, Field, field_validator


def _parse_list(v: Any) -> Optional[List[str]]:
    if v is None:
        return None
    if isinstance(v, list):
        return v
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return []


# ── Task ──────────────────────────────────────────────────────────────────────

# ── Task ─────────────────────────────────────────────

class TaskCreate(BaseModel):
    roadmap_id: int = Field(gt=0)

    title: str = Field(min_length=1, max_length=200)

    description: Optional[str] = None

    status: Literal["todo", "in_progress", "completed", "skipped"] = "todo"

    week_number: int = Field(default=1, ge=1)

    order_index: int = Field(default=0, ge=0)

    estimated_hours: Optional[float] = Field(default=None, ge=0)

    phase: Optional[str] = None

    technologies: Optional[List[str]] = None

    is_milestone: bool = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Task title cannot be empty")
        return value


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)

    description: Optional[str] = None

    status: Optional[
        Literal["todo", "in_progress", "completed", "skipped"]
    ] = None

    week_number: Optional[int] = Field(default=None, ge=1)

    order_index: Optional[int] = Field(default=None, ge=0)

    estimated_hours: Optional[float] = Field(default=None, ge=0)

    phase: Optional[str] = None

    is_milestone: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("Task title cannot be empty")
        return value

class TaskResponse(BaseModel):
    id: int
    roadmap_id: int
    title: str
    description: Optional[str]
    week_number: int
    order_index: int
    status: str
    estimated_hours: Optional[float]
    phase: Optional[str]
    technologies: Optional[List[str]]
    is_milestone: bool
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("technologies", mode="before")
    @classmethod
    def parse_tech(cls, v: Any) -> Optional[List[str]]:
        return _parse_list(v)


# ── Roadmap ───────────────────────────────────────────────────────────────────

class RoadmapGenerateRequest(BaseModel):
    project_id: int
    title: Optional[str] = None
    description: Optional[str] = None


class RoadmapResponse(BaseModel):
    id: int
    project_id: int
    title: str
    description: Optional[str]
    total_weeks: int
    technologies: Optional[List[str]]
    learning_resources: Optional[List[str]]
    tasks: List[TaskResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("technologies", "learning_resources", mode="before")
    @classmethod
    def parse_lists(cls, v: Any) -> Optional[List[str]]:
        return _parse_list(v)


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    domain: Optional[str] = None
    tech_stack: Optional[List[str]] = None
    team_size: int = 1
    budget: Optional[str] = None
    duration_weeks: Optional[int] = None
    generated_idea_id: Optional[int] = None
    is_public: bool = False


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)

    description: Optional[str] = None

    domain: Optional[str] = None

    status: Optional[str] = None

    tech_stack: Optional[List[str]] = None

    team_size: Optional[int] = Field(default=None, ge=1)

    budget: Optional[str] = None

    duration_weeks: Optional[int] = Field(default=None, ge=1)

    is_public: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("Project title cannot be empty")
        return value


class ProjectResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    domain: Optional[str]
    status: str
    tech_stack: Optional[List[str]]
    team_size: int
    budget: Optional[str]
    duration_weeks: Optional[int]
    progress_pct: float
    is_public: bool
    generated_idea_id: Optional[int]
    roadmaps: List[RoadmapResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("tech_stack", mode="before")
    @classmethod
    def parse_tech(cls, v: Any) -> Optional[List[str]]:
        return _parse_list(v)


class ProjectListResponse(BaseModel):
    items: List[ProjectResponse]
    total: int
