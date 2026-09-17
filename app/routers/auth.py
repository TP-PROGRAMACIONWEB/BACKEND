import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_db
from app.models.usuario import EstadoCuenta, RolUsuario, Usuario
from app.schemas.usuario import PerfilOut, Token, UsuarioCreate, UsuarioLogin, UsuarioOut
from app.services.auth0 import Auth0Error, Auth0Service, get_auth0_service

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])

COOKIE_ESTADO_OAUTH = "oauth_state"


@router.post(
    "/registro",
    response_model=UsuarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
    responses={409: {"description": "El email ya está registrado"}},
)
def registrar_usuario(payload: UsuarioCreate, db: Session = Depends(get_db)):
    """RF1/RF4 — Registro de nuevos usuarios Oferentes.

    Crea el Usuario (rol Oferente por defecto). Para poder generar/aprobar
    reseñas o gestionar un perfil profesional, después hay que crear el
    perfil con `POST /api/v1/oferentes` usando el token devuelto por `/login`.
    """
    if db.query(Usuario).filter(Usuario.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email ya está registrado")

    usuario = Usuario(email=payload.email, password_hash=hash_password(payload.password))
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post(
    "/login",
    response_model=Token,
    summary="Iniciar sesión",
    responses={
        401: {"description": "Email o contraseña incorrectos"},
        403: {"description": "La cuenta está suspendida o bloqueada"},
    },
)
def login(payload: UsuarioLogin, db: Session = Depends(get_db)):
    """RF4 — Inicio de sesión.

    Devuelve un JWT (`access_token`). Enviarlo en cada request protegida como
    header `Authorization: Bearer <token>`.
    """
    usuario = db.query(Usuario).filter(Usuario.email == payload.email).first()
    if not usuario or not verify_password(payload.password, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    if usuario.estado_cuenta != EstadoCuenta.ACTIVA:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La cuenta no está activa")

    token = create_access_token(subject=str(usuario.id_usuario), extra_claims={"rol": usuario.rol})
    return Token(access_token=token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión",
    responses={401: {"description": "Token faltante, inválido o expirado"}},
)
def logout(usuario: Usuario = Depends(get_current_user)):
    """HU-03 T03 — El JWT es stateless y no hay tabla de sesiones/blacklist en el
    DER acordado con la PM, así que no se revoca el token en el servidor. Este
    endpoint exige un token válido (confirma que había sesión activa); el cierre
    de sesión real lo hace el cliente descartando el token guardado."""
    return


@router.get(
    "/me",
    response_model=PerfilOut,
    summary="Perfil del usuario autenticado (nombre y correo)",
    responses={401: {"description": "Falta token o es inválido"}},
)
def perfil_actual(usuario: Usuario = Depends(get_current_user)):
    """HU-03 / CA02 — Lo que muestra la vista "Perfil del usuario" al volver del
    login: nombre, correo y nada más. El perfil de Oferente (categoría, fotos,
    etc.) es otra HU y se consulta aparte con `GET /oferentes/{id}`."""
    return usuario


@router.get(
    "/google/login",
    summary="Inicia el login con Google (CA01): redirige a Auth0",
    responses={
        302: {"description": "Redirige a la pantalla de Google/Auth0"},
        503: {"description": "Auth0 no está configurado en este entorno"},
    },
)
def iniciar_login_google(auth0: Auth0Service = Depends(get_auth0_service)):
    """El frontend manda al usuario acá cuando presiona "Iniciar sesión con
    Google". El `state` viaja en una cookie de corta duración, de un solo uso,
    para que `/google/callback` pueda confirmar que la vuelta corresponde a
    esta ida (protección CSRF del flujo OAuth) — no reemplaza ninguna sesión:
    el login sigue siendo stateless."""
    if not settings.auth0_habilitado:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="El login con Google no está configurado")

    state = secrets.token_urlsafe(24)
    respuesta = RedirectResponse(url=auth0.url_autorizacion(state), status_code=status.HTTP_302_FOUND)
    respuesta.set_cookie(
        COOKIE_ESTADO_OAUTH,
        state,
        max_age=300,
        httponly=True,
        samesite="lax",
        secure=not settings.frontend_url.startswith("http://localhost"),
    )
    return respuesta


def _redirect_error(motivo: str) -> RedirectResponse:
    url = f"{settings.frontend_url_base}{settings.google_login_ruta_error}?{urlencode({'error': 'auth_failed', 'motivo': motivo})}"
    respuesta = RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)
    respuesta.delete_cookie(COOKIE_ESTADO_OAUTH)
    return respuesta


@router.get(
    "/google/callback",
    summary="Vuelta de Auth0 tras el login con Google (CA02/CA03)",
    responses={302: {"description": "Redirige al frontend, con el token (éxito) o con ?error=auth_failed (falla)"}},
)
def callback_login_google(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    auth0: Auth0Service = Depends(get_auth0_service),
):
    """CA02 — Autenticación exitosa: redirige a la vista de perfil con el JWT
    propio (mismo formato que `/login`; el resto del backend no distingue de
    qué flujo vino).
    CA03 — Autenticación fallida: redirige a la pantalla de login con
    `?error=auth_failed`, **sin** token. Cualquier falla (el usuario canceló en
    Google, Auth0 rechazó el intercambio, el mail no vino verificado, la cuenta
    está suspendida) cae en esta misma rama."""
    cookie_state = request.cookies.get(COOKIE_ESTADO_OAUTH)
    if error or not code or not state or not cookie_state or state != cookie_state:
        return _redirect_error("state_invalido" if not error else error)

    try:
        perfil = auth0.obtener_perfil(code)
    except Auth0Error:
        return _redirect_error("auth0_error")

    usuario = db.query(Usuario).filter(Usuario.email == perfil.email).first()
    if usuario:
        if usuario.estado_cuenta != EstadoCuenta.ACTIVA:
            return _redirect_error("cuenta_inactiva")
        usuario.nombre = perfil.nombre
    else:
        usuario = Usuario(
            email=perfil.email,
            # Cuenta creada por Google: sin contraseña utilizable. El hash es
            # de un valor aleatorio que nadie conoce, así que /login (email +
            # password) nunca la puede autenticar por accidente.
            password_hash=hash_password(secrets.token_urlsafe(32)),
            rol=RolUsuario.OFERENTE,
            nombre=perfil.nombre,
        )
        db.add(usuario)
    db.commit()
    db.refresh(usuario)

    token = create_access_token(subject=str(usuario.id_usuario), extra_claims={"rol": usuario.rol})
    url = f"{settings.frontend_url_base}{settings.google_login_ruta_exito}?{urlencode({'token': token})}"
    respuesta = RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)
    respuesta.delete_cookie(COOKIE_ESTADO_OAUTH)
    return respuesta
