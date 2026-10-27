# MailMate AI backend

## Email features
- Email draft creation through the shared structured-output workflow.
- Read-only Gmail INBOX search, message reading, sender lookup, important/recent lookup, and summarization via IMAP.
- Drafts are stored in SQLite and can only be sent through the separate approval endpoint after a user approves them.
- Text chat and LiveKit voice email requests use the same LangGraph tools.

## LLM gateway

The gateway is implemented in `backend/llm/gateway.py` and currently supports Groq, Mistral, and Gemini through LangChain chat model integrations.

- **Default provider:** Groq (`LLM_DEFAULT_PROVIDER=groq`).
- **Routing:** routes are task-specific. Draft and assistant requests default to Groq first; summaries default to Gemini first. Configure `LLM_ROUTE_DRAFT`, `LLM_ROUTE_ASSISTANT`, and `LLM_ROUTE_SUMMARIZE` in `.env`.
- **Fallback:** when a provider call fails, the gateway tries the next configured provider in that task's route. Set `LLM_FALLBACK_ENABLED=false` to disable retries across providers.
- **Caching:** exact-input, in-memory cache with TTL and max-entry limits. It caches successful model responses (not tool-call messages); cache is lost on restart and is not a semantic cache.
- **Observability:** structured logs record provider, model, task, latency, errors, token usage, cache events, and estimated cost. Prompt and email contents are not logged.
- **Cost tracking:** token usage and estimated cost are aggregated in memory and written to `LLM_USAGE_LOG_PATH`. Set the six `*_COST_PER_1M` values to the current input/output price for each selected model. Costs are estimates and are zero until rates are configured. Providers that do not return token usage may have unknown usage/cost for a call.
- **Metrics endpoints:** `GET /api/llm/health` and `GET /api/llm/metrics`. Metrics are process-local; the JSONL usage log persists across restarts. Protect these endpoints behind authentication before exposing the API publicly.
- **Voice:** the LiveKit outer conversation uses an OpenAI-compatible endpoint for the first available provider in the configured assistant route. Email work triggered from voice uses the gateway's per-request routing/fallback. The LiveKit session itself is selected at startup and does not dynamically fail over mid-session.

## Provider setup
Set one or more keys in `backend/.env`:

```dotenv
GROQ_API_KEY=...
MISTRAL_API_KEY=...
GEMINI_API_KEY=...
```

All three keys are recommended so routing and fallback can actually use all providers. Model IDs are configurable using `GROQ_MODEL`, `MISTRAL_MODEL`, and `GEMINI_MODEL`.

## Gmail setup
Enable IMAP for the Gmail account and configure a Google App Password (not your normal password) in `backend/.env`. The same app password is used for inbox reading and approved SMTP sending.

Email IDs returned by search refer to numeric UIDs in the Gmail INBOX. This initial implementation searches the INBOX, not All Mail, Spam, or Trash.

## Run from the project root

```powershell
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

Run the LiveKit worker in another terminal:

```powershell
python -m backend.voice.agent dev
```
