from __future__ import annotations

import logging
from dataclasses import dataclass
from unittest.mock import patch

from src.backend.app.core.feedback import persist_answer_feedback, update_answer_feedback_review
from src.backend.app.core.feedback import list_answer_feedback


@dataclass
class _FakeResult:
    row: dict | list[dict] | None
    rowcount: int = 1

    def mappings(self) -> "_FakeResult":
        return self

    def first(self) -> dict | None:
        return self.row if isinstance(self.row, dict) or self.row is None else self.row[0]

    def all(self) -> list[dict]:
        if self.row is None:
            return []
        if isinstance(self.row, list):
            return self.row
        return [self.row]


class _FakeConnection:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []
        self.feedback_state: dict[str, object] = {
            "id": "feedback-123",
            "search_query_id": "request-123",
            "langsmith_run_id": "request-123",
            "request_kind": "chat",
            "question": "How do duplicate refunds work?",
            "verdict": "not_helpful",
            "reason_code": "grounding",
            "issue_category": "grounding",
            "review_status": "new",
            "comment": "Too vague",
            "reviewed_by": None,
            "reviewed_at": None,
            "promoted_eval_path": None,
            "created_at": "2026-04-20T12:00:00+00:00",
            "updated_at": "2026-04-20T12:00:00+00:00",
        }

    def execute(self, statement, params=None):  # noqa: ANN001
        sql = str(statement)
        self.executed_sql.append(sql)

        if "SELECT request_kind, question" in sql:
            return _FakeResult(
                {
                    "request_kind": "chat",
                    "question": "How do duplicate refunds work?",
                }
            )

        if "SELECT COUNT(*) AS count" in sql:
            return _FakeResult({"count": 4})

        if "ORDER BY" in sql and "CASE af.review_status" in sql:
            return _FakeResult(
                [
                    {
                        "id": "feedback-new",
                        "search_query_id": "request-new",
                        "request_kind": "chat",
                        "question": "Needs review question",
                        "verdict": "not_helpful",
                        "reason_code": "grounding",
                        "issue_category": "grounding",
                        "review_status": "new",
                        "comment_preview": "new",
                        "created_at": "2026-04-20T12:00:00+00:00",
                        "reviewed_at": None,
                    },
                    {
                        "id": "feedback-promoted",
                        "search_query_id": "request-promoted",
                        "request_kind": "chat",
                        "question": "Promoted question",
                        "verdict": "helpful",
                        "reason_code": "policy",
                        "issue_category": "policy",
                        "review_status": "promoted",
                        "comment_preview": "promoted",
                        "created_at": "2026-04-20T13:00:00+00:00",
                        "reviewed_at": "2026-04-20T14:00:00+00:00",
                    },
                    {
                        "id": "feedback-triaged",
                        "search_query_id": "request-triaged",
                        "request_kind": "chat",
                        "question": "Triaged question",
                        "verdict": "partially_helpful",
                        "reason_code": "retrieval",
                        "issue_category": "retrieval",
                        "review_status": "triaged",
                        "comment_preview": "triaged",
                        "created_at": "2026-04-20T14:00:00+00:00",
                        "reviewed_at": "2026-04-20T15:00:00+00:00",
                    },
                    {
                        "id": "feedback-ignored",
                        "search_query_id": "request-ignored",
                        "request_kind": "chat",
                        "question": "Ignored question",
                        "verdict": "not_helpful",
                        "reason_code": "other",
                        "issue_category": "other",
                        "review_status": "ignored",
                        "comment_preview": "ignored",
                        "created_at": "2026-04-20T15:00:00+00:00",
                        "reviewed_at": "2026-04-20T16:00:00+00:00",
                    },
                ]
            )

        if "FROM answer_feedback" in sql and "WHERE search_query_id = :search_query_id" in sql:
            return _FakeResult(None)

        if "FROM answer_feedback af" in sql and "comment_preview" in sql:
            row = dict(self.feedback_state)
            row["question"] = "How do duplicate refunds work?"
            row["search_query_id"] = "request-123"
            row["comment_preview"] = _preview(row.get("comment"))
            return _FakeResult(row)

        if "INSERT INTO answer_feedback" in sql:
            self.feedback_state["id"] = params["id"] if params and "id" in params else self.feedback_state["id"]
            self.feedback_state["langsmith_run_id"] = (
                params["langsmith_run_id"] if params and "langsmith_run_id" in params else self.feedback_state["langsmith_run_id"]
            )
            self.feedback_state["comment"] = params["comment"] if params and "comment" in params else self.feedback_state["comment"]
            self.feedback_state["review_status"] = (
                params["review_status"] if params and "review_status" in params else self.feedback_state["review_status"]
            )
            self.feedback_state["reviewed_by"] = params["reviewed_by"] if params and "reviewed_by" in params else self.feedback_state["reviewed_by"]
            return _FakeResult(None)

        if sql.lstrip().startswith("UPDATE answer_feedback"):
            if params:
                self.feedback_state["langsmith_run_id"] = params.get("langsmith_run_id", self.feedback_state["langsmith_run_id"])
                self.feedback_state["verdict"] = params.get("verdict", self.feedback_state["verdict"])
                self.feedback_state["reason_code"] = params.get("reason_code", self.feedback_state["reason_code"])
                self.feedback_state["issue_category"] = params.get("issue_category", self.feedback_state["issue_category"])
                self.feedback_state["comment"] = params.get("comment", self.feedback_state["comment"])
                self.feedback_state["review_status"] = params.get("review_status", self.feedback_state["review_status"])
                self.feedback_state["reviewed_by"] = params.get("reviewed_by", self.feedback_state["reviewed_by"])
                self.feedback_state["reviewed_at"] = params.get("reviewed_at", self.feedback_state["reviewed_at"])
                self.feedback_state["promoted_eval_path"] = params.get("promoted_eval_path", self.feedback_state["promoted_eval_path"])
                self.feedback_state["updated_at"] = params.get("updated_at", self.feedback_state["updated_at"])
            return _FakeResult(None, rowcount=1)

        raise AssertionError(f"Unexpected SQL: {sql}")


class _FakeBegin:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    def __enter__(self) -> _FakeConnection:
        return self._connection

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False


class _FakeEngine:
    def __init__(self) -> None:
        self.connection = _FakeConnection()

    def connect(self) -> _FakeBegin:
        return _FakeBegin(self.connection)

    def begin(self) -> _FakeBegin:
        return _FakeBegin(self.connection)


def _preview(value: object) -> object:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= 300 else text[:299] + "…"


def test_persist_answer_feedback_builds_detail_without_reload() -> None:
    engine = _FakeEngine()

    with (
        patch("src.backend.app.core.feedback.create_engine", return_value=engine),
        patch("src.backend.app.core.feedback.uuid.uuid4", return_value="feedback-123"),
    ):
        feedback = persist_answer_feedback(
            "postgresql://example",
            search_query_id="request-123",
            verdict="not_helpful",
            reason_code="grounding",
            comment="Too vague",
        )

    assert feedback is not None
    assert feedback.id == "feedback-123"
    assert feedback.search_query_id == "request-123"
    assert feedback.question == "How do duplicate refunds work?"
    assert feedback.comment_preview == "Too vague"
    assert not any(
        sql.lstrip().startswith("CREATE TABLE IF NOT EXISTS answer_feedback")
        or sql.lstrip().startswith("CREATE INDEX IF NOT EXISTS ix_answer_feedback")
        for sql in engine.connection.executed_sql
    )
    assert not any("FROM answer_feedback af" in sql for sql in engine.connection.executed_sql)


def test_update_answer_feedback_review_returns_detail() -> None:
    engine = _FakeEngine()

    with patch("src.backend.app.core.feedback.create_engine", return_value=engine):
        feedback = update_answer_feedback_review(
            "postgresql://example",
            "feedback-123",
            review_status="triaged",
            reviewed_by="reviewer@example.com",
        )

    assert feedback.id == "feedback-123"
    assert feedback.review_status == "triaged"
    assert feedback.reviewed_by == "reviewer@example.com"


def test_update_answer_feedback_review_rejects_redundant_transition() -> None:
    engine = _FakeEngine()
    engine.connection.feedback_state["review_status"] = "promoted"

    with patch("src.backend.app.core.feedback.create_engine", return_value=engine):
        try:
            update_answer_feedback_review(
                "postgresql://example",
                "feedback-123",
                review_status="promoted",
                reviewed_by="reviewer@example.com",
            )
        except ValueError as exc:
            assert "promoted to promoted" in str(exc)
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected ValueError")


def test_update_answer_feedback_review_can_move_back_to_new() -> None:
    engine = _FakeEngine()
    engine.connection.feedback_state["review_status"] = "promoted"

    with patch("src.backend.app.core.feedback.create_engine", return_value=engine):
        feedback = update_answer_feedback_review(
            "postgresql://example",
            "feedback-123",
            review_status="new",
        )

    assert feedback.review_status == "new"


def test_update_answer_feedback_review_logs_when_row_missing(caplog) -> None:
    class _MissingRowConnection(_FakeConnection):
        def execute(self, statement, params=None):  # noqa: ANN001
            sql = str(statement)
            if sql.lstrip().startswith("UPDATE answer_feedback"):
                return _FakeResult(None, rowcount=0)
            return super().execute(statement, params)

    class _MissingRowEngine(_FakeEngine):
        def __init__(self) -> None:
            self.connection = _MissingRowConnection()

    engine = _MissingRowEngine()

    with (
        patch("src.backend.app.core.feedback.create_engine", return_value=engine),
        caplog.at_level(logging.WARNING, logger="src.backend.app.core.feedback"),
    ):
        try:
            update_answer_feedback_review(
                "postgresql://example",
                "feedback-123",
                review_status="triaged",
                reviewed_by="reviewer@example.com",
            )
        except KeyError:
            pass
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected KeyError")

    assert "feedback_id=feedback-123" in caplog.text
    assert "review_status=triaged" in caplog.text
    assert "reviewed_by=reviewer@example.com" in caplog.text


def test_list_answer_feedback_orders_by_status_priority() -> None:
    engine = _FakeEngine()

    with patch("src.backend.app.core.feedback.create_engine", return_value=engine):
        items, total = list_answer_feedback("postgresql://example", limit=10, offset=0)

    assert total == 4
    assert [item.review_status for item in items] == ["new", "promoted", "triaged", "ignored"]
