"""The Campus Customs agent team: boss, inventory, accounting, facilities, customer service.

Five PydanticAI agents over one shared MCP server. Three things define the design:

**One source of shop facts.** Every agent gets its tools from the Campus Customs
MCP server, attached in-process. There is no second data layer: no agent queries
SQLite, and no agent is handed facts the MCP server did not produce. If a number
appears in a report, a tool returned it.

**Delegation is a tool, and it is bounded.** Any agent can hand work to any other
through `delegate`, so the team is a mesh rather than a tree. What stops a mesh
of five from calling each other forever is three limits enforced in code: a depth
cap, a total hand-off budget per ticket, and a rule that an agent already on the
call stack cannot be re-entered.

**Everything is recorded as it happens.** Each agent turn appends one step to
`output/audit_trail.json` — who ran, at what depth, for which ticket, which MCP
tools were called with what arguments and results, who it delegated to, what it
cost in tokens, and why it stopped.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from openai import AsyncOpenAI  # noqa: E402
from pydantic_ai import Agent, RunContext  # noqa: E402
from pydantic_ai.mcp import MCPToolset  # noqa: E402
from pydantic_ai.messages import (  # noqa: E402
    BaseToolCallPart,
    BaseToolReturnPart,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
)
from pydantic_ai.models.openai import (  # noqa: E402
    OpenAIResponsesModel,
    OpenAIResponsesModelSettings,
)
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.usage import UsageLimits  # noqa: E402

import audit  # noqa: E402
import settings  # noqa: E402
from models import (  # noqa: E402
    AgentName,
    AuditStep,
    DelegationRecord,
    SpecialistReport,
    TicketOutcome,
    ToolCallRecord,
)

if str(settings.MCP_DIR) not in sys.path:
    sys.path.insert(0, str(settings.MCP_DIR))


# --------------------------------------------------------------- model wiring


def _api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Put it in the repository root .env.")
    return key


def redact(text: str) -> str:
    """Strip the API key from any string before it is logged or returned."""
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    return text.replace(key, "[redacted]") if key else text


_model: OpenAIResponsesModel | None = None


def build_model() -> OpenAIResponsesModel:
    """The gpt-6 model through the Portkey gateway, built once per process."""
    global _model
    if _model is None:
        key = _api_key()
        client = AsyncOpenAI(
            api_key=key,
            base_url=settings.PORTKEY_BASE_URL,
            default_headers={"x-portkey-api-key": key},
        )
        _model = OpenAIResponsesModel(
            settings.MODEL_NAME, provider=OpenAIProvider(openai_client=client)
        )
    return _model


def model_settings(max_output_tokens: int | None = None) -> OpenAIResponsesModelSettings:
    """Low reasoning effort and low verbosity — the token budget, in two settings."""
    return OpenAIResponsesModelSettings(
        openai_reasoning_effort=settings.REASONING_EFFORT,
        openai_text_verbosity=settings.VERBOSITY,
        max_tokens=max_output_tokens or settings.MAX_OUTPUT_TOKENS,
    )


_toolset: MCPToolset | None = None

# Which MCP tools each role can see. Two reasons this is a list and not "all":
#
# **Safety.** The three tools that move money — pay_invoice, pay_rent and
# place_restock_order — are not given to *any* agent. The team cannot pay for
# something it cannot call. The MCP server refuses an agent approver as well, so
# the rule holds at both ends, but not exposing the tool is the stronger half.
#
# **Cost.** A tool schema is input tokens on every single model request. Handing
# all nine tools to all five agents means paying for the payment tools on every
# turn of a conversation that is only ever going to read stock.
TOOLS_BY_AGENT: dict[AgentName, set[str]] = {
    AgentName.BOSS: {"get_ticket_context", "list_open_tickets", "update_ticket"},
    AgentName.INVENTORY: {
        "check_stock_and_restock_options",
        "get_ticket_context",
        "list_open_tickets",
    },
    AgentName.ACCOUNTING: {
        "get_cash_position",
        "quote_bulk_price",
        "get_ticket_context",
        "check_stock_and_restock_options",
    },
    # Facilities does not get list_open_tickets: "what else is claiming the same
    # money" is accounting's question, and the tool went unused while costing a
    # schema on every request.
    AgentName.FACILITIES: {"get_ticket_context", "get_cash_position"},
    AgentName.CUSTOMER_SERVICE: {"get_ticket_context", "check_stock_and_restock_options"},
}

# Named so the exclusion is explicit rather than implied by what is missing.
HUMAN_ONLY_TOOLS = {"pay_invoice", "pay_rent", "place_restock_order"}


def shop_toolset() -> MCPToolset:
    """The Campus Customs MCP server, attached in-process.

    This is the only way any agent reaches shop data. Importing the server module
    rather than spawning a subprocess keeps one process and one database handle,
    but the tools and their guardrails are exactly the ones a separate MCP client
    would get.
    """
    global _toolset
    if _toolset is None:
        from server import mcp as shop_mcp

        _toolset = MCPToolset(shop_mcp)
    return _toolset


def toolset_for(name: AgentName) -> Any:
    """The MCP tools this role is allowed to see, and no others."""
    allowed = TOOLS_BY_AGENT[name]
    return shop_toolset().filtered(lambda ctx, tool: tool.name in allowed)


def load_prompt(name: AgentName) -> str:
    """An agent's instructions, read from backend/prompts/<name>.md on every run."""
    return (settings.PROMPT_DIR / f"{name.value}.md").read_text(encoding="utf-8")


# ------------------------------------------------------------- run bookkeeping


@dataclass
class TeamRun:
    """State shared by every agent working one ticket.

    Carries the delegation budget and the call stack, which is what makes the
    mesh safe: an agent cannot be re-entered while it is still running, and the
    whole ticket has a fixed number of hand-offs.
    """

    run_id: str
    ticket_id: int | None
    stack: list[AgentName] = field(default_factory=list)
    delegations_used: int = 0
    steps: list[AuditStep] = field(default_factory=list)
    total_tokens: int = 0
    # Full specialist output is kept here, by the orchestrator, rather than passed
    # through the boss's context. A draft's body and an approval request's detail
    # are for the human and the audit trail; the boss only needs to know they
    # exist in order to decide. Carrying them through the model would re-send
    # every word on every later boss request.
    collected_approvals: list[Any] = field(default_factory=list)
    collected_drafts: list[Any] = field(default_factory=list)
    reports: list[Any] = field(default_factory=list)

    def budget_left(self) -> int:
        return settings.MAX_DELEGATIONS_PER_TICKET - self.delegations_used


@dataclass
class AgentDeps:
    """What a running agent needs in order to hand work on."""

    run: TeamRun
    me: AgentName
    depth: int


SPECIALISTS = (
    AgentName.INVENTORY,
    AgentName.ACCOUNTING,
    AgentName.FACILITIES,
    AgentName.CUSTOMER_SERVICE,
)


def _summarise(messages: list[Any]) -> tuple[list[ToolCallRecord], int, str | None]:
    """Pull MCP tool calls and the model-request count out of a finished run."""
    calls: list[ToolCallRecord] = []
    by_id: dict[str, ToolCallRecord] = {}
    requests = 0
    finish: str | None = None

    for message in messages:
        if isinstance(message, ModelResponse):
            requests += 1
            finish = getattr(message, "finish_reason", None) or finish
            for part in message.parts:
                if isinstance(part, BaseToolCallPart):
                    rec = ToolCallRecord(
                        tool=part.tool_name, args=audit.clip_args(part.args_as_dict())
                    )
                    calls.append(rec)
                    by_id[part.tool_call_id] = rec
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                rec = by_id.get(getattr(part, "tool_call_id", "") or "")
                if rec is None:
                    continue
                if isinstance(part, RetryPromptPart):
                    rec.error = audit.clip_result(part.content)
                elif isinstance(part, BaseToolReturnPart):
                    rec.result = audit.clip_result(part.content)
                    if isinstance(part.content, dict) and part.content.get("refused"):
                        rec.refused = True
    return calls, requests, finish


def _usage_of(result: Any) -> tuple[int, int, int]:
    """Token counts from a finished run.

    `result.usage` is a property in current PydanticAI and was a method in
    earlier ones; accept either so the token accounting does not depend on it.
    """
    usage = result.usage
    if callable(usage):
        usage = usage()
    return (
        getattr(usage, "input_tokens", 0) or 0,
        getattr(usage, "output_tokens", 0) or 0,
        getattr(usage, "total_tokens", 0) or 0,
    )


def _build_agent(name: AgentName, output_type: type) -> Agent:
    """One agent: its prompt file, the shared MCP toolset, and the delegate tool."""
    agent = Agent(
        build_model(),
        deps_type=AgentDeps,
        instructions=load_prompt(name),
        output_type=output_type,
        toolsets=[toolset_for(name)],
        model_settings=model_settings(),
    )

    @agent.tool
    async def delegate(ctx: RunContext[AgentDeps], to_agent: str, task: str) -> dict[str, Any]:
        """Hand a piece of work to another agent and get their report back.

        Use this when the answer belongs to someone else's expertise: stock and
        vendors to `inventory`, cash and margins to `accounting`, leases and rent
        to `facilities`, anything written to a person to `customer_service`.

        Give a specific instruction and include the figures you already have, so
        the other agent does not look them up again. You get back their summary,
        the facts they used, blockers, and anything they propose.

        Args:
            to_agent: inventory, accounting, facilities, or customer_service.
            task: What you need from them, specifically.
        """
        return await _delegate(ctx.deps, to_agent, task)

    return agent


async def _delegate(deps: AgentDeps, to_agent: str, task: str) -> dict[str, Any]:
    """Run another agent, with the limits that keep a mesh from running away."""
    run = deps.run
    try:
        target = AgentName(to_agent.strip().lower())
    except ValueError:
        return {
            "ok": False,
            "refused": True,
            "reason": f"'{to_agent}' is not an agent. Choose one of: "
            + ", ".join(a.value for a in SPECIALISTS),
        }
    if target == deps.me:
        return {"ok": False, "refused": True, "reason": "An agent cannot delegate to itself."}
    if target == AgentName.BOSS:
        return {
            "ok": False,
            "refused": True,
            "reason": "The boss cannot be delegated to. Report back and let the boss decide.",
        }
    if target in run.stack:
        return {
            "ok": False,
            "refused": True,
            "reason": f"'{target.value}' is already working on this ticket further up the "
            "chain. Report what you have instead of calling back into it.",
        }
    if deps.depth + 1 > settings.MAX_DELEGATION_DEPTH:
        return {
            "ok": False,
            "refused": True,
            "reason": f"Delegation depth limit ({settings.MAX_DELEGATION_DEPTH}) reached. "
            "Answer with what you have.",
        }
    if run.budget_left() <= 0:
        return {
            "ok": False,
            "refused": True,
            "reason": f"This ticket has used its {settings.MAX_DELEGATIONS_PER_TICKET} "
            "hand-offs. Answer with what you have.",
        }

    run.delegations_used += 1
    started = time.perf_counter()
    report = await run_agent(run, target, task, depth=deps.depth + 1, parent=deps.me)
    elapsed = int((time.perf_counter() - started) * 1000)

    record = DelegationRecord(
        from_agent=deps.me,
        to_agent=target,
        depth=deps.depth + 1,
        task=audit.clip_text(task),
        returned_summary=audit.clip_text(report.summary),
        duration_ms=elapsed,
    )
    for step in reversed(run.steps):
        if step.agent == deps.me and step.depth == deps.depth:
            step.delegations.append(record)
            break

    # The orchestrator keeps the full report; the model gets a compact view.
    run.reports.append(report)
    run.collected_approvals.extend(report.approval_requests)
    run.collected_drafts.extend(report.drafts)

    return {
        "ok": True,
        "from": target.value,
        "summary": report.summary,
        "facts_used": report.facts_used,
        "blockers": report.blockers,
        "recommended_actions": report.recommended_actions,
        # Enough to decide on, without the full object: the figure, what it is
        # for, and why.
        "approval_requests": [
            {
                "action": r.action,
                "amount": r.amount,
                "reference": r.reference,
                "why": r.why,
            }
            for r in report.approval_requests
        ],
        # Headers only. The body is written, kept, and attached to the outcome by
        # the orchestrator — the boss does not need to read it back to approve it.
        "drafts": [
            {"to": d.to, "subject": d.subject, "status": d.status} for d in report.drafts
        ],
        "confidence": report.confidence,
        "note": (
            "Full approval requests and draft bodies are attached to this ticket's "
            "outcome automatically. You do not need to repeat them."
        ),
    }


async def run_agent(
    run: TeamRun,
    name: AgentName,
    task: str,
    depth: int,
    parent: AgentName | None = None,
) -> SpecialistReport:
    """Run one specialist and append its step to the audit trail."""
    agent = _build_agent(name, SpecialistReport)
    deps = AgentDeps(run=run, me=name, depth=depth)
    limit = settings.MAX_REQUESTS_SPECIALIST

    step = AuditStep(
        run_id=run.run_id,
        step_id=uuid.uuid4().hex[:10],
        time=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ticket_id=run.ticket_id,
        agent=name,
        depth=depth,
        parent_agent=parent,
        model=settings.MODEL_NAME,
        task=audit.clip_text(task),
    )
    run.steps.append(step)
    run.stack.append(name)
    started = time.perf_counter()

    try:
        result = await agent.run(
            task, deps=deps, usage_limits=UsageLimits(request_limit=limit)
        )
        report = result.output
        calls, requests, finish = _summarise(result.new_messages())
        step.tool_calls = calls
        step.tools_used = list(dict.fromkeys(c.tool for c in calls))
        step.model_requests = requests
        step.input_tokens, step.output_tokens, step.total_tokens = _usage_of(result)
        step.output_summary = audit.clip_text(report.summary)
        step.approval_requests = len(report.approval_requests)
        step.drafts = len(report.drafts)
        step.stop_reason = (
            f"request limit ({limit}) reached"
            if requests >= limit
            else f"returned a report (finish_reason={finish or 'stop'})"
        )
        run.total_tokens += step.total_tokens
    except Exception as exc:  # noqa: BLE001 — recorded, not raised at the human
        detail = f"{type(exc).__name__}: {redact(str(exc))[:300]}"
        step.status = "error"
        step.stop_reason = f"error: {detail}"
        report = SpecialistReport(
            agent=name,
            summary=f"{name.value} could not complete this step.",
            blockers=[detail],
            confidence="low",
        )
    finally:
        step.duration_ms = int((time.perf_counter() - started) * 1000)
        run.stack.pop()
        audit.append_step(step)

    return report


async def run_boss(run: TeamRun, task: str) -> TicketOutcome:
    """Run the boss on one ticket and append its step to the audit trail."""
    agent = _build_agent(AgentName.BOSS, TicketOutcome)
    deps = AgentDeps(run=run, me=AgentName.BOSS, depth=0)
    limit = settings.MAX_REQUESTS_BOSS

    step = AuditStep(
        run_id=run.run_id,
        step_id=uuid.uuid4().hex[:10],
        time=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ticket_id=run.ticket_id,
        agent=AgentName.BOSS,
        depth=0,
        model=settings.MODEL_NAME,
        task=audit.clip_text(task),
    )
    run.steps.append(step)
    run.stack.append(AgentName.BOSS)
    started = time.perf_counter()

    try:
        result = await agent.run(
            task, deps=deps, usage_limits=UsageLimits(request_limit=limit)
        )
        outcome = result.output
        calls, requests, finish = _summarise(result.new_messages())
        step.tool_calls = calls
        step.tools_used = list(dict.fromkeys(c.tool for c in calls))
        step.model_requests = requests
        step.input_tokens, step.output_tokens, step.total_tokens = _usage_of(result)
        step.output_summary = audit.clip_text(outcome.decision)
        step.approval_requests = len(outcome.approval_requests)
        step.drafts = len(outcome.drafts)
        step.stop_reason = (
            f"request limit ({limit}) reached"
            if requests >= limit
            else f"decided (finish_reason={finish or 'stop'})"
        )
        run.total_tokens += step.total_tokens
    except Exception as exc:  # noqa: BLE001
        detail = f"{type(exc).__name__}: {redact(str(exc))[:300]}"
        step.status = "error"
        step.stop_reason = f"error: {detail}"
        outcome = TicketOutcome(
            ticket_id=run.ticket_id or 0,
            outcome="needs_human_decision",
            decision="The team could not complete this ticket.",
            reasoning=detail,
        )
    finally:
        step.duration_ms = int((time.perf_counter() - started) * 1000)
        run.stack.pop()
        audit.append_step(step)

    return outcome
