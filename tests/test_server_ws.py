import pytest
from fastapi.testclient import TestClient

import server
from server import app
from server_adapter import pop_user_response, push_user_response


@pytest.mark.asyncio
async def test_user_response_queue_is_scoped_per_session():
    push_user_response("first", "session-a")
    push_user_response("second", "session-b")

    assert await pop_user_response(timeout=0.1, session_id="session-a") == "first"
    assert await pop_user_response(timeout=0.1, session_id="session-b") == "second"


class _FakeSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._event_handlers = []

    def on(self, handler):
        self._event_handlers.append(handler)

    async def send_and_wait(self, payload, timeout):
        from server_adapter import _send, pop_user_response

        _send(
            {
                "type": "waiting_for_input",
                "question": "1. **Who is the audience?**",
                "choices": ["Internal", "External"],
            },
            self.session_id,
        )
        answer = await pop_user_response(timeout=1.0, session_id=self.session_id)
        assert answer == "Internal"
        return {"status": "ok", "payload": payload, "timeout": timeout}


@pytest.fixture
def client(monkeypatch):
    session_id = "test-session"
    fake_session = _FakeSession(session_id)

    monkeypatch.setitem(server._session_map, session_id, fake_session)
    monkeypatch.setattr(server, "_collector", None)
    monkeypatch.setattr(server, "_event_store", None)

    async def _fake_route_to_agent(_session, _content):
        return None

    monkeypatch.setattr("router.route_to_agent", _fake_route_to_agent)

    with TestClient(app) as test_client:
        yield test_client, session_id

    server._session_map.pop(session_id, None)


def test_websocket_allows_user_response_while_turn_is_waiting(client):
    test_client, session_id = client

    with test_client.websocket_connect(f"/ws/{session_id}") as ws:
        ws.send_json(
            {"type": "message", "content": "@slide-conductor Create something"}
        )

        first = ws.receive_json()
        # First message may be a session_snapshot (always sent on connect)
        if first.get("type") == "session_snapshot" or (
            first.get("v") == 1 and first.get("type") == "session_snapshot"
        ):
            first = ws.receive_json()
        assert first["type"] == "turn_started"

        waiting = ws.receive_json()
        assert waiting["type"] == "waiting_for_input"
        assert "**Who is the audience?**" in waiting["question"]

        ws.send_json({"type": "user_response", "content": "Internal"})

        done = ws.receive_json()
        assert done["type"] == "done"
        assert done.get("data", done).get("status") == "success"
