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
2. Se genera automáticamente una colección con todos los endpoints, agrupados por tag (Autenticación, Oferentes, Categorías, Reseñas, Administración).
3. Configurar una variable de entorno `baseUrl = http://localhost:8000` (o la URL que corresponda) para no tener que editar cada request.

Ese archivo puede quedar desactualizado si el código cambia sin volver a exportarlo. Para regenerarlo:

```bash
python -m app.scripts.export_openapi
```

(requiere el entorno virtual activado — `venv\Scripts\activate.bat` — no hace falta que el servidor esté corriendo).

## Notas de alcance (Sprint 1)

- La validación de matrícula (HU-02) es simulada, vía `PATCH /admin/oferentes/{id}/verificacion`.
- El logout es stateless (no hay revocación real de tokens del lado del servidor).

## El flujo de reseña se está construyendo por fases

El equipo redefinió el caso de uso de HU-01 (ver [`plan-sprint-1.md`](plan-sprint-1.md), revisión 3): hay **dos caminos** para pedir una reseña, uno que inicia el cliente por correo y otro que inicia el profesional por WhatsApp.

**Ya implementado (Fases 1 y 2):**

| Cambio | Detalle |
|---|---|
| `POST /oferentes/{id}/solicitudes-resena` | Ya no recibe body. Es el camino del oferente y marca `origen = Oferente_WhatsApp` |
| `POST /resenas` | Las puntuaciones son decimales de 0.5 a 5 en pasos de media estrella, y `puntuacion_global` ya **no se manda**: la calcula el backend como promedio de los 4 criterios |
| `PUT /oferentes/{id}` | Acepta `notificaciones_email_habilitadas` |
| Servicio de correo | Integrado con Brevo, todavía sin conectar a los endpoints |

**Todavía por venir (Fases 3 y 4):**

| Endpoint | Cambio previsto |
|---|---|
| `POST /oferentes/{id}/solicitudes-resena` | Pasa a ser el camino público del cliente, con body `{nombre_cliente, email_cliente}` y envío del enlace por correo |
| `POST /oferentes/{id}/solicitudes-resena/whatsapp` | Nuevo: el camino del oferente se muda acá y suma la `whatsapp_url` ya armada |
| `GET /solicitudes-resena/{codigo}` | Nuevo, público: alimenta la vista de reseña |
| `POST /resenas/verificar` | Nuevo: confirma una reseña del flujo por WhatsApp |
| `GET /resenas/pendientes` | Nuevo, para el oferente autenticado |

Los endpoints de autenticación, oferentes, categorías y administración ya son estables.

Ver [`docs/plan-sprint-1.md`](plan-sprint-1.md) para el detalle completo de decisiones y alcance.
