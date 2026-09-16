from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import Base, engine
from app.models import (  # noqa: F401
    alerta_admin,
    archivo_adjunto,
    categoria,
    notificacion,
    oferente,
    resena,
    solicitud_resena,
    usuario,
)
from app.routers import admin, auth, categorias, notificaciones, oferentes, resenas

tags_metadata = [
    {"name": "Autenticación", "description": "Registro, inicio y cierre de sesión de Oferentes (RF1, RF4, HU-03)."},
    {"name": "Oferentes", "description": "Perfiles profesionales: alta, edición, búsqueda y consulta pública (RF2, RF7, RF8, HU-02)."},
    {"name": "Categorías", "description": "Rubros/oficios disponibles en la plataforma (RF18)."},
    {"name": "Reseñas", "description": "Flujo de calificaciones y reseñas vía link/QR único (RF10-RF13, HU-01)."},
    {
        "name": "Notificaciones",
        "description": "Bandeja in-app (la campana): reseñas esperando decisión y avisos al usuario (HU-01, HU-02).",
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
        "Sprint 1 — flujo de reseña (HU-01): el enlace se genera desde el perfil público y se envía por "
        "WhatsApp (link `wa.me` con el mensaje precargado) y/o por correo. Ver `docs/plan-sprint-1.md` "
        "para el detalle de alcance y decisiones."
    ),
    version="0.1.0",
    openapi_tags=tags_metadata,
    contact={"name": "Equipo Offix - UTN FRSF"},
    servers=[
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
app.include_router(oferentes.router)
app.include_router(categorias.router)
app.include_router(resenas.router)
app.include_router(notificaciones.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/health", tags=["Salud"], summary="Chequeo de salud del servicio")
def health_check():
    return {"status": "ok"}
