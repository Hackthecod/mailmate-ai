import { Draft } from "../lib/api";
type Props = { draft: Draft | null; onChange: (draft: Draft) => void };
export default function EmailPreview({ draft, onChange }: Props) {
  if (!draft) return <section className="preview-panel empty-preview"><div className="empty-icon">✉</div><h3>Your draft appears here</h3><p>Describe an email in chat or ask the voice assistant to create one.</p></section>;
  return <section className="preview-panel">
    <div className="section-heading"><div><span className="eyebrow">EMAIL COMPOSER</span><h2>Draft preview</h2></div><span className="status-pill pending"><i /> {draft.status}</span></div>
    <label>To<input value={draft.recipient_email} onChange={e => onChange({ ...draft, recipient_email: e.target.value })} disabled={draft.status !== "pending"} /></label>
    <label>Recipient name<input value={draft.recipient_name || ""} onChange={e => onChange({ ...draft, recipient_name: e.target.value })} disabled={draft.status !== "pending"} placeholder="Optional" /></label>
    <label>Subject<input value={draft.subject} onChange={e => onChange({ ...draft, subject: e.target.value })} disabled={draft.status !== "pending"} /></label>
    <label>Message<textarea value={draft.body} onChange={e => onChange({ ...draft, body: e.target.value })} disabled={draft.status !== "pending"} rows={9} /></label>
    <p className="privacy-note"><span>◎</span> Nothing is sent until you approve this draft.</p>
  </section>;
}
