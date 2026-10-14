"""Pipeline unificado: scrapers -> normalizar -> upsert idempotente -> reporte + log (CA02-CA04).

Solo escribe en `padron_matriculas`. Nunca toca `matriculas` ni
`validaciones_matricula`. Transacción única: commit o rollback total.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.matricula import PadronMatricula
from app.services.padrones import parsear_padron_json, parsear_padron_md
from app.services.scrapers.base import FilaPadronExterna, normalizar_texto

DIGITOS = {"Gasista": (2, 10), "Aire acondicionado": (8, 8)}


def _log_dir() -> Path:
    """En Vercel el repo es read-only: usa /tmp como fallback (CA04)."""
    import tempfile

    for candidato in (Path("docs/padron_sync_logs"), Path(tempfile.gettempdir()) / "padron_sync_logs"):
        try:
            candidato.mkdir(parents=True, exist_ok=True)
            return candidato
        except OSError:
            continue
    return Path(tempfile.gettempdir())


def validar_fila(f: FilaPadronExterna) -> str | None:
    if not f.numero_matricula or not f.numero_matricula.isdigit():
        return f"numero no numérico: {f.numero_matricula!r}"
    lo, hi = DIGITOS.get(f.tipo_profesional, (1, 20))
    if not (lo <= len(f.numero_matricula) <= hi):
        return f"longitud fuera de rango {lo}-{hi}: {f.numero_matricula!r}"
    if not normalizar_texto(f.nombre_matriculado):
        return "nombre vacío"
    return None


def upsert_filas(db: Session, filas: list[FilaPadronExterna], dry_run: bool = False) -> dict:
    reporte = {"total": len(filas), "insertadas": 0, "actualizadas": 0, "intactas": 0, "rechazadas": [], "fuente": ""}
    # Dedup intra-lote por (tipo, numero): última gana.
    unicas: dict[tuple[str, str], FilaPadronExterna] = {}
    for f in filas:
        motivo = validar_fila(f)
        if motivo:
            reporte["rechazadas"].append({"numero": f.numero_matricula, "nombre": f.nombre_matriculado[:60], "motivo": motivo})
            continue
        unicas[(f.tipo_profesional, f.numero_matricula)] = f
    for (tipo, numero), f in unicas.items():
        ex = (
            db.query(PadronMatricula)
            .filter(PadronMatricula.tipo_profesional == tipo, PadronMatricula.numero_matricula == numero)
            .first()
        )
        if not ex:
            if not dry_run:
                db.add(
                    PadronMatricula(
                        tipo_profesional=tipo,
                        numero_matricula=numero,
                        nombre_matriculado=normalizar_texto(f.nombre_matriculado),
                        categoria=f.categoria,
                        fecha_vencimiento=f.fecha_vencimiento,
                    )
                )
            reporte["insertadas"] += 1
        elif (
            ex.nombre_matriculado != normalizar_texto(f.nombre_matriculado)
            or ex.categoria != f.categoria
            or ex.fecha_vencimiento != f.fecha_vencimiento
        ):
            if not dry_run:
                ex.nombre_matriculado = normalizar_texto(f.nombre_matriculado)
                ex.categoria = f.categoria
                ex.fecha_vencimiento = f.fecha_vencimiento
            reporte["actualizadas"] += 1
        else:
            reporte["intactas"] += 1
    return reporte


def sincronizar(db: Session, filas: list[FilaPadronExterna], origen: str, dry_run: bool = False) -> dict:
    """Ejecuta upsert en una transacción. Si dry_run, hace rollback al final."""
    reporte = upsert_filas(db, filas, dry_run=dry_run)
    reporte["origen"] = origen
    reporte["dry_run"] = dry_run
    if dry_run:
        db.rollback()
    else:
        db.commit()
    # Log auditoría a archivo (CA04). Nunca tumba la corrida.
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_dir = _log_dir()
        (log_dir / f"sync_{ts}.json").write_text(
            json.dumps({**reporte, "rechazadas": reporte["rechazadas"][:50]}, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        reporte["log_path"] = str(log_dir / f"sync_{ts}.json")
    except Exception:
        pass
    return reporte


def filas_desde_archivos_locales() -> list[FilaPadronExterna]:
    """Reusa parsers actuales (gasistas.md + aire.json) como FilaPadronExterna."""
    base = Path(__file__).resolve().parents[1] / "db" / "padrones"
    out: list[FilaPadronExterna] = []
    for f in parsear_padron_md(base / "gasistas.md"):
        out.append(
            FilaPadronExterna("Gasista", f.numero_matricula, f.nombre_matriculado, f.categoria, f.fecha_vencimiento, fuente="local:gasistas.md")
        )
    for f in parsear_padron_json(base / "aire-acondicionado.json"):
        out.append(
            FilaPadronExterna("Aire acondicionado", f.numero_matricula, f.nombre_matriculado, f.categoria, f.fecha_vencimiento, fuente="local:aire.json")
        )
    return out
