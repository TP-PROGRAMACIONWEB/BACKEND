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

    # Matrícula trampa del CA03 de HU-02: la validación consulta el padrón en la
    # base local y nunca demora, así que el resultado Timeout solo se puede
    # obtener con los números trampa, que responden al instante (decisión del
    # equipo, para que QA no tenga que esperar). Desactivarla en producción.
    matricula_trap_habilitada: bool = True

    # Schema de Postgres donde viven las tablas del backend. No aplica a SQLite.
    database_schema: str = "offix"

    # Auth0 (HU-03, CA01-CA04): login con Google. El tenant es del tipo
    # "Regular Web Application" — el backend es quien intercambia el código por
    # el token (necesita el client_secret), no el frontend. Sin estas tres
    # variables, /auth/google/login responde 503: convive con el login por
    # email/password, que sigue igual.
    auth0_domain: str = ""
    auth0_client_id: str = ""
    auth0_client_secret: str = ""
    # Tiene que estar cargada tal cual en Auth0 (Application > Allowed Callback
    # URLs). Cambia entre entornos (local vs. producción).
    auth0_callback_url: str = "http://localhost:8000/api/v1/auth/google/callback"

    # A dónde redirige el backend en el frontend al terminar el flujo de Google.
    # Éxito: {frontend_url}{ruta_exito}?token=<jwt>. Falla (CA03): sin token,
    # con ?error=auth_failed.
    google_login_ruta_exito: str = "/auth/callback"
    google_login_ruta_error: str = "/login"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def auth0_habilitado(self) -> bool:
        return bool(self.auth0_domain and self.auth0_client_id and self.auth0_client_secret)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def frontend_url_base(self) -> str:
        return self.frontend_url.rstrip("/")


settings = Settings()
