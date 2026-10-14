from app.tests.conftest import crear_categoria_db, crear_oferente_completo, formulario_registro, registrar_y_loguear


def test_crear_perfil_oferente_ok_id_igual_a_usuario(client, db_session):
    from jose import jwt

    from app.core.config import settings

    token, oferente_id = crear_oferente_completo(client, db_session, email="ok@test.com", dni_cuit="20-22222222-3")

    response = client.get(f"/api/v1/oferentes/{oferente_id}")
    assert response.status_code == 200

    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    assert int(payload["sub"]) == oferente_id


def test_crear_perfil_sin_token_401(client, db_session):
    categoria = crear_categoria_db(db_session)
    response = client.post(
        "/api/v1/oferentes",
        json={
            "nombre": "Sin",
            "dni_cuit": "20-33333333-4",
            "telefono": "3564-400000",
            "categoria_id": categoria.id_categoria,
        },
    )
    assert response.status_code == 401


def test_crear_perfil_duplicado_409(client, db_session):
    token, _ = crear_oferente_completo(client, db_session, email="duplicado@test.com", dni_cuit="20-44444444-5")
    categoria = crear_categoria_db(db_session, nombre="OtraCategoria")

    response = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, dni_cuit="20-55555555-6", nombre="Otra Vez"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["codigo"] == "perfil_existente"


def test_crear_perfil_dni_duplicado_409(client, db_session):
    crear_oferente_completo(client, db_session, email="uno@test.com", dni_cuit="20-66666666-7")
    token_dos = registrar_y_loguear(client, "dos@test.com")
    categoria = crear_categoria_db(db_session, nombre="CategoriaDos")

    response = client.post(
        "/api/v1/oferentes",
        json=formulario_registro(categoria.id_categoria, dni_cuit="20-66666666-7", nombre="Dos Prueba"),
        headers={"Authorization": f"Bearer {token_dos}"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["codigo"] == "dni_cuit_duplicado"


def test_crear_perfil_formato_invalido_422(client, db_session):
    token = registrar_y_loguear(client, "formato@test.com")
    categoria = crear_categoria_db(db_session, nombre="CategoriaFormato")

    response = client.post(
        "/api/v1/oferentes",
        json={
            "nombre": "Malo",
            "dni_cuit": "no-es-un-dni!!",
            "telefono": "3564-400000",
            "categoria_id": categoria.id_categoria,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_buscar_oferentes_publico(client, db_session):
    crear_oferente_completo(client, db_session, email="buscable@test.com", dni_cuit="20-77777777-8")
    response = client.get("/api/v1/oferentes")
    assert response.status_code == 200
    assert len(response.json()) >= 1
