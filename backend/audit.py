"""Append-only audit trail for the agent team.

Every step of every agent loop lands in `output/audit_trail.json`. The file is
**never wiped**: it is read, the new record is added to the end, and the whole
list is written to a temporary file that atomically replaces the original, so
nothing already recorded is modified or lost. A file that will not parse is moved
aside rather than overwritten, which means a bad write cannot destroy the history
of earlier runs.

A thread lock serialises concurrent writes, because several agents can be running
at once inside one ticket.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any

from models import AuditStep
from settings import AUDIT_ARG_CHARS, AUDIT_PATH, AUDIT_RESULT_CHARS, AUDIT_TEXT_CHARS

_lock = threading.Lock()


def clip(value: Any, limit: int) -> str:
    """One-line preview of a value, for the record.

    Tool arguments and results are previews rather than full payloads: the point
    is to show what an agent did, and a complete catalogue result would bloat the
    file with data already in the database.
    """
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


clip_args = lambda v: clip(v, AUDIT_ARG_CHARS)
clip_result = lambda v: clip(v, AUDIT_RESULT_CHARS)
clip_text = lambda v: clip(v, AUDIT_TEXT_CHARS)


def append_step(step: AuditStep) -> None:
    """Append one agent loop step. Never rewrites what is already there."""
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        rows: list[dict] = []
        if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size > 0:
            try:
                loaded = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
                rows = loaded if isinstance(loaded, list) else [loaded]
            except json.JSONDecodeError:
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                AUDIT_PATH.replace(AUDIT_PATH.with_name(f"audit_trail.corrupt-{stamp}.json"))
                rows = []
        rows.append(step.model_dump(mode="json"))
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(AUDIT_PATH)


def read_steps() -> list[dict]:
    """The whole trail, for the dashboard and for inspection."""
    if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
        return []
    try:
        loaded = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return loaded if isinstance(loaded, list) else [loaded]
