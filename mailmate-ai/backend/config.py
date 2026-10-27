from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MailMate AI"
    frontend_origin: str = "http://localhost:5173"

    # Legacy Groq settings remain supported; Groq is the default gateway provider.
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    llm_default_provider: str = "groq"
    llm_provider_order: str = "groq,mistral,gemini"
    llm_routing_enabled: bool = True
    llm_fallback_enabled: bool = True
    llm_route_assistant: str = "groq,mistral,gemini"
    llm_route_draft: str = "groq,mistral,gemini"
    # Summaries can route to Gemini first; change this in .env to prefer Groq instead.
    llm_route_summarize: str = "gemini,groq,mistral"

    llm_cache_enabled: bool = True
    llm_cache_ttl_seconds: int = 60
    llm_cache_max_entries: int = 256
    llm_usage_log_path: str = "logs/llm_usage.jsonl"

    # Set these to the current prices for your chosen models. Units: USD per 1M tokens.
    groq_input_cost_per_1m: float = 0.0
    groq_output_cost_per_1m: float = 0.0
    mistral_input_cost_per_1m: float = 0.0
    mistral_output_cost_per_1m: float = 0.0
    gemini_input_cost_per_1m: float = 0.0
    gemini_output_cost_per_1m: float = 0.0

    database_url: str = "sqlite:///./mailmate.db"
    gmail_address: str = ""
    gmail_app_password: str = ""
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    deepgram_api_key: str = ""
    max_email_words: int = 200

    model_config = SettingsConfigDict(env_file="backend/.env", extra="ignore")


settings = Settings()
