from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/offix"
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

<<<<<<< Updated upstream
    # Tiempo máximo de espera de la validación de matrícula (CA03 de HU-02).
    matricula_timeout_segundos: int = 60

    # Matrícula trampa para que QA pueda probar el resultado Timeout sin
    # esperar. Se puede desactivar para que no quede disponible en producción.
=======
    # CA03 de HU-02: si la consulta al padrón no responde en este tiempo, la
    # validación devuelve Timeout. Tiene que quedar por debajo de la duración
    # máxima de la función serverless, o el corte lo hace Vercel con un 504.
    matricula_timeout_segundos: float = 60.0

    # Matrícula trampa del CA03 de HU-02: la validación consulta el padrón en la
    # base local y nunca demora, así que QA no tiene cómo forzar la demora. Los
    # números trampa simulan un padrón que no responde: la validación espera
    # `matricula_timeout_segundos` y devuelve Timeout. Desactivarla en producción.
>>>>>>> Stashed changes
    matricula_trap_habilitada: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def frontend_url_base(self) -> str:
        return self.frontend_url.rstrip("/")


settings = Settings()
