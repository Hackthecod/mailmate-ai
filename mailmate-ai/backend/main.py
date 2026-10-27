from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.database.connection import Base, engine
from backend.api import chat, email, approval, voice, llm

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router)
app.include_router(email.router)
app.include_router(approval.router)
app.include_router(voice.router)
app.include_router(llm.router)

@app.get("/")
def root():
    return {"app": settings.app_name, "status": "running"}

@app.get("/health")
def health():
    return {"status": "ok"}
