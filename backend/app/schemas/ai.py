"""
AI service request / response schemas.
"""
from typing import List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    project_id: Optional[int] = None
    idea_id: Optional[int] = None


class ChatResponse(BaseModel):
    reply: str
    tokens_used: Optional[int] = None


class TechStackRequest(BaseModel):
    project_description: str
    domain: Optional[str] = None
    team_size: Optional[int] = None
    experience_level: str = "intermediate"


class TechCategory(BaseModel):
    category: str
    technologies: List[str]
    reason: str
    beginner_alternative: Optional[str] = None


class TechStackResponse(BaseModel):
    recommendations: List[TechCategory]
    summary: str
    disclaimer: str = "These recommendations are AI-generated based on the project description."


class RecommendationRequest(BaseModel):
    limit: int = 6


class RecommendationResponse(BaseModel):
    ideas: List[dict]
    rationale: str
