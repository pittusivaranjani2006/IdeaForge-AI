"""
Idea-related Pydantic schemas.
"""
import json
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, field_validator


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_json_field(v: Any) -> Optional[List[str]]:
    """Parse a JSON-encoded list field stored as text."""
    if v is None:
        return None
    if isinstance(v, list):
        return v
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return []


# ── Curated Idea (Problem Statement) ─────────────────────────────────────────

class IdeaResponse(BaseModel):
    id: int
    slug: str
    title: str
    domain: str
    difficulty: str
    short_description: str
    full_description: str
    relevance: Optional[str]
    problem_statement: Optional[str]
    tags: Optional[List[str]]
    tech_stack: Optional[List[str]]
    implementation_steps: Optional[List[str]]
    future_enhancements: Optional[List[str]]
    popularity_score: int
    is_saved: bool = False  # populated at the route level
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("tags", "tech_stack", "implementation_steps", "future_enhancements", mode="before")
    @classmethod
    def parse_list_fields(cls, v: Any) -> Optional[List[str]]:
        return _parse_json_field(v)


class IdeaListResponse(BaseModel):
    items: List[IdeaResponse]
    total: int
    page: int
    page_size: int


# ── Generated Idea ────────────────────────────────────────────────────────────

class GenerateIdeaRequest(BaseModel):
    domain: str
    difficulty: str
    category: Optional[str] = None
    budget: Optional[str] = None
    team_size: Optional[int] = None
    preferred_language: Optional[str] = None
    duration_weeks: Optional[int] = None
    purpose: str = "Mini Project"  # Mini Project | Major Project | Hackathon | Startup
    count: int = 5

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: int) -> int:
        return max(1, min(v, 10))


class GeneratedIdeaResponse(BaseModel):
    id: int
    title: str
    domain: str
    difficulty: str
    category: Optional[str]
    purpose: Optional[str]
    problem_statement: Optional[str]
    proposed_solution: Optional[str]
    innovation: Optional[str]
    real_world_applications: Optional[str]
    target_audience: Optional[str]
    tech_stack: Optional[List[str]]
    requirements: Optional[List[str]]
    implementation_roadmap: Optional[List[str]]
    expected_outcomes: Optional[str]
    future_enhancements: Optional[List[str]]
    is_saved: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator(
        "tech_stack", "requirements", "implementation_roadmap", "future_enhancements",
        mode="before",
    )
    @classmethod
    def parse_list_fields(cls, v: Any) -> Optional[List[str]]:
        return _parse_json_field(v)


class GeneratedIdeasListResponse(BaseModel):
    items: List[GeneratedIdeaResponse]
    total: int


# ── Idea Evaluation ───────────────────────────────────────────────────────────

class EvaluateIdeaRequest(BaseModel):
    title: str
    description: str
    generated_idea_id: Optional[int] = None


class IdeaEvaluationResponse(BaseModel):
    id: int
    idea_title: str
    innovation_score: float
    feasibility_score: float
    technical_complexity_score: float
    social_impact_score: float
    scalability_score: float
    cost_effectiveness_score: float
    overall_score: float
    strengths: Optional[List[str]]
    weaknesses: Optional[List[str]]
    missing_features: Optional[List[str]]
    technical_challenges: Optional[List[str]]
    improvement_suggestions: Optional[List[str]]
    potential_risks: Optional[List[str]]
    similar_solutions: Optional[List[str]]
    ai_disclaimer: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator(
        "strengths", "weaknesses", "missing_features", "technical_challenges",
        "improvement_suggestions", "potential_risks", "similar_solutions",
        mode="before",
    )
    @classmethod
    def parse_list_fields(cls, v: Any) -> Optional[List[str]]:
        return _parse_json_field(v)


# ── Save Response ─────────────────────────────────────────────────────────────

class SaveStatusResponse(BaseModel):
    saved: bool
    message: str
