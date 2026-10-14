# Campus Customs — Multi-Agent Operations

MGT 409 Homework 5. A five-agent team that runs a small Yale merchandise shop: it reads the
ticket board, works out what the shop can and cannot afford, and prepares the payments — but
it cannot pay for anything. A person approves every spend from a React desk.

- **An MCP server** holds every shop fact and every write. No agent writes SQL.
- **Five PydanticAI agents** — boss, inventory, accounting, facilities, customer service —
  that delegate to each other.
- **A FastAPI backend** that runs the team and is the only place money moves.
- **A React dashboard** where a person watches the agents work and signs for the money.

The shop's date is **31 August 2026**, held in `desk.date_today`. Everything — what is
overdue, when goods arrive — is measured from that, never from today's real date.

---

## What you need

- **Python 3.12+**
- **Node.js 20+**
- A **Portkey API key** with access to `gpt-6-luna`

Both database files are committed, so there is no data pack to find.

## 1. Set up

```bash
cd hw5
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then put your real key in .env
```

`.env` is git-ignored and must never be committed.

## 2. Copy the original database to the working copy

Two database files live in `data/`:

| File | Role |
| --- | --- |
| `data/campus_customs.db` | The pristine original. Nothing ever writes to it. |
| `data/campus_customs_new.db` | The working copy. The MCP server and the backend point here, and the tools change it as tickets resolve. |

**The committed working copy is the state after the graded run** — all three tickets resolved
and the balance down to $152 — so you can open the board and see the finished result straight
away.

**Before a fresh three-ticket run, reset it:**

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

That restores a $3,400 balance, three open tickets, and invoice 501 unpaid. There is also a
button on the dashboard (**Reset the shop**) and an API route (`POST /api/reset`) that do
exactly the same thing. The audit trail in `output/audit_trail.json` is **not** reset: it is
append-only across runs on purpose.

## 3. Start the MCP server

The agent team attaches the MCP server **in process**, so for normal use you do not start it
separately — running the backend in step 4 starts it with them.

To exercise it on its own, or to attach it to Claude Code as a tool server:

```bash
python mcp_server/server.py
```

`.mcp.json` in this folder registers it as `campus-customs` for an MCP client. Its nine tools
and the tables each one touches are documented in `mcp_server/README.md`.

## 4. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API is on **http://localhost:8000**, with interactive docs at `/docs`. It allows the Vite
origin `http://localhost:5173` so the board can call it from the browser.

## 5. Start the React board

In a second terminal, from this folder:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. Put your name in the box at the top right — every payment
records who approved it — then pick a docket and press **Put the team on it**.

## 6. Running the three tickets

Click each ticket on the board and run it, approving what the team asks for. Or do the whole
board from the command line:

```bash
cd backend
python runner.py --reset            # reset the shop, then work every open ticket
python runner.py --ticket 101       # one ticket
python runner.py --full             # reset, then run + approve + close all three
```

**Reset before a three-ticket run** so the cash figures start from $3,400. A ticket is
normally worked twice: the first pass prepares what needs approving, a person approves it, and
a second pass closes the ticket.

---

## What happened in the graded run

| Ticket | Result | Agents | Never called |
| --- | --- | --- | --- |
| 101 — customer wants a tee in size S | resolved | boss, inventory, accounting, customer service | facilities |
| 102 — rent due | resolved | boss, facilities | the other three |
| 103 — student group wants 20 hoodies, discounted | resolved | boss, inventory, accounting, customer service | facilities |

Cash: **$3,400.00 → $152.00.** Invoice 501 paid ($840), one tee reprinted ($8), rent paid
($2,400). A 12-hoodie reprint was **refused** — $264 against $152, and this shop never goes
below zero. The team proposed every one of those spends and charged none of them.

## Layout

```
hw5/
├── AI_prompts.md          every prompt typed while building this, in order
├── requirements.txt       Python dependencies for the server and the backend
├── .env.example
├── .gitignore
├── .mcp.json              registers the MCP server for an MCP client
├── README.md
├── data/
│   ├── campus_customs.db       the original — never written to
│   └── campus_customs_new.db   the working copy
├── mcp_server/
│   ├── server.py          nine tools over the shop database
│   └── README.md
├── frontend/              React + Vite + TypeScript board
├── backend/
│   ├── main.py            FastAPI app — uvicorn main:app --reload --port 8000
│   ├── models.py          every Pydantic type
│   ├── agents.py          the five agents and the delegation between them
│   ├── settings.py        model, limits, token budget
│   ├── audit.py           the append-only trail
│   ├── runner.py          work tickets from the command line
│   └── prompts/
│       ├── boss.md  inventory.md  accounting.md  facilities.md  customer_service.md
└── output/
    ├── harness.md         the full system write-up — start here
    ├── mcp_smoke.json     evidence the MCP tools return real database values
    ├── desk_tickets.html  plan vs actual per ticket, the cash tab, and the reflection
    ├── design.md          why the dashboard looks the way it does
    ├── resolved_tickets.json
    ├── resolved_board.html  screenshots of the board, one per resolved ticket
    ├── board_images/
    ├── audit_trail.json   every agent step, appended across every run
    └── github_url.txt
```

### A note on the files in `backend/`

The assignment's layout names `main.py`, `models.py` and `prompts/`. Four more modules sit
beside them, and each is there because something the assignment asked for lives in it:

| File | Why it exists |
| --- | --- |
| `agents.py` | The five agents and the delegation between them — "the agent files under `backend/`". |
| `settings.py` | The model choice and every limit that keeps token use in check, in one place. |
| `audit.py` | Writes the append-only `output/audit_trail.json`. |
| `runner.py` | Works tickets from the command line, including the full reset-run-approve-close cycle. |

The agent itself is still what the assignment specified: the prompts in `backend/prompts/`,
the structured types in `models.py`, and the tools on the MCP server.

## Where to look first

**`output/harness.md`** is the complete write-up: the database, the nine MCP tools and the
tables each touches, the five agents and which tools each may call, the safety rules, the
token limits, and what the graded run did.

**`output/desk_tickets.html`** opens in a browser. Five tabs: one per ticket with the plan
written beforehand against what actually happened, a cash tab reconciling every dollar, and a
reflection.

**`output/resolved_board.html`** shows the finished board with a screenshot per ticket.
