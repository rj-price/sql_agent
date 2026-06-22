import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_model():
    """Reusable mock for the Gemini GenerativeModel."""
    return MagicMock()


@pytest.fixture
def agent(mock_model):
    """NaturalLanguageToSQL with mocked LLM and pre-loaded schema (no DB or API calls)."""
    with patch("app.services.sql_agent.genai") as mock_genai:
        mock_genai.GenerativeModel.return_value = mock_model
        from app.services.sql_agent import NaturalLanguageToSQL
        a = NaturalLanguageToSQL()
        a._schema_info = "Table: users\n  - id: int (Primary Key)\n  - name: varchar(100)"
        yield a
