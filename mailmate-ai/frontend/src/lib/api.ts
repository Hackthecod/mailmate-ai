const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data as T;
}

export type Draft = {
  id: string; recipient_name: string; recipient_email: string; purpose: string;
  subject: string; body: string; status: string;
};
export type ChatResult = { thread_id: string; response: string; draft_id: string | null; draft: Draft | null };

export const api = {
  chat: (message: string, thread_id?: string) =>
    request<ChatResult>("/api/chat", { method: "POST", body: JSON.stringify({ message, thread_id }) }),
  drafts: () => request<Draft[]>("/api/email/drafts"),
  updateDraft: (id: string, payload: Partial<Draft>) =>
    request<Draft>(`/api/email/drafts/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  approval: (id: string, action: "approve" | "reject") =>
    request<{ status: string; message: string }>(`/api/approval/${id}`, { method: "POST", body: JSON.stringify({ action }) }),
  voiceToken: () => request<{ server_url: string; participant_token: string; room_name: string }>("/api/voice/token", { method: "POST" }),
};
