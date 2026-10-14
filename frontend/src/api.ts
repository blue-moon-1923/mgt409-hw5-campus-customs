import type { Approvals, Board, Cash, RunResult } from './types'
import type { AgentEvent } from './types'

/** The desk talks to the FastAPI backend directly; that backend allows this origin. */
export const API = import.meta.env.VITE_API ?? 'http://localhost:8000'

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      /* keep the status line */
    }
    throw new Error(detail)
  }
  return (await res.json()) as T
}

export const getBoard = () => json<Board>('/api/tickets')
export const getCash = () => json<Cash>('/api/cash')
export const getApprovals = () => json<Approvals>('/api/approvals')
export const getEvents = (ticketId?: number) =>
  json<{ events: AgentEvent[]; total_recorded: number }>(
    `/api/events?limit=60${ticketId ? `&ticket_id=${ticketId}` : ''}`,
  )

export const runTicket = (ticketId: number) =>
  json<RunResult>(`/api/tickets/${ticketId}/run`, { method: 'POST' })

export const approve = (id: string, approvedBy: string) =>
  json<{ charged: boolean; status: string; refused_because: string | null; cash: number }>(
    `/api/approvals/${id}/approve`,
    { method: 'POST', body: JSON.stringify({ approved_by: approvedBy }) },
  )

export const decline = (id: string, approvedBy: string) =>
  json<{ status: string }>(`/api/approvals/${id}/decline`, {
    method: 'POST',
    body: JSON.stringify({ approved_by: approvedBy }),
  })

export const resetShop = () => json<{ ok: boolean; cash: number }>('/api/reset', { method: 'POST' })

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
