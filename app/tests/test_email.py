import httpx
import pytest

from app.core.config import settings
from app.services import email as email_module
from app.services.email import BrevoEmailService, EmailError, EmailServiceFake, url_resena


class RespuestaFalsa:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


# --- Armado de URLs ---------------------------------------------------------


def test_urls_usan_la_url_base_configurada(monkeypatch):
    monkeypatch.setattr(settings, "frontend_url", "https://offix.vercel.app/")

    assert url_resena("ABC123") == "https://offix.vercel.app/resena/ABC123"


def test_url_resena_escapa_caracteres_especiales(monkeypatch):
    monkeypatch.setattr(settings, "frontend_url", "http://localhost:3000")

    assert url_resena("a b/c") == "http://localhost:3000/resena/a%20b/c"


# --- Plantillas -------------------------------------------------------------


def test_link_resena_arma_asunto_destinatario_y_link():
    servicio = EmailServiceFake()

    servicio.enviar_link_resena(
        email_cliente="cliente@test.com",
        nombre_cliente="Juan Cliente",
        nombre_oferente="María Gómez",
        codigo_unico="CODIGO-1",
    )

    assert len(servicio.enviados) == 1
    correo = servicio.enviados[0]
    assert correo.destinatario == "cliente@test.com"
    assert correo.nombre_destinatario == "Juan Cliente"
    assert "María Gómez" in correo.asunto
    assert url_resena("CODIGO-1") in correo.cuerpo_html
    # El texto es el que definió QA, el mismo que viaja por WhatsApp.
    assert "Gracias por confiar en María Gómez a través de Offix." in correo.cuerpo_html
    assert "¡Gracias por ser parte de Offix!" in correo.cuerpo_html


def test_el_fake_acumula_los_envios_y_se_puede_limpiar():
    servicio = EmailServiceFake()
    servicio.enviar("a@test.com", "A", "Asunto", "<p>hola</p>")
    servicio.enviar("b@test.com", "B", "Asunto", "<p>hola</p>")
    assert len(servicio.enviados) == 2

    servicio.limpiar()
    assert servicio.enviados == []


# --- Transporte Brevo -------------------------------------------------------


def test_brevo_sin_api_key_falla_con_mensaje_claro():
    servicio = BrevoEmailService(api_key="", sender_email="no-reply@offix.test", sender_name="Offix")

    with pytest.raises(EmailError, match="BREVO_API_KEY"):
        servicio.enviar("cliente@test.com", "Cliente", "Asunto", "<p>hola</p>")


def test_brevo_arma_el_payload_y_los_headers_esperados(monkeypatch):
    llamadas = {}

    def post_falso(url, json, headers, timeout):
        llamadas.update(url=url, json=json, headers=headers, timeout=timeout)
        return RespuestaFalsa(201)

    monkeypatch.setattr(email_module.httpx, "post", post_falso)
    servicio = BrevoEmailService(api_key="clave-secreta", sender_email="no-reply@offix.test", sender_name="Offix", timeout=5.0)

    servicio.enviar("cliente@test.com", "Juan Cliente", "Asunto de prueba", "<p>hola</p>")

    assert llamadas["url"] == BrevoEmailService.API_URL
    assert llamadas["timeout"] == 5.0
    assert llamadas["headers"]["api-key"] == "clave-secreta"
    assert llamadas["json"]["sender"] == {"email": "no-reply@offix.test", "name": "Offix"}
    assert llamadas["json"]["to"] == [{"email": "cliente@test.com", "name": "Juan Cliente"}]
    assert llamadas["json"]["subject"] == "Asunto de prueba"
    assert llamadas["json"]["htmlContent"] == "<p>hola</p>"


def test_brevo_convierte_un_error_http_en_email_error(monkeypatch):
    monkeypatch.setattr(
        email_module.httpx,
        "post",
        lambda url, json, headers, timeout: RespuestaFalsa(401, '{"message":"Key not found"}'),
    )
    servicio = BrevoEmailService(api_key="clave-vencida", sender_email="no-reply@offix.test", sender_name="Offix")

    with pytest.raises(EmailError, match="HTTP 401"):
        servicio.enviar("cliente@test.com", "Cliente", "Asunto", "<p>hola</p>")


def test_brevo_convierte_un_error_de_red_en_email_error(monkeypatch):
    def post_que_falla(url, json, headers, timeout):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(email_module.httpx, "post", post_que_falla)
    servicio = BrevoEmailService(api_key="clave", sender_email="no-reply@offix.test", sender_name="Offix")

    with pytest.raises(EmailError, match="No se pudo contactar a Brevo"):
        servicio.enviar("cliente@test.com", "Cliente", "Asunto", "<p>hola</p>")


def test_la_suite_usa_el_doble_y_no_manda_correo_real(client, emails):
    """El override de dependencia está activo en la fixture `client`."""
    from app.services.email import get_email_service

    assert client.app.dependency_overrides[get_email_service]() is emails
    assert isinstance(emails, EmailServiceFake)
