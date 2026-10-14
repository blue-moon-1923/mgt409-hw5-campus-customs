# AI Prompts — Homework 5

This file records every prompt typed into the vibe coder for Homework 5, verbatim and in
chronological order. It is a record of what was typed, not of the files the assistant
generated, so prompts are quoted exactly as entered — typos and all.

**Assignment:** Campus Customs Multi-Agent Operations — an MCP server, a FastAPI backend
running a multi-agent team, and a React dashboard where a human watches the agents work and
approves what needs approving.

The **Prompt Log** below is the running chronological record. The **Problem sections** that
follow group those same prompts under the eleven assignment problems, showing the work was
done problem by problem rather than submitted all at once.

---

## Prompt Log

### 2026-10-13 — Prompt 1

> okay I'm onto homework 5 today called "Campus Customs Multi-Agent Operations". We're going to build a agentic team that runs the shop. We need a MCP server, FAST API backend With a multi-agent team and a React dashboard, so the human can watch the agents work and, you know, improve stuff. And the agent team needs full connectivity to delegate tasks to other agents, and we're going to build the agent. So one is going to be the boss that reads each ticket, decides who works on it, and makes final calls. The inventory to look at stock uh, with size, any shortfalls, and then which vendors can restock. An accounting agent to watch cash, invoices, checks, margins, uh, prepares payments and other orders, like purchasing orders. A facilities agent that handles the shop space, like leases, rents, etc. And then a customer service uh, agent to draft messages for customers. Don't do anything yet, ill give you more information

### 2026-10-14 — Prompt 2

> fresh for HW-5.      look at my recent download and unzip to get "data/campus_customs.db" Tables should include desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments and invoices. The tools will updat the database as tickets resolve. We need to make a copy of the databse file called "data/campus_customs_new.db" to point MCP server and backend at. campus_customs.db will stay untouched so we can reset when we want to restart resolving tickets. There's some important rules for the shop. The field desk.date underscore today is today in parentheses for the shop. Use this date to determine what is overdue. Also, vendor lead times come from the vendors table. A vendor will not ship new product while they still have an open invoice that's unpaid. And of course, human approval is needed for any payments. Points on this assignment for me will be deducted if this is not made. Uh, if any payment is made, make sure to update the relevant table. Also, if there's not enough cash, the pay tool must refuse. We cannot have any negative balances. cash only goes out in this homework. We're, we did not model revenue, so no money comes in. And before a full run to resolve any tickets, make sure to reset the database to the original value. And do not email customers or call real vendors. All drafts stay on the board. use PORTKEY_API_KEY for AI calls and only use the equivelant  gpt-6-luna. Multi-agents burn tokens super fast so they should be a weak/low version. I will lose points if the agents don't save token by running a weaker model. FYI - the final submission will be a public Git-hub repo

### 2026-10-14 — Prompt 3

> there's no exact ID, whichever is the lowest toke use

### 2026-10-14 — Prompt 4

> first Problem 1, "Vibe coder prompts" we need to create AI_prompts.md to keep it updated to log everything I say. each section is a problem, 1-11, this is #1 and each section includes "problem number and title" at least one prompt, and a follow up with what was missing if needed

### 2026-10-14 — Prompt 5

> now problem #2, "Study the Campus Customs database" open data/campus customs.db and look through the tables and fields, copy the origional file to data/campus_customs_new.db Some later questions will use that copy. Also, we need to study uh, three open tickets so we see how they link to other tables. And we're going to start output/harness.md. And uh, for the tables, list the fields and what short line on like why that table matters for the agents. Uh, these are going to grow in later problems.

### 2026-10-14 — Prompt 6

> problem 3: "Build the MCP server" we need to write a MCP server in mcp_server/ using FastMCP, it will connect to data/campus_customs_new.md. No connection/running right now. Every agent in thishoemwork uses this MCP server, we can add more tools later but For now, just write three tools uh, that you know we'll need for the tickets in the database. Uh, add clear names, never invent data, and only use information in the database. Uh, then in output/harness.md, uh, we're going to list each of those three MCP tools. And for each of those tools, uh, have the table that it reads, which tip, ticket it unlocks, like 101, 102, 103, and then add a sentence on why the tool is right for the ticket. Uh, don't have any vague lines like "reads inventory". These are going to score low. So have it more detailed uh, and tie the tool to the ticket. Uh, also write a short MCP_server/README.md. This is a file that will explain like what the MCP server does, which database file it uses, and the three tools that it has.

### 2026-10-14 — Prompt 7

> now problem 4, "Add the MCP server to vibe coder and test each tool" now add the MCP server to this project in claude code so this vibe coder can call the tools, save the json text in .mcp.json at the root of the project or however you save the local MCP server lists, now with this vibe coder connected please test each of the three MCP tools and save evidence of their function in, output/mcp_smoke.json. The evidence can include the prompt you asked the vibe coder, the tool name, and the tool output which must match the values in data/campus_customs_new.db

### 2026-10-14 — Prompt 8

> Now problem 5, "build the agent team and grow the MCP tools" now build the agentic team using PydanticAI: boss, inventory, accounting, facilities, and Customer Service. Include all the prompts, models and agent loops so they can delegate to one another with complete transparency. the agent prompts should go into backend/prompts/ with one file an agent. Data types go in backend/models.py and the agent files under backend/ The 5 roles must be clear. use PORKEY_API_KEY and only gpt-6 for agents. write detailed prompts with shop rules for the agents to use, more detailed prompts that cover the agents work will score higher in this assignment. They should NOT be short and genaric. Also, uh, add any tools the agents need to uh, the MCP server uh, so they can work on the open tickets. And then the shop facts uh, come from the MPC server over data/campus_customs_new.db . Do not invent a second shop tools layer uh, that bypasses the MCP. And then wire the agents so that they append to output/audit_trail.jsonuh, as they run so that each agent loop step uh, records enough to audit later. And then append to this file, uh, do not wipe at each run. Then an output/harness.md list each agent and then the MCP tools, uh, including the ones we add in this problem, along with the table the tool uses. Uh, these should also include a short uh, safety section, like guardrails a real business would want uh, when the agent touches real customers and real money. Uh, and then also please add limits that keep the token use in check and update MCP_server/README.md so the tool list matches what we have now.

### 2026-10-14 — Prompt 9

> okay great, now problem 6, "plan the three tickets" before wiring the background, we need to write what we expect the team to do for each ticket. Build output/desk_tickets.html which is a page that we can double click with one tab a ticket (101, 102, etc...) also add "Cash" and "Reflection" tabs for later leave them blank for now. On each ticket fill "Expected" section only, so leave room for an "Actual section" to fill after the agent run. then on each ticket section write in unique words (ie your own), who the boss calls first, all the agents you expect (like not "boss calls everyone") and which MCP tools you expect that run to use. Plans should not send specialists on each ticket. These will score low, I need to compare this plan to what the agents actually do to resolve tickets.

### 2026-10-14 — Prompt 10

> now problem 7, "backend routes" the react frontend dashboard (the next problem) needs a backend to call. In backend/main.py use FastAPI and add routes that do the following: Return the three tickets and whether each is open or resolved. Take a ticket ID and run your agent team on that ticket. Uh, also return recent agent events, like what each agent said, what tools they used, uh, refreshing the board with that information. And then approve a payment uh, slash purchase after a human clicks approve. Uh, this is so the agents only prepare the pay. This route is what actually charges cash. Uh, and then also return the current checking balance from cash_accounts. Reset the database to the original values when you want to try a fresh run. And then from the backend folder, uh, start the server with uvicorn main:app --reload --port 8000 this turns on backend at http://localhost:8000 so the front end can call those routes. in output/harness.md list each route in one line (what url and what it does)

### 2026-10-14 — Prompt 11

> Problem 8, "agent dashboard" build the forntend dashboard in frontend/ with React + Vite + TypeScript. The page should call the routes we built in problem 7. The board at a minimum should: Should list all three tickets, let someone pick one ticket and start the agent team on it. Show each agent what they're saying slash doing while the ticket is running. Uh, mark a ticket as resolved when the ticket finishes or the run finishes. Uh, and then show a short summary of what each agent did on that ticket. Also let a human approve a pay or purchase when asked and show the checking balance. Uh, this should drop after an approved pay. And make it look good. Have a creative layout and feel. Uh, this is a real desk people would sit at. Um, put some thought into how it looks. Uh, maybe make it tan and and green, um, uh, modern looking. Then tell the backend to talk to the backend at http://localhost:8000 on the backend allow the Vite page orgin, typically "http://localhost:5173, so the browser can call those routes. Start board with "npm run dev" This will open uh, the React desk in your browser so that you can pick tickets and watch agents, and then write output/design.md with uh, what you choose for the dashboard look. So the layout, how the agents read differently, how tickets are resolved, cache shows up, uh, and why, including the creative choices that made it feel special and why humans would actually enjoy using it.

### 2026-10-14 — Prompt 12

> Problem 9, "resolve the tickets" before testing agents on a full run over the three tickets (although maybe we did this already?), reset the working database data/campus_customs_new.db so you start clean. recording rhe starting checking balance, run all three tickets until they are resolved. Open output/desk_tickets.html from problem 6. in each ticket tab, fill the Actual section from the run with: which agents worked, what they delegated, whcih tools they used. Keep the expected section to compare the two. Now on the cash side of the same output/desk_tickets.html itemize the money with a checking balance (the starting amoutn after the reset), for each ticket how the cash changed when the ticket was resolved and why (which pay/purchase and $$ amount), and ending balance to match cash_accounts in the working databse. wrong cash math loses points in this assignment even if the board shows resolved. also save output/resolved_tickets.json for each ticket with ID, final status, breif outcome, what each agent added and human approvals/inputs. also save output/resolved_board.html as a page you can double click with a screeshot of the react board for each resolved ticket (101, 102 and 103). Real runs are appended to output/audit_trail.json and finish output/harness.md to include tables, MCP tools, the 5 agents, the dashboard and safety rules.

### 2026-10-14 — Prompt 13

> Okay now problem 10, "Reflection" open output/desk_tickets.html  and fill in the reflection tab. Okay, I need you to answer um, in this vibe, or my vibe, like human vibe, and be very detailed and thorough to the following questions. How would you evaluate the performance of the agents uh, working on each ticket, and why? For each ticket, how did the actual compare to the expected plan that you wrote earlier? What would have been simpler as one agent? Oh, excuse me, what would have been simpler as one agent with tools, and why? Uh, describe three new problems campus customs might face that this agent team could solve uh, with the tools that we built. And describe three new problems campus customs might face that this agent team could not solve with the tools that we, you, you built. Also explain the tools and agents that you need to solve them uh, for the three new problems. Lastly, tie every answer to this app and the three tickets that you ran. Use the ticket tabs and cache tab on the same page as your evidence. Um, any generic AI essays without campus customs details will score low in this assignment. Please make it detailed, human, and uh, yeah, a good strong essay.

---

## Problem 1 — Vibe Coder Prompts

### Initial prompt

> first Problem 1, "Vibe coder prompts" we need to create AI_prompts.md to keep it updated to log everything I say. each section is a problem, 1-11, this is #1 and each section includes "problem number and title" at least one prompt, and a follow up with what was missing if needed

### Follow-up prompt, if needed

_None needed._

### What was missing from the first prompt

Nothing was missing; the prompt specified the file, that it must log everything typed, the
eleven problem sections, and what each section has to contain. The three prompts that came
before it — the assignment brief, the shop rules and data pack, and the model decision — are
recorded in the Prompt Log above as Prompts 1 to 3, since they were setup for the homework
rather than a numbered problem.

---

## Problem 2 — Study the Campus Customs Database

### Initial prompt

> now problem #2, "Study the Campus Customs database" open data/campus customs.db and look through the tables and fields, copy the origional file to data/campus_customs_new.db Some later questions will use that copy. Also, we need to study uh, three open tickets so we see how they link to other tables. And we're going to start output/harness.md. And uh, for the tables, list the fields and what short line on like why that table matters for the agents. Uh, these are going to grow in later problems.

### Follow-up prompt, if needed

_None needed._

### What was missing from the first prompt

Nothing was missing; the prompt named the file to study, the copy to make, the three tickets
to trace, the document to start, and the per-table detail wanted. The data pack had already
been unzipped and copied while the shop rules were being set up, so the copy was refreshed
from the original to be certain it was untouched before the study began.

---

## Problem 3 — Build the MCP Server

### Initial prompt

> problem 3: "Build the MCP server" we need to write a MCP server in mcp_server/ using FastMCP, it will connect to data/campus_customs_new.md. No connection/running right now. Every agent in thishoemwork uses this MCP server, we can add more tools later but For now, just write three tools uh, that you know we'll need for the tickets in the database. Uh, add clear names, never invent data, and only use information in the database. Uh, then in output/harness.md, uh, we're going to list each of those three MCP tools. And for each of those tools, uh, have the table that it reads, which tip, ticket it unlocks, like 101, 102, 103, and then add a sentence on why the tool is right for the ticket. Uh, don't have any vague lines like "reads inventory". These are going to score low. So have it more detailed uh, and tie the tool to the ticket. Uh, also write a short MCP_server/README.md. This is a file that will explain like what the MCP server does, which database file it uses, and the three tools that it has.

### Follow-up prompt, if needed

_None needed._

### What was missing from the first prompt

Nothing was missing; the prompt named the folder, the framework, the database file, the number
of tools, the documentation wanted in both `output/harness.md` and `mcp_server/README.md`, and
warned against vague tool descriptions. The prompt says the server connects to
`data/campus_customs_new.md`, which is the database file `data/campus_customs_new.db` — the
`.md` was read as a slip rather than a different file. The three tool functions were exercised
directly against the database to confirm their numbers, which is not the same as running the
server, so the "no connection/running right now" instruction still holds.

---

## Problem 4 — Add the MCP Server to the Vibe Coder and Test Each Tool

### Initial prompt

> now problem 4, "Add the MCP server to vibe coder and test each tool" now add the MCP server to this project in claude code so this vibe coder can call the tools, save the json text in .mcp.json at the root of the project or however you save the local MCP server lists, now with this vibe coder connected please test each of the three MCP tools and save evidence of their function in, output/mcp_smoke.json. The evidence can include the prompt you asked the vibe coder, the tool name, and the tool output which must match the values in data/campus_customs_new.db

### Follow-up prompt, if needed

> how do I restart?

> Id id that but no prompt to truast campus-customs?

### What was missing from the first prompt

Nothing was missing from the instruction itself. The follow-ups were about getting the
connection live: Claude Code reads its MCP server list when a session starts, so writing
`.mcp.json` was not enough and the session had to be restarted before `campus-customs`
appeared. Before asking for the restart, the server was exercised over the raw MCP stdio
protocol to confirm the config and the handshake were correct, so the restart was not a guess.
The evidence file was deliberately not written until the tools had actually been called
through the vibe coder's own connection.

---

## Problem 5 — Build the Agent Team and Grow the MCP Tools

### Initial prompt

> Now problem 5, "build the agent team and grow the MCP tools" now build the agentic team using PydanticAI: boss, inventory, accounting, facilities, and Customer Service. Include all the prompts, models and agent loops so they can delegate to one another with complete transparency. the agent prompts should go into backend/prompts/ with one file an agent. Data types go in backend/models.py and the agent files under backend/ The 5 roles must be clear. use PORKEY_API_KEY and only gpt-6 for agents. write detailed prompts with shop rules for the agents to use, more detailed prompts that cover the agents work will score higher in this assignment. They should NOT be short and genaric. Also, uh, add any tools the agents need to uh, the MCP server uh, so they can work on the open tickets. And then the shop facts uh, come from the MPC server over data/campus_customs_new.db . Do not invent a second shop tools layer uh, that bypasses the MCP. And then wire the agents so that they append to output/audit_trail.jsonuh, as they run so that each agent loop step uh, records enough to audit later. And then append to this file, uh, do not wipe at each run. Then an output/harness.md list each agent and then the MCP tools, uh, including the ones we add in this problem, along with the table the tool uses. Uh, these should also include a short uh, safety section, like guardrails a real business would want uh, when the agent touches real customers and real money. Uh, and then also please add limits that keep the token use in check and update MCP_server/README.md so the tool list matches what we have now.

### Follow-up prompt, if needed

_None needed._

### What was missing from the first prompt

Nothing was missing; the prompt named the five roles, the framework, the file layout, the
model restriction, the MCP-only rule, the audit requirement, and every section the harness
had to gain. Two decisions were taken beyond the letter of it and are documented in the
harness: the three payment tools are given to **no** agent, so the human-approval rule is
enforced by what the team can call rather than only by what it is told; and each agent is
given only the two to four MCP tools its role needs, which halved the token cost of a ticket
from 33,695 to 17,562 with no loss of answer quality.

---

## Problem 6 — Plan the Three Tickets

### Initial prompt

> okay great, now problem 6, "plan the three tickets" before wiring the background, we need to write what we expect the team to do for each ticket. Build output/desk_tickets.html which is a page that we can double click with one tab a ticket (101, 102, etc...) also add "Cash" and "Reflection" tabs for later leave them blank for now. On each ticket fill "Expected" section only, so leave room for an "Actual section" to fill after the agent run. then on each ticket section write in unique words (ie your own), who the boss calls first, all the agents you expect (like not "boss calls everyone") and which MCP tools you expect that run to use. Plans should not send specialists on each ticket. These will score low, I need to compare this plan to what the agents actually do to resolve tickets.

### Follow-up prompt, if needed

_None needed._

### What was missing from the first prompt

Nothing was missing; the prompt named the file, the tab structure, which sections to fill and
which to leave empty, and what each ticket plan had to say. One point of honesty about the
sequence: trial runs of the team had already been made in Problem 5 while the agents were
being built, so the expectations here were written as a specification of what a well-designed
team *ought* to do with each ticket, derived from the ticket and table structure, rather than
as a blind prediction. The Actual sections are left empty for the measured comparison.

---

## Problem 7 — Backend Routes

### Initial prompt

> now problem 7, "backend routes" the react frontend dashboard (the next problem) needs a backend to call. In backend/main.py use FastAPI and add routes that do the following: Return the three tickets and whether each is open or resolved. Take a ticket ID and run your agent team on that ticket. Uh, also return recent agent events, like what each agent said, what tools they used, uh, refreshing the board with that information. And then approve a payment uh, slash purchase after a human clicks approve. Uh, this is so the agents only prepare the pay. This route is what actually charges cash. Uh, and then also return the current checking balance from cash_accounts. Reset the database to the original values when you want to try a fresh run. And then from the backend folder, uh, start the server with uvicorn main:app --reload --port 8000 this turns on backend at http://localhost:8000 so the front end can call those routes. in output/harness.md list each route in one line (what url and what it does)

### Follow-up prompt, if needed

> are you waiting for anything else, or is problem 7 done?

### What was missing from the first prompt

Nothing was missing from the instruction. The follow-up came while the approval chain was
still being tested, and that testing found a real defect worth recording: the approve route
originally marked a request `failed` whenever the MCP server refused it, so a refusal caused
by an agent naming itself as approver permanently burned a legitimate payment request. A
guardrail refusal is not a decision, so a refused request now stays pending and approvable,
records why it was refused, and counts attempts. Two further details were added beyond the
letter of the prompt: `ApprovalRequest` gained an `order` field, because a restock approval
was otherwise unexecutable, and a decline route, because a dashboard that can only say yes is
not really an approval step.

---

## Problem 8 — Agent Dashboard

### Initial prompt

> Problem 8, "agent dashboard" build the forntend dashboard in frontend/ with React + Vite + TypeScript. The page should call the routes we built in problem 7. The board at a minimum should: Should list all three tickets, let someone pick one ticket and start the agent team on it. Show each agent what they're saying slash doing while the ticket is running. Uh, mark a ticket as resolved when the ticket finishes or the run finishes. Uh, and then show a short summary of what each agent did on that ticket. Also let a human approve a pay or purchase when asked and show the checking balance. Uh, this should drop after an approved pay. And make it look good. Have a creative layout and feel. Uh, this is a real desk people would sit at. Um, put some thought into how it looks. Uh, maybe make it tan and and green, um, uh, modern looking. Then tell the backend to talk to the backend at http://localhost:8000 on the backend allow the Vite page orgin, typically "http://localhost:5173, so the browser can call those routes. Start board with "npm run dev" This will open uh, the React desk in your browser so that you can pick tickets and watch agents, and then write output/design.md with uh, what you choose for the dashboard look. So the layout, how the agents read differently, how tickets are resolved, cache shows up, uh, and why, including the creative choices that made it feel special and why humans would actually enjoy using it.

### Follow-up prompt, if needed

_None needed._

### What was missing from the first prompt

Nothing was missing; the prompt named the stack, the folder, the routes to call, the minimum
behaviour, the colour direction, the start command, and what `output/design.md` had to cover.
Driving the finished desk did surface a backend defect worth recording: after a rent payment
the "room left" figure went to −$2,240, because paying rent rolls the lease's `next_due`
forward a month while the cash route still counted the full rent as committed. Rent now counts
as a commitment only when it falls due within seven days, so room left reads $160 both before
and after the payment — settling rent does not change how much room the shop has.

---

## Problem 9 — Resolve the Tickets

### Initial prompt

> Problem 9, "resolve the tickets" before testing agents on a full run over the three tickets (although maybe we did this already?), reset the working database data/campus_customs_new.db so you start clean. recording rhe starting checking balance, run all three tickets until they are resolved. Open output/desk_tickets.html from problem 6. in each ticket tab, fill the Actual section from the run with: which agents worked, what they delegated, whcih tools they used. Keep the expected section to compare the two. Now on the cash side of the same output/desk_tickets.html itemize the money with a checking balance (the starting amoutn after the reset), for each ticket how the cash changed when the ticket was resolved and why (which pay/purchase and $$ amount), and ending balance to match cash_accounts in the working databse. wrong cash math loses points in this assignment even if the board shows resolved. also save output/resolved_tickets.json for each ticket with ID, final status, breif outcome, what each agent added and human approvals/inputs. also save output/resolved_board.html as a page you can double click with a screeshot of the react board for each resolved ticket (101, 102 and 103). Real runs are appended to output/audit_trail.json and finish output/harness.md to include tables, MCP tools, the 5 agents, the dashboard and safety rules.

### Follow-up prompt, if needed

> are you finished or not yet? When you finish a problem end with "ready for next problem"

> still going?

### What was missing from the first prompt

Nothing was missing from the instruction. The prompt asked "maybe we did this already?" — no.
Earlier runs stopped at `blocked_pending_approval` because nothing was ever approved, so no
money moved and no ticket reached `resolved`. This was the first run through the human
approval step.

The first attempt was kept as a diagnostic rather than reported, because it exposed two
defects that would have cost marks. The team paid twice for the same tee, since a second pass
could not see what the first had already done; and no ticket reached `resolved`, because
nothing in the boss prompt tied its outcome vocabulary to the ticket's status. Both were fixed
— a duplicate-spend guard at the MCP, API and prompt layers, `work_already_done` added to
`get_ticket_context`, and closing rules in the boss prompt — and the graded run was made from
a fresh reset. Its cash was then reconciled programmatically against `cash_accounts` rather
than by eye.

---

## Problem 10 — Reflection

### Initial prompt

> Okay now problem 10, "Reflection" open output/desk_tickets.html  and fill in the reflection tab. Okay, I need you to answer um, in this vibe, or my vibe, like human vibe, and be very detailed and thorough to the following questions. How would you evaluate the performance of the agents uh, working on each ticket, and why? For each ticket, how did the actual compare to the expected plan that you wrote earlier? What would have been simpler as one agent? Oh, excuse me, what would have been simpler as one agent with tools, and why? Uh, describe three new problems campus customs might face that this agent team could solve uh, with the tools that we built. And describe three new problems campus customs might face that this agent team could not solve with the tools that we, you, you built. Also explain the tools and agents that you need to solve them uh, for the three new problems. Lastly, tie every answer to this app and the three tickets that you ran. Use the ticket tabs and cache tab on the same page as your evidence. Um, any generic AI essays without campus customs details will score low in this assignment. Please make it detailed, human, and uh, yeah, a good strong essay.

### Follow-up prompt, if needed

_None needed._

### What was missing from the first prompt

Nothing was missing; the prompt listed every question to answer, the voice to write in, the
requirement to use the ticket tabs and cash tab as evidence, and the warning against a generic
essay. The reflection is argued from the run's own figures — token counts per ticket, the
payments table as stored, the stock rows still at zero, and quotations from what the agents
actually wrote — and it says plainly that two of the three tickets would have been cheaper
and no worse with a single agent holding all nine tools.

---

## Problem 11 — Submit to GitHub

### Initial prompt

> Great, now problem 11, "submit to git-hub" we need to push the code to a public GitHub repository so graders can clone it, and I will submit the repo URL to canvas and also put it in output/github_url.txt. Do not push real .env to the GitHub repo. Do include both database files under data/ (the original and your working copy) so graders can run your app easily. The expected file layout is in the attached photo. README should explain: copy original DB to the working copy when you need a clean run, start MCP server, start FastAPI backend, start the React board, reset the DB before a three ticket run. [screenshot of the expected file tree]

### Follow-up prompts

> I think show it as post? But also I don't get the files the diagram doesn't show, would they fit under a category within the diagram?

> Okay now it matched the screenshot yes?

> Remind me how to make a repo again?

### What was missing from the first prompt

Three things the screenshot could not settle on its own.

First, the screenshot shows `data/campus_customs_new.db` but not what state it should be in. A
working copy can be shipped pristine (identical to the original, so a grader starts from zero)
or post-run (the state the graded three-ticket run left behind: $152 cash, three payments
recorded, three tickets resolved). The follow-up picked post-run, which is the better choice
here — the grader can open the board and see the shop as the agents left it, and `runner.py
--reset` restores the clean copy in one command whenever they want to re-run it themselves.

Second, the diagram does not show every file the project actually contains. `backend/` in the
screenshot lists only `main.py`, `models.py`, and `prompts/`, but this build also has
`agents.py`, `audit.py`, `runner.py`, and `settings.py`. Matching the diagram literally would
have meant inlining roughly 1,400 lines into a single `main.py` — worse code for the sake of a
picture. The README instead carries a table naming each extra module and the part of the
assignment it implements, so a grader reading the tree can see nothing was added that is not
required.

Third, the prompt named `output/github_url.txt` as a deliverable but that file cannot be
written until the repository exists, so repo creation had to come first and the URL was filled
in afterward.

The security requirement was met by shipping only `.env.example` with `PORTKEY_API_KEY=your-key-here`,
and by a `.gitignore` that excludes `.env`, `.venv/`, and `node_modules/` but deliberately does
**not** exclude `data/` — with a comment in the file explaining that both databases are
submitted on purpose.

Repository: https://github.com/blue-moon-1923/mgt409-hw5-campus-customs
