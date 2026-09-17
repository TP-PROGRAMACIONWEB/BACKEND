from datetime import date
from pathlib import Path

from app.services.padrones import PLACEHOLDER_CATEGORIA, PLACEHOLDER_VENCIMIENTO, parsear_padron_json, parsear_padron_md

PADRONES_DIR = Path(__file__).resolve().parent.parent / "db" / "padrones"
GASISTAS_PATH = PADRONES_DIR / "gasistas.md"
AIRE_ACONDICIONADO_PATH = PADRONES_DIR / "aire-acondicionado.json"


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


# --- Aire acondicionado (export JSON, parcial: 50 de 77 filas totales) ------


def test_parsea_49_filas_validas_de_las_50_del_export():
    """La fila 50 es "Alias, Rado Federico" con matrícula 111111111 (9
    dígitos): ruido de prueba mezclado en el export, no un matriculado real
    (además de que el nombre se repite con una matrícula de 8 dígitos)."""
    filas = parsear_padron_json(AIRE_ACONDICIONADO_PATH)
    assert len(filas) == 49


def test_descarta_la_fila_con_matricula_de_longitud_distinta():
    filas = parsear_padron_json(AIRE_ACONDICIONADO_PATH)
    numeros = {fila.numero_matricula for fila in filas}
    assert "111111111" not in numeros
    assert all(len(numero) == 8 for numero in numeros)


def test_fila_limpia_de_aire_acondicionado():
    filas = parsear_padron_json(AIRE_ACONDICIONADO_PATH)
    abatedaga = next(fila for fila in filas if fila.numero_matricula == "28408435")
    assert abatedaga.nombre_matriculado == "ABATEDAGA MARTIN"


def test_alias_rado_federico_sigue_con_su_matricula_real_de_8_digitos():
    """Se descarta la fila de prueba (111111111), no a la persona: su
    matrícula real (40297082, 8 dígitos) sigue en el padrón."""
    filas = parsear_padron_json(AIRE_ACONDICIONADO_PATH)
    numeros_de_alias = [f.numero_matricula for f in filas if f.nombre_matriculado == "ALIAS RADO FEDERICO"]
    assert numeros_de_alias == ["40297082"]


def test_categoria_y_vencimiento_son_el_placeholder_documentado():
    """El export no trae estos dos campos (a diferencia del de Gasistas): se
    usa un valor explícito hasta que llegue el dato real."""
    filas = parsear_padron_json(AIRE_ACONDICIONADO_PATH)
    assert all(fila.categoria == PLACEHOLDER_CATEGORIA for fila in filas)
    assert all(fila.fecha_vencimiento == PLACEHOLDER_VENCIMIENTO for fila in filas)
    assert PLACEHOLDER_VENCIMIENTO > date.today()  # para que nadie dé "Vencida" con el placeholder
