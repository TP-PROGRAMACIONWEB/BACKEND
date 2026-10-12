"""HU-04 T06 — Fotos de perfil, portada y trabajos realizados, con StorageServiceFake."""

import re

import pytest

from app.core.config import settings
from app.main import app
from app.models.archivo_adjunto import ArchivoAdjunto
from app.models.trabajo_realizado import TrabajoRealizado
from app.services.storage import StorageError, StorageService, StorageServiceFake, get_storage_service
from app.tests.conftest import crear_oferente_completo

MB = 1024 * 1024
PATRON_PATH = re.compile(r"oferentes/(\d+)/(perfil|portada|trabajo)/[0-9a-f]{32}\.(jpg|png)")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def storage(client, monkeypatch):
    """Storage en memoria para toda la prueba, y una URL base para armar las públicas."""
    fake = StorageServiceFake()
    app.dependency_overrides[get_storage_service] = lambda: fake
    monkeypatch.setattr(settings, "supabase_url", "https://proyecto.supabase.co")
    yield fake
    app.dependency_overrides.pop(get_storage_service, None)


@pytest.fixture()
def oferente(client, db_session):
    token, oferente_id = crear_oferente_completo(client, db_session, email="fotos@test.com", dni_cuit="20-30111222-0")
    return token, oferente_id


def _pedir_subida(client, token, tipo="Perfil", content_type="image/jpeg", tamano=1 * MB):
    return client.post(
        "/api/v1/oferentes/me/archivos/subidas",
        json={"tipo": tipo, "content_type": content_type, "tamano_bytes": tamano},
        headers=_auth(token),
    )


def _subir_y_confirmar_perfil(client, storage, token, path, tamano=1 * MB, content_type="image/jpeg"):
    storage.subir(path, tamano, content_type)
    return client.put("/api/v1/oferentes/me/foto-perfil", json={"path": path}, headers=_auth(token))


# --- Subida (paso 1) ----------------------------------------------------------


def test_pedir_subida_devuelve_path_del_backend_y_url_firmada(client, storage, oferente):
    token, oferente_id = oferente

    respuesta = _pedir_subida(client, token, tipo="Perfil", content_type="image/png")

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    coincide = PATRON_PATH.fullmatch(cuerpo["path"])
    assert coincide and coincide.group(1) == str(oferente_id) and coincide.group(2) == "perfil" and coincide.group(3) == "png"
    assert cuerpo["upload_url"].startswith("https://storage.fake/upload/")


def test_formato_que_no_es_jpg_ni_png_da_422(client, storage, oferente):
    token, _ = oferente

    respuesta = _pedir_subida(client, token, content_type="application/pdf")

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [{"campo": "content_type", "codigo": "formato_imagen_invalido"}]


def test_imagen_de_mas_de_5_mb_da_422(client, storage, oferente):
    token, _ = oferente

    respuesta = _pedir_subida(client, token, tamano=5 * MB + 1)

    assert respuesta.json()["errores"] == [{"campo": "tamano_bytes", "codigo": "imagen_demasiado_grande"}]


def test_imagen_de_4_8_mb_se_acepta(client, storage, oferente):
    """El caso que rompería si pasara por Vercel: tiene que pasar directo a Storage."""
    token, _ = oferente

    assert _pedir_subida(client, token, tamano=int(4.8 * MB)).status_code == 201


def test_sin_supabase_configurado_responde_503(client, db_session):
    token, _ = crear_oferente_completo(client, db_session, email="sin.storage@test.com", dni_cuit="20-30111223-9")

    respuesta = _pedir_subida(client, token)

    assert respuesta.status_code == 503
    assert respuesta.json()["detail"]["codigo"] == "storage_no_configurado"


# --- Confirmación (paso 3) ----------------------------------------------------


def test_confirmar_foto_de_perfil_la_guarda_con_url_publica(client, storage, oferente):
    token, _ = oferente
    path = _pedir_subida(client, token).json()["path"]

    respuesta = _subir_y_confirmar_perfil(client, storage, token, path)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["foto_perfil_url"].endswith(f"/storage/v1/object/public/offix-media/{path}")


def test_reemplazar_la_foto_de_perfil_borra_la_anterior(client, storage, oferente):
    token, _ = oferente
    primera = _pedir_subida(client, token).json()["path"]
    segunda = _pedir_subida(client, token).json()["path"]
    _subir_y_confirmar_perfil(client, storage, token, primera)

    _subir_y_confirmar_perfil(client, storage, token, segunda)

    assert primera in storage.eliminados
    assert segunda not in storage.eliminados


def test_confirmar_un_path_de_otro_oferente_da_422(client, storage, oferente):
    token, _ = oferente
    ajeno = "oferentes/9999/perfil/" + "a" * 32 + ".jpg"
    storage.subir(ajeno, 1 * MB, "image/jpeg")

    respuesta = client.put("/api/v1/oferentes/me/foto-perfil", json={"path": ajeno}, headers=_auth(token))

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [{"campo": "path", "codigo": "archivo_invalido"}]


def test_confirmar_un_objeto_que_no_se_subio_da_422(client, storage, oferente):
    token, oferente_id = oferente
    path = f"oferentes/{oferente_id}/perfil/{'b' * 32}.jpg"

    respuesta = client.put("/api/v1/oferentes/me/foto-perfil", json={"path": path}, headers=_auth(token))

    assert respuesta.json()["errores"] == [{"campo": "path", "codigo": "archivo_invalido"}]


def test_confirmar_un_objeto_mas_grande_de_lo_declarado_da_422(client, storage, oferente):
    """El cliente pudo mentir al pedir la subida: se mira el tamaño real del bucket."""
    token, _ = oferente
    path = _pedir_subida(client, token, tamano=1 * MB).json()["path"]

    respuesta = _subir_y_confirmar_perfil(client, storage, token, path, tamano=6 * MB)

    assert respuesta.json()["errores"] == [{"campo": "path", "codigo": "imagen_demasiado_grande"}]


def test_quitar_la_foto_de_perfil_borra_fila_y_objeto(client, storage, oferente):
    token, _ = oferente
    path = _pedir_subida(client, token).json()["path"]
    _subir_y_confirmar_perfil(client, storage, token, path)

    respuesta = client.delete("/api/v1/oferentes/me/foto-perfil", headers=_auth(token))

    assert respuesta.status_code == 204
    assert path in storage.eliminados
    assert client.get("/api/v1/oferentes/me", headers=_auth(token)).json()["foto_perfil_url"] is None


def test_portada_se_guarda_aparte_de_la_foto_de_perfil(client, storage, oferente):
    token, _ = oferente
    perfil = _pedir_subida(client, token, tipo="Perfil").json()["path"]
    portada = _pedir_subida(client, token, tipo="Portada").json()["path"]
    _subir_y_confirmar_perfil(client, storage, token, perfil)
    storage.subir(portada, 2 * MB, "image/png")

    respuesta = client.put("/api/v1/oferentes/me/portada", json={"path": portada}, headers=_auth(token))

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["portada_url"].endswith(portada)
    assert respuesta.json()["foto_perfil_url"].endswith(perfil)


# --- Trabajos realizados (D13, A46–A53) --------------------------------------


def _subir_fotos_trabajo(client, storage, token, cantidad):
    paths = []
    for _ in range(cantidad):
        path = _pedir_subida(client, token, tipo="Trabajo").json()["path"]
        storage.subir(path, 1 * MB, "image/jpeg")
        paths.append(path)
    return paths


def _cargar_trabajo(client, token, fotos, titulo="Cambio de disyuntor", descripcion="Reemplazo del disyuntor diferencial del tablero."):
    return client.post(
        "/api/v1/oferentes/me/trabajos",
        json={"titulo": titulo, "descripcion": descripcion, "fotos": fotos},
        headers=_auth(token),
    )


def test_cargar_trabajo_guarda_fotos_con_orden_y_foto_principal(client, storage, oferente):
    token, oferente_id = oferente
    fotos = _subir_fotos_trabajo(client, storage, token, 3)

    respuesta = _cargar_trabajo(client, token, fotos)

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert [foto["orden"] for foto in cuerpo["fotos"]] == [1, 2, 3]
    assert cuerpo["foto_principal_url"] == cuerpo["fotos"][0]["url"]
    assert cuerpo["fotos"][0]["url"].endswith(fotos[0])
    assert cuerpo["fotos"][2]["url"].endswith(fotos[2])


def test_listado_publico_trae_fotos_ordenadas_y_mas_nuevo_primero(client, storage, oferente):
    token, oferente_id = oferente
    primero = _cargar_trabajo(client, token, _subir_fotos_trabajo(client, storage, token, 2)).json()
    segundo = _cargar_trabajo(client, token, _subir_fotos_trabajo(client, storage, token, 1)).json()

    listado = client.get(f"/api/v1/oferentes/{oferente_id}/trabajos").json()

    assert [t["id_trabajo"] for t in listado] == [segundo["id_trabajo"], primero["id_trabajo"]]
    assert [foto["orden"] for foto in listado[1]["fotos"]] == [1, 2]
    assert client.get(f"/api/v1/oferentes/{oferente_id}").json()["cantidad_trabajos"] == 2


def test_trabajo_sin_fotos_da_422(client, storage, oferente):
    token, _ = oferente

    respuesta = _cargar_trabajo(client, token, [])

    assert respuesta.json()["errores"] == [{"campo": "fotos", "codigo": "fotos_requeridas"}]


def test_mas_de_5_fotos_da_422(client, storage, oferente):
    token, _ = oferente
    fotos = _subir_fotos_trabajo(client, storage, token, 6)

    respuesta = _cargar_trabajo(client, token, fotos)

    assert respuesta.json()["errores"] == [{"campo": "fotos", "codigo": "demasiadas_fotos"}]


def test_la_misma_foto_dos_veces_da_422(client, storage, oferente):
    token, _ = oferente
    foto = _subir_fotos_trabajo(client, storage, token, 1)[0]

    respuesta = _cargar_trabajo(client, token, [foto, foto])

    assert respuesta.json()["errores"] == [{"campo": "fotos", "codigo": "fotos_duplicadas"}]


def test_descripcion_obligatoria_y_con_minimo(client, storage, oferente):
    token, _ = oferente
    fotos = _subir_fotos_trabajo(client, storage, token, 1)

    vacia = _cargar_trabajo(client, token, fotos, descripcion="")
    corta = _cargar_trabajo(client, token, fotos, descripcion="corto")

    assert vacia.json()["errores"] == [{"campo": "descripcion", "codigo": "requerido"}]
    assert corta.json()["errores"] == [{"campo": "descripcion", "codigo": "longitud_minima"}]


def test_titulo_obligatorio_y_no_vacio(client, storage, oferente):
    token, _ = oferente
    fotos = _subir_fotos_trabajo(client, storage, token, 1)

    sin_titulo = client.post(
        "/api/v1/oferentes/me/trabajos",
        json={"descripcion": "Instalación completa de tablero.", "fotos": fotos},
        headers=_auth(token),
    )
    solo_espacios = _cargar_trabajo(client, token, fotos, titulo="   ")

    assert sin_titulo.json()["errores"] == [{"campo": "titulo", "codigo": "requerido"}]
    assert solo_espacios.json()["errores"] == [{"campo": "titulo", "codigo": "longitud_minima"}]


def test_titulo_demasiado_largo_da_422(client, storage, oferente):
    token, _ = oferente
    fotos = _subir_fotos_trabajo(client, storage, token, 1)

    respuesta = _cargar_trabajo(client, token, fotos, titulo="x" * 101)

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [{"campo": "titulo", "codigo": "longitud_maxima"}]


def test_sexto_trabajo_da_409_limite_trabajos(client, storage, oferente):
    token, _ = oferente
    for _ in range(5):
        assert _cargar_trabajo(client, token, _subir_fotos_trabajo(client, storage, token, 1)).status_code == 201

    respuesta = _cargar_trabajo(client, token, _subir_fotos_trabajo(client, storage, token, 1))

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"]["codigo"] == "limite_trabajos"


def test_una_foto_no_puede_usarse_en_dos_trabajos(client, storage, oferente):
    token, _ = oferente
    foto = _subir_fotos_trabajo(client, storage, token, 1)
    assert _cargar_trabajo(client, token, foto).status_code == 201

    respuesta = _cargar_trabajo(client, token, foto)

    assert respuesta.json()["errores"] == [{"campo": "path", "codigo": "archivo_invalido"}]


def test_borrar_trabajo_borra_filas_y_objetos(client, storage, oferente):
    token, _ = oferente
    fotos = _subir_fotos_trabajo(client, storage, token, 2)
    trabajo = _cargar_trabajo(client, token, fotos).json()

    respuesta = client.delete(f"/api/v1/oferentes/me/trabajos/{trabajo['id_trabajo']}", headers=_auth(token))

    assert respuesta.status_code == 204
    assert set(storage.eliminados) >= set(fotos)
    assert client.get(f"/api/v1/oferentes/{oferente[1]}/trabajos").json() == []


def test_no_se_puede_borrar_un_trabajo_ajeno(client, storage, db_session, oferente):
    token, _ = oferente
    trabajo = _cargar_trabajo(client, token, _subir_fotos_trabajo(client, storage, token, 1)).json()
    token_otro, _ = crear_oferente_completo(client, db_session, email="otro.trabajo@test.com", dni_cuit="20-30111223-9")

    respuesta = client.delete(f"/api/v1/oferentes/me/trabajos/{trabajo['id_trabajo']}", headers=_auth(token_otro))

    assert respuesta.status_code == 404
    assert db_session.get(TrabajoRealizado, trabajo["id_trabajo"]) is not None


def test_storage_caido_responde_502_y_no_guarda_nada(client, db_session, oferente, monkeypatch, storage):
    token, _ = oferente
    fotos = _subir_fotos_trabajo(client, storage, token, 1)

    class StorageRoto(StorageServiceFake):
        def obtener_objeto(self, path):
            raise StorageError("Supabase no responde")

    app.dependency_overrides[get_storage_service] = lambda: StorageRoto()

    respuesta = _cargar_trabajo(client, token, fotos)

    assert respuesta.status_code == 502
    assert respuesta.json()["detail"]["codigo"] == "storage_no_disponible"
    assert db_session.query(TrabajoRealizado).count() == 0
    assert db_session.query(ArchivoAdjunto).count() == 0


def test_catalogo_expone_los_limites_de_trabajos(client):
    limites = client.get("/api/v1/catalogos/registro-oferente").json()["limites"]
    assert limites == {"trabajos": 5, "fotos_por_trabajo": 5, "tamano_maximo_mb": 5}
