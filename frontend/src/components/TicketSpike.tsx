import type { Ticket } from '../types'

const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Pricing request',
}

/** Rubber-stamp wording for a ticket's state. */
function stamp(ticket: Ticket): { text: string; tone: string } {
  if (ticket.is_resolved) return { text: 'Resolved', tone: 'resolved' }
  if (ticket.status === 'blocked') return { text: 'Blocked', tone: 'blocked' }
  if (ticket.status === 'in_progress') return { text: 'In progress', tone: 'progress' }
  return { text: 'Open', tone: 'open' }
}

/**
 * The spike: paper slips waiting to be worked.
 *
 * Tickets are the only thing on this board a person starts, so they get the
 * left-hand column and the most physical treatment — torn edges, a stamp, and
 * the requester's name at the top the way a real docket reads.
 */
export default function TicketSpike({
  tickets,
  selected,
  running,
  onSelect,
  onRun,
}: {
  tickets: Ticket[]
  selected: number | null
  running: number | null
  onSelect: (id: number) => void
  onRun: (id: number) => void
}) {
  return (
    <section className="spike" aria-label="Ticket board">
      <h2 className="col-title">The spike</h2>
      <p className="col-sub">{tickets.length} dockets on the board</p>

      <ul className="slips">
        {tickets.map((ticket) => {
          const mark = stamp(ticket)
          const isRunning = running === ticket.id
          return (
            <li key={ticket.id}>
              <article
                className={`slip${selected === ticket.id ? ' is-selected' : ''}${
                  isRunning ? ' is-running' : ''
                }`}
                onClick={() => onSelect(ticket.id)}
              >
                <header className="slip-head">
                  <span className="slip-no">#{ticket.id}</span>
                  <span className={`stamp stamp-${mark.tone}`}>{mark.text}</span>
                </header>
                <p className="slip-type">{TYPE_LABEL[ticket.type] ?? ticket.type}</p>
                <h3 className="slip-subject">{ticket.subject}</h3>
                <p className="slip-from">from {ticket.requester}</p>

                {ticket.sku && (
                  <p className="slip-line">
                    <code>{ticket.sku}</code>
                    {ticket.size && <> · size {ticket.size}</>}
                    {ticket.qty != null && <> · ×{ticket.qty}</>}
                  </p>
                )}
                {ticket.lease_id != null && <p className="slip-line">lease {ticket.lease_id}</p>}
                {ticket.invoice_id != null && (
                  <p className="slip-line slip-flag">carries invoice {ticket.invoice_id}</p>
                )}

                <button
                  type="button"
                  className="slip-run"
                  disabled={running !== null}
                  onClick={(e) => {
                    e.stopPropagation()
                    onRun(ticket.id)
                  }}
                >
                  {isRunning ? 'Team working…' : ticket.has_outcome ? 'Run again' : 'Put the team on it'}
                </button>
              </article>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
