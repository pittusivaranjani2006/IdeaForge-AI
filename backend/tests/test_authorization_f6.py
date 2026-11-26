import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import ai as ai_routes
from app.api.routes import ideas as ideas_routes
from app.api.routes import projects as projects_routes
from app.core.database import Base, get_db
from app.core.dependencies import get_current_user, get_current_user_optional
from app.main import app
from app.models.chat import ChatMessage
from app.models.community import Comment, Like, Notification, Post, PostReport
from app.models.idea import GeneratedIdea, Idea, IdeaEvaluation, SavedIdea
from app.models.project import Project, Roadmap, Task
from app.models.user import User, UserProfile

TestEngine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=TestEngine,
    expire_on_commit=False,
)


def _yield_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _yield_user(user_id):
    def dependency():
        db = TestingSessionLocal()
        try:
            yield db.get(User, user_id)
        finally:
            db.close()

    return dependency


def _yield_none():
    def dependency():
        yield None

    return dependency


class AuthorizationRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=TestEngine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=TestEngine)
        TestEngine.dispose()

    def setUp(self):
        Base.metadata.drop_all(bind=TestEngine)
        Base.metadata.create_all(bind=TestEngine)
        self.client = TestClient(app, raise_server_exceptions=False)
        self._seed_data()
        app.dependency_overrides[get_db] = _yield_db
        self._as_user(self.user_a_id)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def _as_user(self, user_id):
        app.dependency_overrides[get_current_user] = _yield_user(user_id)
        app.dependency_overrides[get_current_user_optional] = _yield_user(user_id)

    def _as_anonymous(self):
        app.dependency_overrides[get_current_user] = _yield_none()
        app.dependency_overrides[get_current_user_optional] = _yield_none()

    def _create_user(self, db, email, name):
        user = User(
            email=email,
            hashed_password="test-hash",
            name=name,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.flush()
        db.add(
            UserProfile(
                user_id=user.id,
                interests=json.dumps(["web"]),
                points=0,
                badges=json.dumps([]),
            )
        )
        db.flush()
        return user

    def _seed_data(self):
        db = TestingSessionLocal()
        try:
            user_a = self._create_user(db, "authorization-a@example.test", "User A")
            user_b = self._create_user(db, "authorization-b@example.test", "User B")

            idea_a = Idea(
                slug="saved-by-a",
                title="Saved by A",
                domain="Web",
                difficulty="Easy",
                short_description="Published idea saved by A",
                full_description="Published idea saved by A",
                tags=json.dumps(["web"]),
                popularity_score=10,
                is_published=True,
            )
            idea_b = Idea(
                slug="saved-by-b",
                title="Saved by B",
                domain="Mobile",
                difficulty="Medium",
                short_description="Published idea saved by B",
                full_description="Published idea saved by B",
                tags=json.dumps(["mobile"]),
                popularity_score=9,
                is_published=True,
            )
            idea_hidden = Idea(
                slug="hidden-idea",
                title="Hidden Idea",
                domain="Web",
                difficulty="Hard",
                short_description="Unpublished idea",
                full_description="Unpublished idea",
                tags=json.dumps([]),
                popularity_score=100,
                is_published=False,
            )
            db.add_all([idea_a, idea_b, idea_hidden])
            db.flush()

            db.add_all(
                [
                    SavedIdea(user_id=user_a.id, idea_id=idea_a.id),
                    SavedIdea(user_id=user_b.id, idea_id=idea_b.id),
                ]
            )

            generated_a = GeneratedIdea(
                user_id=user_a.id,
                title="A generated idea",
                domain="Web",
                difficulty="Medium",
                tech_stack=json.dumps(["python"]),
                is_saved=False,
            )
            generated_b = GeneratedIdea(
                user_id=user_b.id,
                title="B generated idea",
                domain="Mobile",
                difficulty="Medium",
                tech_stack=json.dumps(["dart"]),
                is_saved=False,
            )
            db.add_all([generated_a, generated_b])
            db.flush()

            project_a = Project(
                owner_id=user_a.id,
                title="A project",
                description="Owned by A",
                domain="Web",
                tech_stack=json.dumps(["python"]),
                team_size=1,
                duration_weeks=4,
            )
            project_b = Project(
                owner_id=user_b.id,
                title="B project",
                description="Owned by B",
                domain="Mobile",
                tech_stack=json.dumps(["flutter"]),
                team_size=2,
                duration_weeks=6,
            )
            db.add_all([project_a, project_b])
            db.flush()

            roadmap_a = Roadmap(
                project_id=project_a.id,
                title="A roadmap",
                total_weeks=4,
                technologies=json.dumps(["python"]),
                learning_resources=json.dumps([]),
            )
            roadmap_b = Roadmap(
                project_id=project_b.id,
                title="B roadmap",
                total_weeks=6,
                technologies=json.dumps(["flutter"]),
                learning_resources=json.dumps([]),
            )
            db.add_all([roadmap_a, roadmap_b])
            db.flush()

            task_a = Task(
                roadmap_id=roadmap_a.id,
                title="A task",
                week_number=1,
                order_index=0,
                technologies=json.dumps([]),
            )
            task_b = Task(
                roadmap_id=roadmap_b.id,
                title="B task",
                week_number=1,
                order_index=0,
                technologies=json.dumps([]),
            )
            task_orphan = Task(
                roadmap_id=999999,
                title="Orphan task",
                week_number=1,
                order_index=0,
                technologies=json.dumps([]),
            )
            db.add_all([task_a, task_b, task_orphan])
            db.flush()

            post_a = Post(
                author_id=user_a.id,
                title="A published post",
                content="Public content from A",
                post_type="discussion",
                tags=json.dumps(["a"]),
                is_published=True,
                idea_id=idea_a.id,
            )
            post_b = Post(
                author_id=user_b.id,
                title="B published post",
                content="Public content from B",
                post_type="discussion",
                tags=json.dumps(["b"]),
                is_published=True,
                idea_id=idea_b.id,
            )
            post_hidden = Post(
                author_id=user_b.id,
                title="B hidden post",
                content="Unpublished content from B",
                post_type="discussion",
                tags=json.dumps([]),
                is_published=False,
            )
            db.add_all([post_a, post_b, post_hidden])
            db.flush()

            comment_on_b_post = Comment(
                post_id=post_b.id,
                author_id=user_b.id,
                content="B comment on B post",
            )
            comment_on_a_post = Comment(
                post_id=post_a.id,
                author_id=user_a.id,
                content="A comment on A post",
            )
            comment_on_hidden_post = Comment(
                post_id=post_hidden.id,
                author_id=user_b.id,
                content="B comment on hidden post",
            )
            db.add_all(
                [comment_on_b_post, comment_on_a_post, comment_on_hidden_post]
            )
            db.flush()

            db.add(
                Like(
                    user_id=user_a.id,
                    target_type="post",
                    target_id=post_b.id,
                )
            )
            post_b.like_count = 1

            notification_a = Notification(
                user_id=user_a.id,
                title="A notification",
                message="Visible only to A",
                notification_type="info",
                link="/a",
            )
            notification_b = Notification(
                user_id=user_b.id,
                title="B notification",
                message="Visible only to B",
                notification_type="info",
                link="/b",
            )
            db.add_all([notification_a, notification_b])
            db.commit()

            self.user_a_id = user_a.id
            self.user_b_id = user_b.id
            self.idea_a_id = idea_a.id
            self.idea_b_id = idea_b.id
            self.idea_hidden_id = idea_hidden.id
            self.generated_a_id = generated_a.id
            self.generated_b_id = generated_b.id
            self.project_a_id = project_a.id
            self.project_b_id = project_b.id
            self.roadmap_a_id = roadmap_a.id
            self.roadmap_b_id = roadmap_b.id
            self.task_a_id = task_a.id
            self.task_b_id = task_b.id
            self.task_orphan_id = task_orphan.id
            self.post_a_id = post_a.id
            self.post_b_id = post_b.id
            self.post_hidden_id = post_hidden.id
            self.comment_on_b_post_id = comment_on_b_post.id
            self.comment_on_hidden_post_id = comment_on_hidden_post.id
            self.notification_a_id = notification_a.id
            self.notification_b_id = notification_b.id
        finally:
            db.close()

    def _column_value(self, model, object_id, column):
        db = TestingSessionLocal()
        try:
            return getattr(db.get(model, object_id), column)
        finally:
            db.close()

    def _count_rows(self, model, **filters):
        db = TestingSessionLocal()
        try:
            query = db.query(model)
            for name, value in filters.items():
                query = query.filter(getattr(model, name) == value)
            return query.count()
        finally:
            db.close()

    def _evaluation_result(self):
        return {
            "innovation_score": 80,
            "feasibility_score": 80,
            "technical_complexity_score": 50,
            "social_impact_score": 70,
            "scalability_score": 70,
            "cost_effectiveness_score": 60,
            "overall_score": 70,
            "strengths": [],
            "weaknesses": [],
            "missing_features": [],
            "technical_challenges": [],
            "improvement_suggestions": [],
            "potential_risks": [],
            "similar_solutions": [],
        }

    def test_project_cross_user_mutations_are_forbidden(self):
        response = self.client.get(f"/api/projects/{self.project_b_id}")
        self.assertEqual(response.status_code, 403, response.text)

        response = self.client.put(
            f"/api/projects/{self.project_b_id}", json={"title": "Hacked"}
        )
        self.assertEqual(response.status_code, 403, response.text)

        response = self.client.delete(f"/api/projects/{self.project_b_id}")
        self.assertEqual(response.status_code, 403, response.text)

        self.assertEqual(
            self._column_value(Project, self.project_b_id, "title"), "B project"
        )

    def test_project_list_excludes_other_user_projects(self):
        response = self.client.get("/api/projects")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [item["id"] for item in response.json()["items"]], [self.project_a_id]
        )
        self.assertEqual(response.json()["total"], 1)

        self._as_user(self.user_b_id)
        response = self.client.get("/api/projects")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [item["id"] for item in response.json()["items"]], [self.project_b_id]
        )

    def test_roadmap_and_task_cross_user_access_is_forbidden(self):
        response = self.client.get(f"/api/projects/roadmaps/{self.roadmap_b_id}")
        self.assertEqual(response.status_code, 403, response.text)

        response = self.client.post(
            "/api/projects/tasks",
            json={"roadmap_id": self.roadmap_b_id, "title": "Injected task"},
        )
        self.assertEqual(response.status_code, 403, response.text)

        response = self.client.patch(
            f"/api/projects/tasks/{self.task_b_id}", json={"title": "Hacked task"}
        )
        self.assertEqual(response.status_code, 403, response.text)

        response = self.client.delete(f"/api/projects/tasks/{self.task_b_id}")
        self.assertEqual(response.status_code, 403, response.text)

        self.assertEqual(
            self._column_value(Task, self.task_b_id, "title"), "B task"
        )

    def test_owner_can_update_own_task(self):
        response = self.client.patch(
            f"/api/projects/tasks/{self.task_a_id}", json={"title": "Updated A task"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            self._column_value(Task, self.task_a_id, "title"), "Updated A task"
        )

    def test_task_with_missing_roadmap_returns_404(self):
        response = self.client.patch(
            f"/api/projects/tasks/{self.task_orphan_id}", json={"title": "x"}
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_roadmap_generation_cross_user_access_is_forbidden(self):
        mock_generate = AsyncMock(return_value={})
        with patch.object(
            projects_routes.ai_service, "generate_roadmap", mock_generate
        ):
            response = self.client.post(
                f"/api/projects/{self.project_b_id}/roadmap/generate",
                json={"project_id": self.project_b_id},
            )
        self.assertEqual(response.status_code, 403, response.text)
        mock_generate.assert_not_awaited()

    def test_cross_user_generated_idea_rejected_on_evaluation(self):
        mock_evaluate = AsyncMock(return_value=self._evaluation_result())
        with patch.object(ideas_routes.ai_service, "evaluate_idea", mock_evaluate):
            response = self.client.post(
                "/api/ideas/evaluate",
                json={
                    "title": "Borrowed idea",
                    "description": "Description",
                    "generated_idea_id": self.generated_b_id,
                },
            )
        self.assertIn(response.status_code, (403, 404), response.text)
        self.assertEqual(
            self._count_rows(
                IdeaEvaluation, generated_idea_id=self.generated_b_id
            ),
            0,
        )

    def test_cross_user_generated_idea_rejected_on_project_create(self):
        response = self.client.post(
            "/api/projects",
            json={
                "title": "Project from borrowed idea",
                "generated_idea_id": self.generated_b_id,
            },
        )
        self.assertIn(response.status_code, (403, 404), response.text)
        self.assertEqual(
            self._count_rows(
                Project,
                owner_id=self.user_a_id,
                generated_idea_id=self.generated_b_id,
            ),
            0,
        )

    def test_nonexistent_generated_idea_rejected_on_evaluation(self):
        mock_evaluate = AsyncMock(return_value=self._evaluation_result())
        with patch.object(ideas_routes.ai_service, "evaluate_idea", mock_evaluate):
            response = self.client.post(
                "/api/ideas/evaluate",
                json={
                    "title": "Missing source idea",
                    "description": "Description",
                    "generated_idea_id": 999999,
                },
            )
        self.assertEqual(response.status_code, 404, response.text)
        mock_evaluate.assert_not_awaited()
        self.assertEqual(self._count_rows(IdeaEvaluation), 0)

    def test_nonexistent_generated_idea_rejected_on_project_create(self):
        response = self.client.post(
            "/api/projects",
            json={
                "title": "Project from missing idea",
                "generated_idea_id": 999999,
            },
        )
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(
            self._count_rows(Project, owner_id=self.user_a_id, generated_idea_id=999999),
            0,
        )

    def test_generated_ideas_list_excludes_other_users(self):
        response = self.client.get("/api/ideas/generated/my")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [item["id"] for item in response.json()["items"]], [self.generated_a_id]
        )

        self._as_user(self.user_b_id)
        response = self.client.get("/api/ideas/generated/my")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [item["id"] for item in response.json()["items"]], [self.generated_b_id]
        )

    def test_notifications_list_excludes_other_users(self):
        response = self.client.get("/api/community/notifications")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [item["id"] for item in response.json()], [self.notification_a_id]
        )

        self._as_user(self.user_b_id)
        response = self.client.get("/api/community/notifications")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [item["id"] for item in response.json()], [self.notification_b_id]
        )

    def test_public_catalog_and_feed_still_work(self):
        self._as_anonymous()

        response = self.client.get("/api/ideas")
        self.assertEqual(response.status_code, 200, response.text)
        idea_ids = {item["id"] for item in response.json()["items"]}
        self.assertIn(self.idea_a_id, idea_ids)
        self.assertIn(self.idea_b_id, idea_ids)
        self.assertNotIn(self.idea_hidden_id, idea_ids)

        response = self.client.get(f"/api/ideas/{self.idea_a_id}")
        self.assertEqual(response.status_code, 200, response.text)

        response = self.client.get("/api/community")
        self.assertEqual(response.status_code, 200, response.text)
        post_ids = {item["id"] for item in response.json()["items"]}
        self.assertIn(self.post_a_id, post_ids)
        self.assertIn(self.post_b_id, post_ids)
        self.assertNotIn(self.post_hidden_id, post_ids)

        response = self.client.get(f"/api/community/posts/{self.post_b_id}")
        self.assertEqual(response.status_code, 200, response.text)

    def test_unpublished_post_detail_is_not_publicly_readable(self):
        self._as_anonymous()
        response = self.client.get(f"/api/community/posts/{self.post_hidden_id}")
        self.assertEqual(response.status_code, 404, response.text)

    def test_unpublished_post_comments_are_not_publicly_readable(self):
        self._as_anonymous()
        response = self.client.get(
            f"/api/community/posts/{self.post_hidden_id}/comments"
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_saved_flags_are_scoped_to_current_user(self):
        response = self.client.get("/api/ideas")
        self.assertEqual(response.status_code, 200, response.text)
        flags = {item["id"]: item["is_saved"] for item in response.json()["items"]}
        self.assertTrue(flags[self.idea_a_id])
        self.assertFalse(flags[self.idea_b_id])

        self._as_user(self.user_b_id)
        response = self.client.get("/api/ideas")
        self.assertEqual(response.status_code, 200, response.text)
        flags = {item["id"]: item["is_saved"] for item in response.json()["items"]}
        self.assertFalse(flags[self.idea_a_id])
        self.assertTrue(flags[self.idea_b_id])

    def test_unsave_does_not_delete_other_users_saved_item(self):
        response = self.client.delete(f"/api/ideas/{self.idea_b_id}/save")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["saved"])
        self.assertEqual(
            self._count_rows(
                SavedIdea, user_id=self.user_b_id, idea_id=self.idea_b_id
            ),
            1,
        )

    def test_community_post_cross_user_mutations_are_forbidden(self):
        response = self.client.put(
            f"/api/community/posts/{self.post_b_id}", json={"title": "Hacked post"}
        )
        self.assertEqual(response.status_code, 403, response.text)

        response = self.client.delete(f"/api/community/posts/{self.post_b_id}")
        self.assertEqual(response.status_code, 403, response.text)

        self.assertEqual(
            self._column_value(Post, self.post_b_id, "title"), "B published post"
        )

    def test_comment_cross_user_delete_is_forbidden(self):
        response = self.client.delete(
            f"/api/community/comments/{self.comment_on_b_post_id}"
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_report_post_records_reporter_without_global_mutation(self):
        response = self.client.post(
            f"/api/community/posts/{self.post_b_id}/report"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            self._count_rows(
                PostReport,
                post_id=self.post_b_id,
                reporter_id=self.user_a_id,
            ),
            1,
        )
        self.assertFalse(
            self._column_value(Post, self.post_b_id, "is_reported")
        )

        response = self.client.post(
            f"/api/community/posts/{self.post_b_id}/report"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            self._count_rows(
                PostReport,
                post_id=self.post_b_id,
                reporter_id=self.user_a_id,
            ),
            1,
        )

    def test_comment_parent_must_belong_to_same_post(self):
        response = self.client.post(
            "/api/community/comments",
            json={
                "post_id": self.post_a_id,
                "content": "Reply with foreign parent",
                "parent_id": self.comment_on_b_post_id,
            },
        )
        self.assertIn(response.status_code, (400, 404, 422), response.text)
        self.assertEqual(
            self._count_rows(
                Comment,
                post_id=self.post_a_id,
                parent_id=self.comment_on_b_post_id,
            ),
            0,
        )

    def test_comment_parent_must_exist(self):
        response = self.client.post(
            "/api/community/comments",
            json={
                "post_id": self.post_a_id,
                "content": "Reply to missing parent",
                "parent_id": 999999,
            },
        )
        self.assertIn(response.status_code, (400, 404, 422), response.text)
        self.assertEqual(
            self._count_rows(Comment, post_id=self.post_a_id, parent_id=999999),
            0,
        )

    def test_comment_on_unpublished_post_is_rejected(self):
        response = self.client.post(
            "/api/community/comments",
            json={"post_id": self.post_hidden_id, "content": "Hidden comment"},
        )
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(
            self._count_rows(Comment, post_id=self.post_hidden_id), 1
        )

    def test_like_target_must_exist_for_post(self):
        response = self.client.post(
            "/api/community/likes", json={"target_type": "post", "target_id": 999999}
        )
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(
            self._count_rows(
                Like, user_id=self.user_a_id, target_type="post", target_id=999999
            ),
            0,
        )

    def test_like_target_must_exist_for_comment(self):
        response = self.client.post(
            "/api/community/likes",
            json={"target_type": "comment", "target_id": 999999},
        )
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(
            self._count_rows(
                Like, user_id=self.user_a_id, target_type="comment", target_id=999999
            ),
            0,
        )

    def test_invalid_like_target_type_is_rejected(self):
        response = self.client.post(
            "/api/community/likes",
            json={"target_type": "idea", "target_id": self.idea_a_id},
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_like_unpublished_post_is_rejected(self):
        response = self.client.post(
            "/api/community/likes",
            json={"target_type": "post", "target_id": self.post_hidden_id},
        )
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(
            self._count_rows(
                Like,
                user_id=self.user_a_id,
                target_type="post",
                target_id=self.post_hidden_id,
            ),
            0,
        )

    def test_ai_chat_does_not_include_other_user_context(self):
        mock_chat = AsyncMock(return_value=("Reply", 7))
        with patch.object(ai_routes.ai_service, "mentor_chat", mock_chat):
            response = self.client.post(
                "/api/ai/chat",
                json={
                    "message": "Help",
                    "project_id": self.project_b_id,
                    "idea_id": self.generated_b_id,
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        mock_chat.assert_awaited_once()
        self.assertIsNone(mock_chat.await_args.kwargs["project_context"])
        self.assertIsNone(mock_chat.await_args.kwargs["idea_context"])

    def test_ai_chat_does_not_persist_other_user_context_ids(self):
        mock_chat = AsyncMock(return_value=("Reply", 7))
        with patch.object(ai_routes.ai_service, "mentor_chat", mock_chat):
            response = self.client.post(
                "/api/ai/chat",
                json={
                    "message": "Help",
                    "project_id": self.project_b_id,
                    "idea_id": self.generated_b_id,
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            self._count_rows(
                ChatMessage, user_id=self.user_a_id, project_id=self.project_b_id
            ),
            0,
        )
        self.assertEqual(
            self._count_rows(
                ChatMessage, user_id=self.user_a_id, idea_id=self.generated_b_id
            ),
            0,
        )

    def test_ai_chat_persists_owned_context_ids(self):
        mock_chat = AsyncMock(return_value=("Reply", 7))
        with patch.object(ai_routes.ai_service, "mentor_chat", mock_chat):
            response = self.client.post(
                "/api/ai/chat",
                json={
                    "message": "Help",
                    "project_id": self.project_a_id,
                    "idea_id": self.generated_a_id,
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("A project", mock_chat.await_args.kwargs["project_context"])
        self.assertIn("A generated idea", mock_chat.await_args.kwargs["idea_context"])
        self.assertEqual(
            self._count_rows(
                ChatMessage, user_id=self.user_a_id, project_id=self.project_a_id
            ),
            2,
        )
        self.assertEqual(
            self._count_rows(
                ChatMessage, user_id=self.user_a_id, idea_id=self.generated_a_id
            ),
            2,
        )

    def test_missing_ids_return_404(self):
        missing = 999999
        cases = [
            ("GET", f"/api/projects/{missing}", None, False),
            ("PUT", f"/api/projects/{missing}", {"title": "x"}, False),
            ("DELETE", f"/api/projects/{missing}", None, False),
            ("GET", f"/api/projects/roadmaps/{missing}", None, False),
            (
                "POST",
                "/api/projects/tasks",
                {"roadmap_id": missing, "title": "x"},
                False,
            ),
            ("PATCH", f"/api/projects/tasks/{missing}", {"title": "x"}, False),
            ("DELETE", f"/api/projects/tasks/{missing}", None, False),
            ("GET", f"/api/ideas/{missing}", None, True),
            ("POST", f"/api/ideas/{missing}/save", None, False),
            ("GET", f"/api/community/posts/{missing}", None, True),
            ("PUT", f"/api/community/posts/{missing}", {"title": "x"}, False),
            ("DELETE", f"/api/community/posts/{missing}", None, False),
            ("GET", f"/api/community/posts/{missing}/comments", None, True),
            ("DELETE", f"/api/community/comments/{missing}", None, False),
            (
                "POST",
                f"/api/community/posts/{missing}/report",
                None,
                False,
            ),
        ]

        for method, path, payload, anonymous in cases:
            with self.subTest(method=method, path=path):
                if anonymous:
                    self._as_anonymous()
                else:
                    self._as_user(self.user_a_id)
                response = self.client.request(method, path, json=payload)
                self.assertEqual(response.status_code, 404, response.text)


if __name__ == "__main__":
    unittest.main()
