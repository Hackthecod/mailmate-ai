import { useCallback, useState } from "react";
import ChatWindow from "./components/ChatWindow";
import EmailPreview from "./components/EmailPreview";
import ApprovalDialog from "./components/ApprovalDialog";
import VoiceControls from "./components/VoiceControls";
import { api, Draft } from "./lib/api";

export default function App() {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [notice, setNotice] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const [saveError, setSaveError] = useState("");

  async function saveDraft(updated: Draft) {
    const saved = await api.updateDraft(updated.id, {
      recipient_name: updated.recipient_name, recipient_email: updated.recipient_email,
      subject: updated.subject, body: updated.body,
    });
    setDraft(saved);
  }
  function updateDraft(updated: Draft) { setDraft(updated); setSaveError(""); }
  const handleVoiceDraft = useCallback((d: Draft) => { setDraft(d); setNotice(""); }, []);

  return <main className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">m</div><span>mailmate<span className="brand-ai">.ai</span></span></div>
      <div className="sidebar-label">WORKSPACE</div>
      <div className="nav-item active"><span>✧</span> AI Assistant</div>
      <div className="nav-item"><span>▤</span> Email drafts</div>
      <div className="sidebar-bottom"><div className="avatar">M</div><div><strong>MailMate AI</strong><small>Personal email assistant</small></div></div>
    </aside>
    <section className="main-area">
      <header className="topbar"><div><span className="breadcrumb">Workspace /</span> <strong>AI Assistant</strong></div><span className="topbar-badge">● Secure review workflow</span></header>
      <div className="page-content">
        <div className="welcome"><span className="eyebrow">YOUR EMAIL, SIMPLIFIED</span><h1>Good evening. <span>Let's get things done.</span></h1><p>Search, read, and summarize your inbox, or draft emails with AI. Review every draft before sending.</p></div>
        {notice && <div className="notice">{notice}<button onClick={() => setNotice("")}>×</button></div>}
        {saveError && <p className="error-text">{saveError}</p>}
        <div className="workspace-grid">
          <div className="left-column"><ChatWindow onDraft={d => { setDraft(d); setNotice(""); }} onMessage={m => setMessages(prev => [...prev, m])} /><VoiceControls onDraft={handleVoiceDraft} />
            {messages.length > 0 && <div className="activity-panel"><div className="section-heading"><h2>Recent activity</h2><button className="text-button" onClick={() => setMessages([])}>Clear</button></div>{messages.slice(-4).map((m, i) => <p className="activity-line" key={i}><span>✦</span>{m}</p>)}</div>}
          </div>
          <div className="right-column"><EmailPreview draft={draft} onChange={updateDraft} /><ApprovalDialog draft={draft} onSave={saveDraft} onComplete={(message, status) => { setNotice(message); setDraft(d => d ? { ...d, status } : d); }} /></div>
        </div>
        <footer>MailMate AI <span>•</span> Inbox assistance with human-approved sending</footer>
      </div>
    </section>
  </main>;
}
