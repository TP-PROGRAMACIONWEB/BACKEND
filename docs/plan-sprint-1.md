# Plan Sprint 1 — Backend Offix (HU-01, HU-02, HU-03)

## Contexto

El profesor fijó el mínimo indispensable para Sprint 1 (termina 21/09/2026): base de datos creada, poblada con profesionales de prueba, y el flujo de "Registrar reseña" funcionando de punta a punta (arrancar, completar criterios + comentario, validar, guardar en la base). El equipo ya redactó 3 HU con sus tareas (HU-01 Registrar reseña, HU-02 Registrar Oferente, HU-03 Iniciar/cerrar sesión) pero sin criterios de aceptación, y el usuario (backend dev, dueño de este repo) decidió cerrar las tres completas en Sprint 1, no solo el mínimo.

La PM diseñó un DER definitivo (SQL adjunto) que reemplaza al diagrama de clases original en varios puntos importantes: `OFERENTE` comparte PK con `USUARIO` (no es un ID propio), `RESENA` guarda las puntuaciones por criterio + comentario en una sola columna JSON (`calificaciones_comentarios`) en vez de columnas sueltas, y `SOLICITUD_RESENA.contacto_referencia_cliente` pasa a ser obligatorio. Ese SQL es todavía un borrador (nadie lo ejecutó contra una base real), así que se usa como contrato de datos pero se deja que SQLAlchemy cree el esquema (nombres en snake_case minúscula, más idiomático en Postgres que las tablas `"MAYUSCULA"` citadas del export).

El código actual (escrito en un turno previo de esta sesión) ya tiene un scaffold FastAPI + SQLAlchemy funcionando con auth, perfiles de oferente, categorías y el flujo de reseñas — pero basado en el diagrama de clases viejo. Este plan actualiza ese scaffold para alinearlo al DER de la PM, agrega los faltantes (validaciones, endpoint de logout, endpoint de verificación manual de matrícula, seed de datos, tests automatizados) y redacta los criterios de aceptación de las 3 HU.

Decisiones ya cerradas con el usuario (no volver a preguntar):
- Cerrar HU-01, HU-02 y HU-03 completas en Sprint 1 (no solo el mínimo del profesor).
- El enlace de reseña lo genera el Oferente logueado (endpoint ya existente, se ajusta).
- Envío del enlace: **simulado** — el código/link se devuelve en la respuesta de la API, sin integrar mail/WhatsApp real.
- Criterios de valoración: **Precio, Calidad, Atención, Puntualidad** (los 3 del profesor + Puntualidad, propuesto por Claude y confirmado por el usuario).
- Validación de matrícula (HU-02 T07): **simulada** vía endpoint admin manual, sin integración externa real.
- Carga de archivos: **simulada** con URLs guardadas en `archivos_adjuntos`, sin integrar Cloudflare todavía.
- Nombres de tabla: **snake_case minúscula** (el SQL de la PM es un borrador no ejecutado; se usa como contrato de datos, no como script literal).
- Logout: **stateless** — el endpoint exige token válido y responde 204; no hay tabla de revocación (evita agregar una tabla fuera del DER de la PM sin su visto bueno).
- Testing: sumar **pytest** para endpoints clave, además de (no en reemplazo de) las pruebas manuales de QA con Hoppscotch/Playwright (fuera de este repo).
- No hacer commit ni push — el usuario los hace manualmente.

## Cambios de modelo (fuente de verdad: DER de la PM)

### `app/models/usuario.py`
- Corregir bug latente: `Enum(RolUsuario)` sin `values_callable` persiste el *nombre* del enum Python, no su `.value`. Se agrega `values_callable=lambda e: [x.value for x in e]`.
- Valores de `rol` pasan a `"Oferente"` / `"Administrador"` (coincide con el `CHECK` del DER de la PM). `estado_cuenta` pasa a `String` plano con valores `"Activa"/"Suspendida"/"Bloqueada"` (el DER solo le puso `DEFAULT`, no `CHECK`).

### `app/models/oferente.py` — cambio central: PK compartida con Usuario
```python
id_oferente = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), primary_key=True)
```
No hay columna `id_usuario` separada. SQLAlchemy desactiva el autoincrement automáticamente en una PK que también es FK. Al crear el perfil (usuario ya persistido y autenticado):
```python
oferente = Oferente(id_oferente=usuario.id_usuario, **payload.model_dump())
```
Renombrar `cantidad_resenas_rechazadas` → `cantidad_rechazos_acumulados`. `estado_verificacion` con valores `"Pendiente"/"Verificado"/"Rechazado"`.

### `app/models/resena.py` — columna JSON en vez de columnas sueltas
```python
from sqlalchemy import JSON
calificaciones_comentarios = Column(JSON, nullable=False)
```
Se eliminan `calificacion`, `comentario`, `replica_oferente` (esta última no existe en el DER de la PM — la funcionalidad de réplica queda diferida a un sprint futuro; cuando se retome, se puede guardar como clave adicional dentro de este mismo JSON sin migrar tabla). Estructura JSON:
```json
{
  "puntuacion_global": 5,
  "criterios": {"precio": 4, "calidad": 5, "atencion": 5, "puntualidad": 4},
  "comentario": "texto opcional"
}
```
Valores de `estado`: `"Pendiente_Aprobacion"/"Aprobada"/"Rechazada"`.

### `app/models/solicitud_resena.py`
`contacto_referencia_cliente` pasa a `nullable=False`. Valores de `estado`: `"Pendiente_Uso"/"Utilizada"`.

### `app/models/categoria.py`, `app/models/alerta_admin.py`, `app/models/archivo_adjunto.py`
Solo cambian los valores default de `estado`/`estado_revision` a la convención TitleCase (`"Activa"`, `"Pendiente"`, `"Revisada"`) y se agrega `ondelete="CASCADE"` a los FK, para reflejar el DER.

## Base de datos

- Se mantiene `Base.metadata.create_all` en el `startup` de `app/main.py` (ya funciona). **No** se introduce Alembic todavía — el esquema puede seguir moviéndose sprint a sprint y no hay datos productivos que preservar.
- Como `oferentes` y `resenas` cambian de forma incompatible (columnas eliminadas/renombradas, PK distinta), hay que borrar la base de datos local de desarrollo antes de levantar el server con el nuevo código (drop del `.db` si es SQLite, o `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` si es Postgres local).
- `app/db/database.py`: agregar soporte opcional a SQLite (`connect_args={"check_same_thread": False}` solo si `DATABASE_URL` empieza con `sqlite`), para poder levantar el backend sin instalar Postgres localmente si hace falta.
- Cuando la PM tenga la connection string real de Supabase, alcanza con ponerla en `DATABASE_URL` del `.env` y levantar el backend una vez — `create_all` genera el esquema completo. Avisarle que no hace falta que corra su script SQL a mano (evita el choque de nombres `"USUARIO"` mayúscula vs `usuarios` minúscula).

## Schemas y routers — cambios de contrato

### `app/schemas/resena.py`
```python
class CriteriosValoracion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    precio: int = Field(ge=1, le=5)
    calidad: int = Field(ge=1, le=5)
    atencion: int = Field(ge=1, le=5)
    puntualidad: int = Field(ge=1, le=5)

class CalificacionesComentariosIn(BaseModel):
    puntuacion_global: int = Field(ge=1, le=5)
    criterios: CriteriosValoracion
    comentario: str | None = Field(default=None, max_length=1000)

class SolicitudResenaCreate(BaseModel):
    contacto_referencia_cliente: str = Field(min_length=3, max_length=100)

class ResenaCreate(BaseModel):
    codigo_unico: str
    nombre_cliente: str = Field(min_length=2, max_length=100)
    contacto_cliente_ingresado: str = Field(min_length=3, max_length=100)
    calificaciones_comentarios: CalificacionesComentariosIn

class ResenaModeracion(BaseModel):
    aprobar: bool
```
`ResenaOut.calificaciones_comentarios` como `dict` laxo (tolera que el set de criterios cambie en sprints futuros sin romper la lectura de reseñas viejas). `ResenaOut` pierde `calificacion`/`comentario`/`replica_oferente`.

### `app/routers/resenas.py`
- `generar_solicitud_resena` ahora recibe body `SolicitudResenaCreate` (antes no tenía body) y persiste `contacto_referencia_cliente`.
- `registrar_resena` guarda `payload.calificaciones_comentarios.model_dump()` en la columna JSON.
- `moderar_resena`: sacar toda referencia a `replica_oferente`; renombrar `cantidad_resenas_rechazadas` → `cantidad_rechazos_acumulados`; mantener la lógica ya existente de alerta al llegar a 5 de las últimas 10 reseñas rechazadas (reutilizar tal cual, solo ajustar nombres).

### `app/routers/oferentes.py`
- `crear_perfil_oferente`: crear con `Oferente(id_oferente=usuario.id_usuario, ...)`; agregar guard `if usuario.rol != RolUsuario.OFERENTE: 403` (cierra HU-03 T08).
- `app/schemas/oferente.py`: `OferenteOut` pierde `id_usuario` (queda fusionado en `id_oferente`), gana `cantidad_rechazos_acumulados`. Agregar `field_validator` en `OferenteBase` para `dni_cuit` (solo dígitos/guiones) y `telefono` (dígitos/`+`/espacios) — cierra HU-02 T04.

### `app/routers/auth.py`
- `login`: si `usuario.estado_cuenta` es `"Suspendida"` o `"Bloqueada"`, responder 403 (gap real que hoy no se valida).
- Nuevo endpoint `POST /api/v1/auth/logout` (requiere `get_current_user`, responde 204, sin revocación server-side — comentario explicando el porqué).

### `app/routers/admin.py`
- Nuevo endpoint `PATCH /api/v1/admin/oferentes/{oferente_id}/verificacion` (requiere `require_admin`) que setea `estado_verificacion` manualmente — simula la integración externa de matrícula (HU-02 T07).
- Ajustar referencias a `EstadoResena`/nombres nuevos en `listar_resenas_rechazadas` y `publicar_resena_rechazada`.

## Seed de datos de prueba — `app/db/seed.py` (nuevo)

Script idempotente (patrón get-or-create por campo único):
- 6 categorías: Electricista, Gasista, Plomero, Técnico en Aire Acondicionado, Albañil, Carpintero.
- 6 Oferentes de ejemplo (Usuario + Oferente ligados por PK compartida, vía `db.flush()` para obtener `id_usuario` antes de crear el Oferente), con nombre/apellido reales, repartidos en distintos `estado_verificacion` (Verificado/Pendiente/Rechazado) para poder mostrar el distintivo.
- 1 usuario admin (`admin@offix.test`).
- 1 `SolicitudResena` pre-generada con código legible (`"DEMO-CODE-0001"`) sobre uno de los oferentes, para que el profesor pueda probar `POST /resenas` directo sin loguearse primero, además del flujo completo (login como oferente → generar solicitud → usar el código devuelto).

Ejecutable con `python -m app.db.seed`. Nuevo `cargar_datos_prueba.bat` en la raíz (mismo estilo que `instalar_dependencias.bat`/`iniciar_backend.bat`): activa el venv y corre el script.

## Tests automatizados (pytest)

- Agregar a `requirements.txt`: `pytest==8.3.4`, `httpx==0.28.1` (requerido por `TestClient`, no está instalado hoy).
- `app/tests/conftest.py`: engine SQLite in-memory con `StaticPool`, fixture `db_session` (crea/dropea tablas por test), fixture `client` que overridea `get_db` de `app/db/database.py` con `app.dependency_overrides`.
- Casos mínimos repartidos en `test_auth.py`, `test_oferentes.py`, `test_resenas.py`, `test_admin.py`:
  - Registro/login: email duplicado, credenciales incorrectas, cuenta suspendida bloquea login.
  - Perfil oferente: `id_oferente == id_usuario`, sin token → 401, perfil duplicado → 409, DNI duplicado → 409.
  - Solicitud de reseña: requiere `contacto_referencia_cliente`, solo el dueño puede generarla.
  - Registrar reseña: código válido, código inexistente/ya usado → 400, criterio faltante o fuera de rango → 422.
  - Moderar reseña: aprobar/rechazar, no-dueño → 403, ya moderada → 400.
  - Alerta automática: 5 de las últimas 10 reseñas rechazadas dispara `AlertaAdministrador`; 4 de 10 no la dispara.
  - Solo reseñas `"Aprobada"` aparecen en el listado público.
  - Rutas de admin exigen rol admin (403 si no).
  - Logout: sin token → 401, con token → 204.
- Nuevo `ejecutar_tests.bat` (mismo estilo): activa venv, corre `pytest -v`.

## Criterios de aceptación (para completar las 3 HU)

**HU-01 — Registrar reseña** (historia viva; T15 notificación al oferente y T16 réplica quedan diferidas a sprints futuros):
- Un Oferente autenticado genera una solicitud indicando contacto de referencia → recibe código único, solicitud en `Pendiente_Uso`.
- Con código válido y sin sesión, un cliente envía nombre, contacto, puntuación global, las 4 puntuaciones por criterio y comentario opcional → se crea la reseña en `Pendiente_Aprobacion` y la solicitud pasa a `Utilizada`.
- Código inexistente o ya utilizado → 400, no se crea nada.
- Falta un dato obligatorio o un criterio fuera de 1-5 → 422, no se persiste nada.
- Solo las reseñas `Aprobada` se listan en el perfil público.

**HU-02 — Registrar Oferente** (se cierra completa en Sprint 1):
- Usuario logueado sin perfil previo crea su perfil con datos válidos → `id_oferente = id_usuario`, `estado_verificacion = Pendiente`.
- Campo obligatorio faltante o DNI/CUIT/teléfono con formato inválido → 422.
- DNI/CUIT duplicado o usuario que ya tiene perfil → 409.
- La contraseña nunca se guarda en texto plano (hash bcrypt).
- Un administrador puede marcar manualmente `estado_verificacion` (simulación de HU-02 T07); el perfil público refleja el cambio.
- Integración real con un validador externo de matrícula queda diferida.

**HU-03 — Iniciar y cerrar sesión** (se cierra completa en Sprint 1):
- Login con credenciales correctas y cuenta activa → JWT válido.
- Credenciales incorrectas → 401 genérico (no revela cuál dato falló).
- Cuenta suspendida/bloqueada → 403 aunque la contraseña sea correcta.
- Endpoint protegido sin token o con token inválido → 401; con rol insuficiente → 403.
- Logout con token válido → 204 (stateless: el cliente descarta el token, sin revocación server-side — documentado explícitamente).

## Riesgos / pendientes a señalar al equipo (no bloquean Sprint 1)

- Falta `replica_oferente` en el DER de la PM (T16 diferida; se puede resolver como clave extra dentro del JSON cuando se retome).
- `ON DELETE CASCADE` de Usuario→Oferente es agresivo si en el futuro se agrega un borrado real de usuarios (hoy solo existe `PATCH estado`).
- `fecha_expiracion` de la solicitud existe en el modelo pero no se valida todavía.
- `promedio_calificacion` ya no se recalcula automáticamente (la puntuación global vive dentro del JSON) — queda como TODO para cuando se quiera mostrar el promedio real en el perfil.
- Avisar a la PM que no hace falta correr su DDL a mano contra Supabase; alcanza con apuntar `DATABASE_URL` y levantar el backend una vez.

## Orden de implementación

1. Modelos (`app/models/*.py`).
2. `app/db/database.py` (soporte SQLite opcional) + borrar/recrear la BD local de desarrollo.
3. Schemas (`app/schemas/*.py`).
4. Routers: `auth.py` → `oferentes.py` → `resenas.py` → `admin.py`.
5. `app/db/seed.py` + `cargar_datos_prueba.bat`.
6. Verificación manual: `iniciar_backend.bat` + revisar `/docs`.
7. `requirements.txt` (pytest, httpx) + `app/tests/*` + `ejecutar_tests.bat`.
8. Correr la suite completa y ajustar.

## Verificación end-to-end

1. `instalar_dependencias.bat` (o `pip install -r requirements.txt` si el venv ya existe) para tomar `pytest`/`httpx` nuevos.
2. Borrar la base de datos local y levantar `iniciar_backend.bat`; confirmar en `http://localhost:8000/docs` que el esquema OpenAPI expone los nuevos contratos (body de `solicitudes-resena`, `calificaciones_comentarios` anidado, `PATCH /admin/oferentes/{id}/verificacion`, `POST /auth/logout`).
3. `cargar_datos_prueba.bat` y verificar en `/docs` (o con `GET /api/v1/oferentes`) que aparecen los 6 oferentes seedeados.
4. Probar a mano el flujo completo: login como oferente seedeado → `POST /oferentes/{id}/solicitudes-resena` → copiar `codigo_unico` → `POST /resenas` con ese código y criterios → `GET /oferentes/{id}/resenas` (antes de aprobar, no debe aparecer) → `PATCH /resenas/{id}/moderar` con `aprobar:true` → reaparece en el listado público.
5. `ejecutar_tests.bat` y confirmar que toda la suite pytest pasa en verde.
