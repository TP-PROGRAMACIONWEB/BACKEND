from urllib.parse import unquote

import pytest

from app.core.config import settings
from app.services.mensajes import (
    armar_whatsapp_url,
    normalizar_telefono,
    telefono_es_valido,
    telefono_internacional,
    texto_invitacion,
)


@pytest.mark.parametrize("telefono", ["351-6924551", "3516924551", "3564-692755", "3564692755"])
def test_telefonos_de_10_digitos_son_validos(telefono):
    assert telefono_es_valido(telefono)


@pytest.mark.parametrize(
    "telefono",
    [
        "0351-6924551",  # 0 inicial
        "351-156924551",  # 15
        "+543516924551",  # prefijo de país
        "351-69245",  # menos de 10 dígitos
        "351-69245510",  # más de 10 dígitos
        "351 6924551",  # el separador es el guión, no el espacio
        "351-69A4551",  # caracteres alfabéticos
    ],
)
def test_telefonos_invalidos(telefono):
    assert not telefono_es_valido(telefono)


@pytest.mark.parametrize(
    ("cargado", "guardado", "internacional"),
    [
        ("351-6924551", "3516924551", "5493516924551"),
        ("3564-692755", "3564692755", "5493564692755"),
    ],
)
def test_normalizacion_del_telefono(cargado, guardado, internacional):
    """Los ejemplos de la tabla del plan: se guardan 10 dígitos y `wa.me` recibe
    el formato internacional sin símbolos."""
    assert normalizar_telefono(cargado) == guardado
    assert telefono_internacional(cargado) == internacional


def test_el_prefijo_de_pais_sale_de_configuracion(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_prefijo_pais", "5511")
    assert telefono_internacional("351-6924551") == "55113516924551"


def test_el_texto_es_el_definido_por_qa():
    texto = texto_invitacion("María Gómez", "https://offix.test/resena/ABC")

    assert texto == (
        "¡Hola!\n"
        "Gracias por confiar en María Gómez a través de Offix.\n"
        "Tu opinión nos ayuda a seguir mejorando y a que otros usuarios elijan mejor.\n"
        "¿Nos dejás una reseña sobre tu experiencia con María Gómez?\n"
        "Calificá tu experiencia acá: https://offix.test/resena/ABC\n"
        "Solo te va a tomar un minuto. ¡Gracias por ser parte de Offix!"
    )


def test_whatsapp_url_url_encodea_el_texto():
    url = armar_whatsapp_url("351-6924551", "María Gómez", "https://offix.test/resena/ABC")

    assert url.startswith("https://wa.me/5493516924551?text=")
    # Viaja url-encodeado: ni saltos de línea ni espacios crudos en la URL.
    assert " " not in url and "\n" not in url
    assert unquote(url.split("?text=", 1)[1]) == texto_invitacion("María Gómez", "https://offix.test/resena/ABC")
