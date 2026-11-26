# Import all models here so Alembic autogenerate can discover them.
from app.models.user import User, UserProfile  # noqa: F401
from app.models.idea import (  # noqa: F401
    Category,
    Idea,
    SavedIdea,
    GeneratedIdea,
    IdeaEvaluation,
)
from app.models.project import Project, Roadmap, Task  # noqa: F401
from app.models.community import (  # noqa: F401
    Post,
    Comment,
    Like,
    PostReport,
    Notification,
)
from app.models.chat import ChatMessage  # noqa: F401
