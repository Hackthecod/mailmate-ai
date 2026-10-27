"""Structured email-draft graph, routed through the shared LLM gateway."""
import re
from functools import lru_cache
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from backend.agent.state import EmailState
from backend.agent.prompts import EMAIL_DRAFT_SYSTEM_PROMPT
from backend.llm.gateway import invoke_with_fallback


class DraftResult(BaseModel):
    recipient_name: str = Field(default="", description="Recipient name, or empty string if unknown")
    recipient_email: str = Field(default="", description="Actual recipient email supplied by user; never invent it")
    mail_reason: str = Field(default="", description="Reason or purpose for the email")
    subject: str = Field(default="", description="Professional email subject")
    body: str = Field(default="", description="Email body, at most 200 words")
    response: str = Field(default="", description="Status or question for the user")


def validate_draft(result: DraftResult) -> dict:
    email = result.model_dump()
    for key, value in email.items():
        if isinstance(value, str):
            email[key] = value.strip()
    address = email["recipient_email"]
    if address and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address):
        email["recipient_email"] = ""
    email["body"] = " ".join(email["body"].split()[:200])
    if not email["mail_reason"]:
        email["response"] = "Please explain why you want to send this email."
    elif not email["recipient_email"]:
        email["response"] = "Please provide a valid recipient email address. I will not guess it."
    elif not email["subject"] or not email["body"]:
        email["response"] = "Please provide more details to complete the draft."
    else:
        email["response"] = "Your email draft is ready. Review it before approving it for sending."
    return email


def build_graph():
    def draft_node(state: EmailState) -> EmailState:
        question = str(state.get("question", "")).strip()
        if not question:
            return validate_draft(DraftResult(response="Tell me what email you want to draft."))
        prompt = (
            f"{EMAIL_DRAFT_SYSTEM_PROMPT}\n\n"
            "Rules:\n- Never invent a recipient email address.\n"
            "- Ask for missing details instead of guessing.\n"
            "- Keep the body at 200 words or fewer.\n"
            "- Create a draft only. Never send an email.\n\n"
            f"User request:\n{question}"
        )
        def invoke_structured(model):
            structured = model.with_structured_output(DraftResult, include_raw=True).invoke(prompt)
            if structured.get("parsing_error") is not None or structured.get("parsed") is None:
                raise ValueError("The provider could not return a valid structured draft.")
            return structured

        result = invoke_with_fallback(
            task="draft",
            cache_input=prompt,
            invoke=invoke_structured,
            temperature=0.2,
        )
        if isinstance(result, dict) and "parsed" in result:
            result = result["parsed"]
        elif isinstance(result, dict):
            result = DraftResult.model_validate(result)
        return validate_draft(result)

    builder = StateGraph(EmailState)
    builder.add_node("draft", draft_node)
    builder.add_edge(START, "draft")
    builder.add_edge("draft", END)
    return builder.compile()


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()


def process_email_request(question: str) -> dict:
    return get_graph().invoke({"question": question})
