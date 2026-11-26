"""
AI routes: chat, tech stack recommender, recommendations.
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.chat import ChatMessage
from app.models.idea import GeneratedIdea, Idea
from app.models.project import Project
from app.models.user import User
from app.schemas.ai import (
    ChatRequest,
    ChatResponse,
    RecommendationRequest,
    RecommendationResponse,
    TechStackRequest,
    TechStackResponse,
)
from app.schemas.idea import IdeaResponse
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["AI"])
logger = logging.getLogger(__name__)


# ── AI Mentor Chat ────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Build context strings
    project_context: Optional[str] = None
    idea_context: Optional[str] = None
    persisted_project_id: Optional[int] = None
    persisted_idea_id: Optional[int] = None

    if payload.project_id:
        project = db.get(Project, payload.project_id)
        if project and project.owner_id == current_user.id:
            persisted_project_id = project.id
            tech = json.loads(project.tech_stack or "[]")
            project_context = (
                f"Project: {project.title}\n"
                f"Description: {project.description or 'N/A'}\n"
                f"Domain: {project.domain or 'N/A'}\n"
                f"Tech Stack: {', '.join(tech)}\n"
                f"Status: {project.status}\n"
                f"Progress: {project.progress_pct}%"
            )

    if payload.idea_id:
        idea = db.get(GeneratedIdea, payload.idea_id)
        if idea and idea.user_id == current_user.id:
            persisted_idea_id = idea.id
            idea_context = (
                f"Idea: {idea.title}\n"
                f"Domain: {idea.domain}\n"
                f"Problem: {idea.problem_statement or 'N/A'}\n"
                f"Solution: {idea.proposed_solution or 'N/A'}\n"
                f"Tech: {idea.tech_stack or 'N/A'}"
            )

    # Fetch recent chat history (last 10 messages)
    history_records = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
        .all()
    )
    history = [
        {"role": r.role, "content": r.content}
        for r in reversed(history_records)
    ]

    try:
        reply, tokens = await ai_service.mentor_chat(
            payload.message,
            history,
            project_context=project_context,
            idea_context=idea_context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Persist both messages
    db.add(ChatMessage(
        user_id=current_user.id,
        project_id=persisted_project_id,
        idea_id=persisted_idea_id,
        role="user",
        content=payload.message,
    ))
    db.add(ChatMessage(
        user_id=current_user.id,
        project_id=persisted_project_id,
        idea_id=persisted_idea_id,
        role="assistant",
        content=reply,
        tokens_used=tokens,
    ))
    db.commit()

    return ChatResponse(reply=reply, tokens_used=tokens)


# ── Tech Stack Recommender ─────────────────────────────────────────────────────

@router.post("/tech-stack", response_model=TechStackResponse)
async def recommend_tech_stack(
    payload: TechStackRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        result = await ai_service.recommend_tech_stack(
            description=payload.project_description,
            domain=payload.domain or "",
            team_size=payload.team_size or 1,
            experience_level=payload.experience_level,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return TechStackResponse(
        recommendations=result.get("recommendations", []),
        summary=result.get("summary", ""),
    )


# ── AI Recommendations ─────────────────────────────────────────────────────────

@router.post("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    payload: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Build user context from profile and history
    profile = current_user.profile
    interests: list[str] = []
    if profile and profile.interests:
        try:
            interests = json.loads(profile.interests)
        except (json.JSONDecodeError, TypeError):
            interests = []

    # Domains from saved ideas
    from app.models.idea import SavedIdea
    saved = (
        db.query(Idea.domain)
        .join(SavedIdea, Idea.id == SavedIdea.idea_id)
        .filter(SavedIdea.user_id == current_user.id)
        .distinct()
        .all()
    )
    saved_domains = [r.domain for r in saved]

    # Recently generated idea titles
    recent_generated = (
        db.query(GeneratedIdea.title)
        .filter(GeneratedIdea.user_id == current_user.id)
        .order_by(GeneratedIdea.created_at.desc())
        .limit(5)
        .all()
    )
    viewed_titles = [r.title for r in recent_generated]

    # All published ideas as candidates
    all_ideas = db.query(Idea).filter(Idea.is_published == True).all()  # noqa: E712
    ideas_dicts = [
        {
            "id": i.id,
            "title": i.title,
            "domain": i.domain,
            "difficulty": i.difficulty,
            "short_description": i.short_description,
        }
        for i in all_ideas
    ]

    result = await ai_service.generate_recommendations(
        user_interests=interests,
        saved_domains=saved_domains,
        viewed_titles=viewed_titles,
        all_ideas=ideas_dicts,
        limit=payload.limit,
    )

    return RecommendationResponse(
        ideas=result.get("ideas", []),
        rationale=result.get("rationale", ""),
    )
