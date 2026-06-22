"""Tests for _serialize_row — the MySQL-to-JSON type converter."""
import datetime
import decimal

import pytest

from app.services.sql_agent import _serialize_row


class TestSerializeRow:
    def test_datetime_to_iso(self):
        result = _serialize_row({"ts": datetime.datetime(2024, 6, 15, 10, 30, 45)})
        assert result["ts"] == "2024-06-15T10:30:45"

    def test_date_to_iso(self):
        result = _serialize_row({"dob": datetime.date(1990, 3, 22)})
        assert result["dob"] == "1990-03-22"

    def test_decimal_to_float(self):
        result = _serialize_row({"price": decimal.Decimal("19.99")})
        assert result["price"] == pytest.approx(19.99)
        assert isinstance(result["price"], float)

    def test_bytes_decoded_as_utf8(self):
        result = _serialize_row({"data": b"hello"})
        assert result["data"] == "hello"

    def test_bytes_with_invalid_utf8_replaced(self):
        result = _serialize_row({"data": b"\xff\xfe"})
        assert isinstance(result["data"], str)

    def test_string_passthrough(self):
        result = _serialize_row({"name": "Alice"})
        assert result["name"] == "Alice"

    def test_int_passthrough(self):
        result = _serialize_row({"id": 42})
        assert result["id"] == 42

    def test_none_passthrough(self):
        result = _serialize_row({"value": None})
        assert result["value"] is None

    def test_bool_passthrough(self):
        result = _serialize_row({"active": True})
        assert result["active"] is True

    def test_multiple_types_in_one_row(self):
        row = {
            "id": 1,
            "name": "Bob",
            "score": decimal.Decimal("9.5"),
            "ts": datetime.datetime(2024, 1, 1, 0, 0, 0),
            "raw": b"bytes",
        }
        result = _serialize_row(row)
        assert result["id"] == 1
        assert result["name"] == "Bob"
        assert result["score"] == pytest.approx(9.5)
        assert result["ts"] == "2024-01-01T00:00:00"
        assert result["raw"] == "bytes"
