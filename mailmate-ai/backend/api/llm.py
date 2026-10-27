from fastapi import APIRouter
from backend.llm.gateway import get_gateway_health, get_gateway_metrics

router = APIRouter(prefix="/api/llm", tags=["llm-gateway"])


@router.get("/health")
def llm_gateway_health():
    """Show configured providers and the selected routing order (never returns API keys)."""
    return get_gateway_health()


@router.get("/metrics")
def llm_gateway_metrics():
    """Show in-process gateway metrics and estimated costs."""
    return get_gateway_metrics()
