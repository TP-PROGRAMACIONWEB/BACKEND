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
