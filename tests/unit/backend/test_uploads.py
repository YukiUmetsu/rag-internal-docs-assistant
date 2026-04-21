from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from src.backend.app.core.uploads import _insert_uploaded_file_rows


@dataclass
class _FakeResult:
    row: dict | None

    def mappings(self) -> "_FakeResult":
        return self

    def first(self) -> dict | None:
        return self.row


class _FakeConnection:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []

    def execute(self, statement, params=None):  # noqa: ANN001
        sql = str(statement)
        self.executed_sql.append(sql)

        if "FROM uploaded_files" in sql and "WHERE checksum = :checksum" in sql:
            return _FakeResult(
                {
                    "id": "upload-existing",
                    "original_filename": "existing.md",
                    "stored_path": "artifacts/uploads/upload-existing_existing.md",
                    "content_type": "text/markdown",
                    "file_size_bytes": 12,
                    "checksum": "dup-checksum",
                    "created_at": datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
                    "updated_at": datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
                }
            )

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

    def begin(self) -> _FakeBegin:
        return _FakeBegin(self.connection)


def test_insert_uploaded_file_rows_reuses_existing_checksum() -> None:
    engine = _FakeEngine()
    staged_files = [
        {
            "id": "upload-new",
            "original_filename": "new.md",
            "stored_path": "artifacts/uploads/upload-new_new.md",
            "content_type": "text/markdown",
            "file_size_bytes": 12,
            "checksum": "dup-checksum",
            "created_at": datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
            "temp_path": type("TempPath", (), {"unlink": lambda self, missing_ok=True: None})(),
            "final_path": type("FinalPath", (), {"replace": lambda self, other: None})(),
        }
    ]

    with patch("src.backend.app.core.uploads.create_engine", return_value=engine):
        rows = _insert_uploaded_file_rows("postgresql://example", staged_files)

    assert len(rows) == 1
    assert rows[0].id == "upload-existing"
    assert rows[0].original_filename == "existing.md"
    assert rows[0].checksum == "dup-checksum"
    assert not any("INSERT INTO uploaded_files" in sql for sql in engine.connection.executed_sql)


def test_insert_uploaded_file_rows_logs_context_on_failure(caplog) -> None:
    class _FailingConnection(_FakeConnection):
        def execute(self, statement, params=None):  # noqa: ANN001
            sql = str(statement)
            self.executed_sql.append(sql)
            raise SQLAlchemyError("db down")

    class _FailingEngine(_FakeEngine):
        def __init__(self) -> None:
            self.connection = _FailingConnection()

    staged_files = [
        {
            "id": "upload-new",
            "original_filename": "new.md",
            "stored_path": "artifacts/uploads/upload-new_new.md",
            "content_type": "text/markdown",
            "file_size_bytes": 12,
            "checksum": "dup-checksum",
            "created_at": datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-04-15T12:00:00+00:00"),
            "temp_path": type("TempPath", (), {"unlink": lambda self, missing_ok=True: None})(),
            "final_path": type("FinalPath", (), {"replace": lambda self, other: None})(),
        }
    ]

    with (
        patch("src.backend.app.core.uploads.create_engine", return_value=_FailingEngine()),
        caplog.at_level(logging.WARNING, logger="src.backend.app.core.uploads"),
    ):
        try:
            _insert_uploaded_file_rows("postgresql://example", staged_files)
        except RuntimeError:
            pass
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected RuntimeError")

    assert "Failed to persist uploaded file rows" in caplog.text
    assert "upload_count=1" in caplog.text
    assert "new.md" in caplog.text
