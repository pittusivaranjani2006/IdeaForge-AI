"""
Community Pydantic schemas.
"""
import json
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, field_validator


def _parse_list(v: Any) -> Optional[List[str]]:
    if v is None:
        return None
    if isinstance(v, list):
        return v
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return []


# ── Post ──────────────────────────────────────────────────────────────────────

class PostCreate(BaseModel):
    title: str
    content: str
    post_type: str = "discussion"
    tags: Optional[List[str]] = None
    idea_id: Optional[int] = None


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None


class AuthorResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class PostResponse(BaseModel):
    id: int
    author: AuthorResponse
    title: str
    content: str
    post_type: str
    tags: Optional[List[str]]
    idea_id: Optional[int]
    view_count: int
    like_count: int
    comment_count: int
    is_liked: bool = False  # populated at route level
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v: Any) -> Optional[List[str]]:
        return _parse_list(v)


class PostListResponse(BaseModel):
    items: List[PostResponse]
    total: int
    page: int
    page_size: int


# ── Comment ───────────────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    post_id: int
    content: str
    parent_id: Optional[int] = None


class CommentResponse(BaseModel):
    id: int
    post_id: int
    author: AuthorResponse
    content: str
    parent_id: Optional[int]
    like_count: int
    replies: List["CommentResponse"] = []
    created_at: datetime

    model_config = {"from_attributes": True}


CommentResponse.model_rebuild()


# ── Like ──────────────────────────────────────────────────────────────────────

class LikeRequest(BaseModel):
    target_type: str  # post | comment
    target_id: int


class LikeResponse(BaseModel):
    liked: bool
    like_count: int


# ── Notification ──────────────────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    link: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
