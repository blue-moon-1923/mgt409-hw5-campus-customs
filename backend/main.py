"""Campus Customs operations API — the backend the React dashboard calls.

    cd backend
    uvicorn main:app --reload --port 8000

Six things the dashboard needs: the ticket board, the cash balance, a way to run
the agent team on a ticket, the stream of what the agents did, a way for a person
to approve a payment, and a reset.

**Where the money moves.** The agent team cannot pay for anything — none of the
five agents is given a payment tool. A run produces *approval requests*, which
this API holds as pending. `POST /api/approvals/{id}/approve` is the only place
in the whole system where cash actually leaves, and it only runs when a person
has clicked approve and given their name.

**No second shop-data layer.** Every shop fact and every write goes through the
Campus Customs MCP server, reached here with an in-process FastMCP client. This
module holds no SQL beyond two small read-only queries for the board and the
balance, which are reads of the same working copy.
"""

from __future__ import annotations

import asyncio
import sqlite3
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import audit
import settings
from models import ApprovalRequest, DraftMessage, TicketOutcome
from runner import open_ticket_ids, reset_database, resolve_ticket

if str(settings.MCP_DIR) not in sys.path:
    sys.path.insert(0, str(settings.MCP_DIR))

from fastmcp import Client  # noqa: E402

app = FastAPI(
    title="Campus Customs Operations",
    version="0.1.0",
    description="Ticket board, agent runs, approvals, and cash for the dashboard.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------- MCP access


async def call_shop_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call one Campus Customs MCP tool, in process.

    This is the same server, the same tools and the same guardrails the agents
    use. Paying through it rather than writing SQL here is what keeps one set of
    rules about money in one place.
    """
    from server import mcp as shop_mcp

    async with Client(shop_mcp) as client:
        result = await client.call_tool(name, arguments)
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return data
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            import json

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"ok": True, "text": text}
    return {"ok": True}


def read_only_db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{settings.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ------------------------------------------------------------- pending approvals


class PendingApproval(BaseModel):
    """An approval request waiting for a person.

    Held in memory. A restart clears the queue, which is acceptable because the
    requests are reproduced by running the ticket again, and because nothing here
    has moved money — the record of money that *did* move lives in the database.
    """

    id: str
    ticket_id: int | None
    request: ApprovalRequest
    created_at: str
    status: str = "pending"  # pending | approved | declined
    approved_by: str | None = None
    decided_at: str | None = None
    result: dict[str, Any] | None = None
    # A guardrail refusal is not a decision. It is recorded here so the dashboard
    # can show why the attempt failed, while the request stays approvable.
    last_refusal: str | None = None
    attempts: int = 0


# Rent only claims cash when it is actually coming due. A month's rent paid today
# rolls to next month and stops competing for this month's money.
RENT_HORIZON_DAYS = 7

PENDING: dict[str, PendingApproval] = {}
LAST_OUTCOMES: dict[int, TicketOutcome] = {}
DRAFTS: list[dict[str, Any]] = []


def register(outcome: TicketOutcome) -> list[PendingApproval]:
    """Turn a run's approval requests into items a person can click."""
    created: list[PendingApproval] = []
    for request in outcome.approval_requests:
        item = PendingApproval(
            id=uuid.uuid4().hex[:10],
            ticket_id=outcome.ticket_id,
            request=request,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        PENDING[item.id] = item
        created.append(item)
    for draft in outcome.drafts:
        DRAFTS.append({"ticket_id": outcome.ticket_id, **draft.model_dump()})
    LAST_OUTCOMES[outcome.ticket_id] = outcome
    return created


# --------------------------------------------------------------------- routes


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "database": settings.DB_PATH.name,
        "model": settings.MODEL_NAME,
        "pending_approvals": sum(1 for p in PENDING.values() if p.status == "pending"),
    }


@app.get("/api/tickets")
def get_tickets() -> dict[str, Any]:
    """The ticket board: every ticket, and whether it is still open."""
    conn = read_only_db()
    try:
        today = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()["date_today"]
        rows = conn.execute("SELECT * FROM tickets ORDER BY created_at").fetchall()
    finally:
        conn.close()

    tickets = []
    for r in rows:
        resolved = r["status"] in ("resolved", "cancelled")
        tickets.append(
            {
                "id": r["id"],
                "type": r["type"],
                "requester": r["requester"],
                "subject": r["subject"],
                "sku": r["sku"],
                "size": r["size"],
                "qty": r["qty"],
                "lease_id": r["lease_id"],
                "invoice_id": r["invoice_id"],
                "status": r["status"],
                "is_open": not resolved,
                "is_resolved": resolved,
                "notes": r["notes"],
                "has_outcome": r["id"] in LAST_OUTCOMES,
            }
        )
    return {"shop_date": today, "count": len(tickets), "tickets": tickets}


@app.get("/api/cash")
def get_cash() -> dict[str, Any]:
    """The checking balance, and what is still claiming it."""
    conn = read_only_db()
    try:
        accounts = [dict(r) for r in conn.execute("SELECT * FROM cash_accounts ORDER BY name")]
        checking = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name = 'checking'"
        ).fetchone()
        payments = [dict(r) for r in conn.execute("SELECT * FROM payments ORDER BY id DESC")]
        owed = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM invoices WHERE status != 'paid'"
        ).fetchone()[0]
        # Only rent that is actually coming due counts as a commitment. Paying
        # rent rolls `next_due` forward a month, so without this window a paid
        # lease would keep claiming the same $2,400 and the room left would go
        # negative the moment the rent was settled.
        rent = conn.execute(
            "SELECT COALESCE(SUM(monthly_rent), 0) FROM leases"
            " WHERE julianday(next_due) - julianday((SELECT date_today FROM desk))"
            f" <= {RENT_HORIZON_DAYS}"
        ).fetchone()[0]
    finally:
        conn.close()

    balance = checking["balance"] if checking else 0.0
    return {
        "checking_balance": balance,
        "accounts": accounts,
        "open_invoice_total": owed,
        "rent_due_total": rent,
        "total_committed": round(owed + rent, 2),
        "after_commitments": round(balance - owed - rent, 2),
        "payments": payments,
        "rent_horizon_days": RENT_HORIZON_DAYS,
        "note": (
            "Cash only goes out in this shop; no revenue is modelled. Rent counts as "
            f"committed only when it falls due within {RENT_HORIZON_DAYS} days."
        ),
    }


class RunResponse(BaseModel):
    ticket_id: int
    outcome: str
    decision: str
    reasoning: str
    routed_to: list[str]
    facts_used: list[str]
    approval_requests: list[dict[str, Any]]
    drafts: list[DraftMessage]
    open_questions: list[str]
    steps: int
    delegations: int
    tokens: int
    seconds: float


@app.post("/api/tickets/{ticket_id}/run", response_model=RunResponse)
async def run_ticket(ticket_id: int) -> RunResponse:
    """Run the agent team on one ticket.

    The team reads the shop, delegates between its specialists, records what it
    did on the ticket, and returns a decision. It pays for nothing: anything that
    costs money comes back as an approval request for a person to act on.
    """
    conn = read_only_db()
    try:
        exists = conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    finally:
        conn.close()
    if exists is None:
        raise HTTPException(status_code=404, detail=f"No ticket with id {ticket_id}.")

    started = asyncio.get_event_loop().time()
    outcome, run = await resolve_ticket(ticket_id)
    elapsed = asyncio.get_event_loop().time() - started
    created = register(outcome)

    return RunResponse(
        ticket_id=outcome.ticket_id,
        outcome=outcome.outcome,
        decision=outcome.decision,
        reasoning=outcome.reasoning,
        routed_to=[a.value for a in outcome.routed_to],
        facts_used=outcome.facts_used,
        approval_requests=[
            {"approval_id": item.id, **item.request.model_dump()} for item in created
        ],
        drafts=outcome.drafts,
        open_questions=outcome.open_questions,
        steps=len(run.steps),
        delegations=run.delegations_used,
        tokens=run.total_tokens,
        seconds=round(elapsed, 1),
    )


@app.get("/api/events")
def get_events(limit: int = 40, ticket_id: int | None = None) -> dict[str, Any]:
    """Recent agent activity, newest first — what each agent did and said.

    Read straight from the append-only audit trail, so the board shows the same
    record a person would audit later rather than a separate display log.
    """
    steps = audit.read_steps()
    if ticket_id is not None:
        steps = [s for s in steps if s.get("ticket_id") == ticket_id]
    recent = list(reversed(steps))[: max(1, min(limit, 200))]

    events = [
        {
            "step_id": s.get("step_id"),
            "run_id": s.get("run_id"),
            "time": s.get("time"),
            "ticket_id": s.get("ticket_id"),
            "agent": s.get("agent"),
            "depth": s.get("depth"),
            "parent_agent": s.get("parent_agent"),
            "task": s.get("task"),
            "said": s.get("output_summary"),
            "tools_used": s.get("tools_used", []),
            "tool_calls": [
                {
                    "tool": c.get("tool"),
                    "args": c.get("args"),
                    "result": c.get("result"),
                    "refused": c.get("refused", False),
                }
                for c in s.get("tool_calls", [])
            ],
            "delegated_to": [d.get("to_agent") for d in s.get("delegations", [])],
            "approval_requests": s.get("approval_requests", 0),
            "drafts": s.get("drafts", 0),
            "tokens": s.get("total_tokens", 0),
            "model_requests": s.get("model_requests", 0),
            "duration_ms": s.get("duration_ms", 0),
            "status": s.get("status"),
            "stop_reason": s.get("stop_reason"),
        }
        for s in recent
    ]
    return {"count": len(events), "total_recorded": len(steps), "events": events}


@app.get("/api/approvals")
def list_approvals() -> dict[str, Any]:
    """Everything waiting on a person, plus what has already been decided."""
    items = sorted(PENDING.values(), key=lambda p: p.created_at, reverse=True)
    return {
        "pending": [p.model_dump() for p in items if p.status == "pending"],
        "decided": [p.model_dump() for p in items if p.status != "pending"],
        "drafts": DRAFTS,
    }


class ApproveBody(BaseModel):
    approved_by: str = Field(min_length=1, description="The name of the person approving.")


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: str, body: ApproveBody) -> dict[str, Any]:
    """Approve a payment or purchase, and charge it.

    **This is the only route in the system that moves money.** The agents prepared
    the request; nothing left the account until a person called this with their
    name. The spend itself is executed by the MCP server's payment tools, which
    refuse an empty approver, refuse an agent's name, and refuse to take an
    account below zero — so a refusal here is reported, not overridden.
    """
    item = PENDING.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail="No approval request with that id.")
    if item.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"That request was already {item.status}."
        )

    request = item.request
    action = request.action.strip().lower()
    approver = body.approved_by.strip()

    # A ticket can legitimately be run twice — the second pass lets the team see
    # work the human approved and close the ticket. What must not happen is the
    # same spend being charged twice because the second pass proposed it again.
    # The MCP server refuses a duplicate as well; this stops it before it is even
    # attempted, so the dashboard can say why.
    twin = next(
        (
            p
            for p in PENDING.values()
            if p.id != approval_id
            and p.status == "approved"
            and p.ticket_id == item.ticket_id
            and p.request.action.strip().lower() == action
            and round(p.request.amount, 2) == round(request.amount, 2)
        ),
        None,
    )
    if twin is not None:
        item.last_refusal = (
            f"An identical {action} of ${request.amount:,.2f} was already approved for "
            f"ticket {item.ticket_id} by {twin.approved_by}. Nothing was charged again."
        )
        item.attempts += 1
        return {
            "approval_id": approval_id,
            "status": "pending",
            "charged": False,
            "approved_by": None,
            "refused_because": item.last_refusal,
            "attempts": item.attempts,
            "result": {"ok": False, "refused": True, "reason": item.last_refusal},
            "cash": get_cash()["checking_balance"],
        }

    if action == "pay_invoice":
        ref = _first_int(request.reference)
        if ref is None:
            raise HTTPException(status_code=400, detail="No invoice id in the request.")
        result = await call_shop_tool("pay_invoice", {"invoice_id": ref, "approved_by": approver})
    elif action == "pay_rent":
        ref = _first_int(request.reference)
        if ref is None:
            raise HTTPException(status_code=400, detail="No lease id in the request.")
        result = await call_shop_tool("pay_rent", {"lease_id": ref, "approved_by": approver})
    elif action == "place_restock_order":
        details = request.order or {}
        missing = [k for k in ("sku", "size", "qty", "vendor_id") if not details.get(k)]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"The restock request is missing {', '.join(missing)}.",
            )
        result = await call_shop_tool(
            "place_restock_order",
            {
                "sku": details["sku"],
                "size": details["size"],
                "qty": int(details["qty"]),
                "vendor_id": int(details["vendor_id"]),
                "approved_by": approver,
            },
        )
    else:
        raise HTTPException(status_code=400, detail=f"Cannot action '{request.action}'.")

    item.attempts += 1
    item.result = result

    if result.get("ok"):
        item.status = "approved"
        item.approved_by = approver
        item.decided_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        item.last_refusal = None
    else:
        # The MCP server refused — no approver named, an agent naming itself, not
        # enough cash, a vendor still blocked. Nothing was written to the shop, so
        # the request must stay pending: a refusal means "not like this", not
        # "never". Burning the request here would leave a legitimate payment
        # permanently unapprovable.
        item.status = "pending"
        item.last_refusal = result.get("reason", "The payment tool refused the request.")

    return {
        "approval_id": approval_id,
        "status": item.status,
        "charged": bool(result.get("ok")),
        "approved_by": item.approved_by,
        "refused_because": item.last_refusal,
        "attempts": item.attempts,
        "result": result,
        "cash": get_cash()["checking_balance"],
    }


@app.post("/api/approvals/{approval_id}/decline")
def decline(approval_id: str, body: ApproveBody) -> dict[str, Any]:
    """Decline a request. Nothing is charged and nothing is written to the shop."""
    item = PENDING.get(approval_id)
    if item is None:
        raise HTTPException(status_code=404, detail="No approval request with that id.")
    if item.status != "pending":
        raise HTTPException(status_code=409, detail=f"That request was already {item.status}.")
    item.status = "declined"
    item.approved_by = body.approved_by.strip()
    item.decided_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {"approval_id": approval_id, "status": "declined"}


@app.post("/api/reset")
def reset() -> dict[str, Any]:
    """Restore the shop to its original state for a fresh run.

    Copies the pristine `campus_customs.db` over the working copy and clears the
    pending-approval queue. The audit trail is **not** cleared: it is append-only
    across runs by design, so the history of what the agents did survives a reset
    of the shop they did it to.
    """
    reset_database()
    PENDING.clear()
    LAST_OUTCOMES.clear()
    DRAFTS.clear()
    return {
        "ok": True,
        "reset": settings.DB_PATH.name,
        "from": settings.ORIGINAL_DB_PATH.name,
        "cash": get_cash()["checking_balance"],
        "open_tickets": open_ticket_ids(),
        "audit_trail": "left intact — it is append-only across runs",
    }


def _first_int(text: str) -> int | None:
    """Pull the first whole number out of a reference like 'invoice 501'."""
    digits = ""
    for ch in text:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    return int(digits) if digits else None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
