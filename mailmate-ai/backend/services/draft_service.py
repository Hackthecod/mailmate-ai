import uuid
from backend.agent.graph import process_email_request
from backend.database.connection import SessionLocal
from backend.database.models import EmailDraft

def create_and_store_draft(question: str) -> dict:
    """Run the shared LangGraph workflow and persist a draft so text/voice share it."""
    result = process_email_request(question)
    draft_id = None
    draft_data = None
    if result.get("recipient_email") and result.get("mail_reason") and result.get("subject") and result.get("body"):
        draft_id = str(uuid.uuid4())
        draft = EmailDraft(
            id=draft_id,
            recipient_name=result.get("recipient_name", ""),
            recipient_email=result["recipient_email"],
            purpose=result["mail_reason"],
            subject=result["subject"],
            body=result["body"],
            status="pending",
        )
        with SessionLocal() as db:
            db.add(draft)
            db.commit()
        draft_data = {
            "id": draft_id,
            "recipient_name": result.get("recipient_name", ""),
            "recipient_email": result.get("recipient_email", ""),
            "purpose": result.get("mail_reason", ""),
            "subject": result.get("subject", ""),
            "body": result.get("body", ""),
            "status": "pending",
        }
    return {"result": result, "draft_id": draft_id, "draft": draft_data}
