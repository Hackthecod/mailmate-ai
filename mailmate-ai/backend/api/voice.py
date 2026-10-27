import uuid
from fastapi import APIRouter, HTTPException
from backend.config import settings

router = APIRouter(prefix="/api/voice", tags=["voice"])

@router.post("/token")
def create_voice_token():
    if not all([settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret]):
        raise HTTPException(status_code=503, detail="LiveKit credentials are not configured.")
    try:
        from livekit.api import AccessToken, VideoGrants
        room_name = f"mailmate-{uuid.uuid4().hex[:12]}"
        token = (AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
                 .with_identity(f"user-{uuid.uuid4().hex[:8]}")
                 .with_name("MailMate User")
                 .with_grants(VideoGrants(room_join=True, room=room_name)))
        return {"server_url": settings.livekit_url, "participant_token": token.to_jwt(), "room_name": room_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create LiveKit token: {type(exc).__name__}: {exc}")
