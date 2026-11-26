"""
Ideas routes: curated problems, AI generation, evaluation, save/unsave.
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import PaginationParams, get_current_user, get_current_user_optional
from app.models.idea import GeneratedIdea, Idea, IdeaEvaluation, SavedIdea
from app.models.user import User
from app.schemas.idea import (
    EvaluateIdeaRequest,
    GenerateIdeaRequest,
    GeneratedIdeasListResponse,
    GeneratedIdeaResponse,
    IdeaEvaluationResponse,
    IdeaListResponse,
    IdeaResponse,
    SaveStatusResponse,
)
from app.services import ai_service

router = APIRouter(prefix="/ideas", tags=["Ideas"])
logger = logging.getLogger(__name__)


# ── Curated Ideas (Problem Statements) ───────────────────────────────────────

@router.get("", response_model=IdeaListResponse, summary="List curated problem statements")
async def list_ideas(
    domain: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    sort: str = Query("popular", pattern="^(popular|latest)$"),
    pagination: PaginationParams = Depends(),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    query = db.query(Idea).filter(Idea.is_published == True)  # noqa: E712

    if domain:
        query = query.filter(Idea.domain == domain)
    if difficulty:
        query = query.filter(Idea.difficulty == difficulty)
    if q:
        query = query.filter(
            Idea.title.ilike(f"%{q}%") | Idea.tags.ilike(f"%{q}%")
        )

    total = query.count()

    if sort == "popular":
        query = query.order_by(Idea.popularity_score.desc())
    else:
        query = query.order_by(Idea.created_at.desc())

    items = query.offset(pagination.offset).limit(pagination.page_size).all()

    # Determine which are saved by the current user
    saved_ids: set[int] = set()
    if current_user:
        saved = (
            db.query(SavedIdea.idea_id)
            .filter(SavedIdea.user_id == current_user.id)
            .all()
        )
        saved_ids = {r.idea_id for r in saved}

    result = []
    for idea in items:
        resp = IdeaResponse.model_validate(idea)
        resp.is_saved = idea.id in saved_ids
        result.append(resp)

    return IdeaListResponse(
        items=result, total=total, page=pagination.page, page_size=pagination.page_size
    )


@router.get("/{idea_id}", response_model=IdeaResponse, summary="Get a single curated idea")
async def get_idea(
    idea_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    idea = db.get(Idea, idea_id)
    if not idea or not idea.is_published:
        raise HTTPException(status_code=404, detail="Idea not found")

    # Increment popularity
    idea.popularity_score = (idea.popularity_score or 0) + 1
    db.commit()

    resp = IdeaResponse.model_validate(idea)
    if current_user:
        saved = (
            db.query(SavedIdea)
            .filter(SavedIdea.user_id == current_user.id, SavedIdea.idea_id == idea.id)
            .first()
        )
        resp.is_saved = saved is not None
    return resp


# ── Save / Unsave ─────────────────────────────────────────────────────────────

@router.post("/{idea_id}/save", response_model=SaveStatusResponse)
async def save_idea(
    idea_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    idea = db.get(Idea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    existing = (
        db.query(SavedIdea)
        .filter(SavedIdea.user_id == current_user.id, SavedIdea.idea_id == idea_id)
        .first()
    )
    if existing:
        return SaveStatusResponse(saved=True, message="Already saved")

    db.add(SavedIdea(user_id=current_user.id, idea_id=idea_id))
    # Award points
    if current_user.profile:
        current_user.profile.points = (current_user.profile.points or 0) + 3
        _check_badges(current_user)
    db.commit()
    return SaveStatusResponse(saved=True, message="Idea saved successfully")


@router.delete("/{idea_id}/save", response_model=SaveStatusResponse)
async def unsave_idea(
    idea_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = (
        db.query(SavedIdea)
        .filter(SavedIdea.user_id == current_user.id, SavedIdea.idea_id == idea_id)
        .delete()
    )
    db.commit()
    if not deleted:
        return SaveStatusResponse(saved=False, message="Idea was not saved")
    return SaveStatusResponse(saved=False, message="Idea removed from saved")


# ── AI Idea Generation ────────────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=GeneratedIdeasListResponse,
    summary="Generate AI-powered project ideas",
)
async def generate_ideas(
    payload: GenerateIdeaRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        ideas_data = await ai_service.generate_ideas(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not ideas_data:
        raise HTTPException(
            status_code=503,
            detail="AI could not generate ideas at this time. Please try again.",
        )

    saved_records = []
    for idea_dict in ideas_data:
        record = GeneratedIdea(
            user_id=current_user.id,
            title=idea_dict.get("title", "Untitled Idea"),
            domain=payload.domain,
            difficulty=payload.difficulty,
            category=payload.category,
            purpose=payload.purpose,
            problem_statement=idea_dict.get("problem_statement"),
            proposed_solution=idea_dict.get("proposed_solution"),
            innovation=idea_dict.get("innovation"),
            real_world_applications=idea_dict.get("real_world_applications"),
            target_audience=idea_dict.get("target_audience"),
            tech_stack=json.dumps(idea_dict.get("tech_stack", [])),
            requirements=json.dumps(idea_dict.get("requirements", [])),
            implementation_roadmap=json.dumps(idea_dict.get("implementation_roadmap", [])),
            expected_outcomes=idea_dict.get("expected_outcomes"),
            future_enhancements=json.dumps(idea_dict.get("future_enhancements", [])),
            input_params=json.dumps(payload.model_dump()),
        )
        db.add(record)
        saved_records.append(record)

    # Award points for generation
    if current_user.profile:
        current_user.profile.points = (current_user.profile.points or 0) + 5
        _check_badges(current_user)

    db.commit()
    for r in saved_records:
        db.refresh(r)

    total = db.query(func.count(GeneratedIdea.id)).filter(
        GeneratedIdea.user_id == current_user.id
    ).scalar()

    return GeneratedIdeasListResponse(
        items=[GeneratedIdeaResponse.model_validate(r) for r in saved_records],
        total=total,
    )


# ── AI Idea Evaluation ────────────────────────────────────────────────────────

@router.post(
    "/evaluate",
    response_model=IdeaEvaluationResponse,
    summary="Evaluate a project idea with AI scoring",
)
async def evaluate_idea(
    payload: EvaluateIdeaRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    validated_generated_idea_id = _get_owned_generated_idea(
        payload.generated_idea_id, current_user.id, db
    )

    try:
        result = await ai_service.evaluate_idea(payload.title, payload.description)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    evaluation = IdeaEvaluation(
        user_id=current_user.id,
        generated_idea_id=validated_generated_idea_id,
        idea_title=payload.title,
        idea_description=payload.description,
        innovation_score=result.get("innovation_score", 50),
        feasibility_score=result.get("feasibility_score", 50),
        technical_complexity_score=result.get("technical_complexity_score", 50),
        social_impact_score=result.get("social_impact_score", 50),
        scalability_score=result.get("scalability_score", 50),
        cost_effectiveness_score=result.get("cost_effectiveness_score", 50),
        overall_score=result.get("overall_score", 50),
        strengths=json.dumps(result.get("strengths", [])),
        weaknesses=json.dumps(result.get("weaknesses", [])),
        missing_features=json.dumps(result.get("missing_features", [])),
        technical_challenges=json.dumps(result.get("technical_challenges", [])),
        improvement_suggestions=json.dumps(result.get("improvement_suggestions", [])),
        potential_risks=json.dumps(result.get("potential_risks", [])),
        similar_solutions=json.dumps(result.get("similar_solutions", [])),
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return IdeaEvaluationResponse.model_validate(evaluation)


# ── Generated Ideas (user's history) ─────────────────────────────────────────

@router.get(
    "/generated/my",
    response_model=GeneratedIdeasListResponse,
    summary="Get current user's generated idea history",
)
async def my_generated_ideas(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    pagination: PaginationParams = Depends(),
):
    total = (
        db.query(func.count(GeneratedIdea.id))
        .filter(GeneratedIdea.user_id == current_user.id)
        .scalar()
    )
    items = (
        db.query(GeneratedIdea)
        .filter(GeneratedIdea.user_id == current_user.id)
        .order_by(GeneratedIdea.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
        .all()
    )
    return GeneratedIdeasListResponse(
        items=[GeneratedIdeaResponse.model_validate(i) for i in items],
        total=total,
    )


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


def _check_badges(user: User) -> None:
    """Award badges based on points milestones."""
    if not user.profile:
        return
    pts = user.profile.points or 0
    badges: list = []
    try:
        badges = json.loads(user.profile.badges or "[]")
    except (json.JSONDecodeError, TypeError):
        badges = []

    if pts >= 30 and "Explorer" not in badges:
        badges.append("Explorer")
    if pts >= 70 and "Innovator" not in badges:
        badges.append("Innovator")
    if pts >= 150 and "Builder" not in badges:
        badges.append("Builder")

    user.profile.badges = json.dumps(badges)
