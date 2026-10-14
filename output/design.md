# The operations desk — design notes

What the dashboard looks like, why it looks that way, and what the choices are doing.

The guiding idea: **this is a desk, not a dashboard.** A shop owner sitting here is doing
three things — deciding what to work on, watching it get worked, and signing for money. So the
screen is three places rather than a grid of widgets, and each one is treated like the
physical thing it stands in for.

---

## Layout: three columns, named like furniture

| Column | Called | Holds |
| --- | --- | --- |
| Left | **The spike** | The dockets waiting to be worked |
| Centre | **The floor** | The five agents, and what they are doing |
| Right | **The drawer** and **the tray** | The money, and what needs signing |

Naming them after objects rather than functions ("The spike", not "Tickets") does real work:
it tells you instantly that the left column is a queue you pull from, and the right is where
things end up. Nobody needs a legend.

The widest column is the middle one, because watching the team is what you actually came for.
The spike is narrow — a ticket is three facts and a button. The drawer is narrow and tall,
because money is a column of figures.

## The agents read differently from everything else

This is the part the design works hardest at.

**Five name plates, always visible, even when dark.** A plate lights only when that agent was
called. This matters more than it sounds: a ticket that lights one plate and leaves four dark
*is the team working well*, and that only reads if the unlit four are on screen. Hide idle
agents and you lose the ability to see restraint. Ticket 102 lights Boss, Accounting and
Facilities and leaves Inventory and Customer service dark, and you can see that in half a
second.

**The live agent's lamp blinks brass.** Finished agents hold a steady green. One glance tells
you who is thinking right now.

**Delegation is shown by indentation.** A specialist the boss called sits one step in with a
green rule down its left edge; one called by another specialist sits two steps in with a tan
rule. The shape of the hand-off chain is legible without reading a word — you can see at a
glance whether the boss fanned out or whether a specialist asked for help.

**Each trace carries its own cost.** Tokens and seconds sit in the corner of every step in a
monospace face. Agents are not free, and a desk that hides what they cost teaches the wrong
habit.

**Tool calls are shown underneath, with their arguments.** Refused calls turn rust-red. The
point is that you can audit a claim without leaving the screen: the agent says stock is zero,
and directly below is `check_stock_and_restock_options {"sku": "CC-TEE-WHITE", "size": "S"}`.

## Tickets: rubber stamps, not status pills

Each docket carries a stamp — **open**, **in progress**, **blocked**, **resolved** — set in
small caps with a 1.5px rule and rotated three degrees, the way a stamp lands slightly crooked.
Status pills are everywhere and read as decoration. A stamp reads as *someone decided this*.

Dockets have a torn-pad look, the requester's name in italic underneath the subject, and a
coloured left edge that changes when selected or running. A ticket carrying an unpaid invoice
gets that fact in rust-red on the face of the slip, because it is the single detail most
likely to change what the team must do.

The run button changes its words with the state: **"Put the team on it"** becomes **"Team
working…"** becomes **"Run again"**. It is the one control on the slip, and it says what will
happen rather than what it is.

## Cash: the biggest number on the board, and it only falls

The balance sits in a dark green block — the only inverted panel on the screen — with the
figure in the display serif at twice the size of anything near it. In this shop no revenue is
modelled, so the number is one-directional: every approval makes it smaller. **When it drops
it flashes brass and falls into place**, so an approval has a visible physical consequence
rather than a silent re-render.

Underneath, what is still claiming it: unpaid invoices, rent coming due, and **room left**.
That last line is the one that matters — "we have $3,400" is not useful, "we have $160 of
room" is.

One correctness detail worth recording: rent counts as committed only when it falls due within
seven days. Paying rent rolls its next due date forward a month, and without that window a
paid lease kept claiming the same $2,400 — the room left went to **−$2,240** the instant the
rent was settled. With the window, room left reads $160 both before and after. Paying rent
does not change how much room you have, and the figure now says so.

The ledger below records every payment with **who approved it**, by name.

## Approvals: chits torn off a pad

Each pending spend is a chit with a torn edge along the top, the amount in large display type,
and everything needed to decide without going hunting: what it is for, why, what it unblocks,
and what the balance would become. Approving asks for nothing extra because your name is
already at the top of the desk.

**The team cannot pay.** The tray says so when it is empty — *"The team prepares spends; it
cannot make them."* That sentence is the whole governance model in nine words, and it sits
where a person will read it.

A refused payment stays on the tray with the reason in rust and an attempt count, rather than
vanishing. A guardrail refusal means *not like this*, not *never*.

## Drafts: pinned, and visibly unsent

Draft messages are pinned cards, each rotated a fraction of a degree so the board looks like
paper rather than a list, with a crooked **not sent** seal. The team has no tool that sends
anything, and "did this go out?" is the first question a shop owner would ask, so the answer is
stamped on the card rather than buried in a tooltip.

## The palette and the type

Tan paper, forest-green ink, brass fittings. The background is a faint woven weave at 45° over
warm tan — a desk blotter, not a gradient. Cards are near-white paper, so they lift off it.

- **Newsreader** (serif) for anything a person reads as content: headings, agent names,
  decisions, the balance. It is an editorial face, and it makes the agents' output read like
  writing rather than output.
- **Inter** for the interface — labels, buttons, controls.
- **JetBrains Mono** for figures and tool arguments, because money and arguments should align
  and be obviously machine-exact.

Green is the shop. Brass is attention — the live lamp, eyebrows, the falling balance. Rust is
the only alarm colour, and it is spent carefully: a blocking invoice, a refused tool call, a
negative number, an unsent seal.

## The shop clock

Where a clock would go, the masthead shows **the shop's date** — Monday, 31 August 2026 — with
"all timings measured from here" underneath. Every rule in this shop is measured from
`desk.date_today`, and a person watching the board should never have to wonder whether
"overdue" means overdue today or overdue in the shop. It costs one line and removes a whole
category of confusion.

## Why someone would enjoy sitting here

- **You can see the team think.** Traces arrive one at a time with a small rise, indented by
  who asked whom. It feels like watching work happen rather than waiting for a spinner.
- **Restraint is visible.** The dark plates are as informative as the lit ones.
- **Every claim is checkable in place.** The agent's sentence and the tool call that produced
  it are two lines apart.
- **Your decision has weight.** You sign a chit, and the biggest number on the screen falls.
- **It does not pretend.** The drafts say unsent. The tray says the team cannot pay. The clock
  says which day it is counting from. Nothing is dressed up as more finished than it is.

## Running it

```bash
cd frontend
npm install
npm run dev
```

The desk opens at **http://localhost:5173** and calls the FastAPI backend at
**http://localhost:8000**, which allows that origin by name. Start the backend first.
