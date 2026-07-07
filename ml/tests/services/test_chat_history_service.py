import json

import pytest

from config.settings import settings
from src.services.chat.history_service import ChatHistoryService


class FakeAsyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.deleted_keys: list[str] = []
        self.last_setex: tuple[str, int, str] | None = None

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.last_setex = (key, ttl, value)
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.deleted_keys.append(key)
        self.store.pop(key, None)


class FakeResponse:
    def __init__(self, payload: list[dict[str, object]]) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict[str, object]]:
        return self._payload


class FakeAsyncClient:
    def __init__(self, payload: list[dict[str, object]]) -> None:
        self._response = FakeResponse(payload)
        self.requests: list[dict[str, object]] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        return None

    async def get(
        self, url: str, params: dict[str, int], headers: dict[str, str]
    ) -> FakeResponse:
        self.requests.append({"url": url, "params": params, "headers": headers})
        return self._response


@pytest.mark.anyio
async def test_chat_history_service_fetches_backend_and_caches_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = FakeAsyncRedis()
    backend_payload = [
        {
            "content": "Hello",
            "role": "user",
            "non_substantive": False,
            "id": 19,
            "session_id": 4,
            "created_at": "2026-04-07T12:11:37.647457",
        },
        {
            "content": "Hi there",
            "role": "bot",
            "non_substantive": False,
            "id": 20,
            "session_id": 4,
            "created_at": "2026-04-07T12:11:37.657393",
        },
    ]
    fake_client = FakeAsyncClient(backend_payload)
    service = ChatHistoryService(
        redis_client=fake_redis,
        http_client_factory=lambda: fake_client,
    )

    monkeypatch.setattr(
        settings, "ml_data_transfer_base_url", "https://api.example.com"
    )
    monkeypatch.setattr(settings, "ml_data_transfer_token", "token-value")
    monkeypatch.setattr(settings, "max_message_retrieved", 12)

    records = await service.get_raw_history("session-123", is_new=False)

    assert (
        fake_client.requests[0]["params"]["limit"] == 10
        and records[0]["metadata"]["message_id"] == 19
        and fake_redis.last_setex is not None
    )


@pytest.mark.anyio
async def test_chat_history_service_uses_cached_history_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = FakeAsyncRedis()
    cached_history = [
        {
            "role": "user",
            "content": "Cached question",
            "timestamp": "2026-04-07T12:11:37.647457",
            "created_at": "2026-04-07T12:11:37.647457",
            "session_id": "session-123",
            "type": "human",
            "data": {"content": "Cached question"},
        }
    ]
    fake_redis.store["chat_history:session-123"] = json.dumps(cached_history)
    fake_client = FakeAsyncClient([])
    service = ChatHistoryService(
        redis_client=fake_redis,
        http_client_factory=lambda: fake_client,
    )

    monkeypatch.setattr(
        settings, "ml_data_transfer_base_url", "https://api.example.com"
    )
    monkeypatch.setattr(settings, "ml_data_transfer_token", "token-value")

    records = await service.get_raw_history("session-123", is_new=False)

    assert records[0]["content"] == "Cached question" and fake_client.requests == []


@pytest.mark.anyio
async def test_chat_history_service_skips_fetch_when_new_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = FakeAsyncRedis()
    fake_client = FakeAsyncClient([])
    service = ChatHistoryService(
        redis_client=fake_redis,
        http_client_factory=lambda: fake_client,
    )

    monkeypatch.setattr(
        settings, "ml_data_transfer_base_url", "https://api.example.com"
    )
    monkeypatch.setattr(settings, "ml_data_transfer_token", "token-value")

    records = await service.get_raw_history("session-123", is_new=True)

    assert records == [] and fake_client.requests == []
