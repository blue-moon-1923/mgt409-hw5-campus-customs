import { money } from '../api'
import type { PendingApproval } from '../types'

const ACTION: Record<string, string> = {
  pay_invoice: 'Pay invoice',
  pay_rent: 'Pay rent',
  place_restock_order: 'Place order',
}

/**
 * A chit: one spend, waiting on a person.
 *
 * Styled like something torn off a pad and left on the desk, because that is
 * what it is — the team has done the work and stopped at the one thing it is
 * not allowed to do. Everything needed to decide is on the chit, so nobody has
 * to go hunting through the floor log to approve $840.
 */
export default function ApprovalChit({
  item,
  busy,
  onApprove,
  onDecline,
}: {
  item: PendingApproval
  busy: boolean
  onApprove: (id: string) => void
  onDecline: (id: string) => void
}) {
  const r = item.request
  return (
    <article className={`chit${item.last_refusal ? ' is-refused' : ''}`}>
      <header className="chit-head">
        <span className="chit-action">{ACTION[r.action] ?? r.action}</span>
        <strong className="chit-amount">{money(r.amount)}</strong>
      </header>
      <p className="chit-ref">{r.reference}</p>
      <p className="chit-why">{r.why}</p>
      {r.what_it_unblocks && <p className="chit-unblocks">Unblocks: {r.what_it_unblocks}</p>}
      {r.cash_after != null && (
        <p className="chit-after">
          Balance would go {r.cash_before != null ? `${money(r.cash_before)} → ` : ''}
          {money(r.cash_after)}
        </p>
      )}
      {item.ticket_id && <p className="chit-ticket">for ticket #{item.ticket_id}</p>}

      {item.last_refusal && (
        <p className="chit-refusal">
          Refused: {item.last_refusal}
          <span className="chit-attempts"> — still approvable ({item.attempts} attempt
          {item.attempts === 1 ? '' : 's'})</span>
        </p>
      )}

      <div className="chit-actions">
        <button type="button" className="btn btn-approve" disabled={busy} onClick={() => onApprove(item.id)}>
          Approve &amp; pay
        </button>
        <button type="button" className="btn btn-decline" disabled={busy} onClick={() => onDecline(item.id)}>
          Decline
        </button>
      </div>
    </article>
  )
}
