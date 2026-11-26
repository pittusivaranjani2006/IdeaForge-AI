"""
Idea-related ORM models: Category, Idea, SavedIdea, GeneratedIdea, IdeaEvaluation.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # emoji
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ideas: Mapped[List["Idea"]] = relationship("Idea", back_populates="category")


class Idea(Base):
    """
    Curated/seeded problem statements (the existing 26 problems + future ones).
    These are platform-managed, not user-generated.
    """
    __tablename__ = "ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False)  # Easy/Medium/Hard
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    short_description: Mapped[str] = mapped_column(Text, nullable=False)
    full_description: Mapped[str] = mapped_column(Text, nullable=False)
    relevance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    problem_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    tech_stack: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    implementation_steps: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    future_enhancements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    popularity_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="ideas")
    saved_by: Mapped[List["SavedIdea"]] = relationship("SavedIdea", back_populates="idea")
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="idea")  # type: ignore[name-defined]

    __table_args__ = (
        Index("ix_ideas_domain_difficulty", "domain", "difficulty"),
    )


class SavedIdea(Base):
    """Tracks which ideas a user has saved/bookmarked."""
    __tablename__ = "saved_ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idea_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="saved_ideas")  # type: ignore[name-defined]
    idea: Mapped["Idea"] = relationship("Idea", back_populates="saved_by")

    __table_args__ = (
        UniqueConstraint("user_id", "idea_id", name="uq_saved_ideas_user_idea"),
        Index("ix_saved_ideas_user_id", "user_id"),
    )


class GeneratedIdea(Base):
    """
    AI-generated project ideas personalised per user request.
    Persisted so users can revisit them from the workspace.
    """
    __tablename__ = "generated_ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Rich content fields
    problem_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposed_solution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    innovation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    real_world_applications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tech_stack: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    implementation_roadmap: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    expected_outcomes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    future_enhancements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    # Input parameters stored for context
    input_params: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="generated_ideas")  # type: ignore[name-defined]
    evaluation: Mapped[Optional["IdeaEvaluation"]] = relationship(
        "IdeaEvaluation",
        back_populates="generated_idea",
        foreign_keys="IdeaEvaluation.generated_idea_id",
        uselist=False,
    )

    __table_args__ = (
        Index("ix_generated_ideas_user_id", "user_id"),
    )


class IdeaEvaluation(Base):
    """AI evaluation scores and feedback for a user-submitted or generated idea."""
    __tablename__ = "idea_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Either a generated idea or a free-form user description
    generated_idea_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("generated_ideas.id", ondelete="SET NULL"), nullable=True
    )
    idea_title: Mapped[str] = mapped_column(String(255), nullable=False)
    idea_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Scores out of 100
    innovation_score: Mapped[float] = mapped_column(Float, nullable=False)
    feasibility_score: Mapped[float] = mapped_column(Float, nullable=False)
    technical_complexity_score: Mapped[float] = mapped_column(Float, nullable=False)
    social_impact_score: Mapped[float] = mapped_column(Float, nullable=False)
    scalability_score: Mapped[float] = mapped_column(Float, nullable=False)
    cost_effectiveness_score: Mapped[float] = mapped_column(Float, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Qualitative feedback (JSON arrays / text)
    strengths: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weaknesses: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    missing_features: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    technical_challenges: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    improvement_suggestions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    potential_risks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    similar_solutions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_disclaimer: Mapped[str] = mapped_column(
        Text,
        default="Scores are AI-generated estimates based on the provided description. Conduct your own market research before making decisions.",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="evaluations")  # type: ignore[name-defined]
    generated_idea: Mapped[Optional["GeneratedIdea"]] = relationship(
        "GeneratedIdea", back_populates="evaluation", foreign_keys=[generated_idea_id]
    )

    __table_args__ = (
        Index("ix_idea_evaluations_user_id", "user_id"),
    )
