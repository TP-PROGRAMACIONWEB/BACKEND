from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import Base, engine
from app.models import alerta_admin, archivo_adjunto, categoria, oferente, resena, solicitud_resena, usuario  # noqa: F401
from app.routers import admin, auth, categorias, oferentes, resenas

tags_metadata = [
    {"name": "Autenticación", "description": "Registro, inicio y cierre de sesión de Oferentes (RF1, RF4)."},
    {"name": "Oferentes", "description": "Perfiles profesionales: alta, edición, búsqueda y consulta pública (RF2, RF7, RF8)."},
    {"name": "Categorías", "description": "Rubros/oficios disponibles en la plataforma (RF18)."},
    {"name": "Reseñas", "description": "Flujo de calificaciones y reseñas vía link/QR único (RF10-RF13)."},
    {"name": "Administración", "description": "Gestión de usuarios, alertas y moderación (RF14-RF18)."},
]

app = FastAPI(
    title="Offix API",
    description="API REST del backend de Offix, red social de oficios.",
    version="0.1.0",
    openapi_tags=tags_metadata,
    contact={"name": "Equipo Offix - UTN FRSF"},
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
app.include_router(admin.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/health", tags=["Salud"])
def health_check():
    return {"status": "ok"}
