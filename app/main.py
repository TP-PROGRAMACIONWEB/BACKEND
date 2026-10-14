from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.database import preparar_esquema
from app.models import (  # noqa: F401
    alerta_admin,
    archivo_adjunto,
    categoria,
    matricula,
    notificacion,
    oferente,
    oferente_dia_atencion,
    resena,
    solicitud_resena,
    trabajo_realizado,
    usuario,
)
from app.core.errores import registrar_manejadores
from app.routers import admin, archivos, auth, catalogos, categorias, matriculas, notificaciones, oferentes, padrones_cron, resenas, trabajos
from app.services.storage import StorageError

tags_metadata = [
    {"name": "Autenticación", "description": "Registro, inicio y cierre de sesión de Oferentes (RF1, RF4, HU-03)."},
    {"name": "Oferentes", "description": "Perfiles profesionales: alta, edición, búsqueda y consulta pública (RF2, RF7, RF8, HU-02)."},
    {"name": "Categorías", "description": "Rubros/oficios disponibles en la plataforma (RF18)."},
    {"name": "Reseñas", "description": "Flujo de calificaciones y reseñas vía link/QR único (RF10-RF13, HU-01)."},
    {
        "name": "Notificaciones",
        "description": "Bandeja in-app (la campana): reseñas esperando decisión y avisos al usuario (HU-01, HU-02).",
    },
    {
        "name": "Matrículas",
        "description": "Validación de matrícula profesional contra el padrón cargado, síncrona (HU-02).",
    },
    {"name": "Administración", "description": "Gestión de usuarios, verificación de matrícula, alertas y moderación (RF14-RF18)."},
]

app = FastAPI(
    title="Offix API",
    description=(
        "API REST del backend de Offix, red social de oficios (UTN FRSF).\n\n"
        "### Cómo autenticarse\n"
        "1. `POST /api/v1/auth/registro` para crear un usuario.\n"
        "2. `POST /api/v1/auth/login` para obtener un `access_token` (JWT).\n"
        "3. Enviarlo en cada request protegida como header `Authorization: Bearer <access_token>` "
        "(en Swagger UI: botón **Authorize**, arriba a la derecha).\n\n"
        "### Para el equipo de QA (Hoppscotch)\n"
        "El spec completo también está disponible en `/openapi.json` y como archivo estático en "
        "`docs/openapi.json` del repo — se puede importar directo en Hoppscotch como colección.\n\n"
        "### Estado del proyecto\n"
        "Sprint 2 — registro de Profesional (HU-04) con perfil público y privado, fotos y trabajos realizados "
        "en Supabase Storage, y reseñas con las reglas de HU-01 v1.2. Ver `docs/plan-sprint-2.md` para el "
        "detalle de alcance y decisiones."
    ),
    version="0.1.0",
    openapi_tags=tags_metadata,
    contact={"name": "Equipo Offix - UTN FRSF"},
    servers=[
        {"url": "https://backend-offix3.vercel.app", "description": "Producción (Vercel + Supabase)"},
        {"url": "http://localhost:8000", "description": "Entorno local (iniciar_backend.bat)"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(catalogos.router)
app.include_router(oferentes.router)
app.include_router(archivos.router)
app.include_router(trabajos.router)
app.include_router(categorias.router)
app.include_router(resenas.router)
app.include_router(notificaciones.router)
app.include_router(matriculas.router)
app.include_router(admin.router)
app.include_router(padrones_cron.router)

registrar_manejadores(app)


@app.exception_handler(StorageError)
def manejar_storage_error(request, exc: StorageError):
    # Supabase no respondió: el cliente puede reintentar, y la base no quedó a medias.
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": {"codigo": "storage_no_disponible", "mensaje": str(exc)}},
    )


@app.on_event("startup")
def on_startup():
    preparar_esquema()


@app.get("/health", tags=["Salud"], summary="Chequeo de salud del servicio")
def health_check():
    return {"status": "ok"}
