"""Offline tests for the eval harness: no LLM, no database."""

import decimal
import json
from types import SimpleNamespace

from evals.runner import QUESTIONS, answer_ok, report, rows_match, score


def test_rows_match_ignores_order_and_extra_columns():
    gold = [["Laptop"], ["Monitor"]]
    got = [{"id": 4, "name": "Monitor"}, {"id": 1, "name": "Laptop"}]
    assert rows_match(gold, got)


def test_rows_match_normalises_numbers():
    assert rows_match([[decimal.Decimal("3301.00")]], [{"total": 3301}])
    assert rows_match([[5]], [{"COUNT(*)": 5.0}])


def test_rows_match_rejects_wrong_or_missing_rows():
    assert not rows_match([["Laptop"], ["Monitor"]], [{"name": "Laptop"}])
    assert not rows_match([["Laptop"]], [{"name": "Mouse"}])
    # one returned row cannot satisfy two gold rows
    assert not rows_match([["a"], ["a"]], [{"x": "a"}, {"x": "b"}])


def test_answer_ok_all_and_any():
    assert answer_ok("There are 5 users", {"answer_contains": ["5"]})
    assert not answer_ok("Mouse and Laptop", {"answer_contains": ["Mouse", "Keyboard"]})
    assert answer_ok("£3,301 in total", {"answer_contains": ["3301", "3,301"], "answer_match": "any"})
    assert answer_ok("anything", {})


def test_question_set_is_well_formed():
    questions = json.loads(QUESTIONS.read_text())
    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids)) >= 10
    assert all(q["gold"].lstrip().upper().startswith("SELECT") for q in questions)


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self):
        return SimpleNamespace(execute=lambda sql: None, fetchall=lambda: self.rows)

    def close(self):
        pass


def response(data, answer, success=True):
    return SimpleNamespace(
        query_result=SimpleNamespace(success=success, data=data, sql_query="SELECT", error_message=None),
        natural_language_answer=answer,
        review=None,
    )


def test_score_and_report_threshold():
    questions = [
        {"id": "a", "question": "q", "gold": "SELECT 1", "answer_contains": ["5"]},
        {"id": "b", "question": "q", "gold": "SELECT 1"},
    ]
    answers = iter([response([{"n": 5}], "There are 5"), response([{"n": 4}], "There are 4")])
    outcomes = score(questions, lambda q: next(answers), lambda: FakeConnection([(5,)]))
    assert [o.passed for o in outcomes] == [True, False]
    assert "1/2 (50%), bar 80% - FAIL" in report(outcomes, 0.8)
