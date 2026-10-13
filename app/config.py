import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # WhatsApp Cloud API
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "1455172267668724")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "psmais_datavizbi_wapp_2026")
    WHATSAPP_API_VERSION: str = "v21.0"
    
    # PostgreSQL dw_positivo
    PG_HOST: str = os.getenv("PG_HOST", "127.0.0.1")
    PG_PORT: int = int(os.getenv("PG_PORT", "5432"))
    PG_DB: str = os.getenv("PG_DB", "dw_positivo")
    PG_USER: str = os.getenv("PG_USER", "bi_agent_user")
    PG_PASSWORD: str = os.getenv("PG_PASSWORD", "")
    PG_SCHEMA: str = os.getenv("PG_SCHEMA", "dw_positivo")

    # Gemini AI (Ultra-fast gemini-3.5-flash)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    # Access Control (comma-separated, empty means allow all)
    ALLOWED_NUMBERS: str = os.getenv("ALLOWED_NUMBERS", "5561998379503,556198379503")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
