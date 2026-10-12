# Documentación de la API (OpenAPI)

El backend expone automáticamente su documentación en formato OpenAPI 3.1, generada a partir del código (rutas, modelos Pydantic y validaciones), así que nunca queda desactualizada respecto a lo que realmente hace el servidor.

## Con el backend corriendo (`iniciar_backend.bat`)

- **Swagger UI** (interactiva, permite probar los endpoints desde el navegador): http://localhost:8000/docs
- **ReDoc** (solo lectura, más prolija para consulta): http://localhost:8000/redoc
- **Spec crudo en JSON**: http://localhost:8000/openapi.json

### Cómo autenticarse en Swagger UI

1. `POST /api/v1/auth/registro` para crear un usuario (o usar uno de los oferentes de prueba cargados con `cargar_datos_prueba.bat`, ver `docs/plan-sprint-1.md`).
2. `POST /api/v1/auth/login` para obtener el `access_token`.
3. Click en **Authorize** (arriba a la derecha) y pegar `Bearer <access_token>`.

## Para el equipo de Frontend

El contrato de cada endpoint (parámetros, body, respuestas, códigos de error posibles) está documentado directamente en `/docs`. Los modelos de request/response (`OferenteOut`, `ResenaCreate`, etc.) incluyen ejemplos de payload reales — son los mismos que devuelve/espera el backend.

Los contratos son inestables durante Sprint 1 (el esquema todavía puede cambiar); ante cualquier duda sobre un campo, `/docs` es la fuente de verdad, no este archivo.

## Para el equipo de QA (Hoppscotch)

Sin necesidad de levantar el backend, hay un spec estático versionado en [`docs/openapi.json`](openapi.json). Para importarlo en Hoppscotch:

1. Hoppscotch → **Import** → **OpenAPI** → seleccionar `docs/openapi.json`.
2. Se genera automáticamente una colección con todos los endpoints, agrupados por tag (Autenticación, Oferentes, Categorías, Reseñas, Notificaciones, Matrículas, Administración).
3. Configurar una variable de entorno `baseUrl = http://localhost:8000` (o la URL que corresponda) para no tener que editar cada request.

Ese archivo puede quedar desactualizado si el código cambia sin volver a exportarlo. Para regenerarlo:

```bash
python -m app.scripts.export_openapi
```

(requiere el entorno virtual activado — `venv\Scripts\activate.bat` — no hace falta que el servidor esté corriendo).

## Sprint 2 — errores y endpoints nuevos (ver `docs/plan-sprint-2.md`)

**Errores de validación (422)** traen dos listas. `detail` es lo que devuelve FastAPI, como antes. `errores` es lo que pinta el formulario, con un `campo` y un `codigo` por cada problema, y **todos juntos**:

```json
{
  "detail": [...],
  "errores": [{"campo": "telefono", "codigo": "telefono_invalido"}, {"campo": "dias_atencion", "codigo": "dias_requeridos"}]
}
```

**Errores de negocio** (400, 403, 409, 429) traen `detail` como objeto: `{"codigo": "...", "mensaje": "..."}`. Los códigos que el frontend tiene que mapear al texto de QA están en `docs/plan-sprint-2.md`, sección "Tabla código → texto".

Endpoints nuevos o modificados de Sprint 2:

| Método y ruta | Descripción |
|---|---|
| `GET /api/v1/auth/me` | Suma `requiere_registro`: `true` para un Oferente que todavía no completó el formulario |
| `GET /api/v1/catalogos/registro-oferente` | Categorías activas, rangos de experiencia, días, horario por defecto y límites de trabajos |
| `POST /api/v1/oferentes` | Confirma el registro en una sola transacción (201, 409 `perfil_existente`, 422 con `errores[]`) |
| `GET /api/v1/oferentes/me` / `PUT /api/v1/oferentes/me` | Perfil privado (incluye DNI/CUIT) y edición sin DNI ni correo |
| `GET /api/v1/oferentes/{id}` | Perfil público: sin DNI, sin estado de verificación, sin rechazos acumulados |
| `POST /api/v1/oferentes/me/archivos/subidas` | Paso 1 de la subida: valida y devuelve `path` y `upload_url` firmada de Supabase |
| `PUT /api/v1/oferentes/me/foto-perfil` · `DELETE …/foto-perfil` · `PUT …/portada` | Confirmación (paso 3) y borrado de imágenes únicas |
| `GET /api/v1/oferentes/{id}/trabajos` · `POST /api/v1/oferentes/me/trabajos` · `DELETE …/trabajos/{id}` | Trabajos realizados con fotos ordenadas; el alta devuelve 409 `limite_trabajos` a partir del quinto |
| `POST /api/v1/oferentes/{id}/solicitudes-resena` | Auth opcional: anónimo solo correo; el Profesional dueño, teléfono o correo. Límites anti-spam (el reenvío del mismo enlace también cuenta): 429 `limite_solicitudes` |
| `GET /api/v1/oferentes/{id}/resenas` | Opiniones públicas paginadas (`pagina`, `por_pagina` de 1 a 10, por defecto 5; respuesta con `items`, `total`, `paginas`): `cliente` = "Juan C.", sin contacto |

## Notas de alcance (Sprint 1, revisión 4)

- El logout es stateless (no hay revocación real de tokens del lado del servidor).
- `PATCH /admin/oferentes/{id}/verificacion` sigue existiendo como override manual del Administrador, pero ya no es el camino principal de verificación: eso lo hace ahora la validación automática de matrícula (HU-02).

## Estado de las cuatro fases (ver `docs/plan-sprint-1.md`)

**HU-01 completa (Fases 1 a 3):** generación del enlace de reseña (WhatsApp y/o correo, sin login), formulario de reseña, bandeja de notificaciones in-app (la campana) y moderación Aceptar/Rechazar con recálculo de promedio y alerta al Administrador.

**HU-02 (Fase 4) — validación de matrícula profesional:**

| Método y ruta | Descripción |
|---|---|
| `POST /api/v1/oferentes/me/matriculas/validaciones` | El Oferente logueado valida `{tipo_profesional, numero_matricula}` contra el padrón cargado. Síncrono, devuelve un código de `resultado` (`Validada`, `No_Encontrada`, `Timeout`, `Ya_Fidelizada`, `Reemplazo_Solicitado`, `Vencida`, `Nombre_No_Coincide`) y su mensaje |
| `GET /api/v1/oferentes/me/matriculas` | Matrículas fidelizadas por el Oferente autenticado |
| `GET /api/v1/oferentes/me/matriculas/validaciones` | Historial de todos los intentos, incluidos los fallidos |
| `PATCH /api/v1/admin/matriculas/reemplazos/{id_validacion}` | El Administrador autoriza o deniega un pedido de reemplazo de matrícula |

**Alcance de esta fase:** solo está cargado el padrón de **Gasista** (`app/db/padrones/gasistas.md`, 68 matriculados). El tipo `Aire acondicionado` está soportado por el código (formato, matrícula trampa), pero como no hay padrón cargado, cualquier número de ese tipo devuelve `No_Encontrada` hasta que llegue el archivo real.

Ver [`docs/plan-sprint-1.md`](plan-sprint-1.md) para el detalle completo de decisiones y alcance.
