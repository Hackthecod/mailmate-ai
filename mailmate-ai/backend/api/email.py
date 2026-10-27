from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.database.models import EmailDraft

router = APIRouter(prefix="/api/email", tags=["email"])

def serialize(draft: EmailDraft):
    return {
        "id": draft.id, "recipient_name": draft.recipient_name,
        "recipient_email": draft.recipient_email, "purpose": draft.purpose,
        "subject": draft.subject, "body": draft.body, "status": draft.status,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "sent_at": draft.sent_at.isoformat() if draft.sent_at else None,
    }

@router.get("/drafts")
def list_drafts(db: Session = Depends(get_db)):
    drafts = db.query(EmailDraft).order_by(EmailDraft.created_at.desc()).limit(50).all()
    return [serialize(d) for d in drafts]

@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str, db: Session = Depends(get_db)):
    draft = db.get(EmailDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return serialize(draft)

@router.patch("/drafts/{draft_id}")
def update_draft(draft_id: str, payload: dict, db: Session = Depends(get_db)):
    draft = db.get(EmailDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    if draft.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending drafts can be edited.")
    for field in ("recipient_name", "recipient_email", "subject", "body"):
        if field in payload:
            setattr(draft, field, str(payload[field]).strip())
    db.commit()
    db.refresh(draft)
    return serialize(draft)
