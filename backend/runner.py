"""Run the Campus Customs team over the ticket board.

    python runner.py --reset            # reset the shop, then work every open ticket
    python runner.py --ticket 101       # work one ticket
    python runner.py --full             # reset, then run + approve + close all three
    python runner.py --reset-only       # restore the database and stop

`--full` is the whole cycle a person would otherwise drive from the dashboard: the
team prepares what needs approving, the operator approves it, and the ticket is
worked again so the team can see the work done and close it. It writes
`output/full_run_record.json` for the write-ups.

Resetting copies the pristine `data/campus_customs.db` over the working copy, so
a full run always starts from the same shop. The audit trail is **not** reset: it
accumulates across runs on purpose.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sqlite3
import time
import sys
import uuid

import settings
from agents import TeamRun, run_boss
from audit import read_steps
from models import TicketOutcome


def reset_database() -> None:
    """Restore the working copy from the pristine original."""
    shutil.copyfile(settings.ORIGINAL_DB_PATH, settings.DB_PATH)
    print(f"reset {settings.DB_PATH.name} from {settings.ORIGINAL_DB_PATH.name}")


def shop_snapshot() -> dict:
    conn = sqlite3.connect(f"file:{settings.DB_PATH}?mode=ro", uri=True)
    try:
        cash = conn.execute("SELECT SUM(balance) FROM cash_accounts").fetchone()[0]
        payments = conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
        statuses = dict(conn.execute("SELECT status, COUNT(*) FROM tickets GROUP BY status"))
        open_invoices = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE status != 'paid'"
        ).fetchone()[0]
    finally:
        conn.close()
    return {
        "cash": cash,
        "payments": payments,
        "tickets": statuses,
        "open_invoices": open_invoices,
    }


def open_ticket_ids() -> list[int]:
    conn = sqlite3.connect(f"file:{settings.DB_PATH}?mode=ro", uri=True)
    try:
        return [
            r[0]
            for r in conn.execute(
                "SELECT id FROM tickets WHERE status NOT IN ('resolved','cancelled')"
                " ORDER BY created_at"
            )
        ]
    finally:
        conn.close()


OPERATOR = "Christian Roberts"
# Invoices before orders: a vendor with an open invoice will not ship, so the
# order would be refused if it were approved first.
ORDER = {"pay_invoice": 0, "pay_rent": 1, "place_restock_order": 2}


def cash_now() -> float:
    conn = sqlite3.connect(f"file:{settings.DB_PATH}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
    finally:
        conn.close()


def ticket_status(tid: int) -> str:
    conn = sqlite3.connect(f"file:{settings.DB_PATH}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT status FROM tickets WHERE id=?", (tid,)).fetchone()[0]
    finally:
        conn.close()


def steps_for(run_ids: set[str]) -> list[dict]:
    return [s for s in read_steps() if s.get("run_id") in run_ids]


async def work(tid: int) -> dict:
    import main as api  # imported here: main imports this module, so a top-level
                        # import would be circular.

    record: dict = {"ticket_id": tid, "passes": [], "approvals": [], "cash": []}
    seen_runs: set[str] = set()

    for pass_no in (1, 2):
        before = cash_now()
        print(f"\n--- ticket {tid}, pass {pass_no} (cash ${before:,.2f}) ---", flush=True)
        result = await api.run_ticket(tid)
        after_run = cash_now()
        new_runs = {s["run_id"] for s in read_steps() if s.get("ticket_id") == tid} - seen_runs
        seen_runs |= new_runs

        record["passes"].append(
            {
                "pass": pass_no,
                "outcome": result.outcome,
                "decision": result.decision,
                "reasoning": result.reasoning,
                "routed_to": result.routed_to,
                "facts_used": result.facts_used,
                "open_questions": result.open_questions,
                "drafts": [d.model_dump() for d in result.drafts],
                "steps": result.steps,
                "delegations": result.delegations,
                "tokens": result.tokens,
                "seconds": result.seconds,
                "run_ids": sorted(new_runs),
                "agent_steps": [
                    {
                        "agent": s["agent"],
                        "depth": s["depth"],
                        "parent": s.get("parent_agent"),
                        "said": s.get("output_summary"),
                        "tools": [c["tool"] for c in s.get("tool_calls", []) if c["tool"] != "final_result"],
                        "delegated_to": [d["to_agent"] for d in s.get("delegations", [])],
                        "tokens": s.get("total_tokens", 0),
                    }
                    for s in sorted(steps_for(new_runs), key=lambda x: (x["depth"], x["time"]))
                ],
            }
        )
        print(f"    outcome: {result.outcome} | agents: {result.routed_to} | {result.tokens:,} tok", flush=True)

        # Approve what the team asked for, as the human.
        pending = [p for p in api.PENDING.values() if p.status == "pending" and p.ticket_id == tid]
        pending.sort(key=lambda p: ORDER.get(p.request.action, 9))
        for item in pending:
            cash_before = cash_now()
            res = await api.approve(item.id, api.ApproveBody(approved_by=OPERATOR))
            cash_after = cash_now()
            entry = {
                "ticket_id": tid,
                "action": item.request.action,
                "amount": item.request.amount,
                "reference": item.request.reference,
                "why": item.request.why,
                "approved_by": OPERATOR,
                "charged": res["charged"],
                "refused_because": res.get("refused_because"),
                "cash_before": cash_before,
                "cash_after": cash_after,
            }
            record["approvals"].append(entry)
            mark = "CHARGED" if res["charged"] else "REFUSED"
            print(f"    {mark} {item.request.action} ${item.request.amount:,.2f} "
                  f"-> cash ${cash_after:,.2f}", flush=True)
            if not res["charged"]:
                print(f"            {res.get('refused_because')}", flush=True)

        record["cash"].append({"pass": pass_no, "before": before, "after_run": after_run, "after_approvals": cash_now()})
        record["status_after_pass"] = ticket_status(tid)
        if ticket_status(tid) in ("resolved", "cancelled"):
            print(f"    ticket {tid} is {ticket_status(tid)} — no second pass needed", flush=True)
            break

    record["final_status"] = ticket_status(tid)
    return record




TASK = (
    "Work ticket {ticket_id}. Call get_ticket_context({ticket_id}) first, then delegate to "
    "the specialists the ticket actually needs. Decide what the shop should do, record the "
    "decision on the ticket with update_ticket, and return any approval requests and drafts. "
    "Remember you cannot pay for anything yourself."
)


def _approval_key(approval) -> tuple[str, float]:
    """Identify an approval request by what it does and what it costs.

    The wording of `reference` varies — "CC-TEE-WHITE S x1" and "CC-TEE-WHITE S x1
    from Bulldog Print Co" are the same request — so the action and the amount are
    what identify it. Within a single ticket, two requests to spend the same
    amount in the same way are the same request.
    """
    return (approval.action.strip().lower(), round(float(approval.amount), 2))


def _richer(a, b):
    """Of two versions of the same request, keep the one carrying more detail."""
    score = lambda x: len(x.why) + len(x.what_it_unblocks) + len(x.if_declined) + (
        20 if x.cash_after is not None else 0
    )
    return a if score(a) >= score(b) else b


def merge_specialist_output(outcome: TicketOutcome, run: TeamRun) -> TicketOutcome:
    """Attach every specialist approval request and draft to the final outcome.

    The boss sees a compact view of each report — the figures, and draft headers
    without their bodies — so full text is not re-sent on every later boss
    request. The orchestrator kept the full objects, and merges them back here, so
    the ticket's result carries the complete drafts and the complete approval
    requests either way. Nothing is lost; it simply never travelled through the
    model twice.

    Duplicates are collapsed, because the boss may legitimately restate an item it
    wants to stand behind, and its restatement is usually the thinner one.
    """
    merged_approvals: dict[tuple[str, float], object] = {}
    for approval in [*outcome.approval_requests, *run.collected_approvals]:
        key = _approval_key(approval)
        merged_approvals[key] = (
            _richer(merged_approvals[key], approval) if key in merged_approvals else approval
        )
    outcome.approval_requests = list(merged_approvals.values())

    merged_drafts: dict[tuple[str, str], object] = {}
    for draft in [*outcome.drafts, *run.collected_drafts]:
        key = (draft.to.strip().lower(), draft.subject.strip().lower())
        existing = merged_drafts.get(key)
        # The boss only ever saw a header, so a longer body is the real draft.
        if existing is None or len(draft.body) > len(existing.body):
            merged_drafts[key] = draft
    outcome.drafts = list(merged_drafts.values())

    return outcome


async def resolve_ticket(ticket_id: int) -> tuple[TicketOutcome, TeamRun]:
    run = TeamRun(run_id=uuid.uuid4().hex[:12], ticket_id=ticket_id)
    outcome = await run_boss(run, TASK.format(ticket_id=ticket_id))
    return merge_specialist_output(outcome, run), run


def print_outcome(outcome: TicketOutcome, run: TeamRun) -> None:
    print(f"\n{'=' * 78}\nTICKET {outcome.ticket_id} — {outcome.outcome}")
    print(f"  routed to : {', '.join(a.value for a in outcome.routed_to) or '(none)'}")
    print(f"  decision  : {outcome.decision}")
    if outcome.reasoning:
        print(f"  reasoning : {outcome.reasoning}")
    for fact in outcome.facts_used:
        print(f"    fact    · {fact}")
    for req in outcome.approval_requests:
        print(
            f"  APPROVAL  · {req.action} ${req.amount:,.2f} — {req.reference}\n"
            f"              {req.why}"
        )
    for draft in outcome.drafts:
        print(f"  DRAFT     · to {draft.to}: {draft.subject}  [{draft.status}]")
    for q in outcome.open_questions:
        print(f"  QUESTION  · {q}")
    print(
        f"  agents    : {len(run.steps)} steps, {run.delegations_used} hand-offs, "
        f"{run.total_tokens:,} tokens"
    )


async def full_cycle() -> int:
    """Reset, then run, approve and close every ticket, recording the whole thing."""
    import json
    from datetime import datetime, timezone

    import main as api  # see the note in work()

    print("resetting the shop…", flush=True)
    api.reset()
    start = cash_now()
    print(f"starting checking balance: ${start:,.2f}", flush=True)

    out = {
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "operator": OPERATOR,
        "starting_balance": start,
        "tickets": [],
    }
    for tid in open_ticket_ids():
        out["tickets"].append(await work(tid))

    out["ending_balance"] = cash_now()
    conn = sqlite3.connect(f"file:{settings.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    out["payments"] = [dict(r) for r in conn.execute("SELECT * FROM payments ORDER BY id")]
    out["final_tickets"] = [
        dict(r) for r in conn.execute("SELECT id,status,notes FROM tickets ORDER BY id")
    ]
    out["drafts"] = api.DRAFTS
    conn.close()

    path = settings.AUDIT_PATH.parent / "full_run_record.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n{'=' * 70}\nstart ${start:,.2f} -> end ${out['ending_balance']:,.2f}", flush=True)
    print("statuses:", {t["id"]: t["status"] for t in out["final_tickets"]}, flush=True)
    print("record written to", path, flush=True)
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    parser.add_argument("--ticket", type=int, help="Work a single ticket id.")
    parser.add_argument("--reset", action="store_true", help="Reset the shop before running.")
    parser.add_argument("--reset-only", action="store_true", help="Reset the shop and stop.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Reset, then run, approve and close every ticket — the whole cycle.",
    )
    args = parser.parse_args()

    if args.reset_only:
        reset_database()
        print("shop:", shop_snapshot())
        return 0
    if args.full:
        return await full_cycle()
    if args.reset:
        reset_database()

    before = shop_snapshot()
    print("shop before:", before)

    ticket_ids = [args.ticket] if args.ticket else open_ticket_ids()
    if not ticket_ids:
        print("no open tickets")
        return 0

    # Tickets are independent of one another, and the gateway round trip — not
    # the token count — is what the clock is spent on. Working them concurrently
    # sends exactly the same requests with exactly the same prompts, so it costs
    # no extra tokens; it only stops each one waiting for the last to finish.
    started = time.perf_counter()
    results = await asyncio.gather(*(resolve_ticket(tid) for tid in ticket_ids))
    elapsed = time.perf_counter() - started

    total_tokens = 0
    for outcome, run in results:
        print_outcome(outcome, run)
        total_tokens += run.total_tokens

    print(f"\n{'=' * 78}")
    print("shop after :", shop_snapshot())
    print(f"tickets    : {len(ticket_ids)} worked concurrently")
    print(f"wall clock : {elapsed:.1f}s ({elapsed / 60:.1f} min)")
    print(f"tokens used: {total_tokens:,}")
    print(f"audit trail: {settings.AUDIT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
