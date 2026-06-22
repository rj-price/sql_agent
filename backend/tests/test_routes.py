"""Tests for FastAPI route handlers."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.services.sql_agent import AgentResponse, QueryResult, SQLReview


@pytest.fixture(scope="module")
def app():
    from main import app
    return app


@pytest.fixture
def mock_agent():
    return MagicMock()


@pytest.fixture
def client(app, mock_agent):
    with patch("app.api.routes.agent", mock_agent):
        yield TestClient(app), mock_agent


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_response(
    answer="42 users",
    sql="SELECT COUNT(*) FROM users",
    data=None,
    columns=None,
    success=True,
    review=None,
):
    return AgentResponse(
        natural_language_answer=answer,
        query_result=QueryResult(
            sql_query=sql,
            data=data if data is not None else [{"count": 42}],
            column_names=columns if columns is not None else ["count"],
            success=success,
        ),
        review=review,
    )


# ── /api/health ───────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_returns_200(self, client):
        tc, _ = client
        assert tc.get("/api/health").status_code == 200

    def test_returns_ok_status(self, client):
        tc, _ = client
        assert tc.get("/api/health").json() == {"status": "ok"}


# ── /api/schema ───────────────────────────────────────────────────────────────

class TestSchemaEndpoint:
    def test_returns_schema_string(self, client):
        tc, mock_agent = client
        mock_agent.schema_info = "Table: users\n  - id: int"
        resp = tc.get("/api/schema")
        assert resp.status_code == 200
        assert resp.json()["schema"] == "Table: users\n  - id: int"

    def test_500_when_schema_raises(self, app):
        class BrokenAgent:
            @property
            def schema_info(self):
                raise RuntimeError("DB unavailable")

        with patch("app.api.routes.agent", BrokenAgent()):
            resp = TestClient(app).get("/api/schema")
        assert resp.status_code == 500


# ── /api/ask ──────────────────────────────────────────────────────────────────

class TestAskEndpoint:
    def test_returns_200(self, client):
        tc, mock_agent = client
        mock_agent.ask_question.return_value = _make_response()
        assert tc.post("/api/ask", json={"question": "how many users?"}).status_code == 200

    def test_response_contains_answer(self, client):
        tc, mock_agent = client
        mock_agent.ask_question.return_value = _make_response(answer="There are 5 users.")
        body = tc.post("/api/ask", json={"question": "how many?"}).json()
        assert body["answer"] == "There are 5 users."

    def test_response_contains_sql(self, client):
        tc, mock_agent = client
        mock_agent.ask_question.return_value = _make_response(sql="SELECT COUNT(*) FROM orders")
        body = tc.post("/api/ask", json={"question": "orders?"}).json()
        assert body["sql"] == "SELECT COUNT(*) FROM orders"

    def test_response_contains_data_and_columns(self, client):
        tc, mock_agent = client
        mock_agent.ask_question.return_value = _make_response(
            data=[{"id": 1, "name": "Alice"}],
            columns=["id", "name"],
        )
        body = tc.post("/api/ask", json={"question": "who?"}).json()
        assert body["data"] == [{"id": 1, "name": "Alice"}]
        assert body["columns"] == ["id", "name"]

    def test_review_none_when_not_present(self, client):
        tc, mock_agent = client
        mock_agent.ask_question.return_value = _make_response(review=None)
        body = tc.post("/api/ask", json={"question": "test"}).json()
        assert body["review"] is None

    def test_review_included_when_present(self, client):
        tc, mock_agent = client
        review = SQLReview(review_text="Fixed the table name.", corrected_query="SELECT * FROM users")
        mock_agent.ask_question.return_value = _make_response(review=review)
        body = tc.post("/api/ask", json={"question": "show users"}).json()
        assert body["review"]["text"] == "Fixed the table name."
        assert body["review"]["corrected_query"] == "SELECT * FROM users"

    def test_review_corrected_query_can_be_null(self, client):
        tc, mock_agent = client
        review = SQLReview(review_text="No fix available.", corrected_query=None)
        mock_agent.ask_question.return_value = _make_response(review=review)
        body = tc.post("/api/ask", json={"question": "show users"}).json()
        assert body["review"]["corrected_query"] is None

    def test_passes_exact_question_to_agent(self, client):
        tc, mock_agent = client
        mock_agent.ask_question.return_value = _make_response()
        tc.post("/api/ask", json={"question": "how many orders were placed in June?"})
        mock_agent.ask_question.assert_called_once_with("how many orders were placed in June?")

    def test_422_on_missing_question_field(self, client):
        tc, _ = client
        assert tc.post("/api/ask", json={}).status_code == 422

    def test_422_on_empty_body(self, client):
        tc, _ = client
        assert tc.post("/api/ask").status_code == 422

    def test_500_when_agent_raises(self, app):
        bad_agent = MagicMock()
        bad_agent.ask_question.side_effect = RuntimeError("unexpected failure")
        with patch("app.api.routes.agent", bad_agent):
            resp = TestClient(app).post("/api/ask", json={"question": "test"})
        assert resp.status_code == 500

    def test_success_false_still_returns_200(self, client):
        tc, mock_agent = client
        mock_agent.ask_question.return_value = _make_response(
            answer="Error: table not found",
            data=[],
            columns=[],
            success=False,
        )
        resp = tc.post("/api/ask", json={"question": "show bad table"})
        assert resp.status_code == 200
        assert resp.json()["success"] is False
