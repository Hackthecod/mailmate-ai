import { useEffect, useState } from "react";
import { LiveKitRoom, RoomAudioRenderer, StartAudio } from "@livekit/components-react";
import "@livekit/components-styles";
import { api, Draft } from "../lib/api";
import { getLiveKitConnection } from "../lib/livekit";

type Props = { onDraft: (draft: Draft) => void };

export default function VoiceControls({ onDraft }: Props) {
  const [connection, setConnection] = useState<{server_url:string; participant_token:string; room_name:string} | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function connect() {
    setBusy(true); setError("");
    try { setConnection(await getLiveKitConnection()); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not connect to voice."); }
    finally { setBusy(false); }
  }

  // Voice-created drafts are persisted by the worker; refresh the same UI draft preview.
  useEffect(() => {
    if (!connection) return;
    let active = true;
    const refresh = async () => {
      try {
        const drafts = await api.drafts();
        const pending = drafts.find(d => d.status === "pending");
        if (active && pending) onDraft(pending);
      } catch {
        // The voice conversation can continue; the UI will retry on the next interval.
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 3000);
    return () => { active = false; window.clearInterval(timer); };
  }, [connection, onDraft]);

  if (connection) return <div className="voice-connected">
    <LiveKitRoom serverUrl={connection.server_url} token={connection.participant_token} connect audio video={false} onDisconnected={() => setConnection(null)}>
      <RoomAudioRenderer />
      <StartAudio label="Enable audio" />
      <button className="secondary-button" onClick={() => setConnection(null)}>Disconnect voice</button>
    </LiveKitRoom>
    <p className="muted">Connected to room {connection.room_name}. Keep the LiveKit voice worker running. Voice-created drafts appear in the preview automatically.</p>
  </div>;

  return <div className="voice-card">
    <div className="voice-orb">◖))</div>
    <div className="voice-copy"><strong>Prefer talking?</strong><p>Start a live voice conversation with MailMate AI.</p></div>
    <button className="voice-button" onClick={connect} disabled={busy}>{busy ? "Connecting…" : "＋ Start voice"}</button>
    {error && <p className="error-text">{error}</p>}
  </div>;
}
