# MailMate AI

MailMate AI is a React + FastAPI email assistant with LangGraph tools, SQLite draft storage, Gmail IMAP reading/search, SMTP sending after human approval, and a LiveKit voice agent.

## Features
- Create and save email drafts; drafts are never sent automatically.
- Search recent Gmail inbox messages by keyword/topic, read selected messages, and find mail from a sender.
- Prioritize recent emails using urgency/action heuristics and summarize inbox messages.
- Review/edit/approve/reject drafts in the web UI. Sending happens only after explicit approval.
- **Multi-provider LLM gateway:** Groq default, with Mistral and Gemini routing/fallback options.
- **Gateway routing:** task-based routes for assistant, drafting, and summaries.
- **Fallback:** retries the next configured provider when a provider call fails.
- **Caching:** exact-input in-memory response cache with configurable TTL and size.
- **Observability:** structured JSON logs with provider, model, latency, errors, token counts, cache events, and estimated costs. Prompts and email content are not logged.
- **Cost tracking:** per-provider token totals and cost estimates, with configurable rates.
- Gateway status and metrics endpoints: `GET /api/llm/health`, `GET /api/llm/metrics`.

## Setup (Windows PowerShell)
1. Copy `.env.example` to `backend/.env` and configure the keys for the providers you want to use. Groq is the default; configure Mistral and Gemini too to enable real fallback.
2. Create and activate a virtual environment, then install dependencies:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r backend/requirements.txt
   ```
3. Start the API from the project root:
   ```powershell
   python -m uvicorn backend.main:app --reload --port 8000
   ```
4. In another terminal, install frontend dependencies and start Vite:
   ```powershell
   cd frontend
   npm install
   npm run dev
   ```
5. For voice, configure LiveKit and Deepgram and run from the project root:
   ```powershell
   python -m backend.voice.agent dev
   ```

## Gateway configuration
See `.env.example` and `backend/README.md`. Default assistant/draft routing starts with Groq. Summary routing starts with Gemini, then tries Groq and Mistral; edit `LLM_ROUTE_SUMMARIZE` if you want Groq first for summaries too. Fallback uses only providers with configured API keys.

Caching is process-local and expires; it is not a semantic cache and is cleared when the process restarts. Usage events are appended to `logs/llm_usage.jsonl`, while the metrics endpoint shows current-process aggregates. The default per-million-token price rates are zero to avoid embedding stale provider prices; set them to current model pricing for meaningful dollar estimates. Protect metrics endpoints with authentication before deploying publicly. The LiveKit outer conversation chooses a provider at session startup; the email task called from voice uses request-level gateway routing/fallback.

## Gmail configuration
Enable IMAP for your Gmail account and use a Google App Password for `GMAIL_APP_PASSWORD`. Do not use your regular Gmail password. Inbox tools currently search the Gmail INBOX only. The app does not send mail from a tool call; the separate approval endpoint sends only after a user explicitly approves a pending draft.

SQLite is configured by default (`sqlite:///./mailmate.db`). Keep `backend/.env` private and never commit real credentials.
