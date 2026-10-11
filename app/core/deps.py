from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.oferente import Oferente
from app.models.usuario import RolUsuario, Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
# Para los endpoints que aceptan anónimos (calificar sin login, HU-01): sin
# header devuelve None en vez de 401.
oauth2_scheme_opcional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la credencial",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    usuario = db.get(Usuario, int(user_id))
    if usuario is None:
        raise credentials_exception
    return usuario


def require_admin(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    if usuario.rol != RolUsuario.ADMINISTRADOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere permisos de administrador")
    return usuario


def get_current_user_opcional(token: str | None = Depends(oauth2_scheme_opcional), db: Session = Depends(get_db)) -> Usuario | None:
    """Usuario logueado, o None si la request es anónima. Un token presente pero
    inválido sigue dando 401: no se trata como anónimo en silencio."""
    if not token:
        return None
    return get_current_user(token=token, db=db)


def get_oferente_registrado(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> Oferente:
    """Guard de HU-04 (CA01, caso A9). El frontend también redirige, pero el
    backend no confía en eso: sin la fila de OFERENTE no hay perfil y no se
    opera sobre él."""
    if usuario.rol != RolUsuario.OFERENTE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"codigo": "rol_invalido", "mensaje": "Solo los Profesionales pueden realizar esta acción"},
        )
    oferente = db.get(Oferente, usuario.id_usuario)
    if oferente is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"codigo": "registro_incompleto", "mensaje": "Completá el registro de Profesional para continuar"},
        )
    return oferente


def get_usuario_registrado(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> Usuario:
    """Para las rutas que sirven a Oferentes y Administradores (la bandeja): el
    Oferente tiene que haber completado el registro; el Administrador, no."""
    if usuario.rol == RolUsuario.OFERENTE and db.get(Oferente, usuario.id_usuario) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"codigo": "registro_incompleto", "mensaje": "Completá el registro de Profesional para continuar"},
        )
    return usuario
