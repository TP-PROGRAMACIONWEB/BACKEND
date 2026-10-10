"""Tests CA02/CA03: pipeline sin duplicados ni corrupción (SQLite memoria)."""

from datetime import date

from app.services.padrones_sync import sincronizar
from app.services.scrapers.base import FilaPadronExterna


def _fila(numero="1000008919", nombre="ALESSI MARIA CLARA"):
    return FilaPadronExterna("Gasista", numero, nombre, "Primera", date(2027, 3, 31), fuente="test")


def test_idempotente_doble_corrida(db_session):
    from app.models.matricula import PadronMatricula

    r1 = sincronizar(db_session, [_fila()], origen="test", dry_run=False)
    assert r1["insertadas"] == 1
    r2 = sincronizar(db_session, [_fila()], origen="test", dry_run=False)
    assert r2["insertadas"] == 0 and r2["intactas"] == 1
    assert db_session.query(PadronMatricula).count() == 1


def test_rechaza_no_numerico(db_session):
    r = sincronizar(db_session, [_fila(numero="ABC123")], origen="test", dry_run=False)
    assert r["insertadas"] == 0 and len(r["rechazadas"]) == 1


def test_dry_run_no_escribe(db_session):
    from app.models.matricula import PadronMatricula

    antes = db_session.query(PadronMatricula).count()
    r = sincronizar(db_session, [_fila(numero="1000004305")], origen="test", dry_run=True)
    assert r["insertadas"] == 1
    assert db_session.query(PadronMatricula).count() == antes
