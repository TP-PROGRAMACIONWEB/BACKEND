from pydantic import BaseModel, ConfigDict


class CategoriaBase(BaseModel):
    nombre: str
    descripcion: str | None = None


class CategoriaCreate(CategoriaBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"nombre": "Electricista", "descripcion": "Instalaciones y reparaciones eléctricas."}
        }
    )


class CategoriaUpdate(BaseModel):
    nombre: str | None = None
    descripcion: str | None = None
    estado: str | None = None


class CategoriaOut(CategoriaBase):
    model_config = ConfigDict(from_attributes=True)

    id_categoria: int
    estado: str
