from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_key: str = "dev-key"
    public_base_url: str = "http://localhost:8000"

    # Telnyx
    telnyx_api_key: str
    telnyx_connection_id: str
    telnyx_from_number: str

    # Google Cloud
    google_cloud_project: str = ""

    # Gemini
    gemini_api_key: str
    gemini_primary_model: str = "gemini-2.0-flash"
    gemini_fallback_model: str = "gemini-1.5-flash"

    # Google TTS
    tts_voice_name: str = "en-US-Journey-D"
    tts_language_code: str = "en-US"
    tts_sample_rate: int = 8000

    # Google STT
    stt_model: str = "telephony"
    stt_language_code: str = "en-US"

    # Database
    database_url: str = "postgresql+asyncpg://agent:agent@localhost:5432/salescallagent"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # GCS
    gcs_bucket_name: str = "salescallagent-media"

    # Calendly
    calendly_api_key: str = ""
    calendly_event_url: str = ""

    @property
    def websocket_base_url(self) -> str:
        return self.public_base_url.replace("https://", "wss://").replace("http://", "ws://")

    @property
    def telnyx_stream_url(self) -> str:
        return f"{self.websocket_base_url}/ws/calls"


settings = Settings()
