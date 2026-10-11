# Plan Sprint 2 — Backend Offix (HU-01 v1.2, HU-04)

> **Revisión 1 (2026-10-05)** — Primera versión, armada a partir de las HU
> entregadas, el Excel `Casos_de_Prueba_Offix.xlsx` (hojas *US-Reseña* y *US
> Registro Oferente*) y el estado del código al commit `1ea44a7`. Las decisiones
> marcadas como **[Decidido]** quedaron cerradas con el equipo en esta revisión;
> las marcadas **[A validar con QA/PM]** son correcciones que hay que pedir sobre
> la documentación existente antes de que QA ejecute.
>
> **Revisión 2 (2026-10-11)** — QA actualizó el Excel
> (`Casos_de_Prueba_Offix (1).xlsx`). Cambian solo cuatro casos de *US Registro
> Oferente*, todos de trabajos realizados: **A46** (contador de fotos "X/5" en
> el modal), **A47** (con 5 trabajos se oculta "Cargar nuevo trabajo"), **A50**
> (la tarjeta muestra solo la **primera foto cargada**) y **A51** (el detalle
> muestra **todas las fotos en carrusel**). Impacto en el backend: las fotos de
> un trabajo pasan a tener **orden** (columna `orden`), la salida de trabajos
> expone la foto principal y la lista ordenada, y el perfil expone el cupo de
> trabajos y de fotos para que el frontend oculte el botón. Ver "Reglas de
> trabajos realizados".

## Estado de la implementación (2026-10-11)

**Hecho** (sin commits, todo en el árbol de trabajo):

- **Fase 1** — migración `5e1c2a9b7d30` (única cabeza de Alembic), normalización de
  DNI/teléfono/días/horarios en SQL, handler 422 con `errores[]`, validadores
  (DNI/CUIT con módulo 11, teléfono, horarios en medias horas, días, experiencia,
  `TextoOpcional`), `GET /catalogos/registro-oferente`.
- **Fase 2** — `POST /oferentes` en una transacción con `IntegrityError` → 409,
  `requiere_registro` en `/auth/me`, dependencias `get_oferente_registrado` y
  `get_usuario_registrado`, `GET/PUT /oferentes/me`, perfil público y privado, filtro
  de cuentas no activas en la búsqueda, edición con `nombre_bloqueado_por_matricula`.
- **Fase 3** — auth opcional y reglas D8, anti auto-reseña, idempotencia y límites
  anti-spam en la base, `UPDATE` condicional + `UNIQUE(solicitud_id)`, errores con
  código, `ResenaPublicaOut` ("Juan C."), texto literal de la notificación, dedupe de
  la alerta, `cantidad_resenas` en el perfil.
- **Fase 4** — `StorageService` con `SupabaseStorageService` (httpx) y
  `StorageServiceFake`, subidas firmadas, foto de perfil y portada, `TRABAJO_REALIZADO`
  con `orden` y `foto_principal_url`, límites 5 trabajos y 5 fotos, borrado de filas y
  objetos. **Sin credenciales reales: el spike contra Supabase no se hizo** (ver pendientes).
- **Fase 5 (parcial)** — seed actualizado (Serena Ludueña con Lun–Vie, guardia y dos
  reseñas con las fechas de QA; `sin.registro@offix.example.com` para CA01), OpenAPI
  regenerado, `.env.example` y `docs/openapi.md` actualizados.

**Desviaciones y decisiones tomadas en la implementación**

- Código nuevo no listado en las tablas: `dias_invalidos`, `nombre_invalido`,
  `longitud_minima`, `archivo_vacio`, `fotos_requeridas`, `demasiadas_fotos`,
  `fotos_duplicadas`, `enlace_inexistente`, `enlace_utilizado`, `enlace_vencido`,
  `resena_ya_moderada`, `categoria_invalida`, `storage_no_configurado` (503),
  `storage_no_disponible` (502). Todos quedan en `errores[]` o en `detail.codigo`.
- Un trabajo ajeno da **404** (no 403), para no revelar que existe.
- Token presente pero inválido en un endpoint opcional da **401**: no se trata como anónimo.
- Límite de tamaño: 5 MiB = 5 × 1024 × 1024 bytes.
- El 422 de `POST /resenas` (anónimo) no devuelve contacto: la respuesta es `ResenaOut`.
- La normalización de datos de la migración corre en SQL; no corrige los CUIT viejos del
  seed (el seed nuevo los reemplaza al correr de nuevo).

**Pendiente**

- **Fase 0, tests provisorios:** quitados de `test_oferentes.py` y `test_auth_google.py` (2026-10-11).
- **Spike de Supabase Storage:** los endpoints `POST /storage/v1/object/upload/sign/...`,
  `GET /storage/v1/object/info/...` y `DELETE /storage/v1/object/...` están implementados
  según la documentación, pero no se probaron contra un proyecto real. Hay que verificar
  la forma de la respuesta de `info` (tamaño y MIME) antes de la demo.
- **Migración contra Supabase:** no aplicada. La URL comentada en `.env` no conecta: el pooler responde que el tenant `postgres.luxpxhkssgqqwlceblqm` no existe (proyecto eliminado, pausado o cambiado de referencia). Falta la URL vigente. La migración sí se verificó en SQL offline.
- **Carrera del doble clic (A26):** cubierta por revisión del código (`IntegrityError` →
  409), sin test automático, porque SQLite de tests no reproduce la concurrencia.
- **Coordinación con HU-02:** `numero_matricula` y el campo `Fidelizado` siguen pendientes.
- **Correcciones a QA:** la tabla de "Correcciones a pedir" sigue sin enviarse.
- **Excel "Ejecutado por DEV":** sin completar.

**Tests:** suite completa con 237 tests: 233 pasan y 4 fallan (los provisorios de arriba).

## Contexto

Sprint 2 cierra el **13/10/2026** (8 días corridos desde esta revisión).

| HU | Enunciado | Responsable |
|---|---|---|
| **HU-01 v1.2** | Registrar Reseña — aceptación/rechazo por el Profesional y visualización de las aceptadas | Mateo |
| **HU-04** | Como usuario, quiero registrarme como Oferente/Profesional, para poder ofrecer mis servicios dentro de la plataforma | Mateo |
| HU-02 (fidelización) | Validar la matrícula profesional — CA07/CA08 nuevos | Compañero (fuera de este plan, salvo los puntos de coordinación) |

**Alcance de este documento**: backend completo + **contrato de API** para el
frontend (endpoints, flags, códigos de error y validaciones que tiene que
replicar). Los detalles visuales (colores, íconos, posición de botones) quedan
del lado del frontend y solo se mencionan cuando tienen impacto en el backend o
cuando hay una observación crítica.

---

## Resumen ejecutivo

1. **HU-01 v1.2 ya está implementada en un ~80 %** desde el Sprint 1: la
   moderación (`PATCH /resenas/{id}/moderar`), la bandeja y el listado público de
   aceptadas existen. El trabajo del sprint es de **ajuste y robustez**: texto
   literal de la notificación, salida pública sin datos del cliente, regla nueva
   de "Calificar sin login = solo correo", protección contra spam y contra la
   carrera de doble envío.
2. **HU-04 es la carga pesada del sprint**: formulario de registro con 3
   secciones, días/horarios, guard de "registro incompleto", perfil público con
   pestañas, foto de perfil, portada y trabajos realizados con fotos.
3. **Las fotos no pueden pasar por el backend en Vercel** (límite de ~4,5 MB por
   request y sin disco persistente): se suben directo a **Supabase Storage** con
   URL firmada. Es la parte más riesgosa del sprint y es **la línea de corte**.
4. Se **descarta el enfoque de "perfil provisorio"** que asumían los tests sin
   commitear: el `Oferente` no existe hasta que se confirma el formulario.

---

## Decisiones cerradas en esta revisión

| # | Tema | Decisión |
|---|---|---|
| D1 | Alcance del plan | Backend + contrato de API para el frontend |
| D2 | Perfil provisorio | **Descartado.** El `Oferente` se crea recién al confirmar el formulario. `GET /auth/me` informa `requiere_registro` |
| D3 | Nombre | **Un solo campo** «Nombre y apellido» (o razón social), guardado en `nombre`. Se elimina la columna `apellido` (decisión del equipo, 2026-10-11; reemplaza la versión anterior de D3) |
| D4 | Archivos | **Supabase Storage** con URL de subida firmada; el navegador sube directo |
| D5 | DNI/CUIT | **7–8 dígitos (DNI) u 11 (CUIT)**, solo dígitos; CUIT con dígito verificador |
| D6 | Correo | Es el **mismo email de login**, precargado y **bloqueado** |
| D7 | Privacidad del perfil | DNI/CUIT **solo para el dueño**. Teléfono y correo, públicos |
| D8 | Calificar sin login | **Solo correo, obligatorio.** El teléfono/WhatsApp queda para el Profesional dueño logueado. Se aplica **en el backend** |
| D9 | Días de atención | **Tabla hija** `oferente_dias_atencion` |
| D10 | Formato de errores 422 | **Campo + código**; el frontend mapea el código al texto literal de QA |
| D11 | T07 de HU-01 | Pestaña **"Opiniones (n)"** del perfil público |
| D12 | Cliente en opiniones públicas | Se muestra **solo el nombre de pila + inicial** ("Juan C.") |
| D13 | Trabajos realizados | Obligatorios: **≥ 1 foto y descripción**; título opcional. **1 a 5 fotos** por trabajo, **máx. 5 trabajos** |
| D14 | Años de experiencia | 5 rangos (ver "Catálogos") |
| D15 | Horarios | Obligatorios, **apertura < cierre**, pasos de 30 min, sin cruzar medianoche |
| D16 | Migraciones en paralelo | Cada uno en su rama; el segundo en mergear corre `alembic merge heads` |
| D17 | Categorías | **Se mantienen las actuales** del seed (Electricista, Gasista, …). QA ajusta sus casos |
| D18 | Edición del perfil | **Todo editable menos DNI/CUIT y correo** |

---

## HU-04 — Registrar Oferente

### El flujo, de punta a punta

1. El usuario inicia sesión con Google (HU-03, sin cambios). El callback emite
   el JWT y redirige a `/auth/callback` del frontend, igual que hoy.
2. El frontend llama a `GET /api/v1/auth/me`, que ahora devuelve
   **`requiere_registro`**:
   - `true` → rol `Oferente` **sin** fila en `OFERENTE`. El frontend lo manda
     al formulario **"Registro de Profesional"** y no le deja navegar a otra
     ruta (CA01, caso A9).
   - `false` → ya registrado (o es Administrador). Va directo a su perfil (CA05).
3. El formulario pide `GET /api/v1/catalogos/registro-oferente` para llenar los
   selectores (categorías, rangos de experiencia, días).
4. Al **Confirmar**, `POST /api/v1/oferentes` valida todo de una vez y:
   - si hay errores → **422** con la lista completa de campos a corregir (CA02,
     caso A21: todos los errores juntos);
   - si está OK → **201**, crea el `OFERENTE` y sus días de atención en **una
     sola transacción** (CA03).
5. El frontend muestra "Profesional creado correctamente" y redirige al perfil
   (CA03/CA04).
6. Si el usuario abandona el formulario, **no se persiste nada** (CA06). En el
   próximo login `requiere_registro` sigue en `true`.

### Por qué se descarta el "perfil provisorio"

Los tests sin commitear de `test_oferentes.py` y `test_auth_google.py` asumían
que el registro y el login con Google creaban el `Oferente` con un DNI
placeholder (`0-...`). Se descartan porque:

- **Contradicen el CA06 y el caso A65**: "no existe registro en base de datos"
  si el usuario abandona el formulario.
- **Ensucian la búsqueda pública**: `GET /oferentes` mostraría perfiles vacíos.
  Habría que filtrar por un flag en todas las consultas, para siempre.
- **El DNI placeholder es un hack sobre una columna `UNIQUE`** que termina
  filtrándose a reportes, exportaciones y al match de HU-02.

Con la PK compartida (`id_oferente = id_usuario`), la existencia de la fila
**es** el flag: `requiere_registro = rol == Oferente and usuario.oferente is None`.

> **Acción**: revertir los cambios sin commitear en
> `app/tests/test_oferentes.py` y `app/tests/test_auth_google.py`
> (`git checkout -- app/tests/test_oferentes.py app/tests/test_auth_google.py`).

### Campos del formulario y reglas de validación

Los textos entre comillas son los literales de QA, que **renderiza el
frontend** a partir del `codigo` (D10).

#### Sección 1 — Datos personales

| Campo | Columna | Oblig. | Regla backend | Código de error → texto QA |
|---|---|---|---|---|
| Nombre y apellido / Razón social | `nombre` | ✔ | Un solo campo (D3). 2–150 caracteres tras `strip()`; letras, espacios, `.`, `'`, `-` y `&` | `requerido` → "Complete este campo" |
| DNI / CUIT | `dni_cuit` | ✔ | Se quitan guiones y puntos; quedan **7, 8 u 11 dígitos**. Si son 11, **se valida el dígito verificador** del CUIT (módulo 11). Se guarda **solo dígitos** | `requerido` / `dni_cuit_invalido` → "Debe ingresar un formato válido en el campo DNI/CUIT" |
| Teléfono | `telefono` | ✔ | **Misma regla que HU-01**: 10 dígitos, guion opcional, sin `0`, `15` ni `+54`. Reutiliza `telefono_es_valido()` de `app/services/mensajes.py`. Se guardan los 10 dígitos | `requerido` / `telefono_invalido` → "Ingresa 10 dígitos, con guion opcional. Sin 0, 15 o +54 al inicio." |
| Correo electrónico | — (`usuario.email`) | ✔ | **No viaja en el body** (D6): se muestra precargado y bloqueado desde `/auth/me`. Si viene en el body, se ignora | — |

#### Sección 2 — Rubro y especialidad

| Campo | Columna | Oblig. | Regla backend | Código |
|---|---|---|---|---|
| Categoría u oficio principal | `categoria_id` | ✔ | Tiene que existir y estar `Activa` | `requerido` / `categoria_invalida` |
| Especialidad / tareas frecuentes | `especialidad` **(nueva)** | — | Máx. 100 caracteres. Vacío → `NULL` | `longitud_maxima` |
| Años de experiencia | `experiencia` **(nueva)** | — | Uno de los códigos del catálogo, o `NULL` | `experiencia_invalida` |

#### Sección 3 — Rango horario y disponibilidad

| Campo | Columna | Oblig. | Regla backend | Código |
|---|---|---|---|---|
| Días de atención | tabla `oferente_dias_atencion` **(nueva)** | ✔ | Lista de 1 a 7 enteros únicos entre `1` (Lun) y `7` (Dom), ISO-8601. Los atajos "Lun a Vie" / "Lun a Sáb" / "Toda la semana" son del frontend | `dias_requeridos` → "Complete este campo" |
| Horario de apertura | `hora_inicio_atencion` | ✔ | `HH:MM`, minutos `00` o `30` | `requerido` / `horario_invalido` |
| Horario de cierre | `hora_fin_atencion` | ✔ | Igual, y **estrictamente mayor** que la apertura (D15) | `horario_invalido` |
| Emergencias fuera de horario | `disponible_emergencia` | ✔ | Booleano, default `false` | — |
| Información adicional de guardia | `info_guardia` **(nueva)** | — | Máx. 200 caracteres. Vacío → `NULL` (caso A17: "se guarda NULL, no vacío"). **Si el toggle está apagado se guarda `NULL`** aunque venga texto | `longitud_maxima` |

**Reglas transversales**

- Todo texto se guarda con `strip()`, y **cadena vacía → `NULL`** en los
  opcionales. Se implementa una sola vez, con un tipo anotado de Pydantic
  reutilizable (`TextoOpcional`).
- El body tiene `extra="forbid"`: un campo desconocido (por ejemplo
  `numero_matricula` o `estado_verificacion`) da 422. Hoy `OferenteCreate` deja
  que el propio usuario se cargue `numero_matricula`, y eso pertenece a HU-02.
- `latitud`, `longitud` y `radio_cobertura_km` **salen del formulario de
  registro** (no están en los casos de prueba). Las columnas quedan.

### Formato de los errores (D10)

Un `exception_handler` global para `RequestValidationError` transforma el 422
de Pydantic. **Es compatible hacia atrás**: conserva `detail` para no romper los
llamados que ya existen en el frontend (modal de reseña, matrícula).

```json
{
  "detail": [ "...lo que devuelve Pydantic hoy..." ],
  "errores": [
    {"campo": "nombre", "codigo": "requerido"},
    {"campo": "telefono", "codigo": "telefono_invalido"},
    {"campo": "dias_atencion", "codigo": "dias_requeridos"}
  ]
}
```

- Los validadores propios lanzan `PydanticCustomError("dni_cuit_invalido", ...)`:
  el `type` del error **es** el código, así que el mapeo no necesita una tabla
  aparte.
- Los tipos nativos se traducen: `missing` y `string_too_short` sobre un string
  vacío → `requerido`; `string_too_long` → `longitud_maxima`.
- Los errores de negocio (409, 403) usan el mismo vocabulario:
  `{"detail": {"codigo": "dni_cuit_duplicado", "mensaje": "..."}}`.

Códigos de negocio nuevos:

| HTTP | Código | Cuándo |
|---|---|---|
| 409 | `perfil_existente` | El usuario ya completó el registro (incluye el doble clic, caso A26) |
| 409 | `dni_cuit_duplicado` | El DNI/CUIT pertenece a otro Oferente |
| 403 | `rol_invalido` | Un Administrador intenta registrarse como Oferente |
| 403 | `registro_incompleto` | Un Oferente sin registro llama a un endpoint que exige perfil |

### Doble clic en "Confirmar" (caso A26)

La PK compartida ya **garantiza a nivel de base** que no puede haber dos perfiles
para el mismo usuario. Lo que hay que hacer es **atrapar el `IntegrityError`**
del segundo `INSERT` concurrente y devolver `409 perfil_existente` en vez de un
500. El frontend trata `409 perfil_existente` posterior a su propio envío como
éxito y redirige al perfil. Además, el botón se deshabilita mientras la request
está en vuelo.

### Guard de registro incompleto (CA01, caso A9)

El guard de rutas es del frontend, pero **el backend no puede confiar en él**.
Se crea una dependencia `get_oferente_registrado` en `app/core/deps.py`:

```python
def get_oferente_registrado(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> Oferente:
    oferente = db.get(Oferente, usuario.id_usuario)
    if oferente is None:
        raise HTTPException(403, detail={"codigo": "registro_incompleto", "mensaje": "..."})
    return oferente
```

Se aplica a todos los endpoints que hoy hacen la verificación a mano o no la
hacen: moderación de reseñas, bandeja de notificaciones (rol Oferente),
archivos/trabajos, `GET/PUT /oferentes/me` y **matrículas** (hoy devuelve un
`404 "El usuario no tiene perfil de Oferente"` en `_oferente_actual`;
**coordinar con el compañero** para unificarlo).

### Edición del perfil (caso A33, D18)

`PUT /api/v1/oferentes/me` con el mismo schema del registro, todo opcional
(PATCH semántico), **sin** `dni_cuit` (y sin correo, que nunca viaja).

- **Cambio de nombre con una matrícula fidelizada → bloqueado** (`409
  nombre_bloqueado_por_matricula`). Si no, alguien fideliza con su nombre real y
  después se lo cambia, y el distintivo de verificado queda colgado de una
  identidad distinta. *Coordinar con el compañero*: depende de `Matricula`.
- `PUT /api/v1/oferentes/{id}` se mantiene como alias por compatibilidad, pero
  delega en la misma lógica (y solo permite `{id} == usuario actual`).

---

## HU-04 — Perfil del Profesional (CA04)

### Qué ve el público y qué ve el dueño (D7)

Hoy `GET /oferentes/{id}` es público y devuelve **`dni_cuit`** y
**`cantidad_rechazos_acumulados`**. El segundo es un dato interno de moderación
que, expuesto, permite inferir cuántas reseñas negativas filtró el Profesional.
Se separa la salida en dos:

| Campo | `OferentePublicoOut` (`GET /oferentes/{id}`, `GET /oferentes`) | `OferentePrivadoOut` (`GET /oferentes/me`) |
|---|---|---|
| id, nombre, categoría (id + nombre) | ✔ | ✔ |
| especialidad, experiencia (código + etiqueta) | ✔ | ✔ |
| teléfono, correo (`usuario.email`) | ✔ | ✔ |
| días, horarios, emergencias, info de guardia | ✔ | ✔ |
| foto de perfil y portada (URL pública) | ✔ | ✔ |
| `promedio_calificacion`, `cantidad_resenas`, `cantidad_trabajos` | ✔ | ✔ |
| `tiene_matricula_validada` + matrículas (tipo y número, para el tooltip "Matriculado N° X") | ✔ | ✔ |
| **`dni_cuit`** | ✘ | ✔ |
| `estado_verificacion`, `cantidad_rechazos_acumulados` | ✘ | ✔ |
| `descripcion`, `latitud`, `longitud`, `radio_cobertura_km` | se mantienen como hoy | ✔ |

Los contadores de las pestañas ("Trabajos realizados (n)", "Opiniones (n)") se
resuelven con **`COUNT` en la misma consulta del perfil**, no trayendo las
listas enteras.

> ⚠ **Consecuencia de D6 + D7**: el correo público del perfil es **el mismo con
> el que el Profesional entra con Google**, normalmente su Gmail personal.
> Queda asentado como dato personal expuesto en "Riesgos".

`GET /oferentes` (la búsqueda) además **excluye** los usuarios con
`estado_cuenta != Activa` (observación F4 de QA: "Revisar oferentes que se
pueden visualizar"). Hoy un Profesional suspendido sigue apareciendo.

### Iniciales del avatar (caso A34)

Las calcula el frontend a partir de `nombre`: la inicial de la primera y de la última palabra ("SL"). El backend no
guarda nada.

### Pestaña "Datos del Oficio" (casos A30–A32)

La sirve `GET /oferentes/{id}` (o `/me`). Observación del caso A30: muestra el
**DNI/CUIT**, así que esa línea **solo aparece en la vista del dueño** (D7).
Hay que pedirle a QA que lo aclare en el caso.

---

## HU-04 — Fotos y trabajos realizados (T06)

### Por qué no se suben a través del backend

| Restricción | Detalle |
|---|---|
| Vercel Functions | Cuerpo máximo de request de **~4,5 MB**. Una foto de 4,6 a 5 MB, permitida por QA, fallaría **solo en producción** |
| Vercel Functions | **Sin disco persistente**: lo que se escribe en `/tmp` se pierde |
| Costo/latencia | Cada byte pasaría dos veces por la función (entrada y reenvío) |

### Flujo con Supabase Storage (D4)

Bucket **`offix-media`**, de lectura pública y configurado **en el propio
bucket** con `file_size_limit = 5 MB` y `allowed_mime_types = [image/jpeg,
image/png]`. Así el límite lo hace cumplir Storage y no depende solo del código.

```
Frontend                         Backend                          Supabase Storage
   │ POST /oferentes/me/archivos/subidas                               │
   │ {tipo, content_type, tamano_bytes} ──▶ valida tipo, tamaño,       │
   │                                        cupo; arma el path         │
   │                                        ──── createSignedUploadUrl ▶
   │ ◀── {path, upload_url} ─────────────────────────────────────────── │
   │ PUT archivo ─────────────────────────────────────────────────────▶ │
   │ POST /oferentes/me/foto-perfil {path} ─▶ HEAD del objeto: existe,  │
   │                                          tamaño y MIME reales      │
   │                                          guarda la fila, borra la  │
   │ ◀── perfil actualizado ───────────────── foto anterior            │
```

- **El path lo arma el backend**, nunca el cliente:
  `oferentes/{id_oferente}/{tipo}/{uuid}.{ext}`. Al confirmar se verifica que
  el path empiece con el prefijo del usuario autenticado: nadie puede "adoptar"
  la foto de otro.
- El backend **valida antes de firmar** (para dar el error temprano, con el
  texto de QA) y **vuelve a validar al confirmar** (tamaño y MIME reales del
  objeto), porque el cliente puede mentir en el paso 1.
- Credenciales nuevas en el backend: `SUPABASE_URL` y
  `SUPABASE_SERVICE_ROLE_KEY`. **La service role key nunca llega al
  frontend.**
- Cliente HTTP: `httpx` (ya está en `requirements.txt`) contra la API REST de
  Storage. No hace falta sumar el SDK de Supabase.
- Igual que con `EmailService`, se define un **`StorageService` abstracto con
  un doble en memoria** para los tests (`StorageServiceFake`).

| Validación | Código | Texto QA |
|---|---|---|
| MIME distinto de JPG/PNG | `formato_imagen_invalido` | "Formato de imagen incorrecto, solo se acepta JPG o PNG" |
| Más de 5 MB | `imagen_demasiado_grande` | "Supera el tamaño permitido, solo se acepta hasta 5MB" |
| Path ajeno o inexistente | `archivo_invalido` | — |

### Modelo

Se **reutiliza `ARCHIVO_ADJUNTO`**, que ya está en el DER, en vez de agregar
columnas sueltas:

```python
class TipoArchivo:
    PERFIL = "Perfil"
    PORTADA = "Portada"
    TRABAJO = "Trabajo"

# ARCHIVO_ADJUNTO — cambios
tipo          = Column(String(50), nullable=False)          # ahora con TipoArchivo
url_archivo   -> storage_path = Column(String(255), nullable=False)  # path; la URL pública se arma
content_type  = Column(String(50), nullable=False)          # nuevo
tamano_bytes  = Column(Integer, nullable=False)              # nuevo
trabajo_id    = Column(Integer, ForeignKey("trabajos_realizados.id_trabajo", ondelete="CASCADE"), nullable=True)  # nuevo
orden         = Column(SmallInteger, nullable=True)        # nuevo (rev. 2): 1..5 dentro del trabajo; NULL en Perfil/Portada
# UNIQUE (trabajo_id, orden): dos fotos del mismo trabajo no pueden tener el mismo orden.

# TRABAJO_REALIZADO — tabla nueva
id_trabajo     = Column(Integer, primary_key=True)
oferente_id    = Column(Integer, ForeignKey("oferentes.id_oferente", ondelete="CASCADE"), nullable=False, index=True)
titulo         = Column(String(100), nullable=True)
descripcion    = Column(Text, nullable=False)             # máx. 1000 caracteres, validado en el schema
fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
```

Foto de perfil y portada: **una vigente por tipo**. Al reemplazarla se borra la
fila y el objeto anterior en la misma operación.

### Reglas de trabajos realizados (D13)

| Regla | Definición |
|---|---|
| Fotos | **1 a 5** por trabajo, JPG/PNG, hasta 5 MB cada una |
| Descripción | **Obligatoria**, de 10 a 1000 caracteres |
| Título | Opcional, máx. 100. Vacío → `NULL` |
| Cupo | **Máx. 5 trabajos** por Oferente. El sexto → `409 limite_trabajos` |
| Orden de los trabajos | Más nuevo primero |
| Orden de las fotos (rev. 2) | El **orden en que vienen en `fotos: [path]`** del POST se guarda en `orden` (1..5). **La foto principal es la `orden = 1`**, la primera cargada (caso A50) |
| Cupo visible (rev. 2) | El perfil expone `cantidad_trabajos` y el catálogo expone `limites: {trabajos: 5, fotos_por_trabajo: 5}`. Con 5 trabajos, el frontend oculta "+ Cargar nuevo trabajo" (caso A47). El backend igual responde `409 limite_trabajos` si llega un sexto |
| Borrado | `DELETE` real de las filas **y de los objetos en Storage** (caso A53) |

**Salida de un trabajo** (rev. 2). Una sola forma sirve para la tarjeta (A50) y
para el carrusel del detalle (A51), sin un segundo request:

```json
{
  "id_trabajo": 3,
  "titulo": "Cambio de disyuntor",
  "descripcion": "Reemplazo del disyuntor diferencial...",
  "fecha_creacion": "2026-09-30T14:10:00Z",
  "foto_principal_url": "https://<proyecto>.supabase.co/storage/v1/object/public/offix-media/oferentes/7/trabajo/ab12.jpg",
  "fotos": [
    {"orden": 1, "url": "https://…/ab12.jpg"},
    {"orden": 2, "url": "https://…/cd34.png"}
  ]
}
```

`foto_principal_url` es redundante con `fotos[0].url`, pero deja la tarjeta
independiente del orden en que el frontend recorra la lista. Para este sprint
**no hay** reordenamiento ni edición de fotos de un trabajo ya creado: para
cambiarlas se borra el trabajo y se carga de nuevo.

> **[A validar con QA/PM]** El caso A46 dice que el botón Guardar "no se
> habilita hasta cargar un título e img", pero el título es opcional y la
> descripción obligatoria. Queda: **foto + descripción** habilitan el botón.
> La revisión 2 del Excel **mantiene esa contradicción**, así que hay que
> volver a pedirla. También agrega "en el mockup se propone un formato, avisar
> si lo cambio" sobre las 5 imágenes: el contrato de arriba (lista ordenada +
> foto principal) sirve para cualquier diseño de carga, así que no bloquea.

### Objetos huérfanos

Si el usuario pide la URL firmada, sube el archivo y nunca confirma (cierra la
pestaña), el objeto queda en Storage sin fila. **Fuera de alcance** para este
sprint; queda en "Riesgos" con la mitigación propuesta (limpieza periódica de
objetos de más de 24 h sin fila asociada).

---

## HU-01 v1.2 — Registrar Reseña (T06, T07, CA05)

### Qué ya existe y qué cambia

| Pieza | Estado | Cambio en Sprint 2 |
|---|---|---|
| `PATCH /resenas/{id}/moderar` (Aceptar/Rechazar) | ✔ Hecho | Pasa a usar `get_oferente_registrado`. Errores con `codigo` |
| Bandeja `GET /notificaciones` + contador | ✔ Hecho | **Texto literal de QA** en el mensaje. Se cierra la pregunta abierta #3 del Sprint 1 (ver abajo) |
| `GET /oferentes/{id}/resenas` (aceptadas, más nuevas primero) | ✔ Hecho | **Salida pública nueva**, sin datos de contacto y con nombre de pila (D12) |
| `POST /oferentes/{id}/solicitudes-resena` | ✔ Hecho | **Auth opcional + regla D8**, anti auto-reseña y límites anti-spam |
| `POST /resenas` | ✔ Hecho | **Carrera de doble envío** cerrada a nivel de base |
| Alerta 5 de 10 al Administrador | ✔ Hecho | **Dedupe**: hoy crea una alerta nueva en cada rechazo después del quinto |

### CA05 — Confirmar reseña (T06)

Sin cambios funcionales: la notificación llega, el Profesional elige **Aceptar**
o **Cancelar** (= Rechazar; en la UI el botón dice "Rechazar" según CA4 del
Sprint 1, y la HU dice "Cancelar": **[A validar con QA/PM]** unificar el
nombre). La moderación sigue siendo **a ciegas**: el Profesional decide mirando
el contacto, sin ver el contenido. Es lo que impide que filtre las reseñas
negativas por lo que dicen.

**Texto de la notificación** (literal QA, caso A34):

```
Recibiste una nueva reseña de un cliente {X} a través de Offix.
```

`{X}` = teléfono si se cargó; si no, el correo. Hoy el mensaje es otro
(`"{nombre} ({contacto}) dejó una reseña..."`) y hay que reemplazarlo en
`app/services/notificaciones.py`. `NotificacionOut` sigue exponiendo
`telefono_cliente` y `email_cliente` por separado, así el frontend puede
formatear sin parsear el texto.

**Contador de la campana** — cierra la pregunta abierta #3 del Sprint 1: el caso
A34 dice "notificaciones pendientes de rechazo/aceptación", así que **el badge
usa `pendientes_de_accion`**. `sin_leer` se mantiene en la respuesta para las
informativas de matrícula.

### T07 — Pestaña "Opiniones (n)" (D11, D12)

`GET /oferentes/{id}/resenas` devuelve un `ResenaPublicaOut` nuevo:

```json
{
  "id_resena": 12,
  "cliente": "Juan C.",
  "puntuacion_global": 4.75,
  "criterios": {"puntualidad": 4.5, "precio": 5, "calidad": 5, "atencion": 4.5},
  "comentario": "Buen servicio...",
  "fecha_creacion": "2026-09-29T21:29:00Z"
}
```

- **Se quitan** `solicitud_id`, `estado` (siempre `Aceptada`) y
  `nombre_cliente` completo. `cliente` = primer token del nombre + inicial del
  segundo token, si existe ("Juan Carlos Pérez" → "Juan C.", "Juan" → "Juan").
- `fecha_creacion` es la de **carga por el cliente**, no la de aceptación (caso
  A35, requisito ya cumplido).
- El orden de la tarjeta (columna 1: promedio y calidad; columna 2: precio y
  atención) es del frontend.

> **[A validar con QA/PM]** — dos inconsistencias en los ejemplos:
> - **Redondeo**: el caso A26 del Sprint 1 espera "4.8" para (4.5+5+5+4.5)/4 =
>   **4.75**. El backend guarda 2 decimales (4.75). Propuesta: el frontend
>   muestra **1 decimal** con redondeo *half-up* (4.75 → 4.8). Si se usa el
>   redondeo bancario de Python o `toFixed`, puede dar 4.7 o 4.8 según el
>   valor: hay que fijarlo.
> - **Valores imposibles**: el caso A55 muestra Puntualidad 4.6, Precio 4.2 y
>   Calidad 4.9 en **una sola reseña**. Con la escala de media estrella (pasos de
>   0.5) esos valores no existen por criterio; solo pueden aparecer en un
>   **promedio**. Hay que corregir el ejemplo, o el seed no lo va a poder
>   reproducir.

### Calificar con y sin login (D8)

Regla nueva de la hoja *US-Reseña* (A5/F5): **sin login, el modal solo muestra
el correo, y es obligatorio**. El teléfono (WhatsApp) queda para el Profesional
dueño del perfil, que es quien le manda el link a su cliente.

El endpoint pasa a tener **autenticación opcional**
(`OAuth2PasswordBearer(auto_error=False)` → `get_current_user_opcional`):

| Quién genera | Teléfono | Correo | Resultado |
|---|---|---|---|
| Anónimo, u otro usuario logueado | Prohibido → `422 telefono_no_permitido` | **Obligatorio** → `422 email_requerido` | Solo correo |
| Profesional **dueño** del perfil | Opcional | Opcional | Al menos uno → `422 contacto_requerido` ("Debe completar al menos un dato de contacto para poder generar el enlace.") |

El `nombre_cliente` sigue siendo **obligatorio** en los dos casos (decisión del
Sprint 1). Además, ahora se usa en la tarjeta pública (D12).

### Mejoras de robustez

**1. Anti auto-reseña.** Hoy nada impide que el Profesional genere un enlace a
su propio correo o teléfono y se califique solo. Se rechaza con `422
contacto_propio` si el correo coincide con el `usuario.email` del Profesional,
o si el teléfono coincide con `oferente.telefono`. No es infalible (puede usar
otra casilla), pero cierra el caso trivial. El resto lo cubre la alerta al
Administrador.

**2. Anti spam / abuso de correo.** El endpoint es público y **manda correos con
la marca Offix a cualquier dirección**: es un relay de spam que además quema la
reputación del remitente en Brevo. En Vercel serverless no hay memoria
compartida entre instancias, así que **el límite se cuenta en la base**:

| Límite | Valor | Código |
|---|---|---|
| Solicitudes pendientes para el mismo par (oferente, correo) | 1 activa. Si ya hay una vigente, se **reenvía la misma** en vez de crear otra | — (idempotente) |
| Solicitudes por correo destino, en 24 h, a cualquier oferente | 5 | `429 limite_solicitudes` |
| Solicitudes por oferente, en 24 h | 30 | `429 limite_solicitudes` |

Los valores van a configuración (`RESENA_LIMITE_*`). La idempotencia del primer
renglón también resuelve el doble clic en "Generar enlace".

**3. Carrera en `POST /resenas`.** Hoy dos envíos concurrentes con el mismo
código leen los dos `Pendiente_Uso` y crean **dos reseñas**. Se cierra con dos
medidas complementarias:
- `UNIQUE (solicitud_id)` en `RESENAS` (la relación es 1 a 1 en la práctica).
- La transición de estado se hace con un **UPDATE condicional**:
  `UPDATE solicitudes_resena SET estado='Utilizada' WHERE id=:id AND
  estado='Pendiente_Uso'`. Si `rowcount == 0`, devuelve `400 enlace_utilizado`.

**4. Dedupe de la alerta 5 de 10.** Hoy, a partir del quinto rechazo, **cada
rechazo nuevo crea otra alerta**. Se crea solo si el Oferente **no tiene ya una
alerta en `Pendiente`**.

**5. Errores con código.** Los 400 de reseña pasan a
`enlace_inexistente` / `enlace_utilizado` / `enlace_vencido`, para que el
frontend muestre el mensaje correcto (EXTRAS de QA: "Alinear mensaje de
validación de uso del enlace").

---

## Catálogos

`GET /api/v1/catalogos/registro-oferente` (público, cacheable). Una sola
llamada llena todos los selectores del formulario:

```json
{
  "categorias": [{"id": 1, "nombre": "Electricista"}, "..."],
  "experiencia": [
    {"codigo": "MENOS_1",  "etiqueta": "Menos de 1 año (Inicial)"},
    {"codigo": "1_A_2",    "etiqueta": "1 a 2 años (Junior)"},
    {"codigo": "3_A_5",    "etiqueta": "3 a 5 años (Experimentado)"},
    {"codigo": "6_A_10",   "etiqueta": "6 a 10 años (Senior)"},
    {"codigo": "MAS_10",   "etiqueta": "Más de 10 años (Experto)"}
  ],
  "dias": [{"dia": 1, "corto": "Lun", "largo": "Lunes"}, "...", {"dia": 7, "corto": "Dom", "largo": "Domingo"}],
  "horario_default": {"apertura": "08:00", "cierre": "18:00"},
  "limites": {"trabajos": 5, "fotos_por_trabajo": 5, "tamano_maximo_mb": 5}
}
```

Categorías: **las actuales del seed** (D17), solo las `Activa`. **[A validar con
QA/PM]**: los casos A25–A30 usan "Electricidad e Iluminación", que no existe;
QA tiene que cambiarlo a "Electricista".

---

## Cambios de esquema

**Una sola migración de Alembic** para todo lo de este plan
(`sprint_2_registro_oferente`). Regla D16: si el compañero mergea antes, se hace
rebase y `alembic merge heads`.

### `OFERENTE`

```python
especialidad = Column(String(100), nullable=True)   # nuevo
experiencia  = Column(String(20),  nullable=True)   # nuevo, código del catálogo
info_guardia = Column(String(200), nullable=True)   # nuevo
# hora_inicio_atencion / hora_fin_atencion: pasan a NOT NULL para los registros nuevos.
#   Se dejan nullable en la base (filas viejas) y la obligatoriedad la impone el schema.
# numero_matricula: sale de los schemas. Dropear la columna se coordina con el compañero (HU-02).
```

### `OFERENTE_DIAS_ATENCION` (nueva, D9)

```python
oferente_id = Column(Integer, ForeignKey("oferentes.id_oferente", ondelete="CASCADE"), primary_key=True)
dia         = Column(SmallInteger, primary_key=True)    # 1 = Lunes … 7 = Domingo (ISO-8601)
__table_args__ = (CheckConstraint("dia BETWEEN 1 AND 7", name="ck_dia_atencion_rango"),)
```

### `TRABAJO_REALIZADO` (nueva) y `ARCHIVO_ADJUNTO` (modificada)

Ver "Fotos y trabajos realizados".

### `RESENAS`

```python
UniqueConstraint("solicitud_id", name="uq_resena_solicitud")   # nuevo — carrera de doble envío
```

### Migración de datos

Las filas existentes no cumplen las reglas nuevas. La migración las normaliza
**antes** de que entren en vigor:

| Columna | Hoy (seed) | Después |
|---|---|---|
| `dni_cuit` | `20-30111222-3` | `20301112223` (solo dígitos) |
| `telefono` | `+54 3564 400111` | `3564400111` (los 10 dígitos) |
| días de atención | — | Lunes a viernes para todos los oferentes existentes |
| horarios | `NULL` | `08:00`–`18:00` si estaban vacíos |

> ⚠ Los CUIT del seed son **inventados** y casi seguro **no pasan el dígito
> verificador**. Se reemplazan por CUIT con un dígito verificador válido.
> Mientras tanto, la validación solo corre sobre lo que entra por la API, no
> sobre lo que ya está guardado.

### Coordinación con HU-02 (compañero)

| Tema | Qué hay que acordar |
|---|---|
| Campo `Fidelizado` (bit) en `USUARIO` (caso CA08) | **Duplica** lo que ya calcula `Oferente.tiene_matricula_validada` (existe una fila en `MATRICULAS`). Propuesta: no agregar la columna, o agregarla como columna derivada que se mantiene en la misma transacción que la fidelización. Si QA la exige "visible en BD", va en **`OFERENTE`**, no en `USUARIO` (un Administrador no se fideliza) |
| "Tabla intermedia matrícula–usuario" (CA08) | **Ya existe**: `MATRICULAS` (`oferente_id`, `tipo_profesional`, `numero_matricula`). Hay que mostrársela a QA en vez de crear otra |
| Botón "Validar Matrícula" desaparece al matricularse (caso A43) | **Choca con HU-02**, que admite **más de una matrícula** (una por oficio). Propuesta: el botón desaparece solo cuando están fidelizados los dos tipos |
| `404` de `_oferente_actual` en matrículas | Unificar con `403 registro_incompleto` |
| Bloqueo de cambio de nombre | Depende de que exista una fila en `MATRICULAS` |
| `numero_matricula` en `OFERENTE` | Columna legada. Dropearla en una sola migración |

---

## Endpoints

### Registro y perfil (HU-04)

| Método y ruta | Descripción | Auth |
|---|---|---|
| `GET /api/v1/auth/me` | **Modificado**: suma `requiere_registro: bool` | Cualquier rol |
| `GET /api/v1/catalogos/registro-oferente` | **Nuevo**: categorías, experiencia, días, horario por defecto | Pública |
| `POST /api/v1/oferentes` | **Modificado**: schema nuevo (`OferenteRegistro`). Crea el perfil y los días en una transacción. 201 / 409 / 422 | Oferente sin registro |
| `GET /api/v1/oferentes/me` | **Nuevo**: perfil privado completo | Oferente registrado |
| `PUT /api/v1/oferentes/me` | **Nuevo**: edición, sin DNI ni correo | Oferente registrado |
| `PUT /api/v1/oferentes/{id}` | Alias de compatibilidad; solo si `{id}` es el propio | Oferente registrado |
| `GET /api/v1/oferentes/{id}` | **Modificado**: salida pública (sin DNI ni rechazos) + contadores | Pública |
| `GET /api/v1/oferentes` | **Modificado**: excluye cuentas no activas | Pública |

### Archivos y trabajos (HU-04 T06)

| Método y ruta | Descripción | Auth |
|---|---|---|
| `POST /api/v1/oferentes/me/archivos/subidas` | **Nuevo**: valida y devuelve `{path, upload_url}` | Oferente registrado |
| `PUT /api/v1/oferentes/me/foto-perfil` | **Nuevo**: confirma `{path}`, reemplaza la anterior | Oferente registrado |
| `PUT /api/v1/oferentes/me/portada` | **Nuevo**: ídem | Oferente registrado |
| `DELETE /api/v1/oferentes/me/foto-perfil` | **Nuevo**: vuelve a las iniciales | Oferente registrado |
| `GET /api/v1/oferentes/{id}/trabajos` | **Nuevo**: lista pública, más nuevos primero | Pública |
| `POST /api/v1/oferentes/me/trabajos` | **Nuevo**: `{titulo?, descripcion, fotos: [path]}` | Oferente registrado |
| `DELETE /api/v1/oferentes/me/trabajos/{id}` | **Nuevo**: borra las filas y los objetos | Oferente dueño |

### Reseñas (HU-01 v1.2)

| Método y ruta | Cambio | Auth |
|---|---|---|
| `POST /api/v1/oferentes/{id}/solicitudes-resena` | Auth **opcional**; regla D8; anti auto-reseña; límites; idempotente por (oferente, correo) | Pública / Oferente dueño |
| `POST /api/v1/resenas` | UPDATE condicional + `UNIQUE(solicitud_id)`; errores con código | Pública |
| `GET /api/v1/oferentes/{id}/resenas` | Salida `ResenaPublicaOut` | Pública |
| `PATCH /api/v1/resenas/{id}/moderar` | `get_oferente_registrado`; errores con código; alerta deduplicada | Oferente dueño |
| `GET /api/v1/notificaciones` | Texto literal de QA | Oferente / Admin |

---

## Configuración nueva

```bash
# Supabase Storage (HU-04 T06). La service role key NUNCA va al frontend.
SUPABASE_URL=https://<proyecto>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_STORAGE_BUCKET=offix-media
ARCHIVO_TAMANO_MAXIMO_MB=5

# Límites anti-spam del enlace de reseña (HU-01).
RESENA_LIMITE_POR_EMAIL_24H=5
RESENA_LIMITE_POR_OFERENTE_24H=30
```

Sin `SUPABASE_*`, los endpoints de archivos responden **503** (mismo criterio
que Auth0): no se cae el resto del backend.

**Setup manual en Supabase** (documentarlo en `.env.example`): crear el bucket
`offix-media` como público, con un límite de 5 MB y los MIME
`image/jpeg,image/png`.

---

## Contrato para el frontend

Lo que el frontend tiene que saber y replicar. **Las validaciones del frontend
son de UX; las del backend son las que valen.**

| Tema | Contrato |
|---|---|
| Al volver del login | `GET /auth/me` → si `requiere_registro`, forzar `/registro`. Guard en `middleware.ts` sobre todas las rutas privadas (A9) |
| Correo en el formulario | Precargado desde `/auth/me` y **bloqueado**. No se envía en el body |
| Días | Enviar `dias_atencion: [1,2,3,4,5]`. Los atajos son locales |
| Horarios | `"08:00"`, en pasos de 30 min |
| Errores 422 | Leer `errores[]` y pintar **todos** los campos a la vez (A21). Mapear `codigo` → texto QA. Conservar los valores cargados (A22) |
| Éxito | 201 → toast verde "Profesional creado correctamente" → redirect al perfil (A25, A27) |
| Doble clic | Deshabilitar el botón en vuelo; `409 perfil_existente` = éxito |
| Fotos | 1) `POST …/subidas`; 2) `PUT` del archivo a `upload_url`; 3) `PUT …/foto-perfil {path}`. Validar tipo y tamaño **antes** del paso 1 para dar el feedback inmediato |
| Calificar | Sin login o en un perfil ajeno → solo el input de correo, obligatorio. En el perfil propio → teléfono y correo |
| Trabajos (rev. 2) | Contador "Foto del Trabajo (X/5)" con `limites.fotos_por_trabajo`. Mandar `fotos` **en el orden de carga**. La tarjeta usa `foto_principal_url` y el detalle hace el carrusel con `fotos[]`. Ocultar "+ Cargar nuevo trabajo" cuando `cantidad_trabajos >= limites.trabajos` |
| Badge de la campana | Usar `pendientes_de_accion` |
| Opiniones | `GET /oferentes/{id}/resenas`. Promedio con **1 decimal, half-up** |

**Tabla código → texto (para el frontend)**

| Código | Texto |
|---|---|
| `requerido`, `dias_requeridos` | Complete este campo |
| `dni_cuit_invalido` | Debe ingresar un formato válido en el campo DNI/CUIT |
| `telefono_invalido` | Ingresa 10 dígitos, con guion opcional. Sin 0, 15 o +54 al inicio. |
| `email_invalido` | Ingresá un correo válido. Ej: ejemplo@gmail.com |
| `contacto_requerido` | Debe completar al menos un dato de contacto para poder generar el enlace. |
| `formato_imagen_invalido` | Formato de imagen incorrecto, solo se acepta JPG o PNG |
| `imagen_demasiado_grande` | Supera el tamaño permitido, solo se acepta hasta 5MB |
| Toast general de CA02 | Complete sus datos personales |

### Observaciones de UX para el frontend

- **Confirmación de borrado en verde (caso A53).** QA pide "Confirmar" verde y
  "Cancelar" rojo en el modal de eliminar un trabajo. Va contra la convención: en
  una acción **destructiva** el botón que confirma debería ser el rojo. Con la
  regla general de "las confirmaciones son verdes" el usuario termina borrando
  por reflejo. Proponerlo a QA.
- **Formulario de registro largo sin guardado parcial.** El CA06 obliga a perder
  todo si se cierra la pestaña. Se podría guardar un **borrador en
  `localStorage`**, que no viola el CA06 (no hay registro en la base), pero el
  caso A65 dice explícitamente que el formulario vuelve vacío. Se respeta el caso.

---

## Seed de datos

- Normalizar los DNI/CUIT (con dígito verificador válido) y los teléfonos de los
  6 oferentes de demo.
- Cargarles días, horarios, especialidad y experiencia.
- Una **Oferente de demo que reproduzca los casos de QA**: "Serena Ludueña",
  Electricista, especialidad "prueba", 3 a 5 años, Lun–Vie 08:00–18:00, con
  guardia y "No domingos".
- **Dos reseñas aceptadas** con fechas 25/09/2026 y 29/09/2026 (A54–A56), con
  valores de media estrella (no los de A55, ver la observación de arriba).
- **Una cuenta de Google de prueba sin registro** no se puede sembrar (la crea
  Auth0). Para probar el CA01 por password: un `Usuario` rol Oferente **sin**
  `OFERENTE` (`sin.registro@offix.example.com`).
- Trabajos y fotos: **no se siembran** (dependen de Storage). Se cargan a mano
  en la demo.

---

## Tests

Se ajustan los existentes (los de `ResenaOut` público, `OferenteOut` y
`POST /oferentes`) y se agregan:

**HU-04 — registro**
- `/auth/me` → `requiere_registro=true` para un Oferente sin perfil y `false`
  con perfil y para el Administrador.
- Registro completo válido → 201; se crean el `OFERENTE` y sus días.
- Body vacío → 422 con **todos** los campos obligatorios en `errores[]`.
- DNI de 7, 8 y 11 dígitos válidos → OK; 9 y 10 dígitos → `dni_cuit_invalido`;
  CUIT con dígito verificador incorrecto → `dni_cuit_invalido`; letras → ídem.
- DNI/CUIT con guiones → se guarda solo dígitos.
- Teléfono con `0`, `15`, `+54` o letras → `telefono_invalido`.
- `dias_atencion` vacío → `dias_requeridos`; día 8 o repetido → 422.
- Cierre ≤ apertura, o minutos distintos de 00/30 → `horario_invalido`.
- `especialidad` / `info_guardia` vacíos → `NULL`; toggle apagado con texto →
  `info_guardia` en `NULL`.
- Campo extra (`numero_matricula`) → 422.
- Segundo POST → `409 perfil_existente`; DNI de otro → `409 dni_cuit_duplicado`.
- Administrador → `403 rol_invalido`.
- Sin registro → `403 registro_incompleto` en moderar, notificaciones y
  `/oferentes/me`.
- `PUT /oferentes/me` no acepta `dni_cuit`; cambio de nombre con matrícula →
  `409 nombre_bloqueado_por_matricula`.

**HU-04 — perfil público**
- `GET /oferentes/{id}` **no** expone `dni_cuit` ni
  `cantidad_rechazos_acumulados`; `/oferentes/me` sí.
- Los contadores `cantidad_resenas` y `cantidad_trabajos` son correctos.
- La búsqueda excluye las cuentas suspendidas.

**HU-04 — archivos (con `StorageServiceFake`)**
- Pedir una subida con `application/pdf` o de más de 5 MB → código
  correspondiente.
- Confirmar un path de otro oferente → `archivo_invalido`.
- Reemplazar la foto de perfil borra el objeto anterior.
- Sexto trabajo → `409 limite_trabajos`; trabajo sin fotos o con 6 →
  422; sin descripción → `requerido`.
- `DELETE` de un trabajo borra las filas y los objetos.
- (rev. 2) Las fotos se guardan con `orden` 1..N según el orden del body;
  `foto_principal_url` es la de `orden = 1`; `GET /oferentes/{id}/trabajos`
  devuelve `fotos[]` ordenadas.
- (rev. 2) El mismo path repetido dos veces en `fotos` → 422.
- (rev. 2) El catálogo expone `limites` con los valores de configuración.
- Sin `SUPABASE_*` → 503.

**HU-01 v1.2**
- Anónimo con teléfono → `telefono_no_permitido`; anónimo sin correo →
  `email_requerido`.
- Dueño solo con teléfono → 201 con `whatsapp_url`.
- Correo o teléfono del propio Profesional → `contacto_propio`.
- Segunda solicitud al mismo (oferente, correo) vigente → devuelve la misma, no
  crea otra.
- Superar el límite de 24 h → 429.
- Dos `POST /resenas` con el mismo código → una sola reseña (simular con un
  UPDATE condicional en la misma sesión).
- Texto de la notificación literal; con teléfono muestra el teléfono, sin
  teléfono el correo.
- Salida pública de reseñas: sin contacto, `cliente` = "Juan C.".
- Sexto y séptimo rechazo → **una sola** alerta pendiente.

**Regresión**: la suite completa en verde, salvo los 4 tests del perfil provisorio que se descartan (medido el 2026-10-11: 237 tests, 233 pasan).

---

## Trazabilidad con los casos de prueba de QA

| Caso(s) QA | Cubierto por | Lado |
|---|---|---|
| A4 (CA01 apertura del formulario) | `requiere_registro` en `/auth/me` | Back + Front |
| A5–A8 (formato del formulario) | Catálogo + diseño | Front |
| A9 (navegar sin registro) | Guard de `middleware.ts` + `403 registro_incompleto` | Back + Front |
| A11–A16 (obligatorios) | `errores[]` con `requerido` / `dias_requeridos` | Back + Front |
| A17 (toggle, NULL) | `TextoOpcional` + regla del toggle | Back |
| A18–A20 (formatos) | Validadores de DNI/CUIT, teléfono | Back + Front |
| A21–A23 (errores múltiples, conservar datos) | `errores[]` completo | Front (con soporte back) |
| A25–A27 (guardado, doble clic, redirect) | 201 / `409 perfil_existente` / PK compartida | Back + Front |
| A29–A32 (perfil, datos del oficio) | `OferentePublicoOut` / `OferentePrivadoOut` | Back + Front |
| A33 (editar datos) | `PUT /oferentes/me` | Back + Front |
| A34–A42 (fotos de perfil y portada) | Storage + `foto-perfil` / `portada` | Back + Front |
| A43–A44 (validar matrícula) | HU-02 (compañero) | — |
| A45–A53 (trabajos) | `TRABAJO_REALIZADO` + endpoints | Back + Front |
| A46 rev. 2 (contador X/5) | `limites.fotos_por_trabajo` en el catálogo | Back + Front |
| A47 rev. 2 (ocultar botón con 5) | `cantidad_trabajos` + `limites.trabajos`; `409 limite_trabajos` | Back + Front |
| A50 rev. 2 (miniatura = primera foto) | `orden` + `foto_principal_url` | Back + Front |
| A51 rev. 2 (carrusel) | `fotos[]` ordenadas en la salida del trabajo | Back + Front |
| A54–A56 (opiniones) | `ResenaPublicaOut`, `cantidad_resenas` | Back + Front |
| A57 (pestañas) | — | Front |
| A59–A61 (CA05 logins posteriores) | `requiere_registro=false` | Back + Front |
| A63–A67 (CA06 abandono) | Nada se persiste antes del POST | Back |
| US-Reseña A5 (sin login, solo correo) | Regla D8 | Back + Front |
| US-Reseña A33–A38 (notificación, aceptar/rechazar) | Ya implementado + texto literal | Back |

---

## Correcciones a pedir sobre la documentación existente

| Documento | Qué dice hoy | Qué corresponde |
|---|---|---|
| Caso A6 (Registro) | DNI/CUIT "entre 8 y 11 caracteres" | **7–8 (DNI) u 11 (CUIT)**; el CUIT con dígito verificador |
| Caso A18 (Registro) | "8 dígitos o 11 dígitos" | Sumar los DNI de **7 dígitos** |
| Caso A15 (Registro) | "borrar el contenido precargado de Correo Electrónico" | El correo es el de login y **no es editable** (D6). El caso se elimina |
| Casos A25–A30 (Registro) | Categoría "Electricidad e Iluminación" | **"Electricista"** (D17) |
| Caso A30 (Registro) | Muestra DNI/CUIT en "Datos del Oficio" | Solo en la **vista del dueño** (D7) |
| Caso A46 (Registro) | Botón habilitado con "título e img" | **Foto + descripción**; título opcional (D13) |
| Caso A46 (Registro) | "hasta 5 imágenes por trabajo", modal con una sola foto | ✔ Resuelto en la rev. 2 del Excel ("Foto del Trabajo (X/N)", N = 5) |
| Caso A55 (Registro) | Criterios 4.6 / 4.2 / 4.9 en una reseña | Valores en pasos de **0.5** |
| Caso A26 (US-Reseña, Sprint 1) | 4.75 se muestra "4.8" | Fijar el redondeo: **1 decimal, half-up** |
| Caso A10 (US-Reseña) | "5 código de área + 6 celular" | **10 dígitos** en total (la regla vigente) |
| HU-01 v1.2 CA05 | "Aceptar o Cancelar" | Unificar con la UI: **Aceptar / Rechazar** |
| CA08 de Fidelización | Campo `Fidelizado` en `USUARIO` | Ver "Coordinación con HU-02" |
| Caso A53 (Registro) | Confirmar borrado en verde | Proponer **rojo** para la acción destructiva |

---

## Riesgos

- **Alcance contra calendario (alto).** 8 días para un formulario de 3
  secciones, un guard, un perfil con 3 pestañas, Storage y trabajos. **Línea de
  corte: la Fase 4** (fotos y trabajos). Si no llega, HU-04 se demuestra con
  registro, perfil y opiniones, y T06 pasa al Sprint 3.
- **Supabase Storage es infraestructura nueva.** Si la configuración del bucket o
  de las credenciales se traba, bloquea toda la Fase 4. Hay que probar el flujo
  de URL firmada **el primer día** con un script aislado, antes de escribir los
  endpoints.
- **Correo personal expuesto.** Por D6 + D7, el correo público del perfil es el
  Gmail con el que el Profesional entra. Queda asentado; si molesta, la salida es
  sumar `email_contacto` más adelante.
- **Migraciones en paralelo.** Dos heads de Alembic si los dos mergean sin
  rebase. Mitigación: correr `alembic heads` antes de mergear y esperar una sola
  head.
- **Objetos huérfanos en Storage.** Las subidas que no se confirman quedan
  ocupando espacio. Hay que limpiar a mano o con un cron fuera de este sprint.
- **Límites anti-spam en la base.** Agregan una consulta por cada generación de
  enlace. Con los volúmenes de un MVP es irrelevante, pero se suma un índice en
  `(email_cliente, fecha_generacion)`.
- **DNI 7 dígitos + CUIT.** Una misma persona puede registrarse dos veces, una
  con el DNI y otra con su CUIT (el CUIT contiene al DNI). Mitigación barata:
  al validar un CUIT de persona física (20/23/24/27), chequear también que su DNI
  embebido no esté registrado. **Se implementa** si sobra tiempo en la Fase 2.

---

## Fases de implementación

Ordenadas por dependencia y por valor demostrable. Cada fase termina en algo
verificable.

### Fase 0 — Limpieza y acuerdos (05/10)

- Revertir los tests sin commitear del "perfil provisorio".
- Acordar con el compañero: el campo `Fidelizado`, `numero_matricula`, el 403
  `registro_incompleto` y el orden de merge de las migraciones.
- **Spike de Storage**: crear el bucket y subir un archivo con URL firmada desde
  un script. Si falla, se replantea la Fase 4 ya mismo.
- Enviar a QA la tabla de "Correcciones a pedir".

### Fase 1 — Esquema y base del registro (06/10)

- Migración: columnas nuevas de `OFERENTE`, `OFERENTE_DIAS_ATENCION`,
  `UNIQUE(solicitud_id)`, migración de datos (normalización de DNI y teléfono,
  días y horarios por defecto).
- Handler global de errores 422 con `errores[]`.
- Validadores: DNI/CUIT con módulo 11, teléfono (reutiliza `mensajes.py`),
  `TextoOpcional`, horarios.
- `GET /catalogos/registro-oferente`.

**Se verifica**: `alembic upgrade head` limpio en SQLite y Supabase; la suite
existente en verde.

### Fase 2 — Registro, guard y perfil (07/10 – 08/10)

- `POST /oferentes` con el schema nuevo, días en transacción, `IntegrityError` →
  409.
- `requiere_registro` en `/auth/me`; dependencia `get_oferente_registrado` en
  todos los endpoints de Oferente.
- `GET /oferentes/me`, `PUT /oferentes/me`; salidas pública y privada; filtro
  de cuentas activas en la búsqueda.
- Seed actualizado (Serena Ludueña, usuario sin registro).

**Se verifica**: CA01, CA02, CA03, CA05 y CA06 de punta a punta con Postman
contra el entorno local. **Con esto HU-04 ya es demostrable sin fotos.**

### Fase 3 — HU-01 v1.2 (09/10)

- Auth opcional y regla D8 en la generación del enlace; anti auto-reseña;
  idempotencia y límites.
- UPDATE condicional en `POST /resenas`; errores con código.
- `ResenaPublicaOut` con `cliente` = nombre de pila.
- Texto literal de la notificación; dedupe de la alerta.
- `cantidad_resenas` en el perfil.

**Se verifica**: casos A5–A12 y A33–A38 de *US-Reseña*, más la pestaña
Opiniones.

### Fase 4 — Fotos y trabajos (10/10 – 11/10) · **línea de corte**

- `StorageService` + `StorageServiceFake`.
- Subidas firmadas, foto de perfil, portada.
- `TRABAJO_REALIZADO`, `ARCHIVO_ADJUNTO` modificado (con `orden`), endpoints
  de trabajos con foto principal y lista ordenada para el carrusel.

**Se verifica**: casos A34–A53 con archivos reales contra Supabase, incluido uno
de 4,8 MB (el que rompería si pasara por Vercel).

### Fase 5 — Cierre (12/10 – 13/10)

- Regenerar `docs/openapi.json` y `docs/openapi.md`.
- Actualizar `.env.example` (Storage, límites).
- Completar la columna **"Ejecutado por DEV"** del Excel con los casos de
  backend que pasan.
- Merge con la rama del compañero; `alembic heads` = 1; deploy en Vercel y
  prueba de humo en producción.

---

## Verificación end-to-end

1. Recrear la base local, aplicar las migraciones y correr el seed.
2. Entrar con Google con una cuenta nueva: `/auth/me` devuelve
   `requiere_registro=true` y el frontend muestra el formulario. Intentar ir a
   otra URL → vuelve al formulario.
3. Confirmar el formulario vacío → todos los errores juntos. Corregir y
   confirmar → 201, toast verde, perfil.
4. Cerrar sesión y volver a entrar → directo al perfil.
5. Con otra cuenta nueva, cargar la mitad del formulario y cerrar la pestaña →
   no hay fila en `OFERENTE`; al volver, el formulario está vacío salvo el
   correo.
6. Ver el perfil como anónimo: no aparece el DNI. Como dueño: sí aparece.
7. Subir una foto de perfil de 4,8 MB, una portada y un trabajo con 3 fotos.
   Borrar el trabajo → desaparece del Storage.
8. Como anónimo, "Calificar" con solo correo → llega el mail. Con teléfono →
   422. Como dueño, con teléfono → abre WhatsApp.
9. Cargar la reseña, aceptarla desde la campana → aparece en "Opiniones (1)"
   como "Juan C.", sin datos de contacto.
10. Suite de pytest completa en verde y `alembic heads` con una sola head.
