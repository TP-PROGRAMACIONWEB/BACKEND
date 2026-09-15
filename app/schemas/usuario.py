from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.usuario import RolUsuario


class UsuarioBase(BaseModel):
    email: EmailStr


class UsuarioCreate(UsuarioBase):
    model_config = ConfigDict(json_schema_extra={"example": {"email": "juan.perez@offix.test", "password": "Offix2026!"}})

    password: str


class UsuarioLogin(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"email": "juan.perez@offix.test", "password": "Offix2026!"}})

    email: EmailStr
    password: str


class UsuarioOut(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    rol: RolUsuario
    estado_cuenta: str
    fecha_registro: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
