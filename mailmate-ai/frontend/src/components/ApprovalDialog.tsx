import { useState } from "react";
import { api, Draft } from "../lib/api";
type Props = { draft: Draft | null; onComplete: (message: string, status: string) => void; onSave: (draft: Draft) => Promise<void> };
export default function ApprovalDialog({ draft, onComplete, onSave }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!draft || draft.status !== "pending") return null;

  async function act(action: "approve" | "reject") {
    if (!draft) return;
    if (action === "approve" && !window.confirm(`Send this email to ${draft.recipient_email}?`)) return;
    setBusy(true); setError("");
    try {
      if (action === "approve") await onSave(draft);
      const result = await api.approval(draft.id, action);
      onComplete(result.message, result.status);
    } catch (e) { setError(e instanceof Error ? e.message : "Approval action failed."); }
    finally { setBusy(false); }
  }
  return <div className="approval-box">
    <div className="approval-copy"><span className="approval-check">✓</span><div><strong>Ready for your review</strong><p>Confirm the recipient, subject and body before sending.</p></div></div>
    {error && <p className="error-text">{error}</p>}
    <div className="approval-actions"><button className="secondary-button" onClick={() => act("reject")} disabled={busy}>Reject</button><button className="primary-button" onClick={() => act("approve")} disabled={busy}>{busy ? "Processing…" : "Approve & send"}</button></div>
  </div>;
}
