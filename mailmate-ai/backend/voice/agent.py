"""LiveKit voice agent using the same LangGraph/Groq email tools as text chat."""
from dotenv import load_dotenv
load_dotenv("backend/.env")


import asyncio
from livekit import agents
from livekit.agents import Agent, AgentSession, RunContext
from livekit.agents.llm import function_tool
from livekit.plugins import deepgram, openai, silero
from backend.agent.assistant_graph import process_assistant_request
from backend.llm.gateway import get_livekit_model_config

class MailMateVoiceAgent(Agent):
    def __init__(self):
        super().__init__(instructions=(
            "You are MailMate AI, a concise, friendly email assistant. "
            "For requests to draft, search, read, find sender emails, identify important recent emails, "
            "or summarize emails, call manage_email_request. Never invent inbox contents. "
            "Drafts require review and explicit approval in the web UI before sending. "
            "Never claim an email was sent unless the backend confirms it."
        ))

    @function_tool
    async def manage_email_request(self, context: RunContext, request_text: str) -> str:
        """Use MailMate's shared LangGraph tools to draft, search, read, find, or summarize emails."""
        try:
            result = await asyncio.to_thread(process_assistant_request, request_text)
            return result.get("response", "I processed your email request.")
        except Exception as exc:
            return f"I couldn't complete that email request: {type(exc).__name__}: {exc}"

async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        stt=deepgram.STT(model="nova-2", language="multi"),
        llm=openai.LLM(**get_livekit_model_config()),
        tts=deepgram.TTS(model="aura-2-asteria-en"),
        vad=silero.VAD.load(),
    )
    await session.start(room=ctx.room, agent=MailMateVoiceAgent())
    await session.generate_reply(instructions="Greet the user warmly and ask how you can help with their email.")

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
