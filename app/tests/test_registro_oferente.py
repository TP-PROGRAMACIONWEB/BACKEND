"""HU-04 — Registro de Profesional: formulario, validaciones, guard, perfiles y edición."""

from datetime import date, timedelta

from app.models.matricula import Matricula
from app.models.oferente import Oferente
from app.models.usuario import EstadoCuenta, Usuario
from app.schemas.oferente import cuit_valido, normalizar_dni_cuit
from app.tests.conftest import crear_admin_db, crear_categoria_db, crear_oferente_completo, formulario_registro, registrar_y_loguear


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _codigos(respuesta) -> dict:
    """Mapa campo -> código de los errores de validación."""
    return {error["campo"]: error["codigo"] for error in respuesta.json()["errores"]}


# --- Validadores puros -------------------------------------------------------


def test_cuit_con_digito_verificador_correcto_es_valido():
    assert cuit_valido("20301112220")
    assert not cuit_valido("20301112223")


def test_dni_y_cuit_se_guardan_solo_con_digitos():
    assert normalizar_dni_cuit("30.111.222") == "30111222"
    assert normalizar_dni_cuit("20-30111222-0") == "20301112220"


# --- Catálogo ----------------------------------------------------------------


def test_catalogo_trae_categorias_activas_experiencia_dias_y_limites(client, db_session):
    crear_categoria_db(db_session, nombre="Electricista")
    respuesta = client.get("/api/v1/catalogos/registro-oferente")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert [c["nombre"] for c in cuerpo["categorias"]] == ["Electricista"]
    assert [e["codigo"] for e in cuerpo["experiencia"]] == ["MENOS_1", "1_A_2", "3_A_5", "6_A_10", "MAS_10"]
    assert [d["dia"] for d in cuerpo["dias"]] == [1, 2, 3, 4, 5, 6, 7]
    assert cuerpo["horario_default"] == {"apertura": "08:00", "cierre": "18:00"}
    assert cuerpo["limites"] == {"trabajos": 5, "fotos_por_trabajo": 5, "tamano_maximo_mb": 5}


def test_catalogo_no_lista_categorias_inactivas(client, db_session):
    from app.models.categoria import EstadoCategoria

    categoria = crear_categoria_db(db_session, nombre="Plomero")
    categoria.estado = EstadoCategoria.INACTIVA
    db_session.commit()

    assert client.get("/api/v1/catalogos/registro-oferente").json()["categorias"] == []


# --- /auth/me: requiere_registro (CA01) --------------------------------------


def test_me_marca_requiere_registro_para_oferente_sin_perfil(client):
    token = registrar_y_loguear(client, "nuevo@test.com")
    assert client.get("/api/v1/auth/me", headers=_auth(token)).json()["requiere_registro"] is True


def test_me_no_requiere_registro_con_perfil_creado(client, db_session):
    token, _ = crear_oferente_completo(client, db_session, email="listo@test.com", dni_cuit="20-30111222-0")
    assert client.get("/api/v1/auth/me", headers=_auth(token)).json()["requiere_registro"] is False


def test_me_no_requiere_registro_para_administrador(client, db_session):
    crear_admin_db(db_session, email="admin.me@test.com")
    token = client.post("/api/v1/auth/login", json={"email": "admin.me@test.com", "password": "Test1234!"}).json()["access_token"]
    assert client.get("/api/v1/auth/me", headers=_auth(token)).json()["requiere_registro"] is False


# --- POST /oferentes: alta ---------------------------------------------------


def test_registro_completo_valido_da_201_y_crea_perfil_y_dias(client, db_session):
    from app.models.oferente_dia_atencion import OferenteDiaAtencion

    token = registrar_y_loguear(client, "alta@test.com")
    categoria = crear_categoria_db(db_session, nombre="Gasista")

    respuesta = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, dni_cuit="27-30111222-5", dias_atencion=[5, 1, 3]),
        headers=_auth(token),
    )

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["dni_cuit"] == "27301112225"
    assert cuerpo["dias_atencion"] == [1, 3, 5]
    assert cuerpo["hora_inicio_atencion"] == "08:00"
    assert cuerpo["hora_fin_atencion"] == "18:00"
    assert cuerpo["estado_verificacion"] == "Pendiente"
    assert db_session.query(OferenteDiaAtencion).filter(OferenteDiaAtencion.oferente_id == cuerpo["id_oferente"]).count() == 3


def test_body_vacio_devuelve_todos_los_obligatorios_juntos(client, db_session):
    token = registrar_y_loguear(client, "vacio@test.com")

    respuesta = client.post("/api/v1/oferentes", json={}, headers=_auth(token))

    assert respuesta.status_code == 422
    codigos = _codigos(respuesta)
    assert codigos == {
        "nombre": "requerido",
        "dni_cuit": "requerido",
        "telefono": "requerido",
        "categoria_id": "requerido",
        "dias_atencion": "dias_requeridos",
        "hora_inicio_atencion": "requerido",
        "hora_fin_atencion": "requerido",
    }


def test_dni_de_9_o_10_digitos_o_cuit_mal_verificado_es_invalido(client, db_session):
    token = registrar_y_loguear(client, "dni@test.com")
    categoria = crear_categoria_db(db_session, nombre="Plomero")

    for dni in ("123456789", "1234567890", "20-30111222-3", "abcdefgh"):
        respuesta = client.post(
            "/api/v1/oferentes",
            json=formulario_registro(categoria.id_categoria, dni_cuit=dni),
            headers=_auth(token),
        )
        assert _codigos(respuesta) == {"dni_cuit": "dni_cuit_invalido"}, dni


def test_dni_de_7_digitos_es_valido(client, db_session):
    token = registrar_y_loguear(client, "dni7@test.com")
    categoria = crear_categoria_db(db_session, nombre="Carpintero")

    respuesta = client.post("/api/v1/oferentes", json=formulario_registro(categoria.id_categoria, dni_cuit="1234567"), headers=_auth(token))

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["dni_cuit"] == "1234567"


def test_telefono_con_0_15_54_o_letras_es_invalido(client, db_session):
    token = registrar_y_loguear(client, "tel@test.com")
    categoria = crear_categoria_db(db_session, nombre="Albañil")

    for telefono in ("0351-6924551", "351-156924551", "+543516924551", "35a4-692455"):
        respuesta = client.post(
            "/api/v1/oferentes",
            json=formulario_registro(categoria.id_categoria, telefono=telefono),
            headers=_auth(token),
        )
        assert _codigos(respuesta) == {"telefono": "telefono_invalido"}, telefono


def test_horarios_en_medias_horas_y_cierre_posterior(client, db_session):
    token = registrar_y_loguear(client, "horas@test.com")
    categoria = crear_categoria_db(db_session, nombre="Pintor")

    casos = [
        {"hora_inicio_atencion": "08:15"},
        {"hora_inicio_atencion": "08:00", "hora_fin_atencion": "08:00"},
        {"hora_inicio_atencion": "18:00", "hora_fin_atencion": "08:00"},
        {"hora_fin_atencion": "18:10"},
    ]
    for extra in casos:
        respuesta = client.post(
            "/api/v1/oferentes",
            json=formulario_registro(categoria.id_categoria, **extra),
            headers=_auth(token),
        )
        assert respuesta.status_code == 422, extra
        assert "horario_invalido" in _codigos(respuesta).values(), extra


def test_dias_repetidos_o_fuera_de_rango_son_invalidos(client, db_session):
    token = registrar_y_loguear(client, "dias@test.com")
    categoria = crear_categoria_db(db_session, nombre="Techista")

    for dias in ([1, 1], [8], []):
        respuesta = client.post(
            "/api/v1/oferentes",
            json=formulario_registro(categoria.id_categoria, dias_atencion=dias),
            headers=_auth(token),
        )
        assert respuesta.status_code == 422, dias
        assert _codigos(respuesta)["dias_atencion"] in ("dias_invalidos", "dias_requeridos")


def test_guardia_se_descarta_si_el_toggle_esta_apagado(client, db_session):
    token = registrar_y_loguear(client, "guardia@test.com")
    categoria = crear_categoria_db(db_session, nombre="Cerrajero")

    respuesta = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, disponible_emergencia=False, info_guardia="Atiendo de noche"),
        headers=_auth(token),
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["info_guardia"] is None


def test_textos_opcionales_vacios_se_guardan_como_null(client, db_session):
    token = registrar_y_loguear(client, "vacios@test.com")
    categoria = crear_categoria_db(db_session, nombre="Vidriero")

    respuesta = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, especialidad="   ", info_guardia="", disponible_emergencia=True),
        headers=_auth(token),
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["especialidad"] is None
    assert respuesta.json()["info_guardia"] is None


def test_especialidad_de_mas_de_100_caracteres_es_invalida(client, db_session):
    token = registrar_y_loguear(client, "larga@test.com")
    categoria = crear_categoria_db(db_session, nombre="Soldador")

    respuesta = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, especialidad="x" * 101),
        headers=_auth(token),
    )

    assert _codigos(respuesta) == {"especialidad": "longitud_maxima"}


def test_experiencia_fuera_del_catalogo_es_invalida(client, db_session):
    token = registrar_y_loguear(client, "exp@test.com")
    categoria = crear_categoria_db(db_session, nombre="Jardinero")

    respuesta = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, experiencia="20_ANOS"),
        headers=_auth(token),
    )

    assert _codigos(respuesta) == {"experiencia": "experiencia_invalida"}


def test_categoria_inexistente_o_inactiva_es_invalida(client, db_session):
    from app.models.categoria import EstadoCategoria

    token = registrar_y_loguear(client, "categoria@test.com")
    inactiva = crear_categoria_db(db_session, nombre="Yesero")
    inactiva.estado = EstadoCategoria.INACTIVA
    db_session.commit()

    for categoria_id in (inactiva.id_categoria, 9999):
        respuesta = client.post("/api/v1/oferentes", json=formulario_registro(categoria_id), headers=_auth(token))
        assert _codigos(respuesta) == {"categoria_id": "categoria_invalida"}


def test_campo_desconocido_como_numero_de_matricula_da_422(client, db_session):
    token = registrar_y_loguear(client, "matricula@test.com")
    categoria = crear_categoria_db(db_session, nombre="Gasista2")

    respuesta = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, numero_matricula="EL-12345"),
        headers=_auth(token),
    )

    assert _codigos(respuesta) == {"numero_matricula": "campo_no_permitido"}


def test_el_correo_del_body_se_ignora(client, db_session):
    token = registrar_y_loguear(client, "correo@test.com")
    categoria = crear_categoria_db(db_session, nombre="Mudanzas")

    respuesta = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, email="otro@test.com"),
        headers=_auth(token),
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["email"] == "correo@test.com"


def test_segundo_registro_da_409_perfil_existente(client, db_session):
    token, _ = crear_oferente_completo(client, db_session, email="dos_veces@test.com", dni_cuit="20-30111222-0")
    categoria = crear_categoria_db(db_session, nombre="Otra")

    respuesta = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, dni_cuit="27-30111223-3"),
        headers=_auth(token),
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"]["codigo"] == "perfil_existente"


def test_administrador_no_puede_registrarse_como_oferente(client, db_session):
    crear_admin_db(db_session, email="admin.reg@test.com")
    token = client.post("/api/v1/auth/login", json={"email": "admin.reg@test.com", "password": "Test1234!"}).json()["access_token"]
    categoria = crear_categoria_db(db_session, nombre="Admin")

    respuesta = client.post("/api/v1/oferentes", json=formulario_registro(categoria.id_categoria), headers=_auth(token))

    assert respuesta.status_code == 403
    assert respuesta.json()["detail"]["codigo"] == "rol_invalido"


def test_abandonar_el_formulario_no_persiste_nada(client, db_session):
    """CA06: sin el POST no existe fila de OFERENTE, y el próximo login sigue pidiendo el registro."""
    token = registrar_y_loguear(client, "abandona@test.com")

    assert db_session.query(Oferente).count() == 0
    assert client.get("/api/v1/auth/me", headers=_auth(token)).json()["requiere_registro"] is True


# --- Guard de registro incompleto (CA01, A9) --------------------------------


def test_endpoints_de_oferente_sin_registro_dan_403_registro_incompleto(client):
    token = registrar_y_loguear(client, "sinregistro@test.com")

    for metodo, ruta in (
        ("get", "/api/v1/oferentes/me"),
        ("get", "/api/v1/oferentes/me/matriculas"),
        ("get", "/api/v1/notificaciones"),
    ):
        respuesta = getattr(client, metodo)(ruta, headers=_auth(token))
        assert respuesta.status_code == 403, ruta
        assert respuesta.json()["detail"]["codigo"] == "registro_incompleto", ruta


def test_la_bandeja_sigue_abierta_para_el_administrador(client, db_session):
    crear_admin_db(db_session, email="admin.bandeja@test.com")
    token = client.post("/api/v1/auth/login", json={"email": "admin.bandeja@test.com", "password": "Test1234!"}).json()["access_token"]

    assert client.get("/api/v1/notificaciones", headers=_auth(token)).status_code == 200


# --- Perfiles: público y privado (D7) ---------------------------------------


def test_perfil_publico_no_expone_dni_ni_rechazos(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="publico.dni@test.com", dni_cuit="20-30111222-0")

    cuerpo = client.get(f"/api/v1/oferentes/{oferente_id}").json()

    assert "dni_cuit" not in cuerpo
    assert "cantidad_rechazos_acumulados" not in cuerpo
    assert "estado_verificacion" not in cuerpo
    assert cuerpo["email"] == "publico.dni@test.com"
    assert cuerpo["cantidad_resenas"] == 0
    assert cuerpo["cantidad_trabajos"] == 0


def test_perfil_privado_expone_dni_solo_al_dueno(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="privado.dni@test.com", dni_cuit="20-30111222-0")

    cuerpo = client.get("/api/v1/oferentes/me", headers=_auth(token)).json()

    assert cuerpo["id_oferente"] == oferente_id
    assert cuerpo["dni_cuit"] == "20301112220"
    assert cuerpo["cantidad_rechazos_acumulados"] == 0


def test_busqueda_excluye_cuentas_suspendidas(client, db_session):
    _, activo_id = crear_oferente_completo(client, db_session, email="activo.busq@test.com", dni_cuit="20-30111222-0")
    _, suspendido_id = crear_oferente_completo(client, db_session, email="suspendido.busq@test.com", dni_cuit="20-30111223-9")
    usuario = db_session.query(Usuario).filter(Usuario.email == "suspendido.busq@test.com").one()
    usuario.estado_cuenta = EstadoCuenta.SUSPENDIDA
    db_session.commit()

    ids = [o["id_oferente"] for o in client.get("/api/v1/oferentes").json()]

    assert activo_id in ids
    assert suspendido_id not in ids


def test_perfil_publico_muestra_matriculas_fidelizadas(client, db_session):
    _, oferente_id = crear_oferente_completo(client, db_session, email="matriculado@test.com", dni_cuit="20-30111222-0")
    db_session.add(
        Matricula(
            oferente_id=oferente_id,
            tipo_profesional="Gasista",
            numero_matricula="1000008919",
            categoria="Gasista",
            fecha_vencimiento=date.today() + timedelta(days=365),
        )
    )
    db_session.commit()

    cuerpo = client.get(f"/api/v1/oferentes/{oferente_id}").json()

    assert cuerpo["tiene_matricula_validada"] is True
    assert cuerpo["matriculas"] == [{"tipo_profesional": "Gasista", "numero_matricula": "1000008919"}]


# --- Edición (D18, A33) ------------------------------------------------------


def test_put_me_edita_campos_y_no_acepta_dni(client, db_session):
    token, _ = crear_oferente_completo(client, db_session, email="edita@test.com", dni_cuit="20-30111222-0")

    respuesta = client.put("/api/v1/oferentes/me", json={"especialidad": "Tableros", "dias_atencion": [6, 7]}, headers=_auth(token))
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["especialidad"] == "Tableros"
    assert respuesta.json()["dias_atencion"] == [6, 7]

    rechazado = client.put("/api/v1/oferentes/me", json={"dni_cuit": "20-99999999-9"}, headers=_auth(token))
    assert rechazado.status_code == 422
    assert _codigos(rechazado) == {"dni_cuit": "campo_no_permitido"}


def test_put_me_no_deja_vacios_los_campos_obligatorios(client, db_session):
    token, _ = crear_oferente_completo(client, db_session, email="nulos@test.com", dni_cuit="20-30111222-0")

    respuesta = client.put("/api/v1/oferentes/me", json={"nombre": None}, headers=_auth(token))

    assert _codigos(respuesta) == {"nombre": "requerido"}


def test_cambiar_nombre_con_matricula_fidelizada_da_409(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="bloqueado@test.com", dni_cuit="20-30111222-0")
    db_session.add(
        Matricula(
            oferente_id=oferente_id,
            tipo_profesional="Gasista",
            numero_matricula="1000008919",
            categoria="Gasista",
            fecha_vencimiento=date.today() + timedelta(days=365),
        )
    )
    db_session.commit()

    respuesta = client.put("/api/v1/oferentes/me", json={"nombre": "Otro Nombre"}, headers=_auth(token))

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"]["codigo"] == "nombre_bloqueado_por_matricula"


def test_put_alias_por_id_solo_acepta_el_propio_perfil(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="alias@test.com", dni_cuit="20-30111222-0")
    token_otro, otro_id = crear_oferente_completo(client, db_session, email="alias2@test.com", dni_cuit="20-30111223-9")

    ajeno = client.put(f"/api/v1/oferentes/{otro_id}", json={"especialidad": "X"}, headers=_auth(token))
    propio = client.put(f"/api/v1/oferentes/{oferente_id}", json={"especialidad": "Y"}, headers=_auth(token))

    assert ajeno.status_code == 403
    assert propio.status_code == 200
    assert propio.json()["especialidad"] == "Y"


def test_nombre_y_apellido_van_en_un_solo_campo(client, db_session):
    """El formulario tiene un único campo para nombre y apellido (o razón social)."""
    token = registrar_y_loguear(client, "unico@test.com")
    categoria = crear_categoria_db(db_session, nombre="Pintor de obra")

    separado = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, apellido="Ludueña"),
        headers=_auth(token),
    )
    assert _codigos(separado) == {"apellido": "campo_no_permitido"}

    respuesta = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, nombre="Serena Ludueña"),
        headers=_auth(token),
    )
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["nombre"] == "Serena Ludueña"
    assert "apellido" not in respuesta.json()
