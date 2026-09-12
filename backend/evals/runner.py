"""Execution-accuracy regression suite for the SQL agent.

Each question has a gold SQL query. The agent's final result set is compared with
the gold result set on values, not SQL text, so any query that returns the right
rows passes. Scoring is deterministic: no model grades another model.

    python -m evals.runner --check --min-accuracy 0.8 --results-dir evals/results

Needs GOOGLE_API_KEY and the SQL_* settings pointing at a database loaded with
../init.sql. Exit status is 1 when --check is given and accuracy is below the bar.
"""

from __future__ import annotations

import argparse
import datetime
import decimal
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

QUESTIONS = Path(__file__).with_name("questions.json")


def _normalise(value: Any) -> str:
    if isinstance(value, (float, decimal.Decimal)):
        return f"{float(value):.2f}"
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{float(value):.2f}"
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return str(value).strip()


def rows_match(gold: list[list[Any]], got: list[dict[str, Any]]) -> bool:
    """True when every gold row maps one-to-one onto a returned row containing its values.

    Extra returned columns are allowed (asking for a name and getting name + id is fine);
    missing or extra rows are not. Row order is ignored.
    """
    if len(gold) != len(got):
        return False
    unused = [Counter(_normalise(v) for v in row.values()) for row in got]
    for gold_row in gold:
        needed = Counter(_normalise(v) for v in gold_row)
        for i, candidate in enumerate(unused):
            if candidate is not None and not needed - candidate:
                unused[i] = None
                break
        else:
            return False
    return True


def answer_ok(answer: str, item: dict) -> bool:
    expected = item.get("answer_contains")
    if not expected:
        return True
    hits = [e.lower() in answer.lower() for e in expected]
    return any(hits) if item.get("answer_match") == "any" else all(hits)


@dataclass
class Outcome:
    id: str
    passed: bool
    result_ok: bool
    answer_ok: bool
    sql: str
    answer: str
    error: str | None = None
    notes: list[str] = field(default_factory=list)


def run_gold(sql: str, connect: Callable) -> list[list[Any]]:
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(sql)
        return [list(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def score(questions: list[dict], ask: Callable[[str], Any], connect: Callable) -> list[Outcome]:
    outcomes = []
    for item in questions:
        gold = run_gold(item["gold"], connect)
        response = ask(item["question"])
        result = response.query_result
        result_ok = result.success and rows_match(gold, result.data)
        text_ok = answer_ok(response.natural_language_answer, item)
        outcomes.append(Outcome(
            id=item["id"], passed=result_ok and text_ok, result_ok=result_ok, answer_ok=text_ok,
            sql=result.sql_query, answer=response.natural_language_answer, error=result.error_message,
            notes=["self-corrected after review"] if response.review and response.review.corrected_query else [],
        ))
    return outcomes


def report(outcomes: list[Outcome], min_accuracy: float) -> str:
    passed = sum(o.passed for o in outcomes)
    accuracy = passed / len(outcomes) if outcomes else 0.0
    lines = [
        f"## sql_agent evals: {passed}/{len(outcomes)} ({accuracy:.0%}), bar {min_accuracy:.0%}"
        f" - {'PASS' if accuracy >= min_accuracy else 'FAIL'}",
        "",
        "| Question | Result set | Answer text | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for o in outcomes:
        notes = "; ".join(o.notes + ([o.error] if o.error else []))
        lines.append(f"| {o.id} | {'ok' if o.result_ok else 'WRONG'} | {'ok' if o.answer_ok else 'WRONG'} | {notes} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="sql_agent execution-accuracy suite")
    parser.add_argument("--check", action="store_true", help="exit 1 when accuracy is below --min-accuracy")
    parser.add_argument("--min-accuracy", type=float, default=0.8)
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--only", action="append", help="question id to run (repeatable)")
    args = parser.parse_args(argv)

    from app.db.session import get_db_connection
    from app.services.sql_agent import NaturalLanguageToSQL, _get_langfuse

    questions = json.loads(QUESTIONS.read_text())
    if args.only:
        questions = [q for q in questions if q["id"] in args.only]
    outcomes = score(questions, NaturalLanguageToSQL().ask_question, get_db_connection)
    if langfuse := _get_langfuse():
        langfuse.flush()

    text = report(outcomes, args.min_accuracy)
    print(text, end="")
    if args.results_dir:
        args.results_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        (args.results_dir / f"sql_agent-{stamp}.json").write_text(
            json.dumps([asdict(o) for o in outcomes], indent=2)
        )
    accuracy = sum(o.passed for o in outcomes) / len(outcomes)
    return 1 if args.check and accuracy < args.min_accuracy else 0


if __name__ == "__main__":
    sys.exit(main())
