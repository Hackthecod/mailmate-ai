import { FormEvent, useState } from "react";
import { api, Draft } from "../lib/api";

type Props = { onDraft: (draft: Draft) => void; onMessage: (message: string) => void };
export default function ChatWindow({ onDraft, onMessage }: Props) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    const value = message.trim();
    if (!value || busy) return;
    setBusy(true); setError(""); onMessage(value); setMessage("");
    try {
      const result = await api.chat(value);
      onMessage(result.response);
      if (result.draft) onDraft(result.draft);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not contact MailMate AI.");
    } finally { setBusy(false); }
  }

  return <section className="chat-panel">
    <div className="section-heading"><div><span className="eyebrow">WORKSPACE</span><h2>Talk to MailMate</h2></div><span className="status-pill"><i /> AI ready</span></div>
    <div className="chat-hint"><span className="hint-icon">✦</span><div><strong>What would you like to do with your email?</strong><p>Try: “Summarize my recent emails”, “Find emails from Alex”, or “Draft a meeting request to alex@example.com”.</p></div></div>
    <form className="chat-form" onSubmit={submit}>
      <textarea value={message} onChange={e => setMessage(e.target.value)} placeholder="Search, read, summarize, or draft an email…" rows={3} maxLength={10000} />
      {error && <p className="error-text">{error}</p>}
      <div className="composer-footer"><span>Drafts are reviewed before sending</span><button className="primary-button" disabled={busy || !message.trim()}>{busy ? "Working…" : "Ask MailMate ↗"}</button></div>
    </form>
  </section>;
}
