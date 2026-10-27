from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.database.models import EmailDraft
from backend.services.approval_service import approve_and_send

router = APIRouter(prefix="/api/approval", tags=["approval"])

class ApprovalRequest(BaseModel):
    action: str

@router.post("/{draft_id}")
def handle_approval(draft_id: str, payload: ApprovalRequest, db: Session = Depends(get_db)):
    draft = db.get(EmailDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    action = payload.action.strip().lower()
    if action == "reject":
        if draft.status != "pending":
            raise HTTPException(status_code=409, detail="Only pending drafts can be rejected.")
        draft.status = "rejected"
        db.commit()
        return {"status": "rejected", "message": "Draft rejected. No email was sent."}
    if action != "approve":
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'.")
    try:
        result = approve_and_send(db, draft)
        return {"status": "sent", "message": result}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Email sending failed: {type(exc).__name__}: {exc}")
