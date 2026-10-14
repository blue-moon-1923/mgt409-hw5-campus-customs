import { useCallback, useEffect, useRef, useState } from 'react'

import { approve, decline, getApprovals, getBoard, getCash, getEvents, resetShop, runTicket } from './api'
import AgentFloor from './components/AgentFloor'
import ApprovalChit from './components/ApprovalChit'
import CashDrawer from './components/CashDrawer'
import DraftCard from './components/DraftCard'
import ShopClock from './components/ShopClock'
import TicketSpike from './components/TicketSpike'
import type { AgentEvent, Approvals, Board, Cash, RunResult } from './types'

/** Who is at the desk. Written on every payment, so it is asked for once, up front. */
const WHO_KEY = 'campus-customs-desk-operator'

/**
 * Only the most recent run for a ticket.
 *
 * The audit trail is append-only across runs, so a ticket worked several times
 * carries every earlier attempt too. The floor should show the run you are
 * looking at, not the history of the ticket — otherwise agents that were not part
 * of the latest run appear lit. The whole trail is still available from
 * `/api/events`.
 */
function latestRun(events: AgentEvent[]): AgentEvent[] {
  if (events.length === 0) return events
  const newest = events[0].run_id
  return events.filter((e) => e.run_id === newest)
}

export default function App() {
  const [board, setBoard] = useState<Board | null>(null)
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<Approvals | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [running, setRunning] = useState<number | null>(null)
  const [result, setResult] = useState<RunResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [falling, setFalling] = useState(false)
  const [who, setWho] = useState(() => localStorage.getItem(WHO_KEY) ?? '')
  const lastBalance = useRef<number | null>(null)

  const refresh = useCallback(async (ticketId: number | null) => {
    try {
      const [b, c, a] = await Promise.all([getBoard(), getCash(), getApprovals()])
      setBoard(b)
      setApprovals(a)
      // Flash the balance when it drops, so an approval has a visible consequence.
      if (lastBalance.current !== null && c.checking_balance < lastBalance.current) {
        setFalling(true)
        window.setTimeout(() => setFalling(false), 1400)
      }
      lastBalance.current = c.checking_balance
      setCash(c)
      if (ticketId) setEvents(latestRun((await getEvents(ticketId)).events))
      setError(null)
    } catch (cause) {
      setError((cause as Error).message)
    }
  }, [])

  useEffect(() => {
    void refresh(selected)
  }, [refresh, selected])

  // While the team is working, poll the audit trail so the floor fills in live.
  useEffect(() => {
    if (running === null) return
    const timer = window.setInterval(async () => {
      try {
        setEvents(latestRun((await getEvents(running)).events))
      } catch {
        /* a dropped poll is not worth showing */
      }
    }, 1800)
    return () => window.clearInterval(timer)
  }, [running])

  async function onRun(ticketId: number) {
    setSelected(ticketId)
    setRunning(ticketId)
    setResult(null)
    setEvents([])
    setError(null)
    try {
      const outcome = await runTicket(ticketId)
      setResult(outcome)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setRunning(null)
      await refresh(ticketId)
    }
  }

  async function onApprove(id: string) {
    if (!who.trim()) {
      setError('Put your name at the top of the desk first — every payment records who approved it.')
      return
    }
    setBusy(true)
    try {
      const res = await approve(id, who.trim())
      if (!res.charged && res.refused_because) setError(res.refused_because)
      else setError(null)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
      await refresh(selected)
    }
  }

  async function onDecline(id: string) {
    setBusy(true)
    try {
      await decline(id, who.trim() || 'desk')
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
      await refresh(selected)
    }
  }

  async function onReset() {
    setBusy(true)
    setResult(null)
    setEvents([])
    try {
      await resetShop()
      lastBalance.current = null
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
      await refresh(selected)
    }
  }

  const pending = approvals?.pending ?? []
  const drafts = (approvals?.drafts ?? []).filter((d) => !selected || d.ticket_id === selected)

  return (
    <div className="desk">
      <header className="masthead">
        <div className="masthead-brand">
          <span className="mark" aria-hidden="true">CC</span>
          <div>
            <h1>Campus Customs</h1>
            <p>the operations desk</p>
          </div>
        </div>
        <ShopClock date={board?.shop_date ?? ''} />
        <div className="masthead-right">
          <label className="who">
            <span>At the desk</span>
            <input
              value={who}
              placeholder="your name"
              onChange={(e) => {
                setWho(e.target.value)
                localStorage.setItem(WHO_KEY, e.target.value)
              }}
            />
          </label>
          <button type="button" className="btn btn-quiet" disabled={busy || running !== null} onClick={onReset}>
            Reset the shop
          </button>
        </div>
      </header>

      {error && <p className="alert" role="alert">{error}</p>}

      <main className="columns">
        <TicketSpike
          tickets={board?.tickets ?? []}
          selected={selected}
          running={running}
          onSelect={setSelected}
          onRun={onRun}
        />

        <AgentFloor events={events} running={running !== null} result={result} ticketId={selected} />

        <div className="right-rail">
          <CashDrawer cash={cash} falling={falling} />

          <section className="tray" aria-label="Awaiting approval">
            <h2 className="col-title">The tray</h2>
            <p className="col-sub">
              {pending.length === 0 ? 'nothing waiting on you' : `${pending.length} waiting on you`}
            </p>
            {pending.map((item) => (
              <ApprovalChit key={item.id} item={item} busy={busy} onApprove={onApprove} onDecline={onDecline} />
            ))}
            {pending.length === 0 && (
              <p className="muted">
                The team prepares spends; it cannot make them. Anything that costs money
                appears here first.
              </p>
            )}
          </section>

          {drafts.length > 0 && (
            <section className="pinboard" aria-label="Drafts">
              <h2 className="col-title">The pinboard</h2>
              <p className="col-sub">written, not sent</p>
              {drafts.map((d, i) => (
                <DraftCard key={i} draft={d} />
              ))}
            </section>
          )}
        </div>
      </main>
    </div>
  )
}
