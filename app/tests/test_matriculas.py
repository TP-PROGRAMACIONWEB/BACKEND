import time
from datetime import date, timedelta

from app.core.config import settings
from app.models.matricula import EstadoReemplazo, Matricula, PadronMatricula, ResultadoValidacion, ValidacionMatricula
from app.models.usuario import Usuario
from app.services import matriculas as servicio_matriculas
from app.tests.conftest import (
    PASSWORD,
    TIMEOUT_MATRICULA_TEST,
    crear_admin_db,
    crear_categoria_db,
    formulario_registro,
    registrar_y_loguear,
)

VENCIMIENTO_VIGENTE = date.today() + timedelta(days=365)


def crear_oferente(client, db_session, email: str, nombre: str, apellido: str, dni_cuit: str):
    token = registrar_y_loguear(client, email)
    categoria = crear_categoria_db(db_session, nombre=f"Categoria-{email}")
    respuesta = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, dni_cuit=dni_cuit, nombre=f"{nombre} {apellido}"),
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
    token, _ = crear_oferente(client, db_session, "gasista1@test.com", "Maria Clara", "Alessi", "20-11111111-2")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1"},
        headers=auth(token),
    )
    assert respuesta.status_code == 422


def test_numero_corto_multifuente_valida(client, db_session):
    """Ecogas San Francisco usa esquemas cortos (ej. 3753): con el rango 2-10
    pasan el formato y validan si están en el padrón con nombre coincidente."""
    crear_fila_padron(db_session, numero="3753", nombre="JUAN PEREZ")
    token, _ = crear_oferente(client, db_session, "gasista_corto@test.com", "Juan", "Perez", "20-22222222-3")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "3753"},
        headers=auth(token),
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "Validada"


def test_numero_con_letras_da_422(client, db_session):
    token, _ = crear_oferente(client, db_session, "gasista2@test.com", "Maria Clara", "Alessi", "20-11111112-0")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "10000A8919"},
        headers=auth(token),
    )
    assert respuesta.status_code == 422


def test_tipo_invalido_da_422(client, db_session):
    token, _ = crear_oferente(client, db_session, "gasista3@test.com", "Maria Clara", "Alessi", "20-11111113-9")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Plomero", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    assert respuesta.status_code == 422


def test_matricula_existente_da_validada_y_marca_el_perfil_como_verificado(client, db_session):
    crear_fila_padron(db_session)
    token, oferente_id = crear_oferente(client, db_session, "gasista4@test.com", "Maria Clara", "Alessi", "20-11111114-7")

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
    token, _ = crear_oferente(client, db_session, "gasista5@test.com", "Maria Clara", "Alessi", "20-11111115-5")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000000001"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "No_Encontrada"
    assert respuesta.json()["matricula"] is None


def test_misma_matricula_ya_fidelizada_no_modifica_nada(client, db_session):
    crear_fila_padron(db_session)
    token, _ = crear_oferente(client, db_session, "gasista6@test.com", "Maria Clara", "Alessi", "20-11111116-3")
    body = {"tipo_profesional": "Gasista", "numero_matricula": "1000008919"}

    client.post("/api/v1/oferentes/me/matriculas/validaciones", json=body, headers=auth(token))
    respuesta = client.post("/api/v1/oferentes/me/matriculas/validaciones", json=body, headers=auth(token))
    assert respuesta.json()["resultado"] == "Ya_Fidelizada"


def test_matricula_vencida_es_invalida(client, db_session):
    crear_fila_padron(db_session, vencimiento=date(2020, 1, 1))
    token, _ = crear_oferente(client, db_session, "gasista7@test.com", "Maria Clara", "Alessi", "20-11111117-1")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "Vencida"


def test_nombre_que_no_coincide_con_el_padron(client, db_session):
    crear_fila_padron(db_session, nombre="ALESSI MARIA CLARA")
    token, _ = crear_oferente(client, db_session, "gasista8@test.com", "Pedro", "Rodriguez", "20-11111119-8")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "Nombre_No_Coincide"


def test_nombre_con_error_de_tipeo_igual_matchea(client, db_session):
    crear_fila_padron(db_session, nombre="ALESSI MARIA CLARA")
    token, _ = crear_oferente(client, db_session, "gasista9@test.com", "Maria Clara", "Alesi", "20-11111120-1")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "Validada"


def test_matricula_trampa_da_timeout_recien_al_vencer_el_limite(client, db_session):
    token, _ = crear_oferente(client, db_session, "gasista10@test.com", "Maria Clara", "Alessi", "20-11111150-3")
    inicio = time.perf_counter()
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "9999999999"},
        headers=auth(token),
    )
    duracion = time.perf_counter() - inicio
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "Timeout"
    assert TIMEOUT_MATRICULA_TEST <= duracion < TIMEOUT_MATRICULA_TEST + 2


def test_una_consulta_normal_responde_antes_del_limite(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "matricula_timeout_segundos", 30)
    crear_fila_padron(db_session)
    token, _ = crear_oferente(client, db_session, "rapida@test.com", "Maria Clara", "Alessi", "30111119")
    inicio = time.perf_counter()
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "Validada"
    assert time.perf_counter() - inicio < 5


def test_padron_que_no_responde_da_timeout_con_cualquier_matricula(client, db_session, monkeypatch):
    """El límite aplica a toda consulta, no solo a la matrícula trampa."""
    crear_fila_padron(db_session)
    token, _ = crear_oferente(client, db_session, "lento@test.com", "Maria Clara", "Alessi", "30111120")

    def padron_colgado(bind, tipo_profesional, numero_matricula, cancelar):
        cancelar.wait()

    monkeypatch.setattr(servicio_matriculas, "_consultar_padron", padron_colgado)
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "Timeout"
    assert respuesta.json()["matricula"] is None


def test_con_la_trampa_deshabilitada_el_numero_trampa_no_existe_en_el_padron(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "matricula_trap_habilitada", False)
    token, _ = crear_oferente(client, db_session, "sintrampa@test.com", "Maria Clara", "Alessi", "30111121")
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "9999999999"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "No_Encontrada"


def test_despues_de_un_timeout_se_puede_reintentar(client, db_session):
    crear_fila_padron(db_session)
    token, oferente_id = crear_oferente(client, db_session, "reintento@test.com", "Maria Clara", "Alessi", "30111122")
    url = "/api/v1/oferentes/me/matriculas/validaciones"

    timeout = client.post(url, json={"tipo_profesional": "Gasista", "numero_matricula": "9999999999"}, headers=auth(token))
    assert timeout.json()["resultado"] == "Timeout"
    assert client.get(f"/api/v1/oferentes/{oferente_id}").json()["tiene_matricula_validada"] is False

    reintento = client.post(url, json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"}, headers=auth(token))
    assert reintento.json()["resultado"] == "Validada"

    historial = client.get(url, headers=auth(token)).json()
    assert [fila["resultado"] for fila in historial] == ["Validada", "Timeout"]


def test_historial_incluye_todos_los_intentos_incluidos_los_fallidos(client, db_session):
    crear_fila_padron(db_session)
    token, _ = crear_oferente(client, db_session, "gasista11@test.com", "Maria Clara", "Alessi", "20-11111151-1")

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
    crear_fila_padron(db_session, tipo="Aire acondicionado", numero="10000089", nombre="ALESSI MARIA CLARA")
    token, _ = crear_oferente(client, db_session, "gasista12@test.com", "Maria Clara", "Alessi", "20-11111153-8")

    r1 = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    r2 = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Aire acondicionado", "numero_matricula": "10000089"},
        headers=auth(token),
    )
    assert r1.json()["resultado"] == "Validada"
    assert r2.json()["resultado"] == "Validada"

    matriculas = client.get("/api/v1/oferentes/me/matriculas", headers=auth(token)).json()
    assert {m["tipo_profesional"] for m in matriculas} == {"Gasista", "Aire acondicionado"}


def test_reemplazo_solicitado_no_cambia_la_matricula_vigente_y_avisa_al_admin(client, db_session):
    crear_fila_padron(db_session, numero="1000008919", nombre="ALESSI MARIA CLARA")
    crear_fila_padron(db_session, numero="1000004305", nombre="ALESSI MARIA CLARA")
    token, _ = crear_oferente(client, db_session, "gasista13@test.com", "Maria Clara", "Alessi", "20-11111154-6")
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
    token, _ = crear_oferente(client, db_session, "gasista14@test.com", "Maria Clara", "Alessi", "20-11111155-4")
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
    token, _ = crear_oferente(client, db_session, "gasista15@test.com", "Maria Clara", "Alessi", "20-11111156-2")
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


def test_sin_perfil_de_oferente_da_403_registro_incompleto(client, db_session):
    token = registrar_y_loguear(client, "sinperfil@test.com")
    respuesta = client.get("/api/v1/oferentes/me/matriculas", headers=auth(token))
    assert respuesta.status_code == 403
    assert respuesta.json()["detail"]["codigo"] == "registro_incompleto"


def test_requiere_autenticacion(client):
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones", json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"}
    )
    assert respuesta.status_code == 401


# --- Textos de los criterios de aceptación ------------------------------------

MENSAJE_CA04 = "Su matrícula no fue encontrada en el padrón, revise los datos y vuelva a intentarlo"


def test_los_mensajes_son_los_literales_de_los_criterios_de_aceptacion(client, db_session):
    crear_fila_padron(db_session)
    token, _ = crear_oferente(client, db_session, "textos@test.com", "Maria Clara", "Alessi", "20-11111157-0")
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
    token, _ = crear_oferente(client, db_session, "ca04@test.com", "Maria Clara", "Alessi", "20-11111158-9")
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
    token, _ = crear_oferente(client, db_session, "pisado@test.com", "Maria Clara", "Alessi", "20-11111159-7")
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


# --- CA08: campo Fidelizado y tabla intermedia --------------------------------


def _perfil(client, token: str) -> dict:
    return client.get("/api/v1/auth/me", headers=auth(token)).json()


def test_fidelizado_arranca_en_falso_y_pasa_a_verdadero_al_validar(client, db_session):
    crear_fila_padron(db_session)
    token, oferente_id = crear_oferente(client, db_session, "bit1@test.com", "Maria Clara", "Alessi", "30222221")
    assert _perfil(client, token)["fidelizado"] is False
    assert db_session.query(Matricula).count() == 0

    client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )

    assert _perfil(client, token)["fidelizado"] is True
    assert db_session.get(Usuario, oferente_id).fidelizado is True
    # La tabla intermedia: una fila que une al usuario con su matrícula.
    fila = db_session.query(Matricula).one()
    assert (fila.oferente_id, fila.tipo_profesional, fila.numero_matricula) == (oferente_id, "Gasista", "1000008919")


def test_un_intento_fallido_no_fideliza_ni_toca_la_tabla_intermedia(client, db_session):
    crear_fila_padron(db_session, numero="1000008919", vencimiento=date(2020, 1, 1))
    crear_fila_padron(db_session, numero="1000004305", nombre="ROMERO TATIANA")
    token, oferente_id = crear_oferente(client, db_session, "bit2@test.com", "Maria Clara", "Alessi", "30222222")
    url = "/api/v1/oferentes/me/matriculas/validaciones"

    esperados = {
        "1000000001": "No_Encontrada",
        "9999999999": "Timeout",
        "1000008919": "Vencida",
        "1000004305": "Nombre_No_Coincide",
    }
    for numero, resultado in esperados.items():
        respuesta = client.post(url, json={"tipo_profesional": "Gasista", "numero_matricula": numero}, headers=auth(token))
        assert respuesta.json()["resultado"] == resultado

    assert _perfil(client, token)["fidelizado"] is False
    assert db_session.query(Matricula).count() == 0
    assert client.get(f"/api/v1/oferentes/{oferente_id}").json()["tiene_matricula_validada"] is False


def test_revalidar_la_misma_matricula_no_modifica_el_perfil(client, db_session):
    crear_fila_padron(db_session)
    token, oferente_id = crear_oferente(client, db_session, "bit3@test.com", "Maria Clara", "Alessi", "30222223")
    body = {"tipo_profesional": "Gasista", "numero_matricula": "1000008919"}
    url = "/api/v1/oferentes/me/matriculas/validaciones"

    client.post(url, json=body, headers=auth(token))
    antes = client.get("/api/v1/oferentes/me/matriculas", headers=auth(token)).json()
    perfil_antes = client.get(f"/api/v1/oferentes/{oferente_id}").json()

    assert client.post(url, json=body, headers=auth(token)).json()["resultado"] == "Ya_Fidelizada"

    assert client.get("/api/v1/oferentes/me/matriculas", headers=auth(token)).json() == antes
    assert client.get(f"/api/v1/oferentes/{oferente_id}").json() == perfil_antes
    assert _perfil(client, token)["fidelizado"] is True


def test_el_estado_verificado_persiste_en_una_sesion_nueva(client, db_session):
    crear_fila_padron(db_session)
    token, oferente_id = crear_oferente(client, db_session, "bit4@test.com", "Maria Clara", "Alessi", "30222224")
    client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "1000008919"},
        headers=auth(token),
    )
    client.post("/api/v1/auth/logout", headers=auth(token))

    token_nuevo = client.post("/api/v1/auth/login", json={"email": "bit4@test.com", "password": PASSWORD}).json()["access_token"]
    assert _perfil(client, token_nuevo)["fidelizado"] is True
    assert client.get(f"/api/v1/oferentes/{oferente_id}").json()["tiene_matricula_validada"] is True


# --- CA01/CA02: tipos, dígitos y Aire acondicionado ---------------------------


def test_tipos_en_orden_alfabetico_con_sus_digitos(client, db_session):
    token = registrar_y_loguear(client, "tipos@test.com")
    respuesta = client.get("/api/v1/oferentes/me/matriculas/tipos", headers=auth(token))
    assert respuesta.status_code == 200
    assert respuesta.json() == [
        {"tipo_profesional": "Aire acondicionado", "digitos": 8, "digitos_min": 8},
        {"tipo_profesional": "Gasista", "digitos": 10, "digitos_min": 2},
    ]


def test_el_422_indica_cuantos_digitos_se_esperan(client, db_session):
    token, _ = crear_oferente(client, db_session, "digitos@test.com", "Maria Clara", "Alessi", "30222225")
    url = "/api/v1/oferentes/me/matriculas/validaciones"

    aire = client.post(url, json={"tipo_profesional": "Aire acondicionado", "numero_matricula": "123456789"}, headers=auth(token))
    gasista = client.post(url, json={"tipo_profesional": "Gasista", "numero_matricula": "12345678901"}, headers=auth(token))

    assert aire.status_code == 422 and "Debe ingresar 8 dígitos" in aire.text
    assert gasista.status_code == 422 and "Debe ingresar entre 2 y 10 dígitos" in gasista.text


def test_aire_acondicionado_valida_contra_su_propio_padron(client, db_session):
    crear_fila_padron(db_session, tipo="Aire acondicionado", numero="28408435", nombre="ABATEDAGA MARTIN")
    # Mismo número cargado como Gasista no tiene que servir para el otro oficio.
    token, _ = crear_oferente(client, db_session, "aire@test.com", "Martin", "Abatedaga", "30222226")
    url = "/api/v1/oferentes/me/matriculas/validaciones"

    trampa = client.post(url, json={"tipo_profesional": "Aire acondicionado", "numero_matricula": "99999999"}, headers=auth(token))
    valida = client.post(url, json={"tipo_profesional": "Aire acondicionado", "numero_matricula": "28408435"}, headers=auth(token))

    assert trampa.json()["resultado"] == "Timeout"
    assert valida.json()["resultado"] == "Validada"
    assert valida.json()["matricula"]["tipo_profesional"] == "Aire acondicionado"


def test_el_422_trae_el_campo_y_el_texto_sin_prefijo_de_pydantic(client, db_session):
    token, _ = crear_oferente(client, db_session, "formato422@test.com", "Maria Clara", "Alessi", "30222227")
    url = "/api/v1/oferentes/me/matriculas/validaciones"

    corto = client.post(url, json={"tipo_profesional": "Gasista", "numero_matricula": "1"}, headers=auth(token))
    vacio = client.post(url, json={"tipo_profesional": "Aire acondicionado", "numero_matricula": ""}, headers=auth(token))
    letras = client.post(url, json={"tipo_profesional": "Gasista", "numero_matricula": "10000A8919"}, headers=auth(token))

    assert corto.status_code == 422
    assert corto.json()["detail"][0]["msg"] == "Debe ingresar entre 2 y 10 dígitos"
    assert corto.json()["errores"] == [{"campo": "numero_matricula", "codigo": "digitos_invalidos"}]
    assert vacio.json()["detail"][0]["msg"] == "Debe ingresar 8 dígitos"
    assert letras.json()["errores"] == [{"campo": "numero_matricula", "codigo": "solo_digitos"}]


def test_ya_fidelizada_tiene_prioridad_sobre_el_vencimiento(client, db_session):
    crear_fila_padron(db_session)
    token, _ = crear_oferente(client, db_session, "yafid@test.com", "Maria Clara", "Alessi", "30222228")
    url = "/api/v1/oferentes/me/matriculas/validaciones"
    cuerpo = {"tipo_profesional": "Gasista", "numero_matricula": "1000008919"}
    assert client.post(url, json=cuerpo, headers=auth(token)).json()["resultado"] == "Validada"

    fila = db_session.query(PadronMatricula).first()
    fila.fecha_vencimiento = date(2020, 1, 1)
    db_session.commit()

    assert client.post(url, json=cuerpo, headers=auth(token)).json()["resultado"] == "Ya_Fidelizada"


def test_las_esperas_de_la_trampa_estan_acotadas(client, db_session, monkeypatch):
    import threading

    monkeypatch.setattr(servicio_matriculas, "_ESPERAS_TRAMPA", threading.BoundedSemaphore(0))
    token, _ = crear_oferente(client, db_session, "tope@test.com", "Maria Clara", "Alessi", "30222229")
    inicio = time.monotonic()
    respuesta = client.post(
        "/api/v1/oferentes/me/matriculas/validaciones",
        json={"tipo_profesional": "Gasista", "numero_matricula": "9999999999"},
        headers=auth(token),
    )
    assert respuesta.json()["resultado"] == "No_Encontrada"
    assert time.monotonic() - inicio < TIMEOUT_MATRICULA_TEST
