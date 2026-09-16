from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.usuario import RolUsuario


class UsuarioBase(BaseModel):
    email: EmailStr


class UsuarioCreate(UsuarioBase):
    model_config = ConfigDict(json_schema_extra={"example": {"email": "juan.perez@offix.example.com", "password": "Offix2026!"}})

    password: str


class UsuarioLogin(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"email": "juan.perez@offix.example.com", "password": "Offix2026!"}})

    email: EmailStr
    password: str


class UsuarioOut(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    rol: RolUsuario
    estado_cuenta: str
    fecha_registro: datetime


class PerfilOut(BaseModel):
    """HU-03 / CA02: lo único que se ve al volver del login. Nada de datos del
    perfil de Oferente — esa es otra HU."""

    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    email: EmailStr
    nombre: str | None = Field(default=None, description="Viene de Google. Vacío para cuentas que solo usaron email/password.")
    rol: RolUsuario


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
