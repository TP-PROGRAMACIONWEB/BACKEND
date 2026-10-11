from pydantic import BaseModel, Field


class CategoriaCatalogo(BaseModel):
    id: int
    nombre: str


class ExperienciaCatalogo(BaseModel):
    codigo: str
    etiqueta: str


class DiaCatalogo(BaseModel):
    dia: int = Field(description="ISO-8601: 1 = lunes … 7 = domingo.")
    corto: str
    largo: str


class HorarioPorDefecto(BaseModel):
    apertura: str
    cierre: str


class LimitesCatalogo(BaseModel):
    trabajos: int = Field(description="Trabajos realizados por Oferente.")
    fotos_por_trabajo: int
    tamano_maximo_mb: int


class CatalogoRegistroOut(BaseModel):
    """Llena todos los selectores del formulario de registro en una sola llamada."""

    categorias: list[CategoriaCatalogo]
    experiencia: list[ExperienciaCatalogo]
    dias: list[DiaCatalogo]
    horario_default: HorarioPorDefecto
    limites: LimitesCatalogo
