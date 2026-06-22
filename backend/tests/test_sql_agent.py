"""Tests for NaturalLanguageToSQL — the core agent service."""
import datetime
import decimal

import mysql.connector.errors
import pytest
from unittest.mock import MagicMock, patch

from app.services.sql_agent import NaturalLanguageToSQL, QueryResult, SQLReview


# ── helpers ───────────────────────────────────────────────────────────────────

def _ok_conn(rows=None):
    """Return a mock connection whose cursor.fetchmany() returns `rows`."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchmany.return_value = rows if rows is not None else []
    conn.cursor.return_value = cursor
    return conn


def _fail_conn(exc):
    """Return a mock connection whose cursor.execute() raises `exc`."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.execute.side_effect = exc
    conn.cursor.return_value = cursor
    return conn


# ── SELECT guard ──────────────────────────────────────────────────────────────

class TestSelectGuard:
    """Only SELECT / WITH queries may reach the database."""

    def test_plain_select_allowed(self, agent):
        with patch("app.services.sql_agent.get_db_connection", return_value=_ok_conn([{"id": 1}])):
            result = agent._execute_sql_query("SELECT * FROM users")
        assert result.success is True

    def test_lowercase_select_allowed(self, agent):
        with patch("app.services.sql_agent.get_db_connection", return_value=_ok_conn()):
            result = agent._execute_sql_query("select id from users")
        assert result.success is True

    def test_with_cte_allowed(self, agent):
        with patch("app.services.sql_agent.get_db_connection", return_value=_ok_conn()):
            result = agent._execute_sql_query("WITH cte AS (SELECT 1) SELECT * FROM cte")
        assert result.success is True

    @pytest.mark.parametrize("sql", [
        "INSERT INTO users VALUES (1, 'x')",
        "UPDATE users SET name = 'y'",
        "DELETE FROM users WHERE id = 1",
        "DROP TABLE users",
        "ALTER TABLE users ADD COLUMN foo INT",
        "TRUNCATE TABLE users",
        "CREATE TABLE foo (id INT)",
    ])
    def test_write_queries_blocked(self, agent, sql):
        result = agent._execute_sql_query(sql)
        assert result.success is False
        assert "SELECT" in result.error_message

    def test_empty_query_blocked(self, agent):
        result = agent._execute_sql_query("   ")
        assert result.success is False

    def test_blocked_query_never_touches_db(self, agent):
        with patch("app.services.sql_agent.get_db_connection") as mock_get:
            agent._execute_sql_query("DROP TABLE users")
        mock_get.assert_not_called()


# ── Execute mechanics ─────────────────────────────────────────────────────────

class TestExecuteQuery:

    def test_fetchmany_called_with_1000_row_cap(self, agent):
        conn = _ok_conn()
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            agent._execute_sql_query("SELECT * FROM users")
        conn.cursor().fetchmany.assert_called_once_with(1000)

    def test_connection_closed_on_success(self, agent):
        conn = _ok_conn()
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            agent._execute_sql_query("SELECT * FROM users")
        conn.close.assert_called_once()

    def test_connection_closed_on_sql_error(self, agent):
        conn = _fail_conn(mysql.connector.errors.ProgrammingError("bad sql"))
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            agent._execute_sql_query("SELECT * FROM users")
        conn.close.assert_called_once()

    def test_connection_closed_when_operational_error_propagates(self, agent):
        conn = _fail_conn(mysql.connector.errors.OperationalError("gone away"))
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            try:
                agent._execute_sql_query("SELECT * FROM users")
            except mysql.connector.errors.OperationalError:
                pass
        conn.close.assert_called_once()

    def test_programming_error_returns_failed_result(self, agent):
        conn = _fail_conn(mysql.connector.errors.ProgrammingError("unknown column"))
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            result = agent._execute_sql_query("SELECT * FROM users")
        assert result.success is False
        assert "unknown column" in result.error_message

    def test_operational_error_propagates(self, agent):
        conn = _fail_conn(mysql.connector.errors.OperationalError("server gone away"))
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            with pytest.raises(mysql.connector.errors.OperationalError):
                agent._execute_sql_query("SELECT * FROM users")

    def test_column_names_extracted_from_first_row(self, agent):
        conn = _ok_conn([{"id": 1, "name": "Alice", "score": 10}])
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            result = agent._execute_sql_query("SELECT id, name, score FROM users")
        assert result.column_names == ["id", "name", "score"]

    def test_empty_result_set_is_successful(self, agent):
        conn = _ok_conn([])
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            result = agent._execute_sql_query("SELECT * FROM users WHERE 1=0")
        assert result.success is True
        assert result.data == []
        assert result.column_names == []

    def test_datetime_serialized_to_iso(self, agent):
        dt = datetime.datetime(2024, 6, 15, 10, 30, 0)
        conn = _ok_conn([{"id": 1, "created_at": dt}])
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            result = agent._execute_sql_query("SELECT id, created_at FROM events")
        assert result.data[0]["created_at"] == "2024-06-15T10:30:00"

    def test_decimal_serialized_to_float(self, agent):
        conn = _ok_conn([{"price": decimal.Decimal("19.99")}])
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            result = agent._execute_sql_query("SELECT price FROM products")
        assert isinstance(result.data[0]["price"], float)
        assert result.data[0]["price"] == pytest.approx(19.99)

    def test_bytes_serialized_to_string(self, agent):
        conn = _ok_conn([{"raw": b"hello"}])
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            result = agent._execute_sql_query("SELECT raw FROM blobs")
        assert result.data[0]["raw"] == "hello"


# ── SQL generation ────────────────────────────────────────────────────────────

class TestGenerateSQLQuery:

    def _llm_returns(self, mock_model, text):
        resp = MagicMock()
        resp.text = text
        mock_model.generate_content.return_value = resp

    def test_returns_bare_sql(self, agent, mock_model):
        self._llm_returns(mock_model, "SELECT * FROM users")
        assert agent._generate_sql_query("show all users") == "SELECT * FROM users"

    def test_strips_sql_code_fence(self, agent, mock_model):
        self._llm_returns(mock_model, "```sql\nSELECT * FROM users\n```")
        assert agent._generate_sql_query("show all users") == "SELECT * FROM users"

    def test_strips_trailing_fence_only(self, agent, mock_model):
        self._llm_returns(mock_model, "SELECT * FROM users\n```")
        assert agent._generate_sql_query("show all users") == "SELECT * FROM users"

    def test_strips_surrounding_whitespace(self, agent, mock_model):
        self._llm_returns(mock_model, "  SELECT * FROM users  ")
        assert agent._generate_sql_query("show all users") == "SELECT * FROM users"

    def test_includes_schema_in_prompt(self, agent, mock_model):
        self._llm_returns(mock_model, "SELECT 1")
        agent._generate_sql_query("test question")
        prompt = mock_model.generate_content.call_args[0][0]
        assert "Table: users" in prompt


# ── SQL review ────────────────────────────────────────────────────────────────

class TestReviewSQLQuery:

    def _llm_returns(self, mock_model, text):
        resp = MagicMock()
        resp.text = text
        mock_model.generate_content.return_value = resp

    def test_parses_json_review_and_null_corrected(self, agent, mock_model):
        self._llm_returns(mock_model, '{"review": "Looks fine.", "corrected_query": null}')
        result = agent._review_sql_query("SELECT * FROM users")
        assert result.review_text == "Looks fine."
        assert result.corrected_query is None

    def test_parses_corrected_query(self, agent, mock_model):
        self._llm_returns(mock_model, '{"review": "Wrong table.", "corrected_query": "SELECT * FROM orders"}')
        result = agent._review_sql_query("SELECT * FROM order")
        assert result.corrected_query == "SELECT * FROM orders"

    def test_strips_json_code_fence(self, agent, mock_model):
        self._llm_returns(mock_model, '```json\n{"review": "OK.", "corrected_query": null}\n```')
        result = agent._review_sql_query("SELECT 1")
        assert result.review_text == "OK."

    def test_returns_error_review_on_invalid_json(self, agent, mock_model):
        self._llm_returns(mock_model, "this is not json")
        result = agent._review_sql_query("SELECT 1")
        assert "Error" in result.review_text
        assert result.corrected_query is None

    def test_returns_error_review_on_llm_exception(self, agent, mock_model):
        mock_model.generate_content.side_effect = RuntimeError("quota exceeded")
        result = agent._review_sql_query("SELECT 1")
        assert "Error" in result.review_text
        assert result.corrected_query is None


# ── Lazy schema init ──────────────────────────────────────────────────────────

class TestLazySchemaInit:

    def test_init_does_not_call_get_schema_info(self):
        with patch("app.services.sql_agent.genai"):
            with patch("app.services.sql_agent.get_schema_info") as mock_schema:
                NaturalLanguageToSQL()
                mock_schema.assert_not_called()

    def test_schema_property_loads_on_first_access(self):
        with patch("app.services.sql_agent.genai"):
            with patch("app.services.sql_agent.get_schema_info", return_value="schema") as mock_schema:
                a = NaturalLanguageToSQL()
                _ = a.schema_info
                mock_schema.assert_called_once()

    def test_schema_property_cached_after_first_access(self):
        with patch("app.services.sql_agent.genai"):
            with patch("app.services.sql_agent.get_schema_info", return_value="schema") as mock_schema:
                a = NaturalLanguageToSQL()
                _ = a.schema_info
                _ = a.schema_info
                mock_schema.assert_called_once()

    def test_schema_property_returns_value_from_get_schema_info(self):
        with patch("app.services.sql_agent.genai"):
            with patch("app.services.sql_agent.get_schema_info", return_value="Table: foo"):
                a = NaturalLanguageToSQL()
                assert a.schema_info == "Table: foo"


# ── ask_question orchestration ────────────────────────────────────────────────

class TestAskQuestion:

    def _resp(self, mock_model, *texts):
        responses = [MagicMock() for _ in texts]
        for r, t in zip(responses, texts):
            r.text = t
        mock_model.generate_content.side_effect = responses

    def test_happy_path_returns_answer(self, agent, mock_model):
        self._resp(mock_model, "SELECT COUNT(*) FROM users", "There are 2 users.")
        conn = _ok_conn([{"count": 2}])
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            result = agent.ask_question("how many users?")
        assert result.natural_language_answer == "There are 2 users."
        assert result.query_result.success is True
        assert result.review is None

    def test_happy_path_makes_two_llm_calls(self, agent, mock_model):
        self._resp(mock_model, "SELECT 1", "one")
        conn = _ok_conn([{"1": 1}])
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            agent.ask_question("test")
        assert mock_model.generate_content.call_count == 2

    def test_sql_failure_triggers_review(self, agent, mock_model):
        self._resp(
            mock_model,
            "SELECT * FROM wrong_table",
            '{"review": "Wrong table.", "corrected_query": "SELECT * FROM users"}',
            "Found some users.",
        )
        call_n = [0]

        def make_conn():
            call_n[0] += 1
            if call_n[0] == 1:
                return _fail_conn(mysql.connector.errors.ProgrammingError("no such table"))
            return _ok_conn([{"id": 1}])

        with patch("app.services.sql_agent.get_db_connection", side_effect=make_conn):
            result = agent.ask_question("show users")

        assert result.review is not None
        assert result.review.review_text == "Wrong table."
        assert result.review.corrected_query == "SELECT * FROM users"
        assert result.query_result.success is True
        assert mock_model.generate_content.call_count == 3

    def test_no_corrected_query_skips_second_db_call(self, agent, mock_model):
        self._resp(
            mock_model,
            "SELECT * FROM bad_table",
            '{"review": "Cannot fix.", "corrected_query": null}',
        )
        conn = _fail_conn(mysql.connector.errors.ProgrammingError("no such table"))
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            result = agent.ask_question("show bad table")

        assert result.review.corrected_query is None
        assert result.query_result.success is False
        assert mock_model.generate_content.call_count == 2

    def test_connection_error_not_reviewed(self, agent, mock_model):
        """OperationalError must propagate to the outer except — not trigger LLM review."""
        self._resp(mock_model, "SELECT * FROM users")
        conn = _fail_conn(mysql.connector.errors.OperationalError("server gone away"))
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            result = agent.ask_question("show users")

        assert mock_model.generate_content.call_count == 1
        assert "server gone away" in result.natural_language_answer

    def test_empty_result_returns_no_results_message(self, agent, mock_model):
        self._resp(mock_model, "SELECT * FROM users")
        conn = _ok_conn([])
        with patch("app.services.sql_agent.get_db_connection", return_value=conn):
            result = agent.ask_question("show users")
        assert result.natural_language_answer == "No results found."

    def test_returns_agent_response_on_unexpected_exception(self, agent, mock_model):
        mock_model.generate_content.side_effect = RuntimeError("quota exceeded")
        result = agent.ask_question("show users")
        assert isinstance(result.natural_language_answer, str)
        assert "quota exceeded" in result.natural_language_answer
        assert result.query_result.success is False
