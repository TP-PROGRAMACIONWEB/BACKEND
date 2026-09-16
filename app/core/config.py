from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Sin .env se usa la base SQLite local de pruebas. Para la nube, ver
    # `.env.example` y `app/db/database.py`.
    database_url: str = "sqlite:///./offix_dev.db"
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:3000"

    # URL base del frontend, usada para armar los links que viajan por correo.
    frontend_url: str = "http://localhost:3000"

    # Brevo (envío de correos transaccionales). Sin API key el servicio falla
    # con un mensaje explícito en vez de intentar el envío.
    brevo_api_key: str = ""
    brevo_sender_email: str = "no-reply@offix.example.com"
    brevo_sender_name: str = "Offix"
    brevo_timeout_segundos: float = 10.0

    # Prefijo internacional para armar el link de wa.me (Argentina móvil). El
    # usuario carga los 10 dígitos de área + línea y el backend antepone esto.
    whatsapp_prefijo_pais: str = "549"

    # Vencimiento del enlace de reseña, en días desde la generación.
    solicitud_resena_dias_validez: int = 7

    # Tiempo máximo de espera de la validación de matrícula (CA03 de HU-02).
    matricula_timeout_segundos: int = 60

    # Matrícula trampa para que QA pueda probar el resultado Timeout sin
    # esperar. Se puede desactivar para que no quede disponible en producción.
    matricula_trap_habilitada: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def frontend_url_base(self) -> str:
        return self.frontend_url.rstrip("/")


settings = Settings()
