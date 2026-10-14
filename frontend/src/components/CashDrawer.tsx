import { money } from '../api'
import type { Cash } from '../types'

/**
 * The drawer: the balance, and everything with a claim on it.
 *
 * The balance is the largest number on the board on purpose. In this shop money
 * only ever goes out — no revenue is modelled — so the figure is one-directional
 * and every approval makes it smaller. Showing what is already committed
 * underneath it is what turns "we have $3,400" into "we have $160 of room".
 */
export default function CashDrawer({ cash, falling }: { cash: Cash | null; falling: boolean }) {
  if (!cash) return <section className="drawer" aria-label="Cash" />

  const room = cash.after_commitments
  return (
    <section className="drawer" aria-label="Cash">
      <h2 className="col-title">The drawer</h2>
      <p className="col-sub">cash only goes out — no revenue is modelled</p>

      <div className={`balance${falling ? ' is-falling' : ''}`}>
        <span className="balance-label">Checking</span>
        <strong className="balance-figure">{money(cash.checking_balance)}</strong>
      </div>

      <dl className="claims">
        <div>
          <dt>Unpaid invoices</dt>
          <dd>{money(cash.open_invoice_total)}</dd>
        </div>
        <div>
          <dt>Rent due soon</dt>
          <dd>{money(cash.rent_due_total)}</dd>
        </div>
        <div className="claims-total">
          <dt>Room left</dt>
          <dd className={room < 300 ? 'tight' : ''}>{money(room)}</dd>
        </div>
      </dl>

      <h3 className="drawer-sub">Ledger</h3>
      {cash.payments.length === 0 ? (
        <p className="muted">Nothing has been paid. The team cannot pay — only you can.</p>
      ) : (
        <ul className="ledger">
          {cash.payments.map((p) => (
            <li key={p.id}>
              <span className="ledger-kind">{p.kind.replace(/_/g, ' ')}</span>
              <span className="ledger-amount">−{money(p.amount)}</span>
              <span className="ledger-by">approved by {p.approved_by}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
