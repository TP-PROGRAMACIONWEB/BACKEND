# Plan Sprint 1 — Backend Offix (HU-01, HU-02, HU-03)

> **Revisión 4 (2026-09-15)** — Llegaron las HU y los criterios de aceptación
> redefinidos, más los casos de prueba de QA para las dos HU principales. El
> cambio es grande: HU-01 pasa a tener **un solo flujo iniciado por el cliente**,
> HU-02 **deja de ser "Registrar Oferente"** y pasa a ser la validación de
> matrícula contra un padrón, y el aviso al Profesional deja de ser por correo
> para pasar a una **bandeja de notificaciones in-app**.
> Las revisiones 1 a 3 están en el historial de git.
>
> **Revisión 5 (2026-09-16)** — Cierre de la revisión de la Fase 4. Decisiones
> del equipo: la matrícula trampa del CA03 responde **al instante** (no hay
> demora real ni timeout de 60 s); los mensajes de HU-02 usan **solo los textos
> de los criterios de aceptación** (`Vencida` y `Nombre_No_Coincide` muestran el
> del CA04); y la base de producción es **PostgreSQL en Supabase**, con las
> tablas en un schema propio (`offix`) manejado **solo con migraciones**. Ver
> "Base de datos en la nube y migraciones".

## Contexto

Sprint 1 cierra el **21/09/2026** (fecha sin cambios). El mínimo que pidió el
profesor sigue siendo el mismo: base de datos creada, poblada con profesionales
de prueba, y el flujo de reseña andando de punta a punta.

Las tres HU del sprint ahora son:

| HU | Enunciado |
|---|---|
| **HU-01** | Como **Cliente**, quiero solicitar dejar una reseña a un Profesional |
| **HU-02** | Como **Oferente/Profesional**, quiero validar mi matrícula profesional |
| **HU-03** | Como **Oferente/Profesional o Administrador**, quiero iniciar y cerrar sesión |

La fuente de verdad del modelo sigue siendo el DER de la PM (`DER_Offix.sql`).
Los cambios de esquema de esta revisión están documentados aparte en
[`der-notificaciones.md`](der-notificaciones.md) para que la PM los apruebe antes
de tocar el DER.

---

## Qué cambia respecto de la revisión 3

| Tema | Revisión 3 | Revisión 4 |
|---|---|---|
| Flujos de reseña | **Dos**: cliente por mail, Oferente por WhatsApp | **Uno**: siempre lo inicia quien está en el perfil, con teléfono o mail |
| Canal de envío | Fijo por flujo | Lo define el dato cargado: teléfono → WhatsApp, mail → correo |
| Envío por WhatsApp | `wa.me/?text=` sin número (selector de contactos) | `wa.me/<número>?text=` — abre el chat del número cargado y el usuario presiona enviar |
| Verificación del cliente | Estado `Pendiente_Verificacion` + token firmado + reenvío | **Se elimina por completo**: el canal ya prueba la posesión |
| Aviso al Profesional | Correo (Brevo), desactivable | **Bandeja de notificaciones in-app** (campana) |
| Datos de contacto | Ocultos al Oferente | **Visibles**, para que pueda verificar la identidad y comunicarse |
| Moderación | Aprobar / Rechazar, sobre el contenido | Aceptar / Rechazar, sobre **la identidad del cliente** (no se ve la reseña) |
| Validación de matrícula | Simulada, manual, por el Administrador | **Automática**, iniciada por el propio Profesional, contra un padrón |
| Registrar Oferente | Era HU-02 | Sale del set de HU; el alta sigue por POST a la API |

---

## HU-01 — Solicitar y dejar una reseña

### El flujo, de punta a punta

1. Cualquiera entra al **perfil público** del Profesional (sin login) y presiona
   **"Calificar"**. El botón lo ve tanto un cliente como el propio Profesional.
2. Se abre el modal **"Datos del Cliente"** con los campos **Nombre**, **Número
   de Teléfono** y **Correo Electrónico**. El nombre es obligatorio, y de los dos
   datos de contacto hay que completar **al menos uno** (se pueden cargar los dos).
3. Al presionar **"Generar Enlace"**, el backend crea la solicitud y devuelve:
   - el `codigo_unico` y la `url_resena`;
   - si se cargó teléfono, una **`whatsapp_url`** del tipo
     `https://wa.me/<número>?text=<mensaje>` ya armada;
   - si se cargó mail, **manda el correo** con el mismo texto.

   Si se cargaron los dos, se hacen **las dos cosas**: sale el correo y además se
   redirige a WhatsApp.
4. El frontend redirige a la `whatsapp_url`: se abre el chat de WhatsApp con ese
   número y el mensaje precargado, y **el usuario presiona "enviar"**. Si el que
   generó el enlace es el propio cliente, se lo manda a sí mismo; si es el
   Profesional, se lo manda a su cliente. **No hace falta ningún servicio de
   mensajería saliente.**
5. El cliente abre el link y ve el **"Formulario de Reseña del Servicio"**, con
   nombre, teléfono y correo **precargados y bloqueados** (vacío el dato de
   contacto que no se haya cargado).
6. Puntúa las 4 características (Puntualidad, Precio, Calidad, Atención) de
   **0.5 a 5 en pasos de media estrella**, arrancando en **2.5 por defecto**, y
   opcionalmente escribe una descripción de hasta **200 caracteres**.
7. Al **Confirmar**, la reseña se guarda en `Pendiente_Aceptacion` y se crea una
   **notificación** en la bandeja del Profesional.
8. El Profesional abre la campana, ve **los datos de contacto y la fecha** (no el
   contenido de la reseña) y decide **Aceptar** o **Rechazar**.
9. Al aceptar, la reseña se publica en el perfil y se recalcula el promedio. Al
   rechazar, no se publica ni suma al promedio; si rechaza 5 o más de las últimas
   10, se genera la alerta automática al Administrador.

### Por qué se cae la verificación por correo

En la revisión 3 existía un estado `Pendiente_Verificacion` con token firmado,
para evitar que un Oferente se autogenerara reseñas buenas completando sus
propios links. Ese agujero **ya no existe**: el enlace siempre se envía al canal
de contacto que quedó registrado en la solicitud, y el Profesional ve ese contacto
antes de aceptar la reseña. La verificación de identidad la hace **él**, mirando
el teléfono o el mail (HU-01 T06). Todo el andamiaje de token, reenvío y estado
intermedio se elimina.

### Mensaje predefinido

Mismo texto para WhatsApp y para correo (definido por QA):

```
¡Hola!
Gracias por confiar en {nombre_profesional} a través de Offix.
Tu opinión nos ayuda a seguir mejorando y a que otros usuarios elijan mejor.
¿Nos dejás una reseña sobre tu experiencia con {nombre_profesional}?
Calificá tu experiencia acá: {link_reseña}
Solo te va a tomar un minuto. ¡Gracias por ser parte de Offix!
```

Para WhatsApp viaja url-encodeado dentro de `wa.me/<número>?text=`. Para correo va
dentro de la plantilla HTML ya existente en `app/services/email.py`, que hay que
reemplazar por este texto.

**Normalización del teléfono**: `wa.me` exige el número en formato internacional
sin símbolos ni separadores. El backend recibe los **10 dígitos** que cargó el
usuario, le saca el guión si lo trae y le antepone el prefijo argentino de móvil
(`549`):

| Lo que carga el usuario | Lo que se guarda | Lo que va en `wa.me` |
|---|---|---|
| `351-6924551` | `3516924551` | `5493516924551` |
| `3564-692755` | `3564692755` | `5493564692755` |

El prefijo sale de configuración para no dejarlo hardcodeado. Se rechaza el `0`
inicial, el `15` y el `+54`: el usuario carga código de área y línea, nada más.

### Reglas de negocio de HU-01

| Regla | Definición |
|---|---|
| Acceso | Todo el flujo es **público**. Ni generar el enlace ni dejar la reseña requieren login |
| Nombre del cliente | **Obligatorio.** Se carga en el modal y se muestra bloqueado en la vista de reseña |
| Datos de contacto | **Al menos uno** de teléfono o correo; se pueden cargar los dos y entonces se usan los dos canales. Ninguno de los dos → 422 |
| Formato de teléfono | **10 dígitos** en total: 3 o 4 de código de área + 7 o 6 de línea (`351-6924551`, `3564-692755`). Se acepta el guión como separador, sin `0` ni `15` ni `+54` |
| Formato de correo | **Validación estándar de email** (formato RFC): exige `@` y dominio válido, sin espacios. Acepta `.com.ar`, `.edu.ar` y cualquier TLD real |
| Reusabilidad del enlace | **Un solo uso.** Al enviarse la reseña, la solicitud pasa a `Utilizada` |
| Vencimiento del enlace | **7 días** desde la generación. Vencido, la vista no permite cargar la reseña |
| Criterios | Puntualidad, Precio, Calidad, Atención. `0.5` a `5`, paso `0.5`, default `2.5` |
| Promedio general | Lo calcula el backend como promedio de los 4 criterios, redondeado a 2 decimales. Nunca llega desde el cliente |
| Descripción | Opcional, **máximo 200 caracteres** |
| Contenido de la notificación | Datos de contacto + fecha y hora de creación. **Nunca** el contenido de la reseña |
| Fecha de la notificación | La de creación de la reseña por el cliente, **no** la de la moderación |
| Visibilidad pública | Solo las reseñas aceptadas se ven en el perfil y suman al promedio |
| Alerta al Administrador | Se mantiene: 5 o más rechazos de las últimas 10 |

---

## HU-02 — Validar la matrícula profesional

Reemplaza por completo a la HU-02 anterior ("Registrar Oferente"), y convierte en
real lo que la revisión 3 dejaba simulado con un endpoint de administrador.

### El flujo

1. El Profesional, **logueado**, entra a su perfil y ve el bloque de fidelización:
   un selector **Tipo de profesional** con dos opciones (**Aire acondicionado** y
   **Gasista**, por defecto la primera en orden alfabético, sin opción vacía) y un
   input **Número de matrícula**.
2. El botón **Confirmar** arranca deshabilitado y se habilita recién con los dos
   datos completos y con la cantidad de dígitos correcta.
3. Al confirmar, el backend busca el número en el **padrón** del tipo elegido y
   responde de forma **síncrona**.
4. Según el resultado, el frontend muestra la notificación correspondiente y el
   perfil queda con o sin el distintivo de verificado.

### Padrón de matriculados

El padrón son **archivos `.md`** provistos por el equipo, uno por tipo de
profesional, versionados en `app/db/padrones/`. Se cargan a la base con el seed y
la consulta se hace contra la tabla, no leyendo el archivo en cada request.

| Archivo | Tipo | Estado |
|---|---|---|
| `app/db/padrones/gasistas.md` | Gasista | **Cargado** — 68 matriculados |
| `app/db/padrones/aire-acondicionado.md` | Aire acondicionado | ⚠ **Falta.** Ver pregunta abierta #1 |

#### Formato del archivo

Tabla markdown con seis columnas, exportada de un PDF. El encabezado viene
**malformado** y hay que parsear por posición, no por nombre de columna:

```
|NOMBRE|TELÉFONO||MATRÍCULA|CATEGORÍA VENCIMIENTO||
|---|---|---|---|---|---|
|ALESSI MARIA CLARA|3564-632881|PUEYRREDON 1677, SAN FRANCISCO|1000008919|Primera|31/03/2027|
```

| Posición | Contenido | Uso |
|---|---|---|
| 0 | Nombre y apellido | Se guarda |
| 1 | Teléfono | Se ignora |
| 2 | Dirección (sin encabezado propio) | Se ignora |
| 3 | **Número de matrícula** | **Clave de búsqueda** |
| 4 | Categoría (Primera / Segunda / Tercera) | Se guarda |
| 5 | Vencimiento (`DD/MM/AAAA`) | Se guarda |

Las 68 matrículas del padrón de Gasistas son de **10 dígitos** y arrancan con
`10000` (rango `1000000524`–`1000009803`), consistente con lo que pide el CA01.

#### Filas sucias del export

El PDF de origen desbordó algunos campos. El parser tiene que tolerarlas sin
romper, quedándose siempre con la **columna 3**:

- `GONZALEZ MARIA LAURA` trae dos teléfonos, dos categorías y dos vencimientos en
  la misma celda, con una sola matrícula.
- `PEVERENGO ERICA` tiene parte de la dirección metida dentro del campo teléfono.
- `ROMERO TATIANA` trae el teléfono con un `0` inicial.
- Varias direcciones están desordenadas ("A FRANCISCO V.ROSARIO DE SANTA FE...").
- La primera línea del archivo es un encabezado suelto con etiquetas HTML (`<u>`),
  que hay que descartar.

Ninguna de esas anomalías afecta la columna de matrícula, así que se cargan igual.

#### Coincidencia de nombre

No alcanza con que el número exista: el nombre del perfil tiene que coincidir en
al menos un **90 %** con el del padrón. Eso cierra el agujero de que cualquiera
copie un número del listado público y se fidelice con la matrícula de otro.

La comparación **no puede ser literal**, porque los dos lados están escritos
distinto:

| Origen | Cómo viene | Ejemplo |
|---|---|---|
| Padrón | `APELLIDO NOMBRE(S)`, en mayúsculas, con segundo nombre | `ALESSI MARIA CLARA` |
| Perfil | Campos separados `nombre` y `apellido`, con acentos | `María` + `Alessi` |

Comparar `"MARIA ALESSI"` contra `"ALESSI MARIA CLARA"` carácter a carácter da
bastante menos de 90 %, así que rechazaría a la persona correcta. El algoritmo es:

1. **Normalizar** los dos lados: pasar a mayúsculas, sacar acentos, sacar
   puntuación y colapsar espacios.
2. **Tokenizar** en palabras y comparar como **conjuntos**, no como cadenas: el
   orden no importa y los nombres de más que trae el padrón no penalizan.
3. Exigir que **cada token del perfil** tenga su par en el padrón con una
   similitud de al menos 90 % (`difflib.SequenceMatcher`, de la biblioteca
   estándar — no hace falta sumar una dependencia).

Con ese criterio `María Alessi` matchea `ALESSI MARIA CLARA`, y una diferencia de
una letra por tipeo (`ALESI`) también pasa, pero un apellido distinto no.

> **Impacto en el seed**: los oferentes de demo actuales (Juan Pérez, María Gómez,
> etc.) son nombres inventados y **ninguno existe en el padrón**, así que no
> podrían fidelizarse. El Gasista de demo tiene que pasar a llamarse como alguien
> del listado real.

#### Vencimiento

El padrón trae la fecha de vencimiento en la última columna. Una matrícula que
existe pero está **vencida se trata como inválida**: no se fideliza y el perfil no
se modifica. Se muestra el mensaje del CA04 (ver "Resultados y mensajes").

#### Matrícula reservada para probar el timeout (CA03)

El padrón vive en la base, así que la consulta responde en milisegundos y un
timeout **nunca se dispararía solo**. Para que QA pueda ejecutar el CA03, se
reserva una matrícula trampa por tipo, que **no existe en el padrón real** y que
el backend intercepta antes de consultar, devolviendo `Timeout` **al instante**.
Por decisión del equipo no se simula ninguna demora: es lo más cómodo para QA, y
en el backend no existe un timeout real de 60 segundos.

| Tipo de profesional | Matrícula trampa | Dígitos |
|---|---|---|
| Gasista | `9999999999` | 10 |
| Aire acondicionado | `999999999` | 9 |

Respetan la cantidad de dígitos que exige cada tipo, así que el botón *Confirmar*
se habilita normalmente y el caso de prueba recorre el mismo camino que uno real.
No colisionan con ninguna matrícula del padrón, que arrancan todas con `10000`.

**Para QA**: usar ese número en lugar de "simular/forzar que la respuesta demore
más de 5 minutos". Conviene dejarlo asentado en el campo *Observaciones* del caso
de prueba. El comportamiento se desactiva con `MATRICULA_TRAP_HABILITADA=false`
para que no quede disponible en un entorno productivo.

### Reglas de negocio de HU-02

| Regla | Definición |
|---|---|
| Tipos válidos | `Aire acondicionado` y `Gasista`, únicamente |
| Longitud del número | **9 dígitos** para Aire acondicionado, **10 dígitos** para Gasista |
| Formato | Solo dígitos. Cualquier carácter alfabético se rechaza |
| Relación con la categoría del perfil | **Independiente.** Un Profesional puede tener más de un oficio, así que el tipo de matrícula no tiene que coincidir con su categoría |
| Identidad | Se valida **el número Y el nombre**: el número tiene que existir en el padrón y el nombre del perfil tiene que coincidir en al menos un **90 %** con el del padrón. Ver "Coincidencia de nombre" |
| Vencimiento | Una matrícula **vencida se considera inválida**, aunque exista en el padrón |
| Cantidad de matrículas | Más de una por Profesional (una por oficio) |
| Tiempo de espera | Sin timeout real: la consulta es local. El resultado `Timeout` solo se obtiene con la matrícula trampa, que responde al instante |
| Historial | Se guardan **todos** los intentos, incluidos los fallidos |
| Revalidación de la misma matrícula | No se modifica nada; se informa "ya fidelizada" |
| Reemplazo por otra matrícula | Genera una **solicitud de autorización al Administrador**; no se aplica hasta que la autorice. Mientras tanto **sigue vigente la matrícula vieja**: el Profesional conserva el ícono de verificado y el perfil no se modifica |
| Distintivo del perfil | El ícono de verificado aparece cuando el Profesional tiene al menos una matrícula validada, y persiste entre sesiones |

### Resultados y mensajes

Los textos los define el criterio de aceptación y QA los verifica literales. El
backend devuelve un **código de resultado** y el frontend renderiza el mensaje.

| Resultado | Mensaje | CA |
|---|---|---|
| `Validada` | "Su matrícula fue fidelizada exitosamente" | CA05 |
| `No_Encontrada` | "Su matrícula no fue encontrada en el padrón, revise los datos y vuelva a intentarlo" | CA04 |
| `Timeout` | "No pudimos procesar tu validación en este momento, intentá nuevamente más tarde" | CA03 |
| `Ya_Fidelizada` | "Su matrícula ya fue fidelizada" | CA06 |
| `Vencida` | "Su matrícula no fue encontrada en el padrón, revise los datos y vuelva a intentarlo" | CA04 (reusado) |
| `Nombre_No_Coincide` | "Su matrícula no fue encontrada en el padrón, revise los datos y vuelva a intentarlo" | CA04 (reusado) |
| `Reemplazo_Solicitado` | *Provisorio, sin CA* — ver pregunta abierta #2 | — |

`Vencida` y `Nombre_No_Coincide` muestran el texto del CA04 por decisión del
equipo, para no usar textos que QA no tiene. El `resultado` sigue siendo
distinto, así que el historial conserva el motivo real del rechazo.

Las cinco notificaciones **quedan guardadas en la campana** hasta que el
Profesional las abre; recién ahí pasan a `Leida`. No son toasts efímeros.

> ⚠ **El CA03 dice 5 minutos, pero no hay demora real**: el resultado se obtiene
> con la matrícula trampa, al instante. Hay que corregir el caso de prueba de QA,
> que hoy dice "simular/forzar que la respuesta demore más de 5 minutos".

---

## HU-03 — Iniciar y cerrar sesión

**Sin cambios.** Ya está implementada, con tests en verde: login con JWT, rol en
el claim, 401 genérico ante credenciales inválidas, 403 con cuenta suspendida o
bloqueada, y logout stateless con 204.

El registro de usuarios **sale del set de HU**. Se mantiene `POST /auth/registro`
como herramienta de carga (POST directo contra la API); a futuro el alta se hará
con la API de Google, fuera del alcance de este sprint.

---

## Estado actual del código y qué se rompe

Están cerradas las Fases 1 y 2 del plan anterior: auth completa, perfiles de
Oferente con PK compartida, categorías, administración, moderación con alerta de
5 sobre 10, seed, servicio de correo Brevo con sus plantillas y su doble para
tests, y 50 tests en verde.

Esta redefinición **rompe** lo siguiente:

| Componente | Qué pasa |
|---|---|
| `POST /oferentes/{id}/solicitudes-resena` | Pasa a **público**, recibe teléfono y/o mail, y devuelve la `whatsapp_url` y/o manda el correo |
| Endpoint de WhatsApp del Oferente | **No se implementa.** El flujo B desaparece |
| `RESENA.estado = Pendiente_Verificacion` | **Se elimina** junto con el token firmado, `/resenas/verificar` y el reenvío |
| `OFERENTE.notificaciones_email_habilitadas` | **Se elimina.** El aviso ya no es por correo |
| `ResenaCreate` | Los datos del cliente ya no viajan en el body: salen de la solicitud |
| `ResenaOut` | Debe **exponer** el contacto del cliente al Oferente dueño |
| Plantillas de correo | Queda una sola (link de reseña) y con el texto nuevo de QA. Las de verificación y aviso al Oferente se eliminan |
| `CalificacionesComentariosIn.comentario` | `max_length` de 1000 → **200** |
| `PATCH /admin/oferentes/{id}/verificacion` | Deja de ser el camino principal; queda como override manual del Administrador |
| Tests de reseñas | Los que asumen solicitud autenticada y los datos del cliente en el body quedan obsoletos |
| Seed | Las solicitudes de demo cambian de forma; hay que sumar los padrones de matrículas |

**Lo bueno**: la puntuación de `0.5` a `5` en pasos de `0.5` ya está implementada
tal cual la pide el caso de prueba, así que ese schema no se toca.

---

## Cambios de esquema

**Todos necesitan el visto bueno de la PM antes de tocar el DER.** El detalle
completo de la tabla nueva está en [`der-notificaciones.md`](der-notificaciones.md).

### Tabla nueva: `NOTIFICACION`

Ver documento aparte. Resumen: destinatario (`USUARIO`), tipo, mensaje, estado
(`Pendiente` / `Aceptada` / `Rechazada` / `Leida`), `requiere_accion`, FK opcional
a `RESENA`, fecha de creación y de resolución.

### `SOLICITUD_RESENA`

```python
# Nuevo: el canal de envío depende de qué cargó el usuario.
telefono_cliente = Column(String(20), nullable=True)
email_cliente    = Column(String(255), nullable=True)

# 'WhatsApp' | 'Email' | 'Ambos' — reemplaza el significado anterior de origen,
# que era "quién generó el link".
origen = Column(String(50), nullable=False)

# Se empieza a validar: 7 días desde la generación.
fecha_expiracion = Column(DateTime(timezone=True), nullable=False)
```

`nombre_cliente` pasa a `nullable=False`: ahora siempre se carga en el modal, en
los dos canales. `intentos_rechazo` sigue sin uso; se deja para no divergir del
DER.

### `OFERENTE`

```python
# Se elimina: el aviso pasa a la bandeja in-app.
- notificaciones_email_habilitadas
```

### `RESENA`

```python
# Se elimina el estado intermedio: ya no hay verificación por correo.
- PENDIENTE_VERIFICACION

# Se renombran para alinearse con el vocabulario de la UI y de QA
# (los botones dicen Aceptar / Rechazar, no Aprobar).
- PENDIENTE_APROBACION  -> PENDIENTE_ACEPTACION
- APROBADA              -> ACEPTADA
```

Estados finales: `Pendiente_Aceptacion` → `Aceptada` / `Rechazada`.

El renombre toca el enum, el seed y los tests existentes, y **necesita el aval de
la PM** porque cambia el vocabulario del DER.

### Tablas de HU-02 (a proponer)

`MATRICULA` (varias por Oferente, con tipo, número y estado) y
`VALIDACION_MATRICULA` (historial de intentos con su resultado), más el padrón
cargado. Se documentan en un anexo propio una vez confirmado el formato de los
`.md` del padrón.

---

## Base de datos en la nube y migraciones

La base de producción es **PostgreSQL en Supabase**. SQLite queda como variante
local para desarrollo y pruebas, y es la que se usa si no hay `.env`. La suite de
pytest corre **siempre** sobre SQLite en memoria, aunque el `.env` apunte a la
nube.

### Schema propio: `offix`

El schema `public` de Supabase ya tenía materializado el DER original de la PM
(anterior a la revisión 4, con nombres en singular). No se toca: todas las tablas
del backend viven en un schema aparte, **`offix`**, configurable con
`DATABASE_SCHEMA`.

### Cada cambio de base es una migración

El schema `offix` se crea y se modifica **solo con migraciones de Alembic**
(`migrations/`). En Postgres el backend no ejecuta `create_all` al arrancar; en
SQLite sí, porque ahí no se migra.

Para hacer un cambio de esquema:

1. Modificar los modelos en `app/models/`.
2. Generar la migración: `alembic revision --autogenerate -m "descripcion"`,
   con el `.env` apuntando a la nube.
3. **Revisar el archivo generado** en `migrations/versions/` antes de aplicarlo.
4. Aplicarla con `migrar_bd.bat`, o `alembic upgrade head`.
5. Commitear el modelo y la migración juntos.

El autogenerate está limitado al schema `offix`: nunca propone cambios sobre
`public`. `alembic upgrade head --sql` exporta el SQL sin conectarse, útil para
que la PM lo revise antes de aplicarlo. `alembic check` confirma que los modelos
y la base coinciden.

---

## Endpoints

### HU-01

| Método y ruta | Cambio | Auth |
|---|---|---|
| `POST /api/v1/oferentes/{id}/solicitudes-resena` | **Modificado**: público; body `{telefono_cliente?, email_cliente?}`; devuelve `codigo_unico`, `url_resena` y `whatsapp_url`; manda el correo si corresponde | Pública |
| `GET /api/v1/solicitudes-resena/{codigo_unico}` | **Nuevo**: alimenta la vista con los datos precargados, el estado del enlace y si está vencido | Pública |
| `POST /api/v1/resenas` | **Modificado**: body `{codigo_unico, calificaciones_comentarios}`. Los datos del cliente ya no viajan. Crea la reseña en `Pendiente_Aceptacion` y la notificación | Pública |
| `GET /api/v1/oferentes/{id}/resenas` | Sin cambios (solo aprobadas) | Pública |
| `PATCH /api/v1/resenas/{id}/moderar` | **Modificado**: al aceptar recalcula el promedio, y en la misma transacción resuelve la notificación asociada | Oferente dueño |

### Bandeja de notificaciones

| Método y ruta | Descripción | Auth |
|---|---|---|
| `GET /api/v1/notificaciones` | Bandeja del usuario autenticado, más recientes primero | Oferente / Admin |
| `GET /api/v1/notificaciones/contador` | Cantidad de pendientes, para el badge de la campana | Oferente / Admin |
| `PATCH /api/v1/notificaciones/{id}/leer` | Marca como leída una notificación informativa | Destinatario |

### HU-02

| Método y ruta | Descripción | Auth |
|---|---|---|
| `POST /api/v1/oferentes/me/matriculas/validaciones` | Solicita la validación; body `{tipo_profesional, numero_matricula}`. Síncrono. Devuelve el código de resultado (`Timeout` solo con la matrícula trampa) | Oferente |
| `GET /api/v1/oferentes/me/matriculas` | Matrículas del Profesional y su estado | Oferente |
| `GET /api/v1/oferentes/me/matriculas/validaciones` | Historial de intentos | Oferente |
| `PATCH /api/v1/admin/matriculas/reemplazos/{id}` | El Administrador autoriza o deniega un reemplazo de matrícula | Admin |
| `PATCH /api/v1/admin/oferentes/{id}/verificacion` | Se mantiene como override manual | Admin |

---

## Validación de las puntuaciones

Sin cambios respecto de la revisión 3 — ya coincide con el caso de prueba.

```python
class CriteriosValoracion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    precio: float = Field(ge=0.5, le=5, multiple_of=0.5)
    calidad: float = Field(ge=0.5, le=5, multiple_of=0.5)
    atencion: float = Field(ge=0.5, le=5, multiple_of=0.5)
    puntualidad: float = Field(ge=0.5, le=5, multiple_of=0.5)
```

El valor por defecto de `2.5` lo renderiza el frontend; el backend no asume nada,
exige los 4 criterios explícitos.

---

## Servicio de correo (Brevo)

Se mantiene el módulo `app/services/email.py` ya implementado, con dos podas:

- **Queda una sola plantilla**: el link de reseña, con el texto nuevo de QA.
- **Se eliminan** `enviar_verificacion_resena` (ya no hay verificación) y
  `enviar_aviso_resena_nueva` (el aviso pasa a la bandeja in-app).

El correo sigue siendo **síncrono y crítico** en el camino del mail: si Brevo
falla, el endpoint de generación responde error. La diferencia con la revisión 3
es que **ahora existe un camino sin correo**: si el usuario carga solo teléfono,
Brevo no interviene. Eso reduce bastante el riesgo de bloqueo.

---

## Configuración nueva

```bash
# Prefijo internacional para armar el link de wa.me (Argentina móvil).
WHATSAPP_PREFIJO_PAIS=549

# Vencimiento del enlace de reseña.
SOLICITUD_RESENA_DIAS_VALIDEZ=7

# Matrícula trampa del CA03 de HU-02. Poner en false en producción.
MATRICULA_TRAP_HABILITADA=true

# Base de datos: SQLite local para pruebas, o la URI de Supabase para la nube.
DATABASE_URL=sqlite:///./offix_dev.db
# Schema de Postgres donde viven las tablas del backend (no aplica a SQLite).
DATABASE_SCHEMA=offix
```

---

## Seed de datos

- Se eliminan las solicitudes de demo con verificación; quedan dos, una por canal
  (teléfono y correo), más una reseña ya aceptada para que el perfil muestre un
  promedio real.
- Se cargan los **padrones de matrículas** desde los `.md` de `app/db/padrones/`,
  descartando el encabezado suelto y tolerando las filas con campos desbordados.
  Con eso quedan disponibles todos los resultados de HU-02, incluida la matrícula
  trampa del timeout.
- El Gasista de demo pasa a llamarse como alguien del padrón real, para que pueda
  fidelizarse: con los nombres inventados actuales el match de nombre lo rechaza.
- Se suma al menos una **notificación pendiente** en la bandeja de un Oferente de
  demo, para poder mostrar la campana con contador sin tener que generar una
  reseña primero.

---

## Tests

Se ajustan los existentes y se agregan:

**HU-01 — generación del enlace**
- Sin token funciona (el endpoint es público).
- Solo teléfono → devuelve `whatsapp_url` bien armada y **no** manda correo.
- Solo mail → manda el correo con el texto de QA y **no** devuelve `whatsapp_url`.
- Sin ningún dato de contacto → 422 y no se envía nada.
- Teléfono con caracteres no numéricos → 422.
- El teléfono se normaliza al formato internacional dentro de la `whatsapp_url`.

**HU-01 — carga de la reseña**
- `GET /solicitudes-resena/{codigo}` devuelve los datos precargados; código
  inexistente → 404; ya utilizado o **vencido** → refleja ese estado.
- Enlace vencido (más de 7 días) → no se puede cargar la reseña.
- Criterios de media estrella válidos → 201 y promedio correcto.
- Paso inválido, fuera de rango o criterio faltante → 422.
- Descripción de más de 200 caracteres → 422; sin descripción → 201.

**HU-01 — notificación y moderación**
- Al crear la reseña se crea la notificación `Resena_Nueva` en `Pendiente`.
- El contador de la campana solo cuenta las pendientes del usuario autenticado.
- La notificación **no** expone el contenido de la reseña, y **sí** el contacto.
- La fecha de la notificación es la de creación de la reseña.
- Aceptar → reseña aprobada, publicada, promedio recalculado y notificación en
  `Aceptada`.
- Rechazar → reseña rechazada, no publicada, no suma al promedio, notificación en
  `Rechazada`.
- Se conserva la alerta al Administrador con 5 rechazos de las últimas 10.

**HU-02**
- Número con la cantidad de dígitos equivocada para el tipo → 422.
- Número con caracteres alfabéticos → 422.
- Matrícula existente en el padrón → `Validada`, se guarda y el perfil queda
  verificado.
- Matrícula inexistente → `No_Encontrada`, el perfil no se modifica.
- Misma matrícula ya fidelizada → `Ya_Fidelizada`, sin modificaciones.
- Matrícula distinta sobre un tipo ya fidelizado → `Reemplazo_Solicitado` y
  notificación al Administrador.
- Todos los intentos quedan en el historial, los fallidos también.
- Un Profesional puede fidelizar dos tipos distintos.

**HU-03**
- Se conservan en verde todos los tests de auth.

---

## Riesgos y pendientes

- **Alcance contra calendario.** Queda menos de una semana y entran: el flujo de
  reseña rehecho, la bandeja de notificaciones (tabla nueva, tres endpoints,
  frontend con campana y contador), y HU-02 entera con padrón, historial y
  autorización de reemplazos. **La línea de corte natural es el final de la
  Fase 3**, que ya deja HU-01 completa y demostrable; HU-02 pasaría a Sprint 2.
- **El envío por WhatsApp depende de una acción manual.** El mensaje no sale
  solo: alguien tiene que presionar "enviar" en WhatsApp. Es lo que permite no
  contratar un servicio de mensajería, pero conviene que quede explícito en la
  demo para que no se lea como un bug.
- **Cualquiera puede generar un enlace para cualquier Profesional.** Se acepta
  como riesgo de MVP académico, igual que en la revisión 3. La diferencia es que
  ahora el Profesional ve el contacto antes de aceptar, así que tiene con qué
  filtrar.
- **El contacto del cliente queda visible para el Profesional.** Es una decisión
  explícita del equipo (abre un canal de comunicación), pero conviene dejarlo
  asentado como dato personal expuesto.
- **El match de nombre al 90 % puede dar falsos negativos.** Cierra el agujero de
  apropiación de matrículas ajenas, pero un apellido compuesto o un error de carga
  en el perfil puede dejar afuera a una persona legítima. El override manual del
  Administrador queda como vía de escape.
- **Falta el padrón de Aire acondicionado**, así que la mitad de HU-02 no es
  demostrable todavía.
- **El renombre de `Aprobada` a `Aceptada` toca el DER.** Está decidido, pero
  depende del aval de la PM; si no llega a tiempo, el código queda con un
  vocabulario y QA con otro.
- **RF10 sigue desactualizado**: menciona el código QR (fuera de alcance) y dice
  que el enlace lo genera solo el Oferente. Con esta revisión también hay que
  corregir que el aviso al Profesional ya no es por correo.
- **`ON DELETE CASCADE` de Usuario→Oferente** borraría en cascada reseñas,
  alertas, notificaciones y archivos si alguna vez se agrega un borrado real.

---

## Fases de implementación

Cuatro fases ordenadas por dependencia. Cada una termina en algo verificable.

### Fase 1 — Poda y esquema

Objetivo: dejar la base alineada al modelo nuevo antes de escribir endpoints.

- Eliminar el estado `Pendiente_Verificacion`, el toggle de notificaciones por
  correo y las dos plantillas de correo que ya no van.
- `SOLICITUD_RESENA`: `telefono_cliente`, `origen` con el significado nuevo,
  `fecha_expiracion` obligatoria.
- Tabla `NOTIFICACION` (modelo + creación del esquema).
- `comentario` a 200 caracteres.
- Recrear la base local y actualizar el seed.

**Se verifica**: la suite existente pasa, ya sin los tests obsoletos, y el
esquema nuevo se crea limpio.

### Fase 2 — Generación y envío del enlace

- `POST /oferentes/{id}/solicitudes-resena` público, con las validaciones de
  teléfono y correo, la `whatsapp_url` armada y el envío por Brevo.
- Texto del mensaje unificado para los dos canales.
- `GET /solicitudes-resena/{codigo}` con estado y vencimiento.

**Se verifica**: generar un enlace con un teléfono real, abrir la `whatsapp_url`
en el celular y comprobar que el chat se abre con el mensaje precargado; y
generar uno con un mail real y comprobar que llega.

### Fase 3 — Reseña y bandeja de notificaciones

Objetivo: **HU-01 completa y demostrable. Con esto ya se cubre lo que pidió el
profesor.**

- `POST /resenas` tomando los datos de la solicitud, con validación de
  vencimiento y de un solo uso.
- Creación de la notificación al Profesional.
- `GET /notificaciones`, `GET /notificaciones/contador`, resolución desde la
  bandeja con recálculo del promedio y la alerta de 5 sobre 10.

**Se verifica**: los pasos 2 a 5 de la verificación end-to-end.

### Fase 4 — HU-02: validación de matrícula

> **Hecha, con alcance reducido a Gasista** (ver pregunta abierta #1): el
> padrón de Aire acondicionado no llegó a tiempo, así que ese tipo queda
> soportado por el código pero sin matrículas cargadas.

- Carga de los padrones desde los `.md`, tablas `MATRICULA` y
  `VALIDACION_MATRICULA`.
- Endpoint de validación síncrono con los siete resultados (los cinco de QA más
  `Vencida` y `Nombre_No_Coincide`). `Timeout` se obtiene con la matrícula
  trampa, al instante.
- Autorización de reemplazo por el Administrador, con su notificación.
- Regeneración de `docs/openapi.json` y `docs/openapi.md`.

**Se verifica**: los pasos 6 y 7 de la verificación end-to-end.

---

## Verificación end-to-end

1. Recrear la base local y correr el seed.
2. Desde el perfil público de un Oferente, generar un enlace con un teléfono real:
   comprobar que se abre el chat de WhatsApp con el mensaje y el link correctos.
3. Repetir con un correo real y comprobar que llega con el mismo texto.
4. Abrir el link: los datos de contacto vienen precargados y bloqueados, los 4
   criterios arrancan en 2.5 y el promedio general se actualiza solo.
5. Enviar la reseña: aparece la campana con el contador en 1 en la cuenta del
   Oferente, mostrando el contacto y la fecha, sin el contenido de la reseña.
6. Aceptarla: se publica en el perfil y el promedio se actualiza. Rechazar otra y
   comprobar que no impacta el promedio.
7. Como Profesional logueado, fidelizar una matrícula de cada tipo y comprobar los
   cuatro resultados posibles y el ícono de verificado.
8. Correr la suite de pytest completa en verde.

---

## Preguntas abiertas

1. **🔴 Padrón de Aire acondicionado.** Sigue sin llegar. La Fase 4 se
   implementó y quedó demostrable **solo con Gasista**
   (`app/db/padrones/gasistas.md`, 68 matriculados de 10 dígitos); el tipo
   `Aire acondicionado` ya está soportado en el código (formato de 9 dígitos,
   matrícula trampa `999999999`), así que cuando llegue el archivo real se
   carga desde `app/db/seed.py` sin tocar nada más. **Cuando aparezca, hay que
   confirmar que sus matrículas sean de 9 dígitos**: si también son de 10, el
   CA01 está mal escrito.
2. **Textos de notificación sin CA — resuelto en parte.** Se decidió usar solo
   textos de los criterios de aceptación: matrícula **vencida** y **nombre que no
   coincide** muestran el del CA04. Siguen abiertos los dos que **ningún CA puede
   cubrir**, porque ninguno describe un pedido esperando al Administrador:
   - reemplazo **pendiente** de autorización;
   - reemplazo **resuelto** (autorizado o denegado).

   Hoy tienen un texto provisorio en `app/services/matriculas.py`
   (`MENSAJES_RESULTADO` y `resolver_reemplazo`). Hay que pedírselos a QA/PM.
3. **Contador de la campana.** Los casos de prueba dicen que el badge muestra "las
   notificaciones pendientes de rechazo/aceptación". Pero las informativas de
   matrícula también quedan guardadas hasta visualizarse. ¿El número las cuenta a
   todas, o solo a las que esperan una decisión? Sigue sin definirse:
   `GET /notificaciones/contador` devuelve las dos cifras
   (`pendientes_de_accion` y `sin_leer`) para no bloquearse en esto.

## Correcciones a pedir sobre la documentación existente

Definiciones ya cerradas por el equipo que **contradicen** lo que hoy dicen los
mockups, los criterios de aceptación o los casos de prueba. Hay que corregir esos
documentos antes de que QA empiece a ejecutar, o van a marcar fallas que no lo son.

| Documento | Qué dice hoy | Qué corresponde |
|---|---|---|
| Mockup y caso de prueba de HU-01 CA1 | El modal tiene solo Teléfono y Correo | Sumar el input **Nombre**, obligatorio |
| Caso de prueba de HU-01 CA1 | El correo debe terminar en `.com` | Validación estándar de email; se aceptan `.com.ar`, `.edu.ar`, etc. |
| Casos de prueba de HU-01 CA4 | La reseña pasa a estado "Aceptada" | Correcto, pero hay que actualizar el **DER**, que dice `Aprobada` |
| CA03 de HU-02 y su caso de prueba | Timeout a los **5 minutos**, "simular/forzar" la demora | Sin demora: usar la matrícula trampa `9999999999` (Gasista) o `999999999` (Aire acondicionado), que responde `Timeout` al instante |
| RF10 | Menciona el código QR y dice que el enlace lo genera solo el Oferente | Sin QR; el enlace lo genera cualquiera desde el perfil público. El aviso al Profesional ya no es por correo |
