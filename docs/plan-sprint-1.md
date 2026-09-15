# Plan Sprint 1 — Backend Offix (HU-01, HU-02, HU-03)

> **Revisión 3 (2026-09-14)** — El profesor pidió que convivan **los dos caminos** para pedir una
> reseña: por correo desde la vista del cliente, y por WhatsApp desde la vista del profesional.
> Las revisiones 1 y 2 están en el historial de git.

## Contexto

El profesor fijó el mínimo indispensable para Sprint 1 (cierra el 21/09/2026): base de datos creada, poblada con profesionales de prueba, y el flujo de "Registrar reseña" funcionando de punta a punta. El equipo redactó 3 HU (HU-01 Registrar reseña, HU-02 Registrar Oferente, HU-03 Iniciar/cerrar sesión) y se decidió cerrar las tres en este sprint.

La PM diseñó el DER (`DER_Offix.sql`), fuente de verdad del modelo de datos: `OFERENTE` comparte PK con `USUARIO`, `RESENA` guarda puntuaciones y comentario en una columna JSON, y `SOLICITUD_RESENA` representa el enlace único de reseña. Ese SQL es un borrador que nadie ejecutó; se usa como contrato mientras SQLAlchemy crea el esquema real (snake_case minúscula).

**Qué cambia en esta revisión:** el enlace de reseña puede originarse de dos maneras distintas, con recorridos y garantías diferentes. En ambos casos el cliente termina verificado por correo, así que el enlace deja de ser la simulación que era en la revisión 1.

## Los dos flujos de reseña

### Flujo A — lo inicia el cliente (correo)

1. Un cliente anónimo entra al perfil público de un Oferente y presiona "Generar reseña".
2. Completa **nombre** y **mail** en un dialog, y acepta.
3. El backend crea la solicitud (`origen = Cliente_Email`, con esos datos) y **le envía el link por correo**.
4. El cliente abre el link: la vista muestra su nombre y mail **bloqueados**, el grid 2x2 con los 4 criterios de 0.5 a 5 estrellas, y debajo el comentario opcional.
5. Al enviar, la reseña queda directamente en `Pendiente_Aprobacion` — el correo ya probó que la casilla es suya.
6. Se le avisa al Oferente por mail (si tiene las notificaciones activas).

### Flujo B — lo inicia el profesional (WhatsApp)

1. El Oferente, logueado, presiona "Generar link para reseña".
2. El backend crea una solicitud **en blanco** (`origen = Oferente_WhatsApp`, sin datos del cliente) y devuelve el código, la URL de la reseña y la **URL de WhatsApp ya armada** con el texto predefinido.
3. El frontend redirige a esa URL: se abre la pantalla "Enviar a…" de WhatsApp y el Oferente elige el contacto.
4. El cliente abre el link: la vista es la misma, pero con nombre y mail **editables y vacíos**, porque el sistema todavía no sabe quién es.
5. Al enviar, la reseña queda en `Pendiente_Verificacion` y **se le manda un correo de verificación** al mail que cargó.
6. Cuando hace click en ese correo, la reseña pasa a `Pendiente_Aprobacion` y **recién ahí** se le avisa al Oferente.

### Lo que comparten

Desde `Pendiente_Aprobacion` el recorrido es idéntico: el Oferente aprueba o rechaza; al aprobar la reseña se publica en su perfil y se recalcula su promedio; rechazar 5 o más de las últimas 10 genera la alerta automática al Administrador.

### Por qué el flujo B también verifica por correo

Sin esa verificación, el Oferente puede generar links y completarlos él mismo para autogenerarse reseñas buenas — exactamente lo que el profesor quería evitar. Pedir el mail y confirmar desde ahí cierra ese agujero.

**Consecuencia importante:** el correo queda en el camino crítico de los dos flujos. Ya no existe un flujo "rápido" que se pueda demostrar sin tener Brevo andando, así que la integración del servicio de mail es lo primero que hay que resolver.

### Decisiones cerradas con el equipo

| Tema | Decisión |
|---|---|
| Caminos de generación | **Los dos**: correo iniciado por el cliente, y WhatsApp iniciado por el Oferente |
| Identificación en flujo A | Nombre y mail se cargan en el dialog y la vista los muestra bloqueados |
| Identificación en flujo B | El Oferente no carga nada; el cliente completa nombre y mail en la propia vista de reseña |
| Verificación en flujo B | Obligatoria: la reseña no llega al Oferente hasta que el cliente confirma desde el correo |
| Token de verificación | **Token firmado** (misma clave que el login), sin columna nueva ni consulta a la base |
| Vencimiento de la verificación | **No vence.** La reseña sin confirmar queda pendiente indefinidamente |
| Mail mal escrito | Se puede **reenviar la verificación**, con opción de corregir la dirección |
| Armado del link de WhatsApp | Lo arma el **backend** y lo devuelve listo; el frontend solo redirige |
| Código QR | **Fuera de alcance.** Hay que actualizar RF10, que todavía lo menciona |
| Moderación | **Se mantiene** (RF10/RF11): aprobación del Oferente antes de publicar, con contador de rechazos y alerta al Administrador |
| Link del mail al Oferente | Lleva a la pantalla de la app y **requiere sesión iniciada** |
| Puntuaciones | 4 criterios (Precio, Calidad, Atención, Puntualidad), de **0.5 a 5 en pasos de 0.5** |
| Puntuación global | **Se calcula sola** como promedio de los 4 criterios |
| Comentario | **Opcional** |
| Promedio del perfil | Se **recalcula al aprobar** cada reseña |
| Prevención de abuso | **No se implementa.** Documentado como riesgo aceptado |
| Acceso para las pruebas | **Login sí, registro no.** El frontend construye solo la pantalla de login; los usuarios se cargan con POST desde la consola. El endpoint de registro queda disponible para eso, pero sin pantalla propia en este sprint |
| Validación de matrícula (HU-02) | **Simulada** vía endpoint de admin manual |
| Carga de archivos | **Simulada** con URLs, sin integrar Cloudflare |
| Logout | **Stateless**: exige token válido y responde 204, sin revocación server-side |
| Testing | pytest para los endpoints clave, además de las pruebas manuales de QA |
| Commits | Los hace el dueño del repo manualmente |

## Estado actual del código

Ya implementado y con tests en verde: modelos alineados al DER, auth completa, perfiles de Oferente con PK compartida y validaciones, categorías, administración (verificación manual de matrícula, gestión de usuarios, alertas, moderación de última instancia), seed de datos, 33 tests pytest y documentación OpenAPI.

Lo que esta redefinición **rompe**:

| Componente | Estado |
|---|---|
| `POST /oferentes/{id}/solicitudes-resena` | Pasa a público y cambia el body (flujo A). El camino autenticado se muda a un endpoint propio (flujo B) |
| `CriteriosValoracion` | Enteros 1-5 → decimales 0.5-5 con paso 0.5 |
| `ResenaCreate` | Los datos del cliente ahora son condicionales según el origen de la solicitud |
| Tests de reseñas | El helper `_generar_solicitud` y `test_generar_solicitud_no_dueno_403` quedan obsoletos |
| Seed | La solicitud de demo necesita nombre, mail y origen |

## Cambios de esquema

Tres cambios de columnas más uno de contenido. **Todos necesitan el visto bueno de la PM antes de tocar el DER.**

### `SOLICITUD_RESENA`
```python
# Reemplazan a contacto_referencia_cliente. Nullables: el flujo B crea la solicitud en blanco.
nombre_cliente = Column(String(100), nullable=True)
email_cliente  = Column(String(255), nullable=True)

# Nuevo: define si la vista bloquea los campos y si la reseña necesita verificación.
origen = Column(String(50), nullable=False)  # 'Cliente_Email' | 'Oferente_WhatsApp'
```

`intentos_rechazo` queda sin uso en este flujo; se deja la columna para no divergir del DER.

### `OFERENTE`
```python
notificaciones_email_habilitadas = Column(Boolean, nullable=False, default=True)
```

### `RESENA`
Sin cambios estructurales. Suma un valor de estado y el JSON pasa a decimales:

- Estados: `Pendiente_Verificacion` (**nuevo**) → `Pendiente_Aprobacion` → `Aprobada` / `Rechazada`
- El estado inicial depende del origen de la solicitud: flujo A arranca en `Pendiente_Aprobacion`, flujo B en `Pendiente_Verificacion`.

```json
{
  "puntuacion_global": 4.5,
  "criterios": {"precio": 4.0, "calidad": 5.0, "atencion": 4.5, "puntualidad": 4.5},
  "comentario": "Excelente trabajo, muy prolijo y llegó puntual."
}
```

`puntuacion_global` la calcula el backend como promedio de los 4 criterios, redondeado a 2 decimales; nunca llega desde el cliente. Una reseña en `Pendiente_Verificacion` no se publica, no cuenta para el promedio, no aparece en los pendientes del Oferente y no dispara ningún aviso.

El token de verificación **no necesita columna**: se firma con la clave que ya usa el login, llevando adentro el id de la reseña. Se valida por firma, sin consultar la base. Verificar dos veces es idempotente, así que no hace falta invalidarlo.

## Servicio de correo (Brevo)

Nuevo módulo `app/services/email.py`, encapsulando el envío para poder sustituirlo en tests.

- **Transporte**: API transaccional de Brevo (`POST https://api.brevo.com/v3/smtp/email`) vía `httpx`, que ya es dependencia. Evita sumar el SDK oficial por unas pocas llamadas; si el equipo prefiere el SDK, es un cambio acotado a este módulo.
- **Configuración** (nuevas variables en `.env`, ya está en `.gitignore`): `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME`, `FRONTEND_URL`. Para las pruebas se usa un mail personal como remitente. **Las credenciales las carga cada dev en su `.env`; no se comparten por chat ni se versionan.**
- **Links**: se arman desde `FRONTEND_URL` — reseña `{FRONTEND_URL}/resena/{codigo_unico}`, verificación `{FRONTEND_URL}/resena/verificar/{token}`, moderación `{FRONTEND_URL}/mis-resenas/{id_resena}`. Las rutas finales las define el equipo de frontend; se cambian en una sola variable.

Tres plantillas, con criticidad distinta:

| Correo | Cuándo | Criticidad | Manejo |
|---|---|---|---|
| Link de reseña al cliente | Flujo A, al crear la solicitud | **Crítico**: sin él no hay reseña posible | **Síncrono**. Si Brevo falla, el endpoint responde error |
| Verificación al cliente | Flujo B, al enviar la reseña | **Crítico**: sin él la reseña no avanza | **Síncrono**. Si Brevo falla, el endpoint responde error |
| Aviso al Oferente | Al llegar a `Pendiente_Aprobacion` | No crítico: la reseña ya está guardada | **Background task**. Un fallo se loguea sin romper la respuesta |

En los tests el servicio se sustituye por un doble que registra los envíos en memoria; nunca se manda correo real desde la suite.

### Mensaje de WhatsApp

Texto predefinido que arma el backend:

> ¡Hola! Soy {nombre} {apellido}. Si quedás conforme con mi trabajo, te agradezco que dejes tu reseña acá: {link}

Se devuelve como `https://wa.me/?text={texto url-encodeado}`. Sin número de teléfono, para que WhatsApp abra el selector de contactos.

## Endpoints

| Método y ruta | Cambio | Auth |
|---|---|---|
| `POST /api/v1/oferentes/{id}/solicitudes-resena` | **Modificado**: público; body `{nombre_cliente, email_cliente}`; envía el link por correo (flujo A) | Pública |
| `POST /api/v1/oferentes/{id}/solicitudes-resena/whatsapp` | **Nuevo**: sin body; devuelve `codigo_unico`, `url_resena` y `whatsapp_url` (flujo B) | Oferente dueño |
| `GET /api/v1/solicitudes-resena/{codigo_unico}` | **Nuevo**: alimenta la vista — `origen` (para saber si bloquear los campos), datos del cliente si existen, datos del oferente y estado del enlace | Pública |
| `POST /api/v1/resenas` | **Modificado**: body `{codigo_unico, calificaciones_comentarios}`, más `nombre_cliente` y `email_cliente` **solo si** el origen es WhatsApp. Según el origen deja la reseña en `Pendiente_Aprobacion` o en `Pendiente_Verificacion` + correo | Pública |
| `POST /api/v1/resenas/verificar` | **Nuevo**: body `{token}`; pasa la reseña a `Pendiente_Aprobacion` y dispara el aviso al Oferente | Pública (token firmado) |
| `POST /api/v1/solicitudes-resena/{codigo_unico}/reenviar-verificacion` | **Nuevo**: reenvía la verificación, aceptando una dirección corregida. Solo funciona mientras la reseña siga en `Pendiente_Verificacion` | Pública |
| `GET /api/v1/resenas/pendientes` | **Nuevo**: pendientes de moderación del Oferente autenticado | Oferente |
| `PATCH /api/v1/resenas/{id}/moderar` | **Modificado**: sin cambio de contrato, pero al aprobar recalcula `promedio_calificacion` | Oferente dueño |
| `PUT /api/v1/oferentes/{id}` | **Modificado**: acepta `notificaciones_email_habilitadas` | Oferente dueño |
| `GET /api/v1/oferentes/{id}/resenas` | Sin cambios (solo aprobadas) | Pública |

### Validación de las puntuaciones

```python
class CriteriosValoracion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    precio: float = Field(ge=0.5, le=5, multiple_of=0.5)
    calidad: float = Field(ge=0.5, le=5, multiple_of=0.5)
    atencion: float = Field(ge=0.5, le=5, multiple_of=0.5)
    puntualidad: float = Field(ge=0.5, le=5, multiple_of=0.5)
```

`multiple_of` viaja al esquema OpenAPI, así que frontend y QA ven la restricción de media estrella documentada sin leer el código.

## Seed de datos

Los oferentes de ejemplo se crean con `notificaciones_email_habilitadas=True`. La solicitud de demo (`DEMO-CODE-0001`) pasa a tener nombre, mail y `origen`. Conviene sumar una segunda solicitud de demo con origen WhatsApp (para poder mostrar la vista con campos editables sin depender del correo) y una reseña ya aprobada, para que en la demo el perfil muestre un promedio real y no todo en cero.

## Tests

Se ajustan los existentes (el helper de generación de solicitud pierde la autenticación) y se agregan:

**Flujo A**
- Generar solicitud sin token funciona y dispara el correo al cliente.
- Nombre o mail faltante o mal formado → 422 y no se envía ningún correo.
- La reseña enviada queda directamente en `Pendiente_Aprobacion` y avisa al Oferente.

**Flujo B**
- Generar el link de WhatsApp exige token y ser el dueño del perfil; sin token → 401, ajeno → 403.
- La respuesta trae una `whatsapp_url` válida, con el texto codificado y el link de reseña adentro.
- Enviar la reseña la deja en `Pendiente_Verificacion`, manda el correo de verificación y **no** avisa al Oferente.
- Enviar sin nombre o sin mail cuando el origen es WhatsApp → 422.
- Verificar con el token correcto pasa la reseña a `Pendiente_Aprobacion` y recién ahí avisa al Oferente.
- Token inválido o firmado con otra clave → 401; verificar dos veces es idempotente.
- Reenviar la verificación con una dirección corregida manda el correo a la nueva dirección; reenviar sobre una reseña ya verificada → error.

**Comunes**
- `GET /solicitudes-resena/{codigo}` devuelve el origen correcto y los datos bloqueados solo cuando corresponde; código inexistente → 404; ya utilizado → refleja ese estado.
- Criterios decimales válidos (ej. 4.5) → 201 y la global guardada es el promedio correcto.
- Paso inválido (ej. 0.3) o fuera de rango → 422.
- Con el toggle de notificaciones apagado no se manda el aviso al Oferente.
- Una reseña en `Pendiente_Verificacion` no aparece en el perfil público, ni en los pendientes del Oferente, ni suma al promedio.
- `GET /resenas/pendientes` devuelve solo las del Oferente autenticado y solo las que están en `Pendiente_Aprobacion`.
- Al aprobar se recalcula `promedio_calificacion` con el valor esperado.

Se conservan los tests en verde de auth, oferentes, admin, moderación y la alerta de 5 rechazos sobre 10.

## Criterios de aceptación

### HU-01 — Registrar reseña
Historia viva; T16 (réplica del Oferente) sigue diferida.

**Generación del enlace**
- Un cliente sin sesión, desde el perfil público, carga nombre y mail y recibe el link por correo.
- Nombre o mail faltante o inválido → la solicitud se rechaza y no se envía ningún correo.
- Un Oferente logueado genera un link desde su perfil y obtiene una URL de WhatsApp lista, con el texto predefinido y el link adentro.
- Un Oferente no puede generar links para el perfil de otro.

**Carga de la reseña**
- Si el enlace se originó por correo, la vista muestra nombre y mail en modo lectura.
- Si se originó por WhatsApp, la vista los pide vacíos y son obligatorios.
- Un link inexistente o ya utilizado no permite cargar una reseña.
- El cliente puntúa los 4 criterios de 0.5 a 5 en pasos de media estrella; el comentario es opcional.
- Falta un criterio, o hay un valor fuera de rango o con paso inválido → no se guarda nada.
- La puntuación global se calcula como promedio de los 4 criterios.

**Verificación y moderación**
- Reseña originada por correo → queda en `Pendiente_Aprobacion` y se avisa al Oferente.
- Reseña originada por WhatsApp → queda en `Pendiente_Verificacion`, le llega un correo de verificación al cliente y el Oferente **no** se entera todavía.
- Al confirmar desde el correo, la reseña pasa a `Pendiente_Aprobacion` y ahí sí se avisa al Oferente.
- Mientras no se verifique, la reseña no se publica, no suma al promedio y no aparece en los pendientes del Oferente.
- El cliente puede pedir que le reenvíen la verificación, corrigiendo la dirección si se equivocó.
- Si el Oferente desactivó las notificaciones no recibe el correo, pero la reseña aparece igual en su listado de pendientes.
- Solo las reseñas aprobadas se ven en el perfil público; al aprobarlas se actualiza el promedio del Oferente.
- Rechazar 5 o más de las últimas 10 genera una alerta automática al Administrador.

### HU-02 — Registrar Oferente
El backend se cierra completo en este sprint. **La pantalla de registro queda fuera**: en esta etapa los usuarios se cargan por consola y el frontend solo construye el login (ver Fase 1). La HU no se da por terminada hasta que exista esa pantalla, en un sprint posterior.

- Un usuario logueado sin perfil previo lo crea con datos válidos; su `id_oferente` coincide con su `id_usuario`.
- Campo obligatorio faltante o DNI/CUIT/teléfono con formato inválido → 422.
- DNI/CUIT duplicado, o usuario que ya tiene perfil → 409.
- La contraseña nunca se guarda en texto plano.
- Un administrador puede marcar manualmente el estado de verificación de matrícula y el perfil público lo refleja.
- El Oferente puede activar y desactivar las notificaciones por correo desde su perfil.
- La integración real con un validador externo de matrículas queda diferida.

### HU-03 — Iniciar y cerrar sesión
Se cierra completa en este sprint.

- Login con credenciales correctas y cuenta activa → devuelve un JWT.
- Credenciales incorrectas → 401 genérico, sin revelar cuál dato falló.
- Cuenta suspendida o bloqueada → 403 aunque la contraseña sea correcta.
- Endpoint protegido sin token o con token inválido → 401; con rol insuficiente → 403.
- Logout con token válido → 204.

## Mapeo de tareas de HU-01

| Tarea | Estado |
|---|---|
| T01 Iniciar el proceso de registro de reseña | Sprint 1 — **dos caminos**: cliente (correo) y Oferente (WhatsApp) |
| T02 Generación del enlace | Sprint 1 — dos endpoints, uno público y uno autenticado |
| T03 Validación del enlace | Sprint 1 — **deja de ser simulada** en los dos flujos |
| T04 Interfaz del formulario | Frontend — la vista tiene dos modos según el origen |
| T05 Campos de identificación del cliente | Sprint 1 — bloqueados en flujo A, editables y obligatorios en flujo B |
| T06 Selección de criterios | Sprint 1 — 4 criterios, 0.5 a 5 |
| T07 Comentario | Sprint 1 — opcional |
| T08 Validaciones | Sprint 1 |
| T09 Guardado en base de datos | Sprint 1 |
| T10 Integración frontend-backend | Depende del frontend; el backend deja el contrato en OpenAPI |
| T11-T14 Casos de prueba y verificación | Sprint 1 — pytest + QA manual |
| T15 Notificación al Oferente | **Entra a Sprint 1**: mail vía Brevo, desactivable |
| T16 Réplica del Oferente a una reseña | Diferida |

## Riesgos y pendientes

- **Alcance contra calendario.** Queda una semana y entran los dos flujos, la integración de Brevo, tres plantillas de correo, un estado nuevo y cinco endpoints nuevos o modificados, más las vistas del frontend. Es el riesgo más concreto del sprint. Por eso el trabajo está dividido en fases: **si el tiempo aprieta, la línea de corte natural es el final de la Fase 3**, que ya deja el flujo de reseña completo y demostrable; la Fase 4 (WhatsApp) pasaría al Sprint 2. Dentro de la Fase 4, lo primero que conviene soltar es el reenvío de verificación.
- **Brevo está en el camino crítico de los dos flujos.** Al verificar también el flujo de WhatsApp, ya no queda ningún camino demostrable sin el servicio de correo andando. Conviene resolver esa integración primero y con un mail de prueba real.
- **Límite del plan gratuito de Brevo** (300 correos diarios). Alcanza para desarrollo y demo; a tener en cuenta si QA automatiza muchas corridas contra el entorno real.
- **Reseñas sin verificar se acumulan.** Al no vencer nunca, las que el cliente nunca confirma quedan en la base indefinidamente. No molestan a nadie (son invisibles en todas las vistas), pero conviene revisarlo en un sprint futuro.
- **El endpoint de reenvío puede usarse para mandar correos a terceros.** Quien tenga el código de una solicitud puede disparar mails a direcciones arbitrarias. Está acotado a reseñas sin verificar; si se quiere cerrar, lo más barato es limitar la cantidad de reenvíos por solicitud.
- **Abuso del generador de enlaces (aceptado).** Cualquiera puede pedir un link para cualquier oferente. Se acepta como riesgo de MVP académico.
- **`fecha_expiracion` sigue sin validarse.**
- **La réplica del Oferente no tiene lugar en el DER.** Cuando se retome T16, puede resolverse como una clave dentro del JSON.
- **RF10 quedó desactualizado en dos puntos**: dice que el enlace lo genera solo el Oferente, y menciona el código QR que ahora queda fuera de alcance. Conviene que la PM lo actualice para que el documento y la implementación no se contradigan en la entrega.
- **`ON DELETE CASCADE` de Usuario→Oferente** borraría en cascada reseñas, alertas y archivos si alguna vez se agrega un borrado real de usuarios.

## Fases de implementación

Cuatro fases ordenadas por dependencia. Cada una termina en algo verificable, así que si el calendario aprieta se puede cortar al final de cualquiera de ellas y tener algo que mostrar. La Fase 3 ya alcanza para la demo del profesor: es el flujo de reseña completo de punta a punta.

### Fase 1 — Base para poder probar

Objetivo: que el equipo pueda loguearse y trabajar contra datos reales, sin depender de nada externo.

- Login funcionando y accesible desde el frontend. **No se construye pantalla de registro**: los usuarios se cargan por consola.
- Cambios de esquema: dividir el contacto y agregar `origen` en `SOLICITUD_RESENA`, `notificaciones_email_habilitadas` en `OFERENTE`, estado `Pendiente_Verificacion` en `RESENA`.
- Schemas: criterios decimales de 0.5 a 5.
- Seed actualizado: solicitudes de demo de los dos orígenes y una reseña ya aprobada, para que el perfil muestre un promedio real.
- Recrear la base local con el esquema nuevo.

**Se verifica**: login desde el frontend con un usuario seedeado, y los perfiles de prueba visibles en `GET /oferentes`.

#### Cargar usuarios por consola

El camino más rápido es `cargar_datos_prueba.bat`, que deja seis oferentes y un admin listos (contraseña `Offix2026!`). Para crear uno nuevo a mano son tres llamadas:

```bash
# 1. Crear el usuario
curl -X POST http://localhost:8000/api/v1/auth/registro \
  -H "Content-Type: application/json" \
  -d '{"email":"nuevo@offix.test","password":"Offix2026!"}'

# 2. Obtener el token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"nuevo@offix.test","password":"Offix2026!"}'

# 3. Crear el perfil profesional (pegar el access_token del paso 2)
curl -X POST http://localhost:8000/api/v1/oferentes \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"nombre":"Juan","apellido":"Pérez","dni_cuit":"20-30111222-3","telefono":"+54 3564 400111","categoria_id":1}'
```

Los usuarios administradores no se pueden crear por API (no hay endpoint de alta de admin, a propósito): salen del seed o se cargan a mano en la base.

### Fase 2 — Correo (Brevo)

Objetivo: desbloquear los dos flujos. Es el camino crítico, por eso va antes que cualquier endpoint de reseña.

- Variables de configuración y `app/services/email.py`.
- Las tres plantillas: link de reseña, verificación y aviso al Oferente.
- Doble del servicio para los tests, para que la suite nunca mande correo real.

**Se verifica**: un envío de prueba contra un mail real, comprobando que llega y que el link se arma bien desde `FRONTEND_URL`.

### Fase 3 — Flujo A: reseña por correo

Objetivo: el flujo de reseña completo y demostrable de punta a punta. **Con esto ya se cubre lo que el profesor pidió ver.**

- `POST /oferentes/{id}/solicitudes-resena` público, con envío del link por correo.
- `GET /solicitudes-resena/{codigo}` para alimentar la vista.
- `POST /resenas` dejando la reseña en `Pendiente_Aprobacion` y avisando al Oferente.
- Moderación con recálculo del promedio, `GET /resenas/pendientes` y el toggle de notificaciones en el perfil.

**Se verifica**: los pasos 3, 6 y 7 de la verificación end-to-end.

### Fase 4 — Flujo B: reseña por WhatsApp

Objetivo: el segundo camino y el cierre de la documentación.

- `POST /oferentes/{id}/solicitudes-resena/whatsapp` autenticado, devolviendo la `whatsapp_url` armada.
- `POST /resenas` diferenciando por origen: `Pendiente_Verificacion` y correo de verificación.
- `POST /resenas/verificar` con el token firmado, y el reenvío de verificación.
- Tests de los dos flujos completos y regeneración de `docs/openapi.json` y `docs/openapi.md`.

**Se verifica**: los pasos 4 y 5 de la verificación end-to-end.

## Verificación end-to-end

1. Recrear la base local y correr el seed.
2. Levantar el backend y revisar en `/docs` los contratos nuevos.
3. **Flujo A** con un mail real: pedir el link desde el perfil de un oferente, confirmar que llega el correo, que la vista abre con los datos bloqueados, enviar la reseña con medias estrellas y verificar que queda en `Pendiente_Aprobacion` y que le llega el aviso al oferente.
4. **Flujo B**: generar el link como oferente logueado, confirmar que la `whatsapp_url` abre el selector de contactos con el texto correcto, abrir el link de reseña, comprobar que los campos vienen vacíos, enviar, confirmar que queda en `Pendiente_Verificacion`, que **no** le llegó nada al oferente, y que llega el correo de verificación.
5. Hacer click en la verificación y confirmar que la reseña pasa a `Pendiente_Aprobacion` y que ahí sí le llega el aviso al oferente.
6. Desactivar las notificaciones del oferente, repetir y confirmar que no llega el correo pero la reseña aparece en `GET /resenas/pendientes`.
7. Aprobar la reseña y verificar que se publica en el perfil y que el promedio se actualizó.
8. Correr la suite de pytest completa en verde.
