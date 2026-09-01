from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.database import get_db
from app.models.alerta_admin import AlertaAdministrador
from app.models.resena import Resena
from app.models.usuario import EstadoCuenta, Usuario
from app.schemas.resena import ResenaAdminOut
from app.schemas.usuario import UsuarioOut

router = APIRouter(prefix="/api/v1/admin", tags=["Administración"], dependencies=[Depends(require_admin)])


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db)):
    """RF14 — Gestión de usuarios."""
    return db.query(Usuario).all()


@router.patch("/usuarios/{usuario_id}/estado", response_model=UsuarioOut)
def cambiar_estado_usuario(usuario_id: int, estado: EstadoCuenta, db: Session = Depends(get_db)):
    """RF15 — Bloquear o suspender usuarios."""
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    usuario.estado_cuenta = estado
    db.commit()
    db.refresh(usuario)
    return usuario


@router.get("/alertas")
def listar_alertas(db: Session = Depends(get_db)):
    """RF17 — Revisión de alertas por rechazos reiterados de reseñas."""
    return db.query(AlertaAdministrador).order_by(AlertaAdministrador.fecha_creacion.desc()).all()


@router.get("/resenas/rechazadas", response_model=list[ResenaAdminOut])
def listar_resenas_rechazadas(db: Session = Depends(get_db)):
    """RF17 — El administrador puede revisar y revertir rechazos incorrectos."""
    return db.query(Resena).filter(Resena.estado == "rechazada").order_by(Resena.fecha_creacion.desc()).all()


@router.patch("/resenas/{resena_id}/publicar", response_model=ResenaAdminOut)
def publicar_resena_rechazada(resena_id: int, db: Session = Depends(get_db)):
    """RF17 — El Administrador, como instancia final, publica una reseña rechazada por el Oferente."""
    resena = db.get(Resena, resena_id)
    if not resena:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseña no encontrada")

    resena.estado = "aprobada"
    db.commit()
    db.refresh(resena)
    return resena
