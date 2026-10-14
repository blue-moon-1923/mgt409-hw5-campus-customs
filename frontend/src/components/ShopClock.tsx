/**
 * The shop's date, not the wall clock.
 *
 * Every rule in this shop is measured from `desk.date_today`. Putting that date
 * where a clock would normally go is a small thing that prevents a large
 * misunderstanding: a person watching the board should never wonder whether
 * "overdue" means overdue today or overdue in the shop.
 */
export default function ShopClock({ date }: { date: string }) {
  const shown = date
    ? new Date(`${date}T12:00:00`).toLocaleDateString('en-GB', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      })
    : '—'
  return (
    <div className="clock">
      <span className="clock-label">Shop date</span>
      <strong className="clock-date">{shown}</strong>
      <span className="clock-note">all timings measured from here</span>
    </div>
  )
}
