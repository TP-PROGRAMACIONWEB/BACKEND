import time
from datetime import date, timedelta

from app.models.matricula import EstadoReemplazo, Matricula, PadronMatricula, ResultadoValidacion, ValidacionMatricula
from app.tests.conftest import PASSWORD, crear_admin_db, crear_categoria_db, registrar_y_loguear

VENCIMIENTO_VIGENTE = date.today() + timedelta(days=365)


def crear_oferente(client, db_session, email: str, nombre: str, apellido: str, dni_cuit: str):
    token = registrar_y_loguear(client, email)
    categoria = crear_categoria_db(db_session, nombre=f"Categoria-{email}")
    respuesta = client.post(
        "/api/v1/oferentes",
        json={
            "nombre": nombre,
            "apellido": apellido,
            "dni_cuit": dni_cuit,
            "telefono": "+54 3564 400000",
            "categoria_id": categoria.id_categoria,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respuesta.status_code == 201, respuesta.text
    return token, respuesta.json()["id_oferente"]


def crear_fila_padron(
    db_session,
    tipo="Gasista",
    numero="1000008919",
    nombre="ALESSI MARIA CLARA",
    categoria="Primera",
    vencimiento=VENCIMIENTO_VIGENTE,
) -> PadronMatricula:
    fila = PadronMatricula(
        tipo_profesional=tipo, numero_matricula=numero, nombre_matriculado=nombre, categoria=categoria, fecha_vencimiento=vencimiento
    )
    db_session.add(fila)
    db_session.commit()
    db_session.refresh(fila)
    return fila


def login_admin(client, db_session, email: str = "admin@test.com") -> str:
    crear_admin_db(db_session, email=email)
    respuesta = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return respuesta.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_numero_con_cantidad_de_digitos_incorrecta_da_422(client, db_session):
    token, _ = crear_oferente(client, db_session, "gasista1@test.com", "Maria Clara", "Alessi", "20-11111111-1")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "123"},
        headers=auth(token),
    )
    assert respuesta.status_code == 422


def test_numero_con_letras_da_422(client, db_session):
    token, _ = crear_oferente(client, db_session, "gasista2@test.com", "Maria Clara", "Alessi", "20-11111111-2")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "10000A8919"},
        headers=auth(token),
    )
    assert respuesta.status_code == 422


def test_tipo_invalido_da_422(client, db_session):
    token, _ = crear_oferente(client, db_session, "gasista3@test.com", "Maria Clara", "Alessi", "20-11111111-3")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Plomero", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    assert respuesta.status_code == 422


def test_matricula_existente_da_validada_y_marca_el_perfil_como_verificado(client, db_session):
    crear_fila_padron(db_session)
    token, oferente_id = crear_oferente(client, db_session, "gasista4@test.com", "Maria Clara", "Alessi", "20-11111111-4")

    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["resultado"] == "Validada"
    assert cuerpo["matricula"]["numero_matricula"] == "1000008919"

    perfil = client.get(f"/api/v1/oferentes/{oferente_id}").json()
    assert perfil["tiene_matricula_validada"] is True


def test_matricula_inexistente_da_no_encontrada(client, db_session):
    token, _ = crear_oferente(client, db_session, "gasista5@test.com", "Maria Clara", "Alessi", "20-11111111-5")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000000001"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "No_Encontrada"
    assert respuesta.json()["matricula"] is None


def test_misma_matricula_ya_fidelizada_no_modifica_nada(client, db_session):
    crear_fila_padron(db_session)
    token, _ = crear_oferente(client, db_session, "gasista6@test.com", "Maria Clara", "Alessi", "20-11111111-6")
    body = {"tipo_profesional": "Gasista", "numero_matricula": "1000008919"}

    client.post("/api/v1/oferentes/me/matriculas/validaciones", json=body, headers=auth(token))
    respuesta = client.post("/api/v1/oferentes/me/matriculas/validaciones", json=body, headers=auth(token))
    assert respuesta.json()["resultado"] == "Ya_Fidelizada"


def test_matricula_vencida_es_invalida(client, db_session):
    crear_fila_padron(db_session, vencimiento=date(2020, 1, 1))
    token, _ = crear_oferente(client, db_session, "gasista7@test.com", "Maria Clara", "Alessi", "20-11111111-7")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "Vencida"


def test_nombre_que_no_coincide_con_el_padron(client, db_session):
    crear_fila_padron(db_session, nombre="ALESSI MARIA CLARA")
    token, _ = crear_oferente(client, db_session, "gasista8@test.com", "Pedro", "Rodriguez", "20-11111111-8")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "Nombre_No_Coincide"


def test_nombre_con_error_de_tipeo_igual_matchea(client, db_session):
    crear_fila_padron(db_session, nombre="ALESSI MARIA CLARA")
    token, _ = crear_oferente(client, db_session, "gasista9@test.com", "Maria Clara", "Alesi", "20-11111111-9")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "Validada"


def test_matricula_trampa_da_timeout_sin_demora_real(client, db_session):
    token, _ = crear_oferente(client, db_session, "gasista10@test.com", "Maria Clara", "Alessi", "20-11111111-10")
    inicio = time.perf_counter()
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "9999999999"},
        headers=auth(token),
    )
    duracion = time.perf_counter() - inicio
    assert respuesta.json()["resultado"] == "Timeout"
    assert duracion < 2


def test_historial_incluye_todos_los_intentos_incluidos_los_fallidos(client, db_session):
    crear_fila_padron(db_session)
    token, _ = crear_oferente(client, db_session, "gasista11@test.com", "Maria Clara", "Alessi", "20-11111111-11")

    client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000000001"},
        headers=auth(token),
    )
    client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )

    historial = client.get("/api/v1/oferentes/me/matriculas/validaciones", headers=auth(token)).json()
    resultados = {fila["resultado"] for fila in historial}
    assert resultados == {"No_Encontrada", "Validada"}
    assert len(historial) == 2


def test_un_oferente_puede_fidelizar_dos_oficios_distintos(client, db_session):
    crear_fila_padron(db_session, tipo="Gasista", numero="1000008919", nombre="ALESSI MARIA CLARA")
    crear_fila_padron(db_session, tipo="Aire acondicionado", numero="100000891", nombre="ALESSI MARIA CLARA")
    token, _ = crear_oferente(client, db_session, "gasista12@test.com", "Maria Clara", "Alessi", "20-11111111-12")

    r1 = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    r2 = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Aire acondicionado", "numero_matricula": "100000891"},
        headers=auth(token),
    )
    assert r1.json()["resultado"] == "Validada"
    assert r2.json()["resultado"] == "Validada"

    matriculas = client.get("/api/v1/oferentes/me/matriculas", headers=auth(token)).json()
    assert {m["tipo_profesional"] for m in matriculas} == {"Gasista", "Aire acondicionado"}


def test_reemplazo_solicitado_no_cambia_la_matricula_vigente_y_avisa_al_admin(client, db_session):
    crear_fila_padron(db_session, numero="1000008919", nombre="ALESSI MARIA CLARA")
    crear_fila_padron(db_session, numero="1000004305", nombre="ALESSI MARIA CLARA")
    token, _ = crear_oferente(client, db_session, "gasista13@test.com", "Maria Clara", "Alessi", "20-11111111-13")
    admin_token = login_admin(client, db_session, "admin13@test.com")

    client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000004305"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "Reemplazo_Solicitado"

    matriculas = client.get("/api/v1/oferentes/me/matriculas", headers=auth(token)).json()
    assert matriculas[0]["numero_matricula"] == "1000008919"  # sigue vigente la vieja

    notificaciones_admin = client.get("/api/v1/notificaciones", headers=auth(admin_token)).json()
    pendientes = [n for n in notificaciones_admin if n["tipo"] == "Matricula_Reemplazo_Solicitado"]
    assert len(pendientes) == 1
    assert pendientes[0]["requiere_accion"] is True
    assert pendientes[0]["numero_matricula_actual"] == "1000008919"
    assert pendientes[0]["numero_matricula_solicitada"] == "1000004305"


def test_admin_autoriza_el_reemplazo_y_actualiza_la_matricula(client, db_session):
    crear_fila_padron(db_session, numero="1000008919", nombre="ALESSI MARIA CLARA")
    crear_fila_padron(db_session, numero="1000004305", nombre="ALESSI MARIA CLARA")
    token, _ = crear_oferente(client, db_session, "gasista14@test.com", "Maria Clara", "Alessi", "20-11111111-14")
    admin_token = login_admin(client, db_session, "admin14@test.com")

    client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000004305"},
        headers=auth(token),
    )
    validacion_id = (
        db_session.query(ValidacionMatricula).filter(ValidacionMatricula.resultado == ResultadoValidacion.REEMPLAZO_SOLICITADO).first().id_validacion
    )

    respuesta = client.patch(
        f"/api/v1/admin/matriculas/reemplazos/{validacion_id}", json={"autorizar": True}, headers=auth(admin_token)
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["matricula"]["numero_matricula"] == "1000004305"

    matriculas = client.get("/api/v1/oferentes/me/matriculas", headers=auth(token)).json()
    assert matriculas[0]["numero_matricula"] == "1000004305"

    notificaciones_oferente = client.get("/api/v1/notificaciones", headers=auth(token)).json()
    assert any(n["tipo"] == "Matricula_Reemplazo_Resuelto" for n in notificaciones_oferente)

    # Ya resuelto: un segundo intento sobre el mismo id no puede repetirse.
    repetido = client.patch(
        f"/api/v1/admin/matriculas/reemplazos/{validacion_id}", json={"autorizar": True}, headers=auth(admin_token)
    )
    assert repetido.status_code == 400


def test_admin_deniega_el_reemplazo_y_no_toca_la_matricula(client, db_session):
    crear_fila_padron(db_session, numero="1000008919", nombre="ALESSI MARIA CLARA")
    crear_fila_padron(db_session, numero="1000004305", nombre="ALESSI MARIA CLARA")
    token, _ = crear_oferente(client, db_session, "gasista15@test.com", "Maria Clara", "Alessi", "20-11111111-15")
    admin_token = login_admin(client, db_session, "admin15@test.com")

    client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000004305"},
        headers=auth(token),
    )
    validacion_id = (
        db_session.query(ValidacionMatricula).filter(ValidacionMatricula.resultado == ResultadoValidacion.REEMPLAZO_SOLICITADO).first().id_validacion
    )

    respuesta = client.patch(
        f"/api/v1/admin/matriculas/reemplazos/{validacion_id}", json={"autorizar": False}, headers=auth(admin_token)
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["matricula"] is None

    matriculas = client.get("/api/v1/oferentes/me/matriculas", headers=auth(token)).json()
    assert matriculas[0]["numero_matricula"] == "1000008919"


def test_sin_perfil_de_oferente_da_404(client, db_session):
    token = registrar_y_loguear(client, "sinperfil@test.com")
    respuesta = client.get("/api/v1/oferentes/me/matriculas", headers=auth(token))
    assert respuesta.status_code == 404


def test_requiere_autenticacion(client):
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones", json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"}
    )
    assert respuesta.status_code == 401


# --- Textos de los criterios de aceptación ------------------------------------

MENSAJE_CA04 = "Su matrícula no fue encontrada en el padrón, revise los datos y vuelva a intentarlo"


def test_los_mensajes_son_los_literales_de_los_criterios_de_aceptacion(client, db_session):
    crear_fila_padron(db_session)
    token, _ = crear_oferente(client, db_session, "textos@test.com", "Maria Clara", "Alessi", "20-11111111-16")
    url = "/api/v1/oferentes/me/matriculas/validaciones"

    def validar(numero):
        return client.post(url, json={"tipo_profesional": "Gasista", "numero_matricula": numero}, headers=auth(token)).json()

    assert validar("1000000001")["mensaje"] == MENSAJE_CA04
    assert validar("9999999999")["mensaje"] == "No pudimos procesar tu validación en este momento, intentá nuevamente más tarde"
    assert validar("1000008919")["mensaje"] == "Su matrícula fue fidelizada exitosamente"
    assert validar("1000008919")["mensaje"] == "Su matrícula ya fue fidelizada"


def test_vencida_y_nombre_no_coincide_muestran_el_texto_del_ca04_pero_guardan_el_motivo(client, db_session):
    crear_fila_padron(db_session, numero="1000008919", vencimiento=date(2020, 1, 1))
    crear_fila_padron(db_session, numero="1000004305", nombre="ROMERO TATIANA")
    token, _ = crear_oferente(client, db_session, "ca04@test.com", "Maria Clara", "Alessi", "20-11111111-17")
    url = "/api/v1/oferentes/me/matriculas/validaciones"

    vencida = client.post(url, json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"}, headers=auth(token)).json()
    otro_nombre = client.post(url, json={"tipo_profesional": "Gasista", "numero_matricula": "1000004305"}, headers=auth(token)).json()

    assert vencida["resultado"] == "Vencida" and vencida["mensaje"] == MENSAJE_CA04
    assert otro_nombre["resultado"] == "Nombre_No_Coincide" and otro_nombre["mensaje"] == MENSAJE_CA04
    # La notificación de la campana lleva el mismo texto.
    mensajes = {n["mensaje"] for n in client.get("/api/v1/notificaciones", headers=auth(token)).json()}
    assert mensajes == {MENSAJE_CA04}


# --- Pedido de reemplazo pisado por uno más nuevo -----------------------------


def test_un_reemplazo_pisado_cierra_la_notificacion_del_admin(client, db_session):
    for numero in ("1000008919", "1000004305", "1000002233"):
        crear_fila_padron(db_session, numero=numero)
    token, _ = crear_oferente(client, db_session, "pisado@test.com", "Maria Clara", "Alessi", "20-11111111-18")
    admin_token = login_admin(client, db_session, "adminpisado@test.com")
    url = "/api/v1/oferentes/me/matriculas/validaciones"

    for numero in ("1000008919", "1000004305", "1000002233"):
        client.post(url, json={"tipo_profesional": "Gasista", "numero_matricula": numero}, headers=auth(token))

    pedidos = [
        n for n in client.get("/api/v1/notificaciones", headers=auth(admin_token)).json() if n["tipo"] == "Matricula_Reemplazo_Solicitado"
    ]
    estados = {n["numero_matricula_solicitada"]: n["estado"] for n in pedidos}
    assert estados == {"1000004305": "Leida", "1000002233": "Pendiente"}
    # El contador del Administrador solo cuenta el pedido vigente.
    assert client.get("/api/v1/notificaciones/contador", headers=auth(admin_token)).json()["pendientes_de_accion"] == 1

    pisado_id = next(n["validacion_matricula_id"] for n in pedidos if n["numero_matricula_solicitada"] == "1000004305")
    respuesta = client.patch(f"/api/v1/admin/matriculas/reemplazos/{pisado_id}", json={"autorizar": True}, headers=auth(admin_token))
    assert respuesta.status_code == 400
    assert "más nuevo" in respuesta.json()["detail"]
