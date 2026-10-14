# Campus Customs MCP server

A small [FastMCP](https://github.com/jlowin/fastmcp) server that exposes the Campus Customs
shop database as tools. **Every agent in this homework reads shop data through this server** —
the boss, inventory, accounting, facilities, and customer service all call the same tools, so
there is one definition of what the shop's numbers are and no agent writes SQL of its own.

## Which database it uses

```
../data/campus_customs_new.db
```

That is the **working copy**. `../data/campus_customs.db` is the pristine original and is
never opened by this server, so a run can always be reset:

```bash
cp ../data/campus_customs.db ../data/campus_customs_new.db
```

The three tools below open the file **read-only**. They cannot change the shop. Tools that
write — paying an invoice, placing an order, closing a ticket — arrive in a later problem and
will open their own read-write connection.

## The nine tools

Six read the shop. Three change it, and each of those enforces its own guardrail before it
touches a row.

### Reading

**`get_ticket_context(ticket_id)`** — one ticket and everything it links to in a single call:
the inventory row for its SKU and size, the pricing row with margin, the invoice it references
together with the vendor behind it, and the lease it concerns. Returns `desk.date_today`
alongside, so the caller never reaches for the real calendar.
*Tables: `tickets`, `desk`, `inventory`, `pricing`, `invoices`, `vendors`, `leases`.*

**`check_stock_and_restock_options(sku, size, qty_needed)`** — stock on hand for that exact
SKU **and size**, the shortfall, which other sizes have stock, and the restock cost. On a
shortfall it lists every vendor with whether its specialty covers the product, whether an
unpaid invoice blocks it, its lead time, and the arrival date that implies. No vendor is
silently dropped.
*Tables: `inventory`, `pricing`, `vendors`, `invoices`, `desk`.*

**`get_cash_position()`** — every balance, every unpaid invoice with days overdue, every lease
with days until rent is due, the total committed, and whether cash covers it.
*Tables: `cash_accounts`, `invoices`, `vendors`, `leases`, `payments`, `desk`.*

**`list_open_tickets()`** — the work queue: every ticket not yet resolved or cancelled.
*Tables: `tickets`, `desk`.*

**`quote_bulk_price(sku, qty, proposed_unit_price)`** — list price, unit cost, margin per unit
and for the whole order, and what a proposed price does to all of it, including whether it
falls below cost.
*Tables: `pricing`, `inventory`.*

### Writing

**`update_ticket(ticket_id, status, note)`** — move a ticket to `open`, `in_progress`,
`blocked`, `resolved` or `cancelled` and append a dated note. Moves no money, needs no
approval, but the note is required so the change can be audited.
*Tables: `tickets`, `desk`.*

**`pay_invoice(invoice_id, approved_by)`** — settle a supplier invoice. Writes a `payments`
row, marks the invoice paid, and reduces the balance — all three together. Paying a vendor's
open invoice is what unblocks them.
*Tables: `invoices`, `cash_accounts`, `payments`, `desk`.*

**`pay_rent(lease_id, approved_by)`** — pay one month's rent, and advance `next_due` by a
month so the same month cannot be paid twice.
*Tables: `leases`, `cash_accounts`, `payments`, `desk`.*

**`place_restock_order(sku, size, qty, vendor_id, approved_by)`** — order stock. Records the
spend, reduces cash, and returns the arrival date from the vendor's lead time. Stock is **not**
added to inventory: the goods have not arrived yet.
*Tables: `vendors`, `invoices`, `pricing`, `cash_accounts`, `payments`, `desk`.*

## Rules these tools hold to

1. **Only what is in the database.** Every number returned is a column value or arithmetic
   over column values. Nothing is estimated or filled in.
2. **`desk.date_today` is the clock.** Overdue, due-in, and arrival dates all come from the
   shop's date, so a run on any real day reaches the same conclusions about the same data.
3. **Lead times come from `vendors.lead_days`.** No agent may invent a delivery date.
4. **A vendor with an unpaid invoice will not ship**, and the tool says so, naming the invoice
   and the amount, rather than just omitting the vendor.
5. **Money needs a named human.** The three payment tools refuse when no approver is given,
   and refuse again when the name supplied is one of the agents — an agent cannot sign its own
   cheque. None of the three is given to any agent in the first place; they exist for a person
   acting through the dashboard.
6. **Cash never goes below zero.** A payment that would overdraw an account is refused, with
   the shortfall stated. Nothing is written when a tool refuses.
7. **A refusal is a result, not an error.** Refusing tools return `{"refused": true, "reason":
   ...}` so the agent reads why and can act on it, rather than seeing an exception.

## One stated interpretation

The database has no product-category column, so a vendor's `specialty` text has to be matched
against the kind of product a SKU is. The SKU's middle token is that kind — `CC-TEE-WHITE` is
a `TEE` — and the mapping from kind to specialty is written out at the top of `server.py`.
It is an interpretation of the data rather than a column in it, which is why it sits in the
open, is returned to the caller as `match_reason`, and never silently removes a vendor from
the results.

## Setup

The server needs no separate environment: it is installed with everything else from the
`requirements.txt` at the repository root, and the agent team attaches it in-process. To
exercise it on its own:

```bash
# from the repository root, with .venv active
python mcp_server/server.py
```
