"""Envío de correos transaccionales.

El servicio se expone como dependencia de FastAPI (`get_email_service`) para que
los tests puedan reemplazarlo por `EmailServiceFake` con `dependency_overrides`
y la suite nunca mande correo real.

Las tres plantillas del flujo de reseña viven en la clase base, así que son las
mismas sin importar el transporte; lo único que cambia entre implementaciones es
el método `enviar`.
"""

from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote

import httpx

from app.core.config import settings


class EmailError(Exception):
    """El correo no se pudo entregar al proveedor."""


@dataclass(frozen=True)
class CorreoEnviado:
    destinatario: str
    nombre_destinatario: str
    asunto: str
    cuerpo_html: str


def url_resena(codigo_unico: str) -> str:
    return f"{settings.frontend_url_base}/resena/{quote(codigo_unico)}"


def url_verificacion(token: str) -> str:
    return f"{settings.frontend_url_base}/resena/verificar/{quote(token)}"


def url_moderacion(id_resena: int) -> str:
    return f"{settings.frontend_url_base}/mis-resenas/{id_resena}"


def _plantilla(titulo: str, cuerpo: str, texto_boton: str, url: str) -> str:
    return f"""\
<html>
  <body style="font-family: Arial, Helvetica, sans-serif; color: #1f2933; line-height: 1.5;">
    <h2 style="color: #0b7285;">{titulo}</h2>
    {cuerpo}
    <p style="margin: 24px 0;">
      <a href="{url}" style="background: #0b7285; color: #ffffff; padding: 12px 20px;
         text-decoration: none; border-radius: 6px; display: inline-block;">{texto_boton}</a>
    </p>
    <p style="font-size: 12px; color: #616e7c;">
      Si el botón no funciona, copiá y pegá este enlace en tu navegador:<br>{url}
    </p>
    <p style="font-size: 12px; color: #616e7c;">Offix — Red social de oficios</p>
  </body>
</html>"""


class EmailService:
    """Contrato de envío más las plantillas del flujo de reseña."""

    def enviar(self, destinatario: str, nombre_destinatario: str, asunto: str, cuerpo_html: str) -> None:
        raise NotImplementedError

    def enviar_link_resena(self, *, email_cliente: str, nombre_cliente: str, nombre_oferente: str, codigo_unico: str) -> None:
        """Flujo por correo: el cliente pidió dejar una reseña y recibe el enlace."""
        url = url_resena(codigo_unico)
        cuerpo = (
            f"<p>¡Hola {nombre_cliente}!</p>"
            f"<p>Pediste dejar una reseña sobre el trabajo de <strong>{nombre_oferente}</strong>. "
            f"Entrá desde el siguiente enlace para calificarlo.</p>"
        )
        self.enviar(
            destinatario=email_cliente,
            nombre_destinatario=nombre_cliente,
            asunto=f"Dejá tu reseña de {nombre_oferente} en Offix",
            cuerpo_html=_plantilla("Dejá tu reseña", cuerpo, "Calificar el trabajo", url),
        )

    def enviar_verificacion_resena(self, *, email_cliente: str, nombre_cliente: str, nombre_oferente: str, token: str) -> None:
        """Flujo por WhatsApp: la reseña ya se cargó pero falta confirmar el mail."""
        url = url_verificacion(token)
        cuerpo = (
            f"<p>¡Hola {nombre_cliente}!</p>"
            f"<p>Recibimos tu reseña sobre <strong>{nombre_oferente}</strong>. "
            f"Para publicarla necesitamos confirmar que esta casilla es tuya.</p>"
            f"<p>Hasta que la confirmes, la reseña no se le envía al profesional.</p>"
        )
        self.enviar(
            destinatario=email_cliente,
            nombre_destinatario=nombre_cliente,
            asunto=f"Confirmá tu reseña de {nombre_oferente}",
            cuerpo_html=_plantilla("Confirmá tu reseña", cuerpo, "Confirmar mi reseña", url),
        )

    def enviar_aviso_resena_nueva(self, *, email_oferente: str, nombre_oferente: str, nombre_cliente: str, id_resena: int) -> None:
        """Aviso al Oferente de que tiene una reseña esperando aprobación."""
        url = url_moderacion(id_resena)
        cuerpo = (
            f"<p>¡Hola {nombre_oferente}!</p>"
            f"<p><strong>{nombre_cliente}</strong> dejó una reseña sobre tu trabajo. "
            f"Todavía no está publicada: podés aprobarla o rechazarla desde tu perfil.</p>"
        )
        self.enviar(
            destinatario=email_oferente,
            nombre_destinatario=nombre_oferente,
            asunto="Tenés una reseña nueva para aprobar",
            cuerpo_html=_plantilla("Tenés una reseña nueva", cuerpo, "Ver la reseña", url),
        )


class BrevoEmailService(EmailService):
    """Envío real contra la API transaccional de Brevo."""

    API_URL = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, api_key: str, sender_email: str, sender_name: str, timeout: float = 10.0):
        self.api_key = api_key
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.timeout = timeout

    def enviar(self, destinatario: str, nombre_destinatario: str, asunto: str, cuerpo_html: str) -> None:
        if not self.api_key:
            raise EmailError("Falta configurar BREVO_API_KEY en el archivo .env")

        payload = {
            "sender": {"email": self.sender_email, "name": self.sender_name},
            "to": [{"email": destinatario, "name": nombre_destinatario}],
            "subject": asunto,
            "htmlContent": cuerpo_html,
        }
        headers = {
            "api-key": self.api_key,
            "accept": "application/json",
            "content-type": "application/json",
        }

        try:
            respuesta = httpx.post(self.API_URL, json=payload, headers=headers, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise EmailError(f"No se pudo contactar a Brevo: {exc}") from exc

        if respuesta.status_code >= 400:
            raise EmailError(f"Brevo rechazó el envío (HTTP {respuesta.status_code}): {respuesta.text}")


class EmailServiceFake(EmailService):
    """Doble para tests y desarrollo sin credenciales: guarda los envíos en memoria."""

    def __init__(self):
        self.enviados: list[CorreoEnviado] = []

    def enviar(self, destinatario: str, nombre_destinatario: str, asunto: str, cuerpo_html: str) -> None:
        self.enviados.append(
            CorreoEnviado(
                destinatario=destinatario,
                nombre_destinatario=nombre_destinatario,
                asunto=asunto,
                cuerpo_html=cuerpo_html,
            )
        )

    def limpiar(self) -> None:
        self.enviados.clear()


@lru_cache
def _servicio_brevo() -> BrevoEmailService:
    return BrevoEmailService(
        api_key=settings.brevo_api_key,
        sender_email=settings.brevo_sender_email,
        sender_name=settings.brevo_sender_name,
        timeout=settings.brevo_timeout_segundos,
    )


def get_email_service() -> EmailService:
    """Dependencia de FastAPI. En tests se reemplaza con `EmailServiceFake`."""
    return _servicio_brevo()
