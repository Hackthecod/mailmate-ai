import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.database.models import ConversationMessage
from backend.agent.assistant_graph import process_assistant_request

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    thread_id: str | None = None

@router.post("")
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    thread_id = payload.thread_id or str(uuid.uuid4())
    db.add(ConversationMessage(thread_id=thread_id, role="user", content=payload.message))
    try:
        output = process_assistant_request(payload.message)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"AI workflow failed: {type(exc).__name__}: {exc}")
    response = output.get("response") or "I processed your request."
    db.add(ConversationMessage(thread_id=thread_id, role="assistant", content=response))
    db.commit()
    return {
        "thread_id": thread_id,
        "response": response,
        "draft_id": output.get("draft_id"),
        "draft": output.get("draft"),
    }
