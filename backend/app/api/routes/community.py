"""
Community routes: posts, comments, likes.
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import PaginationParams, get_current_user, get_current_user_optional
from app.models.community import Comment, Like, Notification, Post, PostReport
from app.models.user import User
from app.schemas.community import (
    CommentCreate,
    CommentResponse,
    LikeRequest,
    LikeResponse,
    NotificationResponse,
    PostCreate,
    PostListResponse,
    PostResponse,
    PostUpdate,
)

router = APIRouter(prefix="/community", tags=["Community"])
logger = logging.getLogger(__name__)


# ── Posts ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=PostListResponse, summary="List community posts")
async def list_posts(
    post_type: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
 sort: str = Query("latest", pattern="^(latest|popular)$"),
    pagination: PaginationParams = Depends(),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    query = db.query(Post).filter(Post.is_published == True)  # noqa: E712

    if post_type:
        query = query.filter(Post.post_type == post_type)
    if q:
        query = query.filter(Post.title.ilike(f"%{q}%") | Post.content.ilike(f"%{q}%"))

    total = query.count()

    if sort == "popular":
        query = query.order_by(Post.like_count.desc(), Post.view_count.desc())
    else:
        query = query.order_by(Post.created_at.desc())

    posts = query.offset(pagination.offset).limit(pagination.page_size).all()

    # Determine likes for current user
    liked_ids: set[int] = set()
    if current_user:
        likes = (
            db.query(Like.target_id)
            .filter(
                Like.user_id == current_user.id,
                Like.target_type == "post",
                Like.target_id.in_([p.id for p in posts]),
            )
            .all()
        )
        liked_ids = {r.target_id for r in likes}

    result = []
    for post in posts:
        resp = PostResponse.model_validate(post)
        resp.is_liked = post.id in liked_ids
        result.append(resp)

    return PostListResponse(
        items=result, total=total, page=pagination.page, page_size=pagination.page_size
    )


@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = Post(
        author_id=current_user.id,
        title=payload.title,
        content=payload.content,
        post_type=payload.post_type,
        tags=json.dumps(payload.tags or []),
        idea_id=payload.idea_id,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    resp = PostResponse.model_validate(post)
    resp.is_liked = False
    return resp


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)
    if not post or not post.is_published:
        raise HTTPException(status_code=404, detail="Post not found")

    post.view_count = (post.view_count or 0) + 1
    db.commit()

    resp = PostResponse.model_validate(post)
    if current_user:
        liked = (
            db.query(Like)
            .filter(
                Like.user_id == current_user.id,
                Like.target_type == "post",
                Like.target_id == post_id,
            )
            .first()
        )
        resp.is_liked = liked is not None
    return resp


@router.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: int,
    payload: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = _get_owned_post(post_id, current_user.id, db)
    if payload.title is not None:
        post.title = payload.title
    if payload.content is not None:
        post.content = payload.content
    if payload.tags is not None:
        post.tags = json.dumps(payload.tags)
    db.commit()
    db.refresh(post)
    resp = PostResponse.model_validate(post)
    resp.is_liked = False
    return resp


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = _get_owned_post(post_id, current_user.id, db)
    db.delete(post)
    db.commit()


@router.post("/posts/{post_id}/report", status_code=status.HTTP_200_OK)
async def report_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)
    if not post or not post.is_published:
        raise HTTPException(status_code=404, detail="Post not found")

    existing = (
        db.query(PostReport)
        .filter(
            PostReport.post_id == post_id,
            PostReport.reporter_id == current_user.id,
        )
        .first()
    )
    if not existing:
        db.add(PostReport(post_id=post_id, reporter_id=current_user.id))
        db.commit()
    return {"message": "Post reported for review"}


# ── Comments ──────────────────────────────────────────────────────────────────

@router.get("/posts/{post_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    post_id: int,
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)
    if not post or not post.is_published:
        raise HTTPException(status_code=404, detail="Post not found")

    # Return only top-level comments; replies are nested via relationship
    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post_id, Comment.parent_id == None)  # noqa: E711
        .order_by(Comment.created_at)
        .all()
    )
    return [CommentResponse.model_validate(c) for c in comments]


@router.post("/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.get(Post, payload.post_id)
    if not post or not post.is_published:
        raise HTTPException(status_code=404, detail="Post not found")

    if payload.parent_id is not None:
        parent = db.get(Comment, payload.parent_id)
        if not parent or parent.post_id != payload.post_id:
            raise HTTPException(status_code=404, detail="Parent comment not found")

    comment = Comment(
        post_id=payload.post_id,
        author_id=current_user.id,
        content=payload.content,
        parent_id=payload.parent_id,
    )
    db.add(comment)

    # Update comment count
    post.comment_count = (post.comment_count or 0) + 1

    # Notify post author if someone else commented
    if post.author_id != current_user.id:
        notif = Notification(
            user_id=post.author_id,
            title="New comment on your post",
            message=f"{current_user.name} commented on '{post.title}'",
            notification_type="comment",
            link=f"/community/posts/{post.id}",
        )
        db.add(notif)

    db.commit()
    db.refresh(comment)
    return CommentResponse.model_validate(comment)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your comment")

    post = db.get(Post, comment.post_id)
    if post:
        post.comment_count = max(0, (post.comment_count or 1) - 1)

    db.delete(comment)
    db.commit()


# ── Likes ─────────────────────────────────────────────────────────────────────

@router.post("/likes", response_model=LikeResponse)
async def toggle_like(
    payload: LikeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.target_type not in ("post", "comment"):
        raise HTTPException(status_code=400, detail="target_type must be 'post' or 'comment'")

    if payload.target_type == "post":
        post = db.get(Post, payload.target_id)
        if not post or not post.is_published:
            raise HTTPException(status_code=404, detail="Post not found")
    else:
        comment = db.get(Comment, payload.target_id)
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        post = db.get(Post, comment.post_id)
        if not post or not post.is_published:
            raise HTTPException(status_code=404, detail="Comment not found")

    existing = (
        db.query(Like)
        .filter(
            Like.user_id == current_user.id,
            Like.target_type == payload.target_type,
            Like.target_id == payload.target_id,
        )
        .first()
    )

    if existing:
        db.delete(existing)
        _update_like_count(payload.target_type, payload.target_id, -1, db)
        db.commit()
        new_count = _get_like_count(payload.target_type, payload.target_id, db)
        return LikeResponse(liked=False, like_count=new_count)

    db.add(Like(
        user_id=current_user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
    ))
    _update_like_count(payload.target_type, payload.target_id, +1, db)

    # Notify owner
    _notify_like(payload.target_type, payload.target_id, current_user, db)

    db.commit()
    new_count = _get_like_count(payload.target_type, payload.target_id, db)
    return LikeResponse(liked=True, like_count=new_count)


# ── Notifications ─────────────────────────────────────────────────────────────

@router.get("/notifications", response_model=list[NotificationResponse])
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notifs = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return [NotificationResponse.model_validate(n) for n in notifs]


@router.post("/notifications/read-all", status_code=200)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.is_read == False  # noqa: E712
    ).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_owned_post(post_id: int, user_id: int, db: Session) -> Post:
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != user_id:
        raise HTTPException(status_code=403, detail="Not your post")
    return post


def _update_like_count(target_type: str, target_id: int, delta: int, db: Session):
    if target_type == "post":
        post = db.get(Post, target_id)
        if post:
            post.like_count = max(0, (post.like_count or 0) + delta)
    elif target_type == "comment":
        comment = db.get(Comment, target_id)
        if comment:
            comment.like_count = max(0, (comment.like_count or 0) + delta)


def _get_like_count(target_type: str, target_id: int, db: Session) -> int:
    if target_type == "post":
        post = db.get(Post, target_id)
        return post.like_count if post else 0
    comment = db.get(Comment, target_id)
    return comment.like_count if comment else 0


def _notify_like(target_type: str, target_id: int, liker: User, db: Session):
    try:
        if target_type == "post":
            post = db.get(Post, target_id)
            if post and post.author_id != liker.id:
                db.add(Notification(
                    user_id=post.author_id,
                    title="Someone liked your post",
                    message=f"{liker.name} liked '{post.title}'",
                    notification_type="like",
                    link=f"/community/posts/{post.id}",
                ))
    except Exception:
        pass  # Notifications are non-critical
