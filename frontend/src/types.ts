export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  is_open: boolean
  is_resolved: boolean
  notes: string | null
  has_outcome: boolean
}

export interface Board {
  shop_date: string
  count: number
  tickets: Ticket[]
}

export interface Payment {
  id: number
  kind: string
  ref_id: number | null
  amount: number
  account: string
  paid_at: string
  approved_by: string
}

export interface Cash {
  checking_balance: number
  open_invoice_total: number
  rent_due_total: number
  total_committed: number
  after_commitments: number
  payments: Payment[]
  rent_horizon_days: number
}

export interface ToolCall {
  tool: string
  args: string
  result: string
  refused: boolean
}

export interface AgentEvent {
  step_id: string
  run_id: string
  time: string
  ticket_id: number | null
  agent: string
  depth: number
  parent_agent: string | null
  task: string
  said: string
  tools_used: string[]
  tool_calls: ToolCall[]
  delegated_to: string[]
  approval_requests: number
  drafts: number
  tokens: number
  model_requests: number
  duration_ms: number
  status: string
  stop_reason: string
}

export interface ApprovalRequest {
  action: string
  amount: number
  reference: string
  ticket_id: number | null
  why: string
  what_it_unblocks: string
  if_declined: string
  cash_before: number | null
  cash_after: number | null
  urgency: string
  order: Record<string, unknown> | null
}

export interface PendingApproval {
  id: string
  ticket_id: number | null
  request: ApprovalRequest
  created_at: string
  status: string
  approved_by: string | null
  decided_at: string | null
  last_refusal: string | null
  attempts: number
}

export interface Draft {
  ticket_id: number | null
  to: string
  subject: string
  body: string
  about_ticket: number | null
  status: string
}

export interface Approvals {
  pending: PendingApproval[]
  decided: PendingApproval[]
  drafts: Draft[]
}

export interface RunResult {
  ticket_id: number
  outcome: string
  decision: string
  reasoning: string
  routed_to: string[]
  facts_used: string[]
  approval_requests: (ApprovalRequest & { approval_id: string })[]
  drafts: Draft[]
  open_questions: string[]
  steps: number
  delegations: number
  tokens: number
  seconds: number
}
