"""Campus Customs MCP server.

The single place every agent in this homework reads shop data from. It exposes
the Campus Customs database as a small set of tools, so no agent ever writes SQL
and no agent can reach a table a tool does not expose.

Three rules hold everywhere in this file:

1. **Only what is in the database.** Every number returned is a column value or
   arithmetic over column values. Nothing is estimated, assumed, or filled in.
2. **`desk.date_today` is the clock.** Overdue, due-in, and arrival dates are all
   computed from the shop's date, never from the real one, so a run on any day
   reaches the same conclusions about the same data.
3. **Reads are read-only.** The six reading tools open the database read-only and
   cannot change anything. The three writing tools open a separate read-write
   connection and each enforces its own guardrail before it touches a row.
4. **Money needs a human.** Every tool that moves cash refuses unless a human
   approver is named, refuses if an agent tries to name itself, and refuses if the
   payment would take an account below zero.

Database: ../data/campus_customs_new.db (the working copy; the original is never
touched, so a run can always be reset by copying it back).
"""

from __future__ import annotations

import sqlite3
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"

mcp = FastMCP("campus-customs")

# Agents may propose a payment; only a person may approve one. These names are
# refused as approvers so an agent cannot sign its own cheque, which is the one
# guardrail that cannot be left to a prompt.
AGENT_NAMES = {
    "boss",
    "inventory",
    "accounting",
    "facilities",
    "customer_service",
    "agent",
    "assistant",
    "ai",
    "system",
    "campus customs",
}

TICKET_STATUSES = {"open", "in_progress", "blocked", "resolved", "cancelled"}

# The database has no product-category column, so a vendor's `specialty` text has
# to be matched against the kind of product a SKU is. The SKU's middle token is
# that kind: CC-TEE-WHITE is a TEE. This mapping is an interpretation of the data
# rather than a column in it, which is why it lives here in the open, is reported
# back as `match_reason`, and never silently drops a vendor from the results.
SKU_KIND_TO_SPECIALTY = {
    "TEE": "apparel",
    "HOOD": "apparel",
    "MUG": "mugs and small goods",
    "HAT": "mugs and small goods",
}
# A courier moves goods; it does not make them. Named explicitly so the reason a
# courier is excluded from a restock is visible rather than implied.
COURIER_KEYWORD = "courier"


def _connect_rw() -> sqlite3.Connection:
    """Open the working copy for writing. Only the three write tools use this."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}.")
    # Tickets are worked concurrently, so two agents can reach a write at the same
    # moment. The timeout makes the second one wait for the first rather than
    # failing with "database is locked".
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def _refuse(reason: str, **extra: Any) -> dict[str, Any]:
    """A refusal is a result, not an exception: the agent must see why."""
    return {"ok": False, "refused": True, "reason": reason, **extra}


def _check_human_approver(approved_by: str) -> dict[str, Any] | None:
    """Reject a missing approver, or an agent trying to approve its own request."""
    name = (approved_by or "").strip()
    if not name:
        return _refuse(
            "No approver named. Every payment in this shop needs a named human "
            "approval. Return an approval request to the human instead of paying."
        )
    if name.lower() in AGENT_NAMES:
        return _refuse(
            f"'{name}' is an agent, not a person. An agent may not approve its own "
            "payment. Return an approval request to the human instead."
        )
    return None


def _already_spent_today(
    conn: sqlite3.Connection, kind: str, ref_id: int, amount: float, today: str
) -> sqlite3.Row | None:
    """Has this exact spend already gone through on the shop's date?

    Re-running a ticket is normal — a second pass lets the team see work the human
    approved and close the ticket. What is not normal is paying for the same thing
    twice because the second pass could not tell the first one had happened.

    Keyed on kind, reference and amount within one shop day, which is the
    strongest statement this schema supports: `payments` has no ticket column, so
    a "same ticket" test is not available. Same thing, same amount, same day is
    the duplicate a re-run produces.
    """
    return conn.execute(
        "SELECT * FROM payments WHERE kind = ? AND ref_id = ? AND amount = ? AND paid_at = ?"
        " ORDER BY id LIMIT 1",
        (kind, ref_id, amount, today),
    ).fetchone()


def _add_one_month(d: date) -> date:
    """Advance to the same day next month, clamping to the month's length."""
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    last = monthrange(year, month)[1]
    return date(year, month, min(d.day, last))


def _connect() -> sqlite3.Connection:
    """Open the working copy read-only."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Copy data/campus_customs.db to "
            "data/campus_customs_new.db first."
        )
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _shop_today(conn: sqlite3.Connection) -> date:
    """The shop's date from `desk.date_today`. The only clock any tool may use."""
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    if row is None:
        raise ValueError("The desk table is empty; the shop has no date.")
    return date.fromisoformat(row["date_today"])


def _days_between(earlier: date, later: date) -> int:
    return (later - earlier).days


def _sku_kind(sku: str) -> str:
    """The middle token of a SKU, e.g. CC-TEE-WHITE -> TEE."""
    parts = sku.upper().split("-")
    return parts[1] if len(parts) > 2 else ""


@mcp.tool
def get_ticket_context(ticket_id: int) -> dict[str, Any]:
    """Read one ticket and every record it is linked to, in a single call.

    Returns the ticket itself plus whichever of these it points at: the inventory
    row for its SKU and size, the pricing row for its SKU, the invoice it is tied
    to together with the vendor who issued it, and the lease it concerns. Also
    returns the shop's date from the desk, so the caller never has to ask for it
    separately or reach for the real calendar.

    Use this first on any ticket. It is what tells you which specialist the work
    belongs to and what the ticket is actually about.

    Args:
        ticket_id: The id from the tickets table, e.g. 101.
    """
    with _connect() as conn:
        today = _shop_today(conn)
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return {"found": False, "ticket_id": ticket_id, "error": "No ticket with that id."}

        result: dict[str, Any] = {
            "found": True,
            "shop_date": today.isoformat(),
            "ticket": dict(ticket),
            "linked": {},
        }
        linked = result["linked"]

        if ticket["sku"]:
            if ticket["size"]:
                stock = conn.execute(
                    "SELECT * FROM inventory WHERE sku = ? AND size = ?",
                    (ticket["sku"], ticket["size"]),
                ).fetchone()
                linked["inventory"] = dict(stock) if stock else None
            price = conn.execute(
                "SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],)
            ).fetchone()
            if price:
                linked["pricing"] = {
                    **dict(price),
                    "margin_per_unit": round(price["list_price"] - price["unit_cost"], 2),
                }

        if ticket["invoice_id"]:
            invoice = conn.execute(
                "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],)
            ).fetchone()
            if invoice:
                due = date.fromisoformat(invoice["due_date"])
                vendor = conn.execute(
                    "SELECT * FROM vendors WHERE id = ?", (invoice["vendor_id"],)
                ).fetchone()
                linked["invoice"] = {
                    **dict(invoice),
                    "days_overdue": max(0, _days_between(due, today)),
                    "is_overdue": today > due and invoice["status"] != "paid",
                    "vendor": dict(vendor) if vendor else None,
                }

        if ticket["lease_id"]:
            lease = conn.execute(
                "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)
            ).fetchone()
            if lease:
                nxt = date.fromisoformat(lease["next_due"])
                linked["lease"] = {
                    **dict(lease),
                    "days_until_due": _days_between(today, nxt),
                    "is_overdue": today > nxt,
                }

        # What has already been done about this ticket.
        #
        # A ticket can be worked more than once: the first pass prepares what needs
        # approving, a person approves it, and a second pass closes the ticket. The
        # second pass is blind without this — it cannot tell whether the invoice was
        # settled or the order placed, so it proposes the same spend again and leaves
        # the ticket blocked on work that is already finished.
        done: list[dict[str, Any]] = []
        if ticket["invoice_id"]:
            for row in conn.execute(
                "SELECT * FROM payments WHERE kind = 'invoice' AND ref_id = ?",
                (ticket["invoice_id"],),
            ):
                done.append(
                    {
                        "what": f"Invoice {row['ref_id']} paid",
                        "amount": row["amount"],
                        "paid_at": row["paid_at"],
                        "approved_by": row["approved_by"],
                    }
                )
        if ticket["lease_id"]:
            for row in conn.execute(
                "SELECT * FROM payments WHERE kind = 'rent' AND ref_id = ?",
                (ticket["lease_id"],),
            ):
                done.append(
                    {
                        "what": f"Rent paid on lease {row['ref_id']}",
                        "amount": row["amount"],
                        "paid_at": row["paid_at"],
                        "approved_by": row["approved_by"],
                    }
                )
        for row in conn.execute(
            "SELECT * FROM payments WHERE kind = 'purchase_order' AND paid_at = ?",
            (today.isoformat(),),
        ):
            vendor = conn.execute(
                "SELECT name, lead_days FROM vendors WHERE id = ?", (row["ref_id"],)
            ).fetchone()
            arrives = (today + timedelta(days=vendor["lead_days"])).isoformat() if vendor else None
            done.append(
                {
                    "what": f"Order placed with {vendor['name'] if vendor else row['ref_id']}",
                    "amount": row["amount"],
                    "paid_at": row["paid_at"],
                    "approved_by": row["approved_by"],
                    "expected_arrival": arrives,
                }
            )

        result["work_already_done"] = done
        result["note"] = (
            "Nothing has been paid or ordered for this ticket yet."
            if not done
            else (
                f"{len(done)} action(s) have already been approved and paid for. Do not ask "
                "for the same money again — if the work is done, say so and close the ticket."
            )
        )

    return result


@mcp.tool
def check_stock_and_restock_options(sku: str, size: str, qty_needed: int) -> dict[str, Any]:
    """Check whether a SKU and size can be supplied now, and if not, who can restock it.

    Reports the quantity on hand for that exact SKU and size, the shortfall against
    the quantity requested, and the other sizes of the same SKU that do have stock.
    When there is a shortfall it also lists every vendor, each marked with whether
    it can make this kind of product, whether it is currently blocked by an unpaid
    invoice, its lead time, and the arrival date that lead time implies from the
    shop's date. Vendors are never silently dropped — each carries the reason it
    does or does not qualify.

    The restock cost is the shortfall multiplied by the SKU's unit cost from the
    pricing table.

    Args:
        sku: Product code, e.g. CC-TEE-WHITE.
        size: Size code, e.g. S. Stock is held per size, so this is required.
        qty_needed: How many the ticket asks for.
    """
    with _connect() as conn:
        today = _shop_today(conn)

        stock = conn.execute(
            "SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        on_hand = stock["qty"] if stock else 0
        shortfall = max(0, qty_needed - on_hand)

        other_sizes = [
            {"size": r["size"], "qty": r["qty"]}
            for r in conn.execute(
                "SELECT size, qty FROM inventory WHERE sku = ? AND size != ? AND qty > 0"
                " ORDER BY size",
                (sku, size),
            )
        ]

        price = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
        unit_cost = price["unit_cost"] if price else None

        result: dict[str, Any] = {
            "shop_date": today.isoformat(),
            "sku": sku,
            "size": size,
            "product_name": stock["name"] if stock else None,
            "location": stock["location"] if stock else None,
            "qty_on_hand": on_hand,
            "qty_needed": qty_needed,
            "shortfall": shortfall,
            "can_fulfil_now": shortfall == 0,
            "other_sizes_in_stock": other_sizes,
            "unit_cost": unit_cost,
            "restock_cost": round(shortfall * unit_cost, 2) if unit_cost is not None else None,
            "vendors": [],
        }
        if stock is None:
            result["note"] = (
                f"No inventory row exists for {sku} in size {size}; treating on hand as 0."
            )
        if shortfall == 0:
            result["note"] = "No shortfall. No restock is needed."
            return result

        wanted_specialty = SKU_KIND_TO_SPECIALTY.get(_sku_kind(sku))
        unpaid = {
            r["vendor_id"]: r
            for r in conn.execute(
                "SELECT id, vendor_id, amount, due_date, status FROM invoices"
                " WHERE status != 'paid'"
            )
        }

        for vendor in conn.execute("SELECT * FROM vendors ORDER BY id"):
            is_courier = COURIER_KEYWORD in vendor["specialty"].lower()
            makes_this = (
                wanted_specialty is not None
                and wanted_specialty in vendor["specialty"].lower()
                and not is_courier
            )
            blocker = unpaid.get(vendor["id"])
            arrival = today + timedelta(days=vendor["lead_days"])

            if is_courier:
                reason = "Courier — delivers goods, does not make them."
            elif makes_this:
                reason = f"Specialty '{vendor['specialty']}' covers this product."
            else:
                reason = (
                    f"Specialty '{vendor['specialty']}' does not cover this product"
                    + (f" (needs {wanted_specialty})." if wanted_specialty else ".")
                )

            entry: dict[str, Any] = {
                "vendor_id": vendor["id"],
                "name": vendor["name"],
                "specialty": vendor["specialty"],
                "can_make_this_product": makes_this,
                "match_reason": reason,
                "lead_days": vendor["lead_days"],
                "earliest_arrival": arrival.isoformat(),
                "blocked_by_unpaid_invoice": blocker is not None,
            }
            if blocker is not None:
                entry["blocking_invoice"] = {
                    "id": blocker["id"],
                    "amount": blocker["amount"],
                    "due_date": blocker["due_date"],
                    "status": blocker["status"],
                }
                entry["blocked_reason"] = (
                    f"Invoice {blocker['id']} for ${blocker['amount']:,.2f} is "
                    f"{blocker['status']}. This vendor will not ship until it is paid."
                )
            entry["usable_now"] = makes_this and blocker is None
            result["vendors"].append(entry)

        usable = [v for v in result["vendors"] if v["usable_now"]]
        capable = [v for v in result["vendors"] if v["can_make_this_product"]]
        if usable:
            result["note"] = f"{len(usable)} vendor(s) can restock this now."
        elif capable:
            result["note"] = (
                "The only vendor(s) who can make this product are blocked by an unpaid "
                "invoice. The invoice has to be settled before a restock can be ordered."
            )
        else:
            result["note"] = "No vendor on file makes this kind of product."

    return result


@mcp.tool
def get_cash_position() -> dict[str, Any]:
    """Report cash on hand and everything currently claiming it.

    Returns each cash account's balance, every invoice that is not yet paid with
    how many days overdue it is, and every lease with its rent and how many days
    until it falls due — all measured from the shop's date. Finishes with the
    total owed and whether the cash on hand covers it.

    Cash only leaves in this shop; no revenue is modelled. Use this before
    proposing any payment, because the balance it reports is the ceiling on what
    the team can commit to.
    """
    with _connect() as conn:
        today = _shop_today(conn)

        accounts = [dict(r) for r in conn.execute("SELECT * FROM cash_accounts ORDER BY name")]
        total_cash = round(sum(a["balance"] for a in accounts), 2)

        open_invoices = []
        for r in conn.execute("SELECT * FROM invoices WHERE status != 'paid' ORDER BY due_date"):
            due = date.fromisoformat(r["due_date"])
            vendor = conn.execute(
                "SELECT name FROM vendors WHERE id = ?", (r["vendor_id"],)
            ).fetchone()
            open_invoices.append(
                {
                    "id": r["id"],
                    "vendor_id": r["vendor_id"],
                    "vendor_name": vendor["name"] if vendor else None,
                    "amount": r["amount"],
                    "due_date": r["due_date"],
                    "status": r["status"],
                    "description": r["description"],
                    "days_overdue": max(0, _days_between(due, today)),
                    "is_overdue": today > due,
                }
            )

        leases = []
        for r in conn.execute("SELECT * FROM leases ORDER BY next_due"):
            nxt = date.fromisoformat(r["next_due"])
            leases.append(
                {
                    "id": r["id"],
                    "space_name": r["space_name"],
                    "landlord": r["landlord"],
                    "monthly_rent": r["monthly_rent"],
                    "next_due": r["next_due"],
                    "days_until_due": _days_between(today, nxt),
                    "is_overdue": today > nxt,
                }
            )

        payments_made = [dict(r) for r in conn.execute("SELECT * FROM payments ORDER BY id")]

    invoice_total = round(sum(i["amount"] for i in open_invoices), 2)
    rent_total = round(sum(l["monthly_rent"] for l in leases), 2)
    committed = round(invoice_total + rent_total, 2)

    return {
        "shop_date": today.isoformat(),
        "accounts": accounts,
        "total_cash": total_cash,
        "open_invoices": open_invoices,
        "open_invoice_total": invoice_total,
        "leases": leases,
        "rent_due_total": rent_total,
        "total_committed": committed,
        "cash_after_all_commitments": round(total_cash - committed, 2),
        "covers_all_commitments": total_cash >= committed,
        "payments_recorded": payments_made,
        "note": (
            "Cash only goes out in this shop; no revenue is modelled, so this balance "
            "can only fall. Any payment needs human approval and must not take an "
            "account below zero."
        ),
    }


@mcp.tool
def list_open_tickets() -> dict[str, Any]:
    """List every ticket that is not yet resolved, with the shop's date.

    Each entry carries the ticket's type, requester, subject, the product line if
    it has one, and which lease or invoice it points at. This is the work queue —
    read it first to see what the shop has been asked to do.
    """
    with _connect() as conn:
        today = _shop_today(conn)
        rows = conn.execute(
            "SELECT * FROM tickets WHERE status NOT IN ('resolved','cancelled')"
            " ORDER BY created_at"
        ).fetchall()
    return {
        "shop_date": today.isoformat(),
        "count": len(rows),
        "tickets": [
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
                "notes": r["notes"],
            }
            for r in rows
        ],
    }


@mcp.tool
def quote_bulk_price(sku: str, qty: int, proposed_unit_price: float | None = None) -> dict[str, Any]:
    """Price a bulk order against the shop's own cost and list price.

    Returns the list price, the unit cost, the margin per unit at list, and what
    the whole order is worth at list. If a proposed unit price is given it also
    returns the discount that implies, the margin per unit at that price, the
    total margin on the order, and whether the price falls below cost.

    Use this before agreeing any discount. The floor is `unit_cost`: below it the
    shop loses money on every item sold.

    Args:
        sku: Product code, e.g. CC-HOOD-NAVY.
        qty: How many units the customer wants.
        proposed_unit_price: Optional price per unit being considered.
    """
    with _connect() as conn:
        price = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return _refuse(f"No pricing row for {sku}; the shop has no cost for this product.")
        name_row = conn.execute(
            "SELECT name FROM inventory WHERE sku = ? LIMIT 1", (sku,)
        ).fetchone()

    unit_cost, list_price = price["unit_cost"], price["list_price"]
    out: dict[str, Any] = {
        "ok": True,
        "sku": sku,
        "product_name": name_row["name"] if name_row else None,
        "qty": qty,
        "unit_cost": unit_cost,
        "list_price": list_price,
        "margin_per_unit_at_list": round(list_price - unit_cost, 2),
        "order_value_at_list": round(list_price * qty, 2),
        "order_margin_at_list": round((list_price - unit_cost) * qty, 2),
        "floor_unit_price": unit_cost,
    }
    if proposed_unit_price is not None:
        margin = round(proposed_unit_price - unit_cost, 2)
        out.update(
            {
                "proposed_unit_price": proposed_unit_price,
                "discount_per_unit": round(list_price - proposed_unit_price, 2),
                "discount_pct": round((list_price - proposed_unit_price) / list_price * 100, 1),
                "margin_per_unit_at_proposed": margin,
                "order_margin_at_proposed": round(margin * qty, 2),
                "below_cost": proposed_unit_price < unit_cost,
                "margin_given_up_vs_list": round(
                    (list_price - proposed_unit_price) * qty, 2
                ),
            }
        )
        if proposed_unit_price < unit_cost:
            out["warning"] = (
                f"${proposed_unit_price:,.2f} is below the ${unit_cost:,.2f} unit cost. "
                "The shop loses money on every unit at this price."
            )
    return out


@mcp.tool
def update_ticket(ticket_id: int, status: str, note: str) -> dict[str, Any]:
    """Move a ticket to a new status and append a note explaining why.

    This is how work is recorded. It does not move money and needs no approval,
    but the note is the record a person will read later, so say what was decided
    and what it rests on.

    Args:
        ticket_id: The ticket to update.
        status: One of open, in_progress, blocked, resolved, cancelled.
        note: A sentence or two on what changed and why. Required.
    """
    status = status.strip().lower()
    if status not in TICKET_STATUSES:
        return _refuse(
            f"'{status}' is not a ticket status. Use one of: {', '.join(sorted(TICKET_STATUSES))}."
        )
    if not (note or "").strip():
        return _refuse("A note is required so the change can be audited later.")

    conn = _connect_rw()
    try:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return _refuse(f"No ticket with id {ticket_id}.")
        today = _shop_today(conn).isoformat()
        stamped = f"[{today}] {note.strip()}"
        notes = f"{row['notes']}\n{stamped}" if row["notes"] else stamped
        conn.execute(
            "UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id)
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "status_before": row["status"],
        "status_after": status,
        "note_appended": stamped,
    }


@mcp.tool
def pay_invoice(invoice_id: int, approved_by: str) -> dict[str, Any]:
    """Pay a supplier invoice in full. Requires a named human approver.

    Refuses if no human approver is named, if an agent names itself, if the
    invoice is already paid, or if the cash balance would go below zero. On
    success it writes a row to payments, marks the invoice paid, and reduces the
    cash balance — all three, so the books stay consistent.

    Paying a vendor's open invoice is also what unblocks that vendor: they will
    not ship new product while an invoice is outstanding.

    Args:
        invoice_id: The invoice to settle.
        approved_by: The name of the person who approved this payment. An agent
            name is refused.
    """
    blocked = _check_human_approver(approved_by)
    if blocked:
        return blocked

    conn = _connect_rw()
    try:
        inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if inv is None:
            return _refuse(f"No invoice with id {invoice_id}.")
        if inv["status"] == "paid":
            return _refuse(f"Invoice {invoice_id} is already paid.", already_paid=True)

        acct = conn.execute(
            "SELECT * FROM cash_accounts ORDER BY balance DESC LIMIT 1"
        ).fetchone()
        if acct is None:
            return _refuse("No cash account exists.")
        if acct["balance"] < inv["amount"]:
            return _refuse(
                f"Not enough cash. Invoice {invoice_id} is ${inv['amount']:,.2f} and "
                f"'{acct['name']}' holds ${acct['balance']:,.2f}. This shop never goes "
                "below zero, so the payment was not made.",
                shortfall=round(inv["amount"] - acct["balance"], 2),
                balance=acct["balance"],
            )

        today = _shop_today(conn).isoformat()
        new_balance = round(acct["balance"] - inv["amount"], 2)
        conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("invoice", invoice_id, inv["amount"], acct["name"], today, approved_by.strip()),
        )
        payment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (invoice_id,))
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, today, acct["name"]),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "payment_id": payment_id,
        "kind": "invoice",
        "invoice_id": invoice_id,
        "amount": inv["amount"],
        "account": acct["name"],
        "balance_before": acct["balance"],
        "balance_after": new_balance,
        "paid_at": today,
        "approved_by": approved_by.strip(),
        "invoice_status_after": "paid",
        "effect": f"Vendor {inv['vendor_id']} is no longer blocked by this invoice.",
    }


@mcp.tool
def pay_rent(lease_id: int, approved_by: str) -> dict[str, Any]:
    """Pay one month's rent on a lease. Requires a named human approver.

    Refuses on the same terms as paying an invoice. On success it writes a
    payments row, reduces the cash balance, and advances the lease's next_due by
    one month so the same rent cannot be paid twice.

    Args:
        lease_id: The lease to pay.
        approved_by: The name of the person who approved this payment.
    """
    blocked = _check_human_approver(approved_by)
    if blocked:
        return blocked

    conn = _connect_rw()
    try:
        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if lease is None:
            return _refuse(f"No lease with id {lease_id}.")
        acct = conn.execute(
            "SELECT * FROM cash_accounts ORDER BY balance DESC LIMIT 1"
        ).fetchone()
        if acct is None:
            return _refuse("No cash account exists.")
        rent = lease["monthly_rent"]
        if acct["balance"] < rent:
            return _refuse(
                f"Not enough cash. Rent is ${rent:,.2f} and '{acct['name']}' holds "
                f"${acct['balance']:,.2f}. This shop never goes below zero, so the "
                "payment was not made.",
                shortfall=round(rent - acct["balance"], 2),
                balance=acct["balance"],
            )

        today = _shop_today(conn).isoformat()
        duplicate = _already_spent_today(conn, "rent", lease_id, rent, today)
        if duplicate is not None:
            return _refuse(
                f"Rent of ${rent:,.2f} on lease {lease_id} was already paid today "
                f"(payment {duplicate['id']}, approved by {duplicate['approved_by']}). "
                "Nothing was charged a second time.",
                already_paid=True,
                existing_payment_id=duplicate["id"],
            )
        new_balance = round(acct["balance"] - rent, 2)
        next_due = _add_one_month(date.fromisoformat(lease["next_due"])).isoformat()
        conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("rent", lease_id, rent, acct["name"], today, approved_by.strip()),
        )
        payment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, lease_id))
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, today, acct["name"]),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "payment_id": payment_id,
        "kind": "rent",
        "lease_id": lease_id,
        "space_name": lease["space_name"],
        "amount": rent,
        "account": acct["name"],
        "balance_before": acct["balance"],
        "balance_after": new_balance,
        "paid_at": today,
        "approved_by": approved_by.strip(),
        "next_due_before": lease["next_due"],
        "next_due_after": next_due,
    }


@mcp.tool
def place_restock_order(
    sku: str, size: str, qty: int, vendor_id: int, approved_by: str
) -> dict[str, Any]:
    """Order stock from a vendor. Requires a named human approver.

    Refuses if no human approver is named, if the vendor does not make this kind
    of product, if the vendor is blocked by an unpaid invoice, or if the cash
    balance would go below zero. On success it records the spend in payments,
    reduces cash, and returns the arrival date implied by the vendor's lead time.

    Stock is **not** added to inventory: the goods have not arrived yet. The
    arrival date is what the customer should be told.

    Args:
        sku: Product code to order.
        size: Size to order. Stock is held per size.
        qty: How many units.
        vendor_id: Which vendor is making it.
        approved_by: The name of the person who approved this spend.
    """
    blocked = _check_human_approver(approved_by)
    if blocked:
        return blocked
    if qty <= 0:
        return _refuse("Quantity must be at least 1.")

    conn = _connect_rw()
    try:
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return _refuse(f"No vendor with id {vendor_id}.")
        price = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return _refuse(f"No pricing row for {sku}; the order cannot be costed.")

        wanted = SKU_KIND_TO_SPECIALTY.get(_sku_kind(sku))
        is_courier = COURIER_KEYWORD in vendor["specialty"].lower()
        if is_courier or not wanted or wanted not in vendor["specialty"].lower():
            return _refuse(
                f"{vendor['name']} has specialty '{vendor['specialty']}' and does not make "
                f"{sku}. Order from a vendor whose specialty covers this product."
            )

        unpaid = conn.execute(
            "SELECT id, amount, status FROM invoices WHERE vendor_id = ? AND status != 'paid'",
            (vendor_id,),
        ).fetchone()
        if unpaid is not None:
            return _refuse(
                f"{vendor['name']} will not ship while invoice {unpaid['id']} for "
                f"${unpaid['amount']:,.2f} is {unpaid['status']}. Settle that invoice first.",
                blocking_invoice_id=unpaid["id"],
                blocking_amount=unpaid["amount"],
            )

        cost = round(price["unit_cost"] * qty, 2)
        acct = conn.execute(
            "SELECT * FROM cash_accounts ORDER BY balance DESC LIMIT 1"
        ).fetchone()
        if acct is None:
            return _refuse("No cash account exists.")
        if acct["balance"] < cost:
            return _refuse(
                f"Not enough cash. The order costs ${cost:,.2f} and '{acct['name']}' holds "
                f"${acct['balance']:,.2f}. This shop never goes below zero, so nothing was "
                "ordered.",
                order_cost=cost,
                shortfall=round(cost - acct["balance"], 2),
                balance=acct["balance"],
            )

        today = _shop_today(conn)
        duplicate = _already_spent_today(
            conn, "purchase_order", vendor_id, cost, today.isoformat()
        )
        if duplicate is not None:
            return _refuse(
                f"An order of ${cost:,.2f} with {vendor['name']} was already placed today "
                f"(payment {duplicate['id']}, approved by {duplicate['approved_by']}). "
                "The goods are already on their way; nothing was ordered or charged again.",
                already_ordered=True,
                existing_payment_id=duplicate["id"],
            )
        arrival = (today + timedelta(days=vendor["lead_days"])).isoformat()
        new_balance = round(acct["balance"] - cost, 2)
        conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("purchase_order", vendor_id, cost, acct["name"], today.isoformat(), approved_by.strip()),
        )
        payment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, today.isoformat(), acct["name"]),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "payment_id": payment_id,
        "kind": "purchase_order",
        "sku": sku,
        "size": size,
        "qty": qty,
        "vendor_id": vendor_id,
        "vendor_name": vendor["name"],
        "unit_cost": price["unit_cost"],
        "order_cost": cost,
        "balance_before": acct["balance"],
        "balance_after": new_balance,
        "ordered_on": today.isoformat(),
        "lead_days": vendor["lead_days"],
        "expected_arrival": arrival,
        "approved_by": approved_by.strip(),
        "note": (
            "Stock has not been added to inventory. The goods arrive on "
            f"{arrival}; that is the date to quote."
        ),
    }


if __name__ == "__main__":
    mcp.run()
