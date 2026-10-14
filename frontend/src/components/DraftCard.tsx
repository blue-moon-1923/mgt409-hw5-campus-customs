import type { Draft } from '../types'

/**
 * A draft message, pinned to the desk.
 *
 * The team has no tool that sends anything, to anyone. The card says so in
 * plain words rather than in a tooltip, because "did this go out?" is the first
 * question a shop owner would ask.
 */
export default function DraftCard({ draft }: { draft: Draft }) {
  return (
    <article className="draft">
      <header className="draft-head">
        <span className="draft-to">to {draft.to}</span>
        <span className="draft-seal">not sent</span>
      </header>
      <h4 className="draft-subject">{draft.subject}</h4>
      <p className="draft-body">{draft.body}</p>
    </article>
  )
}
