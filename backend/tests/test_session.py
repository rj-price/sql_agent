"""Tests for DB session helpers — connection and schema extraction."""
import pytest
import mysql.connector
from unittest.mock import MagicMock, call, patch


def _make_conn(*fetchall_returns):
    """Build a mock connection whose cursor.fetchall() returns the given sequence."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.side_effect = list(fetchall_returns)
    return conn, cursor


class TestGetSchemaInfo:
    """get_schema_info() creates its own connection, queries the DB, and closes."""

    def _run(self, conn):
        with patch("app.db.session.get_db_connection", return_value=conn):
            from app.db.session import get_schema_info
            return get_schema_info()

    def test_backtick_quotes_table_name_in_describe(self):
        conn, cursor = _make_conn(
            [("users",)],                                          # SHOW TABLES
            [("id", "int", "NO", "PRI", None, "")],               # DESCRIBE
            [],                                                     # SELECT sample
        )
        self._run(conn)
        executed = [str(c) for c in cursor.execute.call_args_list]
        describe_calls = [c for c in executed if "DESCRIBE" in c]
        assert any("`users`" in c for c in describe_calls)

    def test_backtick_quotes_table_name_in_select(self):
        conn, cursor = _make_conn(
            [("users",)],
            [("id", "int", "NO", "PRI", None, "")],
            [],
        )
        self._run(conn)
        executed = [str(c) for c in cursor.execute.call_args_list]
        select_calls = [c for c in executed if "SELECT" in c and "SHOW" not in c]
        assert any("`users`" in c for c in select_calls)

    def test_connection_closed_on_success(self):
        conn, cursor = _make_conn(
            [("users",)],
            [("id", "int", "NO", "PRI", None, "")],
            [],
        )
        self._run(conn)
        conn.close.assert_called_once()

    def test_connection_closed_on_error(self):
        conn, cursor = _make_conn()
        cursor.execute.side_effect = mysql.connector.Error("boom")
        self._run(conn)  # must not raise
        conn.close.assert_called_once()

    def test_returns_table_name_in_output(self):
        conn, cursor = _make_conn(
            [("orders",)],
            [("id", "int", "NO", "PRI", None, ""), ("total", "decimal(10,2)", "YES", "", None, "")],
            [(1, "99.99")],
        )
        result = self._run(conn)
        assert "Table: orders" in result

    def test_marks_primary_key_columns(self):
        conn, cursor = _make_conn(
            [("users",)],
            [("id", "int", "NO", "PRI", None, ""), ("name", "varchar(100)", "YES", "", None, "")],
            [],
        )
        result = self._run(conn)
        assert "(Primary Key)" in result

    def test_non_pk_columns_have_no_pk_marker(self):
        conn, cursor = _make_conn(
            [("users",)],
            [("id", "int", "NO", "PRI", None, ""), ("name", "varchar(100)", "YES", "", None, "")],
            [],
        )
        result = self._run(conn)
        lines = result.splitlines()
        name_line = next(l for l in lines if "name" in l)
        assert "(Primary Key)" not in name_line

    def test_sample_data_included(self):
        conn, cursor = _make_conn(
            [("products",)],
            [("id", "int", "NO", "PRI", None, "")],
            [(1,), (2,)],
        )
        result = self._run(conn)
        assert "Sample data" in result
        assert "(1,)" in result

    def test_empty_database_returns_empty_string(self):
        conn, cursor = _make_conn([])  # SHOW TABLES → no tables
        result = self._run(conn)
        assert result == ""

    def test_multiple_tables_all_included(self):
        conn, cursor = _make_conn(
            [("users",), ("orders",)],          # SHOW TABLES
            [("id", "int", "NO", "PRI", None, "")],  # DESCRIBE users
            [],                                  # SELECT users sample
            [("id", "int", "NO", "PRI", None, "")],  # DESCRIBE orders
            [],                                  # SELECT orders sample
        )
        result = self._run(conn)
        assert "Table: users" in result
        assert "Table: orders" in result


class TestGetDbConnection:
    def test_raises_on_connector_error(self):
        with patch("app.db.session.mysql.connector.connect") as mock_connect:
            mock_connect.side_effect = mysql.connector.Error("refused")
            from app.db.session import get_db_connection
            with pytest.raises(mysql.connector.Error):
                get_db_connection()
