"""Login con Google vía Auth0 (HU-03, CA01-CA04).

El tenant de Auth0 está configurado como una **Regular Web Application**: el
backend, no el frontend, es quien tiene el `client_secret` y quien intercambia
el `code` por tokens. El flujo completo:

1. El frontend manda al usuario a `GET /api/v1/auth/google/login`.
2. Ese endpoint redirige a Auth0 (`/authorize`, con `connection=google-oauth2`
   para saltear la pantalla de selección de conexión).
3. El usuario se autentica con Google; Auth0 redirige de vuelta a
   `AUTH0_CALLBACK_URL` (`GET /api/v1/auth/google/callback`) con un `code`.
4. El backend cambia ese `code` por un `access_token` de Auth0 (`/oauth/token`)
   y con ese token pide el perfil (`/userinfo`): nombre, mail, si el mail está
   verificado.
5. Con eso arma (o encuentra) el `Usuario` y emite **el JWT propio** de
   siempre (`create_access_token`) — el resto del backend no distingue de qué
   login vino ese token.

Este servicio se expone como dependencia de FastAPI, igual que
`get_email_service`, para que los tests lo reemplacen con un doble y la suite
nunca llame a Auth0 de verdad.
"""

from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlencode

import httpx

from app.core.config import settings


class Auth0Error(Exception):
    """El intercambio con Auth0 falló, o el perfil que devolvió es inservible
    (sin mail, o mail no verificado). Cualquiera de estos casos es el CA03:
    "Autenticación fallida"."""


@dataclass(frozen=True)
class PerfilGoogle:
    email: str
    nombre: str


class Auth0Service:
    def url_autorizacion(self, state: str) -> str:
        parametros = {
            "response_type": "code",
            "client_id": settings.auth0_client_id,
            "redirect_uri": settings.auth0_callback_url,
            "scope": "openid profile email",
            "connection": "google-oauth2",
            "state": state,
        }
        return f"https://{settings.auth0_domain}/authorize?{urlencode(parametros)}"

    def obtener_perfil(self, code: str) -> PerfilGoogle:
        """Intercambia el `code` por un token y trae el perfil. Cualquier paso
        que falle levanta `Auth0Error` — nunca deja pasar un mail sin
        verificar, que es la puerta de entrada obvia para un login falso."""
        token = self._intercambiar_code(code)
        return self._userinfo(token)

    def _intercambiar_code(self, code: str) -> str:
        payload = {
            "grant_type": "authorization_code",
            "client_id": settings.auth0_client_id,
            "client_secret": settings.auth0_client_secret,
            "code": code,
            "redirect_uri": settings.auth0_callback_url,
        }
        try:
            respuesta = httpx.post(f"https://{settings.auth0_domain}/oauth/token", data=payload, timeout=10.0)
        except httpx.HTTPError as exc:
            raise Auth0Error(f"No se pudo contactar a Auth0: {exc}") from exc

        if respuesta.status_code >= 400:
            raise Auth0Error(f"Auth0 rechazó el código (HTTP {respuesta.status_code}): {respuesta.text}")

        access_token = respuesta.json().get("access_token")
        if not access_token:
            raise Auth0Error("La respuesta de Auth0 no trajo access_token")
        return access_token

    def _userinfo(self, access_token: str) -> PerfilGoogle:
        try:
            respuesta = httpx.get(
                f"https://{settings.auth0_domain}/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            raise Auth0Error(f"No se pudo obtener el perfil de Auth0: {exc}") from exc

        if respuesta.status_code >= 400:
            raise Auth0Error(f"Auth0 rechazó la consulta de perfil (HTTP {respuesta.status_code})")

        perfil = respuesta.json()
        email = perfil.get("email")
        if not email or not perfil.get("email_verified", False):
            raise Auth0Error("El perfil de Google no trae un mail verificado")

        nombre = perfil.get("name") or email.split("@")[0]
        return PerfilGoogle(email=email, nombre=nombre)


@lru_cache
def _servicio_auth0() -> Auth0Service:
    return Auth0Service()


def get_auth0_service() -> Auth0Service:
    """Dependencia de FastAPI. En tests se reemplaza con `Auth0ServiceFake`."""
    return _servicio_auth0()


class Auth0ServiceFake(Auth0Service):
    """Doble para tests: no llama a Auth0. `url_autorizacion` se hereda tal
    cual (no pega afuera, solo arma un string) para poder verificarla."""

    def __init__(self, perfil: PerfilGoogle | None = None):
        self.perfil = perfil or PerfilGoogle(email="cliente.google@test.com", nombre="Cliente Google")
        self.codigos_recibidos: list[str] = []

    def obtener_perfil(self, code: str) -> PerfilGoogle:
        self.codigos_recibidos.append(code)
        return self.perfil


class Auth0ServiceFakeFalla(Auth0Service):
    """Doble que simula cualquier falla contra Auth0 (CA03)."""

    def obtener_perfil(self, code: str) -> PerfilGoogle:
        raise Auth0Error("simulado para tests")
