# Propuesta de DER — Tabla `NOTIFICACION`

> **Para revisión de la PM.** Cambio derivado de la redefinición de HU-01 y HU-02
> (bandeja de notificaciones in-app). Este documento propone la tabla nueva; el
> DER (`DER_Offix.sql`) no se modifica hasta tener el visto bueno.
>
> Fecha: 2026-09-15 · Autor: equipo de backend

---

## 1. Por qué hace falta

Hasta la revisión anterior, al Profesional se le avisaba de una reseña nueva
**por correo electrónico** (servicio Brevo, ya implementado). Las HU nuevas
cambian ese canal:

- **HU-01 / CA04** — "informar en la **bandeja de notificaciones** del Profesional
  la reseña creada. Debe permitir visualizar los datos de contacto ingresados por
  el cliente."
- **HU-01 / Casos de prueba CA4** — campana en la parte superior de la pantalla,
  con un **contador de notificaciones pendientes** de aceptación/rechazo, que se
  actualiza al llegar cada reseña nueva.
- **HU-02 / T04** — "Mostrar en el perfil del Oferente una **notificación** y el
  estado de la matrícula".
- **HU-02 / decisión del equipo** — cuando un Profesional pide reemplazar una
  matrícula ya fidelizada, se le envía una notificación al **Administrador** para
  que autorice o rechace el reemplazo.

Ninguna de esas cuatro cosas se resuelve con el correo: la notificación tiene que
**persistir**, tener **estado** y ser **consultable** por el usuario destinatario.
Eso es una entidad nueva del modelo.

El toggle `OFERENTE.notificaciones_email_habilitadas` **queda sin sentido** con
este cambio y se propone eliminarlo (ver §7).

---

## 2. SQL propuesto

Escrito en el mismo estilo del DER vigente (entidad en singular, mayúsculas).
En el esquema real lo crea SQLAlchemy como `notificaciones` (snake_case plural),
igual que el resto de las tablas.

```sql
CREATE TABLE NOTIFICACION (
    id_notificacion   SERIAL        PRIMARY KEY,

    -- Destinatario. Apunta a USUARIO y no a OFERENTE a propósito: el
    -- Administrador también recibe notificaciones (autorización de reemplazo
    -- de matrícula).
    usuario_id        INTEGER       NOT NULL,

    tipo              VARCHAR(50)   NOT NULL,
    mensaje           TEXT          NOT NULL,

    -- TRUE  -> la notificación espera una decisión del usuario (Aceptar /
    --          Rechazar) y suma al contador de la campana.
    -- FALSE -> es solo informativa (resultado de validación de matrícula).
    requiere_accion   BOOLEAN       NOT NULL DEFAULT FALSE,

    estado            VARCHAR(50)   NOT NULL DEFAULT 'Pendiente',

    -- Reseña asociada, cuando la notificación nace de una. NULL en las
    -- notificaciones de matrícula.
    resena_id         INTEGER       NULL,

    -- Momento del hecho notificado. Para HU-01 es la fecha en que EL CLIENTE
    -- cargó la reseña, no la de la moderación del Profesional (requisito
    -- explícito de los casos de prueba de QA).
    fecha_creacion    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Se completa al Aceptar / Rechazar. NULL mientras siga Pendiente.
    fecha_resolucion  TIMESTAMP     NULL,

    CONSTRAINT fk_notificacion_usuario
        FOREIGN KEY (usuario_id) REFERENCES USUARIO (id_usuario)
        ON DELETE CASCADE,

    CONSTRAINT fk_notificacion_resena
        FOREIGN KEY (resena_id) REFERENCES RESENA (id_resena)
        ON DELETE CASCADE,

    CONSTRAINT ck_notificacion_estado
        CHECK (estado IN ('Pendiente', 'Aceptada', 'Rechazada', 'Leida')),

    CONSTRAINT ck_notificacion_tipo
        CHECK (tipo IN ('Resena_Nueva',
                        'Matricula_Validada',
                        'Matricula_No_Encontrada',
                        'Matricula_Timeout',
                        'Matricula_Ya_Fidelizada',
                        'Matricula_Reemplazo_Solicitado'))
);

-- Consulta caliente: el contador de la campana y el desplegable de la bandeja.
CREATE INDEX idx_notificacion_usuario_estado
    ON NOTIFICACION (usuario_id, estado);

-- Orden de la bandeja: más recientes primero.
CREATE INDEX idx_notificacion_fecha
    ON NOTIFICACION (fecha_creacion DESC);
```

### Variante MySQL

Si el DER se materializa en MySQL en lugar de PostgreSQL, los únicos cambios son:

```sql
id_notificacion  INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
fecha_creacion   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
fecha_resolucion DATETIME NULL,
```

---

## 3. Diccionario de datos

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| `id_notificacion` | INTEGER | No | PK autoincremental. |
| `usuario_id` | INTEGER | No | FK a `USUARIO`. Destinatario de la notificación. |
| `tipo` | VARCHAR(50) | No | Discrimina el origen. Ver §4. |
| `mensaje` | TEXT | No | Texto ya armado que se muestra en la bandeja. Se guarda materializado para que un cambio de redacción no reescriba el historial. |
| `requiere_accion` | BOOLEAN | No | Si es `TRUE`, la notificación espera Aceptar/Rechazar y cuenta para el badge de la campana. |
| `estado` | VARCHAR(50) | No | `Pendiente` / `Aceptada` / `Rechazada` / `Leida`. Ver §5. |
| `resena_id` | INTEGER | Sí | FK a `RESENA`. Permite resolver la reseña al Aceptar/Rechazar desde la bandeja. |
| `fecha_creacion` | TIMESTAMP | No | Fecha y hora del hecho notificado. Es la que se muestra en la esquina superior derecha de la tarjeta. |
| `fecha_resolucion` | TIMESTAMP | Sí | Fecha y hora en que el usuario tomó la decisión. |

---

## 4. Valores de `tipo`

| Valor | HU | Destinatario | ¿Requiere acción? |
|---|---|---|---|
| `Resena_Nueva` | HU-01 | Oferente | **Sí** — Aceptar / Rechazar |
| `Matricula_Validada` | HU-02 | Oferente | No |
| `Matricula_No_Encontrada` | HU-02 | Oferente | No |
| `Matricula_Timeout` | HU-02 | Oferente | No |
| `Matricula_Ya_Fidelizada` | HU-02 | Oferente | No |
| `Matricula_Reemplazo_Solicitado` | HU-02 | **Administrador** | **Sí** — Autorizar / Denegar |

---

## 5. Ciclo de vida del estado

```
                     ┌──────────────┐
     (se crea) ─────▶│  Pendiente   │
                     └──────┬───────┘
                            │
      requiere_accion = TRUE│requiere_accion = FALSE
             ┌──────────────┴───────────────┐
             ▼                              ▼
   ┌──────────────────┐              ┌─────────────┐
   │ Aceptada │ Rechazada│            │    Leida    │
   └──────────────────┘              └─────────────┘
```

- **`Pendiente`** — estado inicial de toda notificación.
- **`Aceptada` / `Rechazada`** — solo para las que tienen `requiere_accion = TRUE`.
  Es el resultado de que el Profesional presione *Aceptar* o *Rechazar* en la
  bandeja.
- **`Leida`** — cierre de las informativas (las de matrícula), cuando el usuario
  abre la bandeja.

**Contador de la campana** = cantidad de filas con
`usuario_id = <logueado> AND estado = 'Pendiente' AND requiere_accion = TRUE`.

---

## 6. Regla de consistencia con `RESENA`

El estado de la notificación y el de la reseña se mueven **en la misma
transacción**, nunca por separado:

| Acción en la bandeja | `NOTIFICACION.estado` | `RESENA.estado` |
|---|---|---|
| Se crea la reseña | `Pendiente` | `Pendiente_Aceptacion` |
| El Profesional Acepta | `Aceptada` | `Aceptada` — se publica y se recalcula el promedio |
| El Profesional Rechaza | `Rechazada` | `Rechazada` — cuenta para la alerta de 5 sobre 10 |

> **Cambio de vocabulario en `RESENA`.** El DER vigente usa `Pendiente_Aprobacion`
> y `Aprobada`, pero tanto la UI (botones **Aceptar** / **Rechazar**) como los
> casos de prueba de QA hablan de **Aceptada**. Se propone renombrar los dos
> valores a `Pendiente_Aceptacion` y `Aceptada`, para que el modelo, la interfaz
> y las pruebas usen la misma palabra. Ver §9.2.

---

## 7. Impacto en las tablas existentes

| Tabla | Cambio propuesto |
|---|---|
| `OFERENTE` | **Eliminar** `notificaciones_email_habilitadas`. El aviso deja de ser por correo, así que el toggle no tiene qué apagar. |
| `RESENA` | **Eliminar** el estado `Pendiente_Verificacion`. Ya no existe el flujo que lo necesitaba: el enlace siempre se envía al canal de contacto que cargó el cliente. |
| `SOLICITUD_RESENA` | Agregar `telefono_cliente VARCHAR(20) NULL` junto a `email_cliente`; `nombre_cliente` pasa a `NOT NULL`; `fecha_expiracion` pasa a `NOT NULL` (7 días). `origen` deja de significar "quién generó el link" y pasa a ser el **canal de envío** (`WhatsApp` / `Email` / `Ambos`). |

Los tres cambios se detallan en la revisión 4 del plan de sprint; se listan acá
solo para que se vean juntos al revisar el DER.

---

## 8. Tablas que va a necesitar HU-02 (adelanto, todavía sin proponer)

Las decisiones tomadas sobre la validación de matrícula implican dos entidades
más, que **no se proponen todavía** porque dependen de definiciones abiertas:

1. **`MATRICULA`** — un Profesional puede tener **más de un oficio** y, por lo
   tanto, más de una matrícula (una de Gasista y una de Aire acondicionado). Hoy
   `OFERENTE.numero_matricula` es una sola columna y no alcanza.
2. **`VALIDACION_MATRICULA`** — historial de intentos. Se decidió guardar
   **todos** los intentos, incluidos los fallidos, con su resultado.

Se proponen en un documento aparte una vez confirmado el punto §9.1.

---

## 9. Preguntas para la PM

1. ¿Se acepta partir `numero_matricula` a una tabla `MATRICULA` propia, para
   soportar más de un oficio por Profesional?
2. ¿Se aprueba renombrar los estados de `RESENA` de `Pendiente_Aprobacion` /
   `Aprobada` a **`Pendiente_Aceptacion` / `Aceptada`**, para alinear el DER con
   la interfaz y con los casos de prueba de QA?
3. ¿Se confirma la baja de `OFERENTE.notificaciones_email_habilitadas` y del
   estado `RESENA.Pendiente_Verificacion`?
4. ¿Las notificaciones informativas de matrícula se persisten en esta tabla o son
   solo mensajes flotantes que no quedan en la base? Los casos de prueba de HU-02
   las describen como flotantes, pero la tarea T04 pide mostrarlas "en el perfil
   del Oferente", lo que sugiere que sí deben persistir.
