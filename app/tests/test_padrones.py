from datetime import date
from pathlib import Path

from app.services.padrones import parsear_padron_md

GASISTAS_PATH = Path(__file__).resolve().parent.parent / "db" / "padrones" / "gasistas.md"


def test_parsea_68_filas_del_padron_real():
    filas = parsear_padron_md(GASISTAS_PATH)
    assert len(filas) == 68


def test_encabezado_suelto_y_header_de_tabla_no_generan_fila():
    filas = parsear_padron_md(GASISTAS_PATH)
    nombres = {fila.nombre_matriculado for fila in filas}
    assert "LISTADO DE MATRICULADOS HABILITADOS" not in nombres
    assert "NOMBRE" not in nombres


def test_fila_limpia():
    filas = parsear_padron_md(GASISTAS_PATH)
    alessi = next(fila for fila in filas if fila.nombre_matriculado == "ALESSI MARIA CLARA")
    assert alessi.numero_matricula == "1000008919"
    assert alessi.categoria == "Primera"
    assert alessi.fecha_vencimiento == date(2027, 3, 31)


def test_fila_con_categoria_y_vencimiento_duplicados_en_la_misma_celda():
    filas = parsear_padron_md(GASISTAS_PATH)
    gonzalez = next(fila for fila in filas if fila.nombre_matriculado == "GONZALEZ MARIA LAURA")
    assert gonzalez.numero_matricula == "1000002233"
    assert gonzalez.categoria == "Primera"
    assert gonzalez.fecha_vencimiento == date(2027, 3, 31)


def test_fila_con_direccion_metida_en_el_telefono_no_afecta_la_matricula():
    filas = parsear_padron_md(GASISTAS_PATH)
    peverengo = next(fila for fila in filas if fila.nombre_matriculado == "PEVERENGO ERICA")
    assert peverengo.numero_matricula == "1000001777"


def test_fila_con_cero_inicial_en_el_telefono_no_afecta_la_matricula():
    filas = parsear_padron_md(GASISTAS_PATH)
    romero = next(fila for fila in filas if fila.nombre_matriculado == "ROMERO TATIANA")
    assert romero.numero_matricula == "1000002470"
