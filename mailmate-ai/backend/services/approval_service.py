from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.database.models import EmailDraft
from backend.email_service.provider import send_mail

def approve_and_send(db: Session, draft: EmailDraft) -> str:
    if draft.status != "pending":
        raise ValueError(f"This draft cannot be sent because its status is '{draft.status}'.")
    if not draft.recipient_email or "@" not in draft.recipient_email:
        raise ValueError("A valid recipient email is required.")
    # Mark first to block concurrent duplicate approvals. If sending fails, restore pending status.
    draft.status = "sending"
    db.commit()
    try:
        result = send_mail(draft.recipient_email, draft.subject, draft.body)
    except Exception:
        draft.status = "pending"
        db.commit()
        raise
    draft.status = "sent"
    draft.sent_at = datetime.now(timezone.utc)
    db.commit()
    return result
