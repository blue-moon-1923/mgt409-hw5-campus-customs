import { useEffect, useRef } from 'react'

import type { AgentEvent, RunResult } from '../types'

const ROLES = [
  { id: 'boss', name: 'Boss', owns: 'routes the work, makes the call' },
  { id: 'inventory', name: 'Inventory', owns: 'stock, shortfalls, vendors' },
  { id: 'accounting', name: 'Accounting', owns: 'cash, margins, what it costs' },
  { id: 'facilities', name: 'Facilities', owns: 'the premises, rent' },
  { id: 'customer_service', name: 'Customer service', owns: 'what we say to people' },
] as const

const LABEL: Record<string, string> = Object.fromEntries(ROLES.map((r) => [r.id, r.name]))

/**
 * The floor: five name plates, and the trace of what each agent did.
 *
 * The five roles are always visible, even when idle, because a person needs to
 * see *who was not called* as much as who was. A ticket that lights one plate
 * and leaves four dark is the team working well, and that only reads if the dark
 * ones are on screen.
 */
export default function AgentFloor({
  events,
  running,
  result,
  ticketId,
}: {
  events: AgentEvent[]
  running: boolean
  result: RunResult | null
  ticketId: number | null
}) {
  const feedRef = useRef<HTMLOListElement>(null)
  const active = new Set(events.map((e) => e.agent))
  const live = running ? events[0]?.agent : null

  useEffect(() => {
    feedRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
  }, [events.length])

  return (
    <section className="floor" aria-label="Agent activity">
      <h2 className="col-title">The floor</h2>
      <p className="col-sub">
        {ticketId ? `Ticket #${ticketId}` : 'Pick a docket from the spike'}
        {running && <span className="pulse"> · team working</span>}
      </p>

      <ul className="plates">
        {ROLES.map((role) => (
          <li
            key={role.id}
            className={`plate${active.has(role.id) ? ' is-on' : ''}${
              live === role.id ? ' is-live' : ''
            }`}
          >
            <span className="plate-name">{role.name}</span>
            <span className="plate-owns">{role.owns}</span>
            <span className="plate-lamp" aria-hidden="true" />
          </li>
        ))}
      </ul>

      {result && (
        <div className={`verdict verdict-${result.outcome}`}>
          <span className="verdict-tag">{result.outcome.replace(/_/g, ' ')}</span>
          <p className="verdict-decision">{result.decision}</p>
          <p className="verdict-why">{result.reasoning}</p>
          {result.facts_used.length > 0 && (
            <ul className="facts">
              {result.facts_used.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          )}
          {result.open_questions.map((q, i) => (
            <p key={i} className="verdict-question">Needs you: {q}</p>
          ))}
          <p className="verdict-meta">
            {result.steps} agent steps · {result.delegations} hand-offs ·{' '}
            {result.tokens.toLocaleString()} tokens · {result.seconds}s
          </p>
        </div>
      )}

      <ol className="feed" ref={feedRef}>
        {running && (
          <li className="trace trace-live">
            <span className="trace-dots" aria-hidden="true"><i /><i /><i /></span>
            working…
          </li>
        )}
        {events.map((e) => (
          <li
            key={e.step_id}
            className={`trace depth-${Math.min(e.depth, 2)}${
              e.status !== 'ok' ? ' trace-error' : ''
            }`}
          >
            <header className="trace-head">
              <span className="trace-agent">{LABEL[e.agent] ?? e.agent}</span>
              {e.parent_agent && (
                <span className="trace-from">asked by {LABEL[e.parent_agent] ?? e.parent_agent}</span>
              )}
              <span className="trace-cost">
                {e.tokens.toLocaleString()} tok · {(e.duration_ms / 1000).toFixed(1)}s
              </span>
            </header>

            {e.said && <p className="trace-said">{e.said}</p>}

            {e.tool_calls.length > 0 && (
              <ul className="tools">
                {e.tool_calls
                  .filter((c) => !c.tool.startsWith('final_result'))
                  .map((c, i) => (
                    <li key={i} className={c.refused ? 'tool refused' : 'tool'}>
                      <code>{c.tool === 'delegate' ? 'delegate →' : c.tool}</code>
                      <span className="tool-args">{c.args}</span>
                    </li>
                  ))}
              </ul>
            )}

            {(e.approval_requests > 0 || e.drafts > 0) && (
              <p className="trace-made">
                {e.approval_requests > 0 && <>prepared {e.approval_requests} approval request(s) </>}
                {e.drafts > 0 && <>wrote {e.drafts} draft(s)</>}
              </p>
            )}
          </li>
        ))}
        {!running && events.length === 0 && (
          <li className="trace trace-empty">
            Nothing on the floor yet. Choose a docket and put the team on it.
          </li>
        )}
      </ol>
    </section>
  )
}
