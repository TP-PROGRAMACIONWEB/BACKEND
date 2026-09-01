from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_db
from app.models.usuario import EstadoCuenta, Usuario
from app.schemas.usuario import Token, UsuarioCreate, UsuarioLogin, UsuarioOut

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])


@router.post("/registro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def registrar_usuario(payload: UsuarioCreate, db: Session = Depends(get_db)):
    """RF1/RF4 — Registro de nuevos usuarios Oferentes."""
    if db.query(Usuario).filter(Usuario.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email ya está registrado")

    usuario = Usuario(email=payload.email, password_hash=hash_password(payload.password))
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post("/login", response_model=Token)
def login(payload: UsuarioLogin, db: Session = Depends(get_db)):
    """RF4 — Inicio de sesión."""
    usuario = db.query(Usuario).filter(Usuario.email == payload.email).first()
    if not usuario or not verify_password(payload.password, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    if usuario.estado_cuenta != EstadoCuenta.ACTIVA:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La cuenta no está activa")

    token = create_access_token(subject=str(usuario.id_usuario), extra_claims={"rol": usuario.rol})
    return Token(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(usuario: Usuario = Depends(get_current_user)):
    """HU-03 T03 — El JWT es stateless y no hay tabla de sesiones/blacklist en el
    DER acordado con la PM, así que no se revoca el token en el servidor. Este
    endpoint exige un token válido (confirma que había sesión activa); el cierre
    de sesión real lo hace el cliente descartando el token guardado."""
    return
