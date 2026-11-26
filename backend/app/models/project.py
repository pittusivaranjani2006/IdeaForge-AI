"""
Project, Roadmap, and Task ORM models.
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Optionally linked to a generated idea
    generated_idea_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("generated_ideas.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="planning", nullable=False
    )  # planning | active | completed | paused | cancelled
    tech_stack: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    team_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    budget: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration_weeks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    owner: Mapped["User"] = relationship("User", back_populates="projects")  # type: ignore[name-defined]
    roadmaps: Mapped[List["Roadmap"]] = relationship(
        "Roadmap", back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_projects_owner_id", "owner_id"),
    )


class Roadmap(Base):
    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_weeks: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    technologies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    learning_resources: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    project: Mapped["Project"] = relationship("Project", back_populates="roadmaps")
    tasks: Mapped[List["Task"]] = relationship(
        "Task", back_populates="roadmap", cascade="all, delete-orphan",
        order_by="Task.week_number, Task.order_index",
    )

    __table_args__ = (
        Index("ix_roadmaps_project_id", "project_id"),
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    roadmap_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    week_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="todo", nullable=False
    )  # todo | in_progress | completed | skipped
    estimated_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    phase: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dependencies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of task IDs
    technologies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    is_milestone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    roadmap: Mapped["Roadmap"] = relationship("Roadmap", back_populates="tasks")

    __table_args__ = (
        Index("ix_tasks_roadmap_id", "roadmap_id"),
    )
