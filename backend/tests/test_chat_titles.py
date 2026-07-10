import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.database import Base
from app.main import app
from app.models.tiers import Tier
from app.models.users import Role, UserRole


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


# Setup in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    # Create tables
    # Ensure all models are imported so tables are created
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Create required initial data: Role and Tier
    user_role = Role(id=1, role=UserRole.USER)
    tier = Tier(
        id=1, name="Foundation", level=1, description="Free tier", price_amount=0
    )
    db.add(user_role)
    db.add(tier)
    db.commit()

    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_chat_session_title(client, db):
    # 1. Signup and login
    # Need to disable secure cookies for test client if needed
    from app.core.config import settings

    settings.COOKIE_SECURE = False

    signup_res = client.post(
        "/api/v1/auth/signup",
        json={"email": "chat@example.com", "password": "password123", "role_id": 1},
    )
    assert signup_res.status_code == 200, f"Signup failed: {signup_res.json()}"

    # 2. Create session without providing a title
    session_res = client.post("/api/v1/chat/sessions", json={})
    assert session_res.status_code == 200
    session_data = session_res.json()
    session_id = session_data["session_id"]  # Use UUID session_id

    # 3. Send first message
    # A long message to test truncation
    msg1_content = "This is a very long message that should serve as the title for the chat session. It is definitely longer than fifty characters so we can test if the truncation logic is working correctly as expected."
    msg_res = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": msg1_content, "role": "user"},
    )
    assert msg_res.status_code == 200
    # For StreamingResponse, we need to consume the stream
    full_text = "".join(msg_res.iter_text())
    assert full_text is not None

    # 4. Fetch session to check title
    get_session_res = client.get(f"/api/v1/chat/sessions/{session_id}")
    assert get_session_res.status_code == 200
    updated_session = get_session_res.json()

    if len(msg1_content) > 50:
        expected_title = msg1_content[:50] + "..."
    else:
        expected_title = msg1_content

    assert updated_session.get("title") == expected_title

    # 5. Send second message
    msg2_content = "This is the second message."
    msg_res2 = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": msg2_content, "role": "user"},
    )
    assert msg_res2.status_code == 200
    "".join(msg_res2.iter_text())  # Consume stream

    # 6. Fetch session again to ensure title hasn't changed
    get_session_res2 = client.get(f"/api/v1/chat/sessions/{session_id}")
    assert get_session_res2.status_code == 200
    updated_session2 = get_session_res2.json()
    assert updated_session2.get("title") == expected_title

    # 7. Fetch all sessions
    all_sessions_res = client.get("/api/v1/chat/sessions")
    assert all_sessions_res.status_code == 200
    all_sessions = all_sessions_res.json()
    assert len(all_sessions) >= 1

    # Check if correct session has the title (match by session_id UUID)
    found_session = next(
        (s for s in all_sessions if s["session_id"] == session_id), None
    )
    assert found_session is not None
    assert found_session.get("title") == expected_title


def test_chat_session_with_custom_title(client, db):
    """Test creating a chat session with a custom title provided by user"""
    # 1. Signup and login
    from app.core.config import settings

    settings.COOKIE_SECURE = False

    signup_res = client.post(
        "/api/v1/auth/signup",
        json={"email": "chat2@example.com", "password": "password123", "role_id": 1},
    )
    assert signup_res.status_code == 200, f"Signup failed: {signup_res.json()}"

    # 2. Create session with custom title
    custom_title = "My Custom Chat Title"
    session_res = client.post("/api/v1/chat/sessions", json={"title": custom_title})
    assert session_res.status_code == 200
    session_data = session_res.json()
    session_id = session_data["session_id"]  # Use UUID session_id

    # Verify the title was set correctly
    assert session_data.get("title") == custom_title

    # 3. Fetch session to double-check title
    get_session_res = client.get(f"/api/v1/chat/sessions/{session_id}")
    assert get_session_res.status_code == 200
    fetched_session = get_session_res.json()
    assert fetched_session.get("title") == custom_title

    # 4. Send a message and ensure the title doesn't get overwritten
    msg_content = "This message should not change the existing title"
    msg_res = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": msg_content, "role": "user"},
    )
    assert msg_res.status_code == 200
    "".join(msg_res.iter_text())  # Consume stream

    # 5. Verify title remains unchanged
    get_session_res2 = client.get(f"/api/v1/chat/sessions/{session_id}")
    assert get_session_res2.status_code == 200
    final_session = get_session_res2.json()
    assert (
        final_session.get("title") == custom_title
    )  # Should still be the custom title

    # 6. Test creating session without a title (should be None)
    session_res_no_title = client.post("/api/v1/chat/sessions", json={})
    assert session_res_no_title.status_code == 200
    session_data_no_title = session_res_no_title.json()
    assert session_data_no_title.get("title") is None
