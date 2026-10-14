"""Every structured type the Campus Customs agent team passes around.

One file, so the shapes that cross a boundary — boss to specialist, specialist to
specialist, team to human, team to audit trail — are visible together.

Two ideas run through these models:

* **A hand-off is a message, not a conversation.** A specialist returns a
  `SpecialistReport`: what it found, which facts it used, what is blocking, and
  what it proposes. The next agent reads that rather than a transcript, which is
  both cheaper and easier to audit.
* **Nothing here can move money.** `ApprovalRequest` is a *request*. It carries
  everything a person needs to decide, and the decision is theirs.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentName(str, Enum):
    """The five roles. Used for routing, delegation, and the audit trail."""

    BOSS = "boss"
    INVENTORY = "inventory"
    ACCOUNTING = "accounting"
    FACILITIES = "facilities"
    CUSTOMER_SERVICE = "customer_service"


class ApprovalRequest(BaseModel):
    """A proposed spend, put to a human.

    Agents cannot pay. They produce one of these and stop. The fields are the
    ones a person needs in order to say yes or no without going back to the
    database: what it costs, what it unblocks, and what happens if it is refused.
    """

    action: str = Field(
        description="One of: pay_invoice, pay_rent, place_restock_order."
    )
    amount: float = Field(description="Cash that would leave the shop, in dollars.")
    reference: str = Field(
        description="What it settles, e.g. 'invoice 501' or 'lease 1' or 'CC-TEE-WHITE S x1'."
    )
    ticket_id: int | None = Field(default=None, description="The ticket this serves.")
    why: str = Field(description="Why this spend is needed, in one or two sentences.")
    what_it_unblocks: str = Field(
        default="", description="What becomes possible once it is paid."
    )
    if_declined: str = Field(
        default="", description="The consequence of not approving it."
    )
    cash_before: float | None = Field(default=None)
    cash_after: float | None = Field(default=None)
    urgency: str = Field(default="normal", description="low, normal, or urgent.")
    order: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Required when action is place_restock_order: {sku, size, qty, vendor_id}. "
            "Without it a person cannot execute the order, because the approve route has "
            "nothing to send the vendor."
        ),
    )


class DraftMessage(BaseModel):
    """A message written for a person to send. Never sent by the team."""

    to: str = Field(description="Who it is addressed to.")
    subject: str
    body: str
    about_ticket: int | None = None
    status: str = Field(
        default="draft_only_not_sent",
        description="Always draft_only_not_sent. The team has no send tool.",
    )


class SpecialistReport(BaseModel):
    """What a specialist hands back.

    `facts_used` is the honesty field: every number in the summary should be
    traceable to a tool result listed here. A report with conclusions and an
    empty `facts_used` means the agent was guessing.
    """

    agent: AgentName
    summary: str = Field(description="The finding, in two or three sentences.")
    facts_used: list[str] = Field(
        default_factory=list,
        description="Short factual statements taken from MCP tool results, each with its number.",
    )
    blockers: list[str] = Field(
        default_factory=list,
        description="Anything stopping this from being resolved, stated plainly.",
    )
    recommended_actions: list[str] = Field(
        default_factory=list, description="What the boss should do next."
    )
    approval_requests: list[ApprovalRequest] = Field(default_factory=list)
    drafts: list[DraftMessage] = Field(default_factory=list)
    confidence: str = Field(
        default="high", description="high, medium or low — low if a fact could not be checked."
    )


class TicketOutcome(BaseModel):
    """The boss's decision on one ticket."""

    ticket_id: int
    routed_to: list[AgentName] = Field(
        default_factory=list, description="Which specialists were consulted, in order."
    )
    outcome: str = Field(
        description="resolved, blocked_pending_approval, blocked_no_cash, or needs_human_decision."
    )
    decision: str = Field(description="What was decided, in plain language.")
    reasoning: str = Field(description="Why, referencing the facts that drove it.")
    facts_used: list[str] = Field(default_factory=list)
    approval_requests: list[ApprovalRequest] = Field(default_factory=list)
    drafts: list[DraftMessage] = Field(default_factory=list)
    ticket_status_set: str | None = Field(
        default=None, description="The status written back to the ticket, if any."
    )
    open_questions: list[str] = Field(
        default_factory=list, description="Anything the human must decide."
    )


class DelegationRecord(BaseModel):
    """One hand-off, for the audit trail and the dashboard."""

    from_agent: AgentName
    to_agent: AgentName
    depth: int
    task: str
    returned_summary: str = ""
    duration_ms: int = 0


class ToolCallRecord(BaseModel):
    """One MCP tool call, as recorded in the audit trail."""

    tool: str
    args: str = ""
    result: str = ""
    error: str | None = None
    refused: bool = False


class AuditStep(BaseModel):
    """One agent loop step, appended to output/audit_trail.json.

    Enough to reconstruct what happened without the transcript: who ran, for which
    ticket, how deep in the delegation chain, which MCP tools were called with
    what, who it handed off to, what it cost, and why it stopped.
    """

    run_id: str
    step_id: str
    time: str
    ticket_id: int | None
    agent: AgentName
    depth: int
    parent_agent: AgentName | None = None
    model: str
    task: str = Field(default="", description="The instruction this agent was given, clipped.")
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    delegations: list[DelegationRecord] = Field(default_factory=list)
    output_summary: str = ""
    approval_requests: int = 0
    drafts: int = 0
    model_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    duration_ms: int = 0
    status: str = "ok"
    stop_reason: str = ""
