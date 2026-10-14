# Campus Customs Multi-Agent Operations — Harness

How the agent team that runs the shop is built and bounded. This document grows one section
at a time as the assignment progresses.

---

## 1. The database

**Source:** `data/campus_customs.db` — SQLite, 52 KB, nine application tables.

**Two files, on purpose.**

| File | Role |
| --- | --- |
| `data/campus_customs.db` | The pristine original. **Never written to.** It is the reset point. |
| `data/campus_customs_new.db` | A byte-identical copy. The MCP server and the backend point here, and the tools write here as tickets resolve. |

Restoring is a file copy, so a full ticket-resolution run always starts from the same shop:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

Every field below was read from the live database with `PRAGMA table_info` and the table
DDL, and sampled with real queries. Nothing here is assumed.

### 1.1 `desk` — 1 row

The shop's clock and scratchpad.

| Field | Type | Why it matters to the agents |
| --- | --- | --- |
| `date_today` | TEXT NOT NULL | **`2026-08-31`.** This is "today" for the shop, and the only date any agent may compare against. Overdue invoices, rent timing, and vendor arrival dates are all judged from here — never from the real clock, or a run on a different day would reach different conclusions about the same data. |
| `notes` | TEXT | Free-text desk note. Currently empty. |

**Why the table matters:** it makes the scenario reproducible. One row, one date, and every
agent's sense of "late" comes from it.

### 1.2 `tickets` — 3 rows

The work queue. Everything the team does starts here.

| Field | Type | Why it matters to the agents |
| --- | --- | --- |
| `id` | INTEGER PK | How a ticket is referred to on the board and in the audit trail. |
| `type` | TEXT NOT NULL | `customer_order`, `rent_notice`, `price_override`. The boss's main routing signal — it is the cheapest way to pick a specialist without spending a model call working it out. |
| `requester` | TEXT NOT NULL | Who is asking. A customer, a landlord, a student org — which changes who drafts the reply and in what tone. |
| `subject`, `notes` | TEXT | The human description. `notes` carries the detail the structured fields cannot, e.g. "asking for a bulk discount". |
| `sku`, `size`, `qty` | TEXT / TEXT / INTEGER, nullable | Set on product tickets. These join straight to `inventory` and `pricing`, so inventory can compute a shortfall without parsing prose. |
| `lease_id` | INTEGER → `leases.id` | Set on facilities tickets. Points at the lease being invoked. |
| `invoice_id` | INTEGER → `invoices.id` | Set when a ticket is tied to money already owed. |
| `status` | TEXT NOT NULL | `open` on all three now. The team moves this as work completes. |
| `created_at` | TEXT NOT NULL | Arrival order. |

**Why the table matters:** it is the single entry point for the whole system, and its two
foreign keys are what let a ticket pull in the money and the property it concerns without
anyone guessing.

### 1.3 `inventory` — 10 rows

What is physically on the shelf, keyed by **(sku, size)**.

| Field | Type | Why it matters to the agents |
| --- | --- | --- |
| `sku` | TEXT, PK part | Joins to `pricing` and to ticket lines. |
| `name` | TEXT NOT NULL | The human name for a reply to a customer. |
| `size` | TEXT, PK part | The composite key means stock is always a per-size fact. A product is never simply "in stock". |
| `qty` | INTEGER NOT NULL | The number the inventory agent must read and never estimate. |
| `location` | TEXT NOT NULL | Aisle, for a staff instruction. |

**Why the table matters:** shortfall is computed here — `ticket.qty − inventory.qty` for that
exact sku and size — and a shortfall is what triggers everything downstream: a vendor, a
cost, a payment, a human approval.

### 1.4 `pricing` — 4 rows

| Field | Type | Why it matters to the agents |
| --- | --- | --- |
| `sku` | TEXT PK | One row per product, not per size. |
| `unit_cost` | REAL NOT NULL | What a restock costs. Accounting multiplies this by the shortfall to price a purchase order. |
| `list_price` | REAL NOT NULL | What the shop charges. Margin is `list_price − unit_cost`, which is the floor any discount request has to be judged against. |

**Why the table matters:** it is the only source of money-per-item. A discount agent with no
`unit_cost` would be guessing at whether a deal loses money.

### 1.5 `vendors` — 3 rows

| Field | Type | Why it matters to the agents |
| --- | --- | --- |
| `id` | INTEGER PK | Referenced by `invoices.vendor_id`. |
| `name` | TEXT NOT NULL | For the purchase order and the audit record. |
| `specialty` | TEXT NOT NULL | `apparel reprint`, `mugs and small goods`, `local courier`. How inventory decides **who can actually make the thing** — a courier cannot reprint a tee. |
| `lead_days` | INTEGER NOT NULL | 5, 3, and 1. Arrival date is `desk.date_today + lead_days`. The only acceptable source for a delivery promise, which means no agent may invent an ETA. |

**Why the table matters:** it supplies both halves of a restock answer — who, and when — and
it is where the shop rule about unpaid invoices bites, because a vendor is also an entity the
shop can owe money to.

### 1.6 `invoices` — 1 row

| Field | Type | Why it matters to the agents |
| --- | --- | --- |
| `id` | INTEGER PK | **501** is the only one. |
| `vendor_id` | INTEGER → `vendors.id` | Which vendor is owed. This join is what enforces the no-ship-while-unpaid rule. |
| `amount` | REAL NOT NULL | $840. |
| `due_date` | TEXT NOT NULL | `2026-08-28` — **three days overdue** against `desk.date_today`. |
| `status` | TEXT NOT NULL | `open`. Becomes `paid` only through an approved payment. |
| `description` | TEXT | "Rush reprint CC-TEE-WHITE S" — ties the debt to the very product ticket 101 is asking for. |

**Why the table matters:** it is the blocker. An open invoice against a vendor stops that
vendor shipping, so clearing it is a precondition for restocking, not an unrelated errand.

### 1.7 `leases` — 1 row

| Field | Type | Why it matters to the agents |
| --- | --- | --- |
| `id` | INTEGER PK | Referenced by `tickets.lease_id`. |
| `space_name`, `landlord` | TEXT NOT NULL | Chapel Street shop, Elm City Properties. |
| `monthly_rent` | REAL NOT NULL | $2,400 — the largest single claim on cash. |
| `next_due` | TEXT NOT NULL | `2026-09-02`, two days out. Advanced when rent is paid. |
| `notes` | TEXT | Empty. |

**Why the table matters:** it is the facilities agent's whole world, and rent is the obligation
that makes the cash arithmetic tight.

### 1.8 `cash_accounts` — 1 row

| Field | Type | Why it matters to the agents |
| --- | --- | --- |
| `name` | TEXT PK | `checking`. |
| `balance` | REAL NOT NULL | **$3,400.** The hard constraint on everything the team can do. |
| `date` | TEXT NOT NULL | `2026-08-31`, as-of date for the balance. |

**Why the table matters:** cash only leaves in this homework — no revenue is modelled — so
this number only falls. Every payment tool must check it first and refuse rather than go
negative.

### 1.9 `payments` — 0 rows

The ledger. Empty at the start, which makes it the clearest evidence of what the team did.

| Field | Type | Why it matters to the agents |
| --- | --- | --- |
| `id` | INTEGER PK | — |
| `kind` | TEXT NOT NULL | What was paid — an invoice, rent, a purchase order. |
| `ref_id` | INTEGER | The invoice or lease it settles. |
| `amount` | REAL NOT NULL | — |
| `account` | TEXT NOT NULL | Which cash account it came from. |
| `paid_at` | TEXT NOT NULL | Stamped from `desk.date_today`, not the wall clock. |
| `approved_by` | TEXT NOT NULL | **The human who approved it.** `NOT NULL`, so the schema itself refuses to record a payment nobody approved. |

**Why the table matters:** it is the audit record for money. Every row here should pair with a
balance reduction in `cash_accounts` and a status change on whatever it settled.

### 1.10 Referential integrity

```
vendors ──1:many──> invoices ──┐
                               ├──> tickets
leases ────────────────────────┘
inventory (sku,size) ──┐
                       ├── sku ──> pricing
tickets.sku ───────────┘
cash_accounts <── payments ──> invoices / leases   (by kind + ref_id)
```

`payments.ref_id` is deliberately untyped — it points at an invoice or a lease depending on
`kind`, so the tool that writes it has to set both fields consistently.

---

## 2. The three open tickets

All three are `open`, and they are not independent. Read together they describe a shop that
cannot do everything it has been asked to do.

### Ticket 101 — `customer_order` — Tauhid Zaman

> Needs a tee in size S. · `sku` CC-TEE-WHITE, `size` S, `qty` 1 · `invoice_id` **501**

**How it links:**

```
ticket 101 ──sku+size──> inventory (CC-TEE-WHITE, S) = 0 on hand   → shortfall of 1
          ──sku───────> pricing (unit_cost $8)
          ──invoice_id─> invoice 501 ($840, open, 3 days overdue)
                                 └──vendor_id──> Bulldog Print Co (apparel reprint, 5 days)
```

This is the ticket that teaches the rule. The customer wants a tee the shop does not have.
The only vendor who can reprint apparel is Bulldog Print Co — and the shop already owes them
$840 on an overdue invoice, so **they will not ship until it is paid**. The invoice even
describes the same product. Fulfilling a one-item customer order therefore requires an $840
payment, which requires a human.

### Ticket 102 — `rent_notice` — Elm City Properties

> Email: shop rent due in 2 days. · `lease_id` **1**

**How it links:**

```
ticket 102 ──lease_id──> lease 1 (Chapel Street, $2,400, next_due 2026-09-02)
                                   └──> cash_accounts.checking ($3,400)
```

Straightforward facilities work, except for its size. At $2,400 against a $3,400 balance,
paying rent consumes most of the shop's cash, so **when it is paid relative to everything
else decides what remains possible.**

### Ticket 103 — `price_override` — Yale AI Club

> Student org wants 20 hoodies, size M, asking for a bulk discount. · CC-HOOD-NAVY, M, 20

**How it links:**

```
ticket 103 ──sku+size──> inventory (CC-HOOD-NAVY, M) = 8 on hand   → shortfall of 12
          ──sku───────> pricing (unit_cost $22, list_price $58 → margin $36)
                        restocking 12 at cost = $264, from Bulldog Print Co (5 days)
```

Two questions in one ticket: *can we supply 20?* (no — 12 short) and *what discount is
defensible?* (judged against the $36 margin). It needs inventory and accounting together,
which makes it the natural test of agent-to-agent delegation.

### What the three tickets add up to

| Claim on cash | Amount |
| --- | --- |
| Opening balance | **$3,400** |
| Invoice 501 — unblocks the only apparel vendor | − $840 |
| Rent — due in 2 days | − $2,400 |
| **Remaining** | **$160** |
| Hoodie restock for ticket 103 (12 × $22) | − $264 ✗ |

**The shop cannot afford all three.** Clearing the invoice and paying rent leaves $160, and
the hoodie reprint needs $264. There is no ordering of payments that fits everything, because
the total demand is $3,504 against $3,400.

That shortfall looks deliberate rather than accidental. A team that reports "all three
resolved" has either invented money or skipped a check; the correct outcome is a partial
resolution with an explicit escalation to the human about what cannot be funded. The design
problem is therefore not "make the agents finish the work" but **"make the agents notice they
cannot, and say so with the numbers."**

---

## 3. Shop rules the build must honour

Derived from the assignment and visible in the data:

1. **`desk.date_today` is the only clock.** Overdue is judged from `2026-08-31`.
2. **Lead times come from `vendors.lead_days`.** Arrival = shop date + lead days. No invented ETAs.
3. **A vendor with an open unpaid invoice will not ship.** Clearing the debt is a precondition for the restock.
4. **Every payment needs explicit human approval.** No agent pays anything on its own; `payments.approved_by` is `NOT NULL`.
5. **A payment updates everything it touches** — a `payments` row, the `cash_accounts` balance, and the status of the invoice or the `next_due` on the lease.
6. **The pay tool refuses when cash is short.** Balances never go negative.
7. **Cash only goes out.** No revenue is modelled, so the balance is monotonically decreasing.
8. **Reset before a full run.** Copy the pristine database over the working one.
9. **No real contact.** No emails to customers, no calls to vendors. Drafts stay on the board.

---

## 4. The MCP server

`mcp_server/mcp_server.py` — a FastMCP server, and the only route any agent has to shop data.
Every agent in this homework calls these tools, so there is one definition of what the shop's
numbers are and no agent writes SQL of its own.

**Database:** `data/campus_customs_new.db`, opened **read-only**. The pristine
`data/campus_customs.db` is never opened, so a run is always resettable by copying it back.
Tools that write arrive in a later problem.

### 4.1 `get_ticket_context(ticket_id)`

**Tables read:** `tickets` (the row itself) · `desk` (`date_today`) · `inventory` (by the
ticket's `sku` **and** `size`) · `pricing` (by `sku`, with margin computed) · `invoices` (via
`tickets.invoice_id`) · `vendors` (via `invoices.vendor_id`) · `leases` (via
`tickets.lease_id`).

**Unlocks:** **101, 102 and 103** — it is the first call on any ticket.

**Why it is the right tool for each:**

- **101** — the ticket carries `invoice_id` 501, and following that key is the only way to
  discover that the customer's tee is entangled with an $840 debt. The tool returns the
  invoice *and* the vendor behind it in one call, so the boss learns that the shop owes
  Bulldog Print Co three days late at the same moment it learns a tee is wanted. Routing this
  to customer service alone would miss that entirely.
- **102** — the rent ticket's only substance is `lease_id` 1. The tool resolves it to the
  Chapel Street lease at $2,400 with `next_due` 2026-09-02, and converts that into
  `days_until_due: 2` using the shop's date rather than the real one. The ticket text says
  "due in 2 days"; this is how an agent confirms that against the record instead of trusting
  the prose.
- **103** — returns the hoodie's `unit_cost` 22 and `list_price` 58 together with
  `margin_per_unit: 36`. A discount request cannot be judged without that number, and
  computing it in the tool means the model never does the subtraction itself.

### 4.2 `check_stock_and_restock_options(sku, size, qty_needed)`

**Tables read:** `inventory` (that exact `sku` + `size`, plus the other sizes of the same SKU)
· `pricing` (`unit_cost`, to price the shortfall) · `vendors` (all three, with `specialty` and
`lead_days`) · `invoices` (any row not `paid`, to find blockers) · `desk` (to turn lead days
into a date).

**Unlocks:** **101 and 103** — the two tickets with a product line.

**Why it is the right tool for each:**

- **101** — asked for CC-TEE-WHITE in S, it reports 0 on hand and a shortfall of 1, then names
  the reason the obvious fix is unavailable: Bulldog Print Co is the only vendor whose
  specialty covers apparel, and invoice 501 is open, so **"this vendor will not ship until it
  is paid."** It also returns L, M and XL as having stock, which is the one piece of
  information that lets customer service offer the customer an alternative instead of only
  bad news. One call turns "we are out of stock" into a decision with a price and a blocker
  attached.
- **103** — asked for 20 hoodies in M against 8 on hand, it returns a shortfall of 12 and a
  restock cost of **$264**, computed from `unit_cost` rather than guessed. That figure is what
  collides with the cash position later, and it arrives alongside the same Bulldog Print Co
  blocker and a 5-day lead meaning a 2026-09-05 arrival. Accounting cannot price a bulk
  discount without knowing that supplying the order costs money the shop may not have.

### 4.3 `get_cash_position()`

**Tables read:** `cash_accounts` (balances) · `invoices` (every row not `paid`, with
`days_overdue`) · `vendors` (to name who is owed) · `leases` (rent and `next_due`) ·
`payments` (what has already been paid) · `desk` (the clock).

**Unlocks:** **102 directly, and it gates 101 and 103.**

**Why it is the right tool for each:**

- **102** — rent is a $2,400 claim against a $3,400 balance. The tool returns both numbers
  together with `total_committed` 3,240 and `cash_after_all_commitments` 160, so the
  facilities agent can see that paying rent is affordable but nearly exhausting, rather than
  checking the lease in isolation and calling it routine.
- **101** — settling invoice 501 is the precondition for the tee ever arriving, and this is
  the tool that confirms the shop can actually afford the $840 before anyone asks a human to
  approve it.
- **103** — the $264 reprint has to be tested against what is left after the invoice and the
  rent. This tool supplies the $160 that makes that order impossible to fund, which is the
  finding the team is supposed to surface rather than paper over.

It also returns `payments_recorded`, empty at the start, which is how an agent can tell
whether an approval has already been acted on instead of paying something twice.

### 4.4 Verified against the live database

Called directly, with the server not running:

| Call | Result |
| --- | --- |
| `get_ticket_context(101)` | shop date 2026-08-31; inventory S = 0; invoice 501 $840 `open`, **3 days overdue**; vendor Bulldog Print Co, 5 lead days |
| `get_ticket_context(102)` | lease 1, $2,400, next due 2026-09-02, **days_until_due 2** |
| `get_ticket_context(103)` | pricing 22 / 58, **margin 36**; hoodie M stock 8 |
| `check_stock_and_restock_options("CC-TEE-WHITE", "S", 1)` | shortfall 1, cost $8; other sizes L 3, M 5, XL 2; Bulldog **blocked by invoice 501**; Elm City excluded on specialty; QuickShip excluded as a courier |
| `check_stock_and_restock_options("CC-HOOD-NAVY", "M", 20)` | shortfall 12, cost **$264**, same blocker, arrival 2026-09-05 |
| `get_cash_position()` | cash $3,400; committed $3,240; **$160 remaining**; invoice 501 3 days overdue; rent due in 2 days; no payments yet |

Every figure matches the tables by hand.

### 4.5 One stated interpretation

The database has no product-category column, so a vendor's `specialty` has to be matched
against the kind of product a SKU is. The SKU's middle token is that kind — `CC-TEE-WHITE` is
a `TEE` — and the kind-to-specialty mapping is written out at the top of `mcp_server.py`. It
is an interpretation of the data rather than a column in it, so it sits in the open, is
returned to the caller as `match_reason`, and never silently removes a vendor from the
results. A courier is excluded from making goods by an explicit rule, with the reason stated,
rather than by quietly filtering it out.

---

## 5. The MCP server connected to the vibe coder

### 5.1 Configuration

`.mcp.json` at the project root registers the server as `campus-customs`:

```json
{
  "mcpServers": {
    "campus-customs": {
      "command": "mcp_server/.venv/bin/python",
      "args": ["mcp_server/mcp_server.py"]
    }
  }
}
```

Paths are relative, so the file works for anyone who clones the project. The same server is
also registered with absolute paths in the wider coursework repository's `.mcp.json`, which is
the root this particular Claude Code session was started from.

Claude Code reads its MCP server list when the session starts, so the server only appeared
after a restart. Once restarted it connected with no further setup, and
`session_connectors_status` reports `campus-customs · project · stdio · connected · 3 tools`.

### 5.2 Smoke test

Evidence is in **`output/mcp_smoke.json`**. Six calls were made from the vibe coder over the
MCP connection — every tool, and every ticket:

| # | Tool | Arguments | Ticket |
| --- | --- | --- | --- |
| 1 | `get_ticket_context` | `ticket_id: 101` | 101 |
| 2 | `get_ticket_context` | `ticket_id: 102` | 102 |
| 3 | `get_ticket_context` | `ticket_id: 103` | 103 |
| 4 | `check_stock_and_restock_options` | `CC-TEE-WHITE, S, 1` | 101 |
| 5 | `check_stock_and_restock_options` | `CC-HOOD-NAVY, M, 20` | 103 |
| 6 | `get_cash_position` | — | 102 (and gates 101, 103) |

For each call the file records the prompt, the tool name, the arguments, the **complete raw
output**, and a field-by-field comparison against a direct read-only SQL read of
`data/campus_customs_new.db` — each with the query used, the database value, and whether it
matched.

**32 fields checked, 32 matched.** Date arithmetic is reproduced in SQL from
`desk.date_today` rather than the real calendar, so the overdue and arrival figures are
verified the same way the tools compute them.

Findings confirmed straight from the database:

- Invoice 501 is **3 days overdue** — `julianday(desk.date_today) − julianday(due_date)`.
- CC-TEE-WHITE size S is **0 on hand**; L, M and XL hold 3, 5 and 2.
- The hoodie shortfall is **12** and the reprint costs **$264** — 12 × `unit_cost` 22.
- Bulldog Print Co's `earliest_arrival` of **2026-09-05** is `date(desk.date_today, '+5 days')`.
- Cash **$3,400**, committed **$3,240**, leaving **$160**, and `payments` is still empty.

### 5.3 What the smoke test establishes

The tools are not merely callable — they return the shop's real numbers through the MCP
layer, which is the layer every agent will use. In particular the blocking rule survives the
round trip: asked for a tee the shop does not have, the tool reports over MCP that the only
capable vendor is held by invoice 501 and names the amount, rather than returning an empty
vendor list the agent would have to interpret.

---

## 6. The agent team

Five PydanticAI agents over the one MCP server. `backend/agents.py` builds them,
`backend/runner.py` runs them, `backend/models.py` holds every type they pass, and each
agent's instructions live in its own file under `backend/prompts/`.

**One source of shop facts.** Every agent gets its tools from the Campus Customs MCP server,
attached in-process. No agent queries SQLite, and no agent is handed a number the MCP server
did not produce. There is deliberately no second shop-data layer.

### 6.1 The five roles

| Agent | Owns | Prompt |
| --- | --- | --- |
| **boss** | Reads each ticket, routes it, reads the reports, makes the final call, records it on the ticket | `prompts/boss.md` |
| **inventory** | Stock by size, shortfalls, which vendor can make the product, when it would arrive | `prompts/inventory.md` |
| **accounting** | Cash, invoices, margins, the cost of any proposal, payment sequencing | `prompts/accounting.md` |
| **facilities** | The premises — leases, rent, landlords, due dates | `prompts/facilities.md` |
| **customer_service** | Drafting messages to customers, organisations, landlords | `prompts/customer_service.md` |

### 6.2 Delegation

Any agent can hand work to any other through a `delegate(to_agent, task)` tool, so the team is
a **mesh**, not a tree — accounting can ask inventory for a restock cost without going back
through the boss. The hand-off passes a `SpecialistReport` (summary, facts used, blockers,
recommendations, approval requests, drafts), not a transcript, which is both cheaper and
easier to audit.

Four rules in code stop a mesh of five from running away:

| Rule | Value | Why |
| --- | --- | --- |
| Depth cap | 2 | Boss → specialist → one more. Deeper is almost always a loop. |
| Hand-offs per ticket | 6 | A total budget across every agent. |
| No re-entry | — | An agent already on the call stack cannot be called back into. |
| No delegating to the boss, or to yourself | — | Report back and let the boss decide. |

A refused delegation returns a reason the agent can read and act on, not an exception.

### 6.3 MCP tools, and who can see which

Nine tools. **The three that move money are given to no agent at all.**

| Tool | Tables it uses | boss | inv | acct | fac | cs |
| --- | --- | :-: | :-: | :-: | :-: | :-: |
| `get_ticket_context` | `tickets`, `desk`, `inventory`, `pricing`, `invoices`, `vendors`, `leases` | ● | ● | ● | ● | ● |
| `list_open_tickets` | `tickets`, `desk` | ● | ● | | ● | |
| `check_stock_and_restock_options` | `inventory`, `pricing`, `vendors`, `invoices`, `desk` | | ● | ● | | ● |
| `get_cash_position` | `cash_accounts`, `invoices`, `vendors`, `leases`, `payments`, `desk` | | | ● | ● | |
| `quote_bulk_price` | `pricing`, `inventory` | | | ● | | |
| `update_ticket` | `tickets`, `desk` | ● | | | | |
| `pay_invoice` | `invoices`, `cash_accounts`, `payments`, `desk` | — | — | — | — | — |
| `pay_rent` | `leases`, `cash_accounts`, `payments`, `desk` | — | — | — | — | — |
| `place_restock_order` | `vendors`, `invoices`, `pricing`, `cash_accounts`, `payments`, `desk` | — | — | — | — | — |

Scoping tools per role does two jobs at once. It is the strongest form of the
human-approval rule — **the team cannot pay for something it cannot call** — and it is also
the single largest token saving, because a tool schema is input tokens on every model request.
Measured: giving each agent only its own tools took one ticket from **33,695 to 17,562
tokens**, with the same answer.

### 6.4 Safety — the guardrails a real business would want

These sit at three levels, because a rule that lives only in a prompt is a request.

**In the schema.** `payments.approved_by` is `NOT NULL`. The database itself will not record a
payment nobody approved.

**In the MCP server**, where an agent cannot talk its way past them:

| Guardrail | Behaviour |
| --- | --- |
| Named human approver required | A payment with no approver is refused. |
| An agent cannot approve itself | `accounting`, `boss`, `ai`, `assistant` and the rest are refused as approver names. |
| Cash floor | A payment that would overdraw an account is refused, with the shortfall stated. Nothing is written. |
| Vendor blocking | An order from a vendor with an open unpaid invoice is refused, naming the invoice. |
| Capability check | An order from a vendor whose specialty does not cover the product is refused; a courier makes nothing. |
| Reads cannot write | The six reading tools open the database read-only. |
| Refusals are results | `{"refused": true, "reason": ...}` — the agent reads why and acts, rather than hitting an exception. |

**In the toolset.** No agent is given `pay_invoice`, `pay_rent`, or `place_restock_order`.

**In the prompts.** No message is ever sent — `customer_service` has no send tool and every
draft carries `draft_only_not_sent`. No agent may state a figure a tool did not return. No
agent may promise a date not derived from `vendors.lead_days`. No agent may imply something
has been ordered, paid, or reserved when it has not.

**What a real business would still want before this touched live money**, and does not have
yet: a second approver above a threshold, a daily spend cap, an idempotency key so one
approval cannot be executed twice, and a way to reverse a payment made in error.

### 6.5 Limits that keep token use in check

All in `backend/settings.py`, so the cost of a run can be read and changed in one place.

| Limit | Value | Effect |
| --- | --- | --- |
| Model | `gpt-6-luna` | The only gpt-6 Luna model on the gateway; there is no smaller variant. |
| Reasoning effort | **low** | The largest single lever. Reasoning tokens are charged as output and never seen. |
| Verbosity | **low** | Short replies without a prompt having to beg for brevity. |
| Max output tokens | 1,200 per turn | A ceiling, not a hope. |
| Model requests — specialist | 4 | Enforced by `UsageLimits`. |
| Model requests — boss | 8 | It routes, reads reports, and decides. |
| Delegation depth | 2 | |
| Hand-offs per ticket | 6 | |
| Tools per agent | 2–4 of 9 | Fewer schemas re-sent on every request. |
| Reports, not transcripts | — | A hand-off passes a structured summary, not the conversation. |

Measured on the full board: **105,505 tokens for three tickets**, roughly 35k per ticket
across 2–5 agent steps, with input tokens about 95% of the total — which is why schema size
and prompt reuse, rather than reply length, are where the savings are.

### 6.6 The audit trail

`output/audit_trail.json` — **append-only, never wiped**. The file is read, the new record is
added to the end, and the whole list is written to a temporary file that atomically replaces
the original. A file that will not parse is moved aside as `audit_trail.corrupt-<stamp>.json`
rather than overwritten. A thread lock serialises writes, because several agents run inside
one ticket.

One record per agent loop step: `run_id`, `step_id`, time, ticket, agent, **depth**, parent
agent, model, the task it was given, every MCP tool call with clipped arguments and result and
whether it was **refused**, who it delegated to and what came back, the output summary, how
many approval requests and drafts it produced, model requests used, input/output/total tokens,
duration, status, and the stop reason.

Failures are recorded too. The first full run errored on a usage accessor and left three
`status: error` steps in the trail, which is how the fault was found.

### 6.7 What the team actually did

A full run from a freshly reset shop, all three tickets:

| Ticket | Outcome | Agents | Hand-offs | Tokens |
| --- | --- | --- | --- | --- |
| 101 customer order | `blocked_pending_approval` | inventory, accounting, customer_service | 4 | 47,386 |
| 102 rent notice | `blocked_pending_approval` | facilities | 1 | 17,562 |
| 103 bulk discount | `needs_human_decision` | inventory, accounting, customer_service | 3 | 40,557 |

**After the run: cash still $3,400, `payments` still empty, invoice 501 still open.** The team
proposed four payments and made none, which is the rule working.

On ticket 103 the team reached the shortfall on its own:

> Cash is $3,400. Invoice 501 ($840) plus rent ($2,400) total $3,240, leaving $160. The
> 12-unit restock costs $264, so all obligations plus restock total $3,504, **$104 more than
> cash.**

It then declined to confirm the discount or promise all twenty hoodies, drafted a message
saying what *could* be supplied, and put the sequencing decision to a person. That is the
correct answer to this board — the shop cannot do everything it has been asked to do, and
saying so with the arithmetic is worth more than three tickets marked resolved.

---

## 7. Backend routes

`backend/main.py` — the FastAPI app the React dashboard calls. Started from `backend/`:

```bash
uvicorn main:app --reload --port 8000
```

Then the API is at **http://localhost:8000**, with interactive docs at `/docs`.

| Route | What it does |
| --- | --- |
| `GET /api/health` | Service status: which database file, which model, how many approvals are waiting. |
| `GET /api/tickets` | The ticket board — every ticket with `is_open` / `is_resolved`, its linked lease or invoice, and whether the team has worked it. |
| `GET /api/cash` | The checking balance from `cash_accounts`, what is still committed against it, and the payments ledger. |
| `POST /api/tickets/{ticket_id}/run` | Runs the agent team on one ticket and returns the decision, the facts it used, its approval requests and drafts, plus steps, hand-offs, tokens and seconds. |
| `GET /api/events` | Recent agent activity, newest first, read straight from the audit trail: what each agent said, which MCP tools it called with what arguments and results, and who it delegated to. Filterable by ticket. |
| `GET /api/approvals` | Everything waiting on a person, everything already decided, and the drafts the team wrote. |
| `POST /api/approvals/{id}/approve` | **The only route in the system that moves money.** Charges a payment or purchase after a person clicks approve and gives their name. |
| `POST /api/approvals/{id}/decline` | Refuses a request. Nothing is charged and nothing is written to the shop. |
| `POST /api/reset` | Restores `campus_customs_new.db` from the pristine original and clears the pending queue, for a fresh run. The audit trail is left intact. |

### 7.1 Where money moves, and only there

The agent team prepares; a person pays. None of the five agents holds a payment tool, so a
run can only ever produce approval requests. `POST /api/approvals/{id}/approve` executes the
spend by calling the MCP server's own payment tools in-process through a FastMCP client — the
same tools, with the same guardrails, rather than a second copy of the payment logic living in
the web layer.

Verified end to end against the running API:

| Attempt | Result |
| --- | --- |
| Approve with no name | **HTTP 422** — rejected by validation before anything is attempted |
| Approve naming `accounting` | **Refused**: *"'accounting' is an agent, not a person."* Nothing charged |
| Same request, approved by a person | **Charged.** Cash $3,400 → $1,000, `next_due` rolled to 2026-10-02 |
| Approve it a second time | **HTTP 409** — already approved, no double charge |
| Approve the $840 invoice | **Charged.** Cash → $160, invoice `paid`, vendor unblocked |
| Approve a $264 restock against $160 | **Refused**: *"This shop never goes below zero, so nothing was ordered."* Cash unchanged |

Afterwards the `payments` table held exactly two rows, both stamped `Christian Roberts`.

### 7.2 A bug this testing found

The first version marked a request `failed` whenever the payment tool refused it. That meant
the refusal in row two of the table above — an agent naming itself — **permanently burned a
legitimate payment request**: the later human approval hit "already failed" and the rent could
never be paid.

A guardrail refusal is not a decision. It means *not like this*, not *never*. A refused request
now stays `pending` and approvable, records `last_refusal` so the dashboard can show why, and
counts `attempts`. Only a successful charge or an explicit decline is terminal. The behaviour
in the table was re-verified after the fix.

---

## 8. The dashboard

`frontend/` — React + Vite + TypeScript, started with `npm run dev`, served at
**http://localhost:5173**, calling the FastAPI backend at **http://localhost:8000** which
allows that origin by name.

Three columns, named after furniture rather than functions: **the spike** (dockets waiting),
**the floor** (the five agents and what they are doing), **the drawer** and **the tray** (the
money, and what needs signing).

| Piece | What it does |
| --- | --- |
| Ticket slips | Every ticket with a rubber stamp — open, in progress, blocked, resolved — and one button that starts the team |
| Agent plates | All five roles, always visible. A plate lights only when that agent was called, so **who was not called** is as legible as who was |
| Trace feed | Each agent's step as it happens: what it said, which MCP tools it called with what arguments, who it delegated to, and what it cost in tokens and seconds. Indentation shows the hand-off depth |
| The drawer | The checking balance, what is still committed, and the ledger of payments with the name of whoever approved each one. The balance flashes as it falls |
| The tray | Pending approvals as chits, each with the amount, the reason, what it unblocks, and the balance it would leave. Approve or decline |
| The pinboard | Drafts, pinned at a slight angle with a **not sent** seal |
| The shop clock | `desk.date_today` where a clock would be, with "all timings measured from here" |

The full design rationale is in `output/design.md`.

---

## 9. The resolved board

A full run from a freshly reset database on 14 October 2026. Evidence:
`output/desk_tickets.html` (plan against actual, plus the cash tab),
`output/resolved_tickets.json`, `output/resolved_board.html` (screenshots), and
`output/audit_trail.json`.

### 9.1 What happened

| Ticket | Final status | Agents involved | Never called | Passes | Agent steps |
| --- | --- | --- | --- | --- | --- |
| 101 — Bulldog tee | **resolved** | boss, inventory, accounting, customer service | facilities | 4 | 13 |
| 102 — Rent due | **resolved** | boss, facilities | inventory, accounting, customer service | 2 | 4 |
| 103 — Bulk hoodie discount | **resolved** | boss, inventory, accounting, customer service | facilities | 1 | 5 |

Ticket 102 used one specialist and four agent steps; ticket 101 used three specialists and
thirteen. That difference is the team sizing its response to the work, and it matches the plan
written in Problem 6 before any of it ran.

### 9.2 The cash

| | Amount | Balance |
| --- | --- | --- |
| Starting checking balance, after reset | | **$3,400.00** |
| Ticket 101 — invoice 501, Bulldog Print Co | − $840.00 | $2,560.00 |
| Ticket 101 — reprint, one tee in size S | − $8.00 | $2,552.00 |
| Ticket 102 — rent, lease 1 | − $2,400.00 | $152.00 |
| Ticket 101 — second reprint **refused**, duplicate | $0.00 | $152.00 |
| Ticket 103 — 12-hoodie reprint **refused**, $264 against $152 | $0.00 | $152.00 |
| **Ending balance** | | **$152.00** |

$3,400.00 − $840.00 − $8.00 − $2,400.00 = **$152.00**, checked programmatically against
`cash_accounts.balance`. The `payments` table holds exactly three rows, each naming
*Christian Roberts* as approver.

The three tickets together asked for $3,504 against $3,400. There is no order of payments that
funds all of it, and the hoodie reprint is what did not happen.

### 9.3 Two defects the run found

A first run was made before this one and is kept as
`output/full_run_record.diagnostic.json`. It is the reason the numbers above are trustworthy.

**Paying twice for the same thing.** A ticket is worked more than once — the first pass
prepares approvals, a person approves, a later pass closes it — and the second pass started
blind. On ticket 101 it re-proposed the $8 reprint it had already placed, and the money went
out twice. The fix is in three places: `pay_rent` and `place_restock_order` refuse an identical
spend already recorded on the same shop date, naming the existing payment; the approve route
refuses a twin before attempting it; and `get_ticket_context` now returns
`work_already_done`, so a later pass can see what has been settled. In the graded run the
second $8 order was **refused** and the balance held.

**No ticket ever reached `resolved`.** The boss had an outcome vocabulary for its own report
but nothing tying it to the ticket's status, so it left tickets blocked after the block had
cleared. The prompt now says when to close one, that **a refusal is a resolution**, and that
goods in transit do not hold a ticket open. The diagnostic run resolved one ticket of three;
this one resolved all three.

---

## 10. The system, end to end

### 10.1 The nine MCP tools and the tables they touch

| Tool | Tables | Writes? |
| --- | --- | --- |
| `get_ticket_context` | `tickets`, `desk`, `inventory`, `pricing`, `invoices`, `vendors`, `leases`, `payments` | no |
| `list_open_tickets` | `tickets`, `desk` | no |
| `check_stock_and_restock_options` | `inventory`, `pricing`, `vendors`, `invoices`, `desk` | no |
| `get_cash_position` | `cash_accounts`, `invoices`, `vendors`, `leases`, `payments`, `desk` | no |
| `quote_bulk_price` | `pricing`, `inventory` | no |
| `update_ticket` | `tickets`, `desk` | yes — status and notes |
| `pay_invoice` | `invoices`, `cash_accounts`, `payments`, `desk` | **yes — money** |
| `pay_rent` | `leases`, `cash_accounts`, `payments`, `desk` | **yes — money** |
| `place_restock_order` | `vendors`, `invoices`, `pricing`, `cash_accounts`, `payments`, `desk` | **yes — money** |

### 10.2 The five agents and what they may call

| Agent | Owns | MCP tools |
| --- | --- | --- |
| **boss** | Routes each ticket, reads the reports, decides, records it | `get_ticket_context`, `list_open_tickets`, `update_ticket` |
| **inventory** | Stock by size, shortfalls, vendors, arrival dates | `check_stock_and_restock_options`, `get_ticket_context`, `list_open_tickets` |
| **accounting** | Cash, invoices, margins, affordability, sequencing | `get_cash_position`, `quote_bulk_price`, `get_ticket_context`, `check_stock_and_restock_options` |
| **facilities** | The premises — leases, rent, landlords | `get_ticket_context`, `get_cash_position` |
| **customer_service** | Drafting messages to people | `get_ticket_context`, `check_stock_and_restock_options` |

**No agent holds a payment tool.** All five can delegate to any other through `delegate`.

### 10.3 Safety rules

| Level | Rule |
| --- | --- |
| Schema | `payments.approved_by` is `NOT NULL` — the database will not record a payment nobody approved |
| MCP server | A payment with no approver is refused |
| MCP server | An agent naming itself as approver is refused |
| MCP server | A payment that would overdraw an account is refused; nothing is written |
| MCP server | An identical spend already made on the shop's date is refused |
| MCP server | An order from a vendor with an open unpaid invoice is refused, naming the invoice |
| MCP server | An order from a vendor whose specialty does not cover the product is refused |
| MCP server | The six reading tools open the database read-only |
| MCP server | Refusals are results, not exceptions — the agent reads why and acts |
| Toolset | `pay_invoice`, `pay_rent` and `place_restock_order` are given to no agent |
| API | Only `POST /api/approvals/{id}/approve` moves money, and only with a person's name |
| API | A refused payment stays **pending** and approvable — a guardrail refusal is not a decision |
| Prompts | No agent may state a figure a tool did not return |
| Prompts | No delivery date except `desk.date_today` plus the vendor's `lead_days` |
| Prompts | No message is ever sent; every draft carries `draft_only_not_sent` |
| Prompts | No agent may imply something has been ordered, paid or reserved when it has not |

**Still missing, for a real business:** a second approver above a threshold, a daily spend cap,
and a way to reverse a payment made in error.

### 10.4 Limits that keep token use in check

| Limit | Value |
| --- | --- |
| Model | `gpt-6-luna` — the only gpt-6 Luna model on the gateway |
| Reasoning effort / verbosity | **low** / **low** — the largest single lever |
| Max output tokens per turn | 1,200 |
| Model requests — specialist / boss | 4 / 8 |
| Delegation depth | 2 |
| Hand-offs per ticket | 6 |
| Search results per call | 8 |
| Tools per agent | 2–4 of 9 |
| Hand-offs pass a structured report, not a transcript | — |

Measured: scoping tools per agent took one ticket from 33,695 to 17,562 tokens. Keeping full
reports and draft bodies out of the boss's context took ticket 101 from 48,164 to 28,999.
Running tickets concurrently cut wall clock 612s → 340s at no token cost.
