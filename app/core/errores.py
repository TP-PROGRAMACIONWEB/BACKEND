"""Formato uniforme de los errores de la API (HU-04, D10).

- **422 de validación** (Pydantic o reglas de negocio): `{"detail": [...], "errores": [{"campo", "codigo"}]}`.
  `detail` se conserva con lo que devuelve FastAPI, para no romper a los
  frontends que ya lo leen. `errores` es lo que pinta el formulario: el
  frontend mapea `codigo` al texto literal de QA y marca **todos** los campos.
- **Errores de negocio** (400, 403, 409, 429, 503): `{"detail": {"codigo", "mensaje"}}`,
  construidos con `error_negocio`.
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Tipos de error que Pydantic usa por defecto, traducidos al vocabulario de QA.
# Cualquier tipo que no esté acá es un código propio (`PydanticCustomError`), y
# se devuelve tal cual: el código es el `type` del error.
_TIPOS_BUILTIN = {
    "missing": "requerido",
    "string_too_short": "longitud_minima",
    "string_too_long": "longitud_maxima",
    "string_type": "invalido",
    "extra_forbidden": "campo_no_permitido",
    "time_parsing": "horario_invalido",
    "time_type": "horario_invalido",
    "int_parsing": "invalido",
    "int_type": "invalido",
    "bool_parsing": "invalido",
    "bool_type": "invalido",
    "list_type": "invalido",
    "value_error": "invalido",
    "assertion_error": "invalido",
    "literal_error": "invalido",
    "json_invalid": "invalido",
    "model_attributes_type": "invalido",
    "dict_type": "invalido",
}

# Un campo puede tener un código más específico que el genérico de su tipo.
_CODIGO_POR_CAMPO = {("dias_atencion", "requerido"): "dias_requeridos"}

_PARTES_NO_CAMPO = {"body", "query", "path", "header", "cookie"}


class ErrorValidacion(Exception):
    """Error de validación que no sale de Pydantic (por ejemplo, una categoría
    que no existe). Se responde con el mismo formato que el 422 de FastAPI.

    `errores` es una lista de `{"campo", "codigo", "mensaje"}`: el mensaje solo
    va en `detail`; el contrato con el frontend es campo + código.
    """

    def __init__(self, errores: list[dict]):
        super().__init__("validación")
        self.errores = errores


def error_validacion(campo: str, codigo: str, mensaje: str) -> ErrorValidacion:
    return ErrorValidacion([{"campo": campo, "codigo": codigo, "mensaje": mensaje}])


def error_negocio(status_code: int, codigo: str, mensaje: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"codigo": codigo, "mensaje": mensaje})


def _campo(loc: tuple) -> str:
    partes = [str(parte) for parte in loc if parte not in _PARTES_NO_CAMPO and not isinstance(parte, int)]
    return ".".join(partes) or "general"


def _codigo(error: dict) -> str:
    tipo = error["type"]
    if tipo == "string_too_short" and error.get("input") in ("", None):
        return "requerido"
    if tipo == "string_type" and error.get("input") is None:
        return "requerido"
    if tipo in _TIPOS_BUILTIN:
        return _TIPOS_BUILTIN[tipo]
    return tipo


def respuesta_validacion(detail: list, errores: list[dict]) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(detail), "errores": errores},
    )


async def manejar_validacion_request(request: Request, exc: RequestValidationError) -> JSONResponse:
    errores = []
    for error in exc.errors():
        campo = _campo(error["loc"])
        codigo = _codigo(error)
        codigo = _CODIGO_POR_CAMPO.get((campo, codigo), codigo)
        errores.append({"campo": campo, "codigo": codigo})
    return respuesta_validacion(exc.errors(), errores)


async def manejar_error_validacion(request: Request, exc: ErrorValidacion) -> JSONResponse:
    detail = [{"loc": ["body", error["campo"]], "msg": error["mensaje"], "type": error["codigo"]} for error in exc.errores]
    errores = [{"campo": error["campo"], "codigo": error["codigo"]} for error in exc.errores]
    return respuesta_validacion(detail, errores)


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, manejar_validacion_request)
    app.add_exception_handler(ErrorValidacion, manejar_error_validacion)
