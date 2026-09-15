"""Manda un correo de prueba real por Brevo, para verificar que la configuración
del `.env` funciona antes de conectar el servicio a los endpoints.

Uso: python -m app.scripts.probar_email destinatario@ejemplo.com
"""

import sys

from app.core.config import settings
from app.services.email import EmailError, get_email_service


def run(destinatario: str):
    servicio = get_email_service()
    print(f"Remitente configurado: {settings.brevo_sender_name} <{settings.brevo_sender_email}>")
    print(f"URL base del frontend: {settings.frontend_url_base}")
    print(f"Enviando correo de prueba a {destinatario}...")

    try:
        servicio.enviar_link_resena(
            email_cliente=destinatario,
            nombre_cliente="Cliente de Prueba",
            nombre_oferente="Juan Pérez",
            codigo_unico="DEMO-CODE-0001",
        )
    except EmailError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)

    print("Correo enviado. Revisá la casilla (y la carpeta de spam).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python -m app.scripts.probar_email destinatario@ejemplo.com")
        raise SystemExit(2)
    run(sys.argv[1])
