"""Pliegos incorrectos en el cierre (Fase 6, v20.24). Ver docs/ai/04 §4 y docs/ai/05 §1."""
from decimal import Decimal

import pytest

from services.cierres_service import ejecutar_cierre_marcaje_real, simular_cierre_marcaje
from tests.test_cierre_marcaje import MARCAJE, preparar

URL = "/api/marcajes/ejecutar-cierre-real"


def insert_usuario(bd) -> str:
    return bd.escrituras()[0]


def insert_f(bd) -> str:
    return [s for s in bd.escrituras() if "'SMARTFACTORY'" in s][0]


@pytest.mark.parametrize("tipo", ["FINAL", "MD", "MT"])
def test_guarda_buenos_e_incorrectos_por_separado(bd, escritura_habilitada, tipo):
    preparar(bd)
    r = ejecutar_cierre_marcaje_real(MARCAJE, tipo, 480, pliegos_incorrectos=20)
    assert r["ok"] is True, r
    sql = insert_usuario(bd)
    assert "totalUsuario" in sql and "'480'" in sql
    assert "pliegosIncorrectos)" in sql and sql.rstrip(";").endswith(", 20)")
    # Los incorrectos no se restan de los buenos ni de cantidadreal.
    assert r["valores"]["cantreal_calculada"] == 500
    assert r["valores"]["totalUsuario"] == "480"
    assert r["valores"]["pliegosIncorrectos"] == 20


def test_cero_incorrectos_se_guarda_como_cero(bd, escritura_habilitada):
    preparar(bd)
    assert ejecutar_cierre_marcaje_real(MARCAJE, "MD", 10, pliegos_incorrectos=0)["ok"] is True
    assert insert_usuario(bd).rstrip(";").endswith(", 0)")


@pytest.mark.parametrize("valor", [-1, 1.5, "3", True, 2_147_483_648])
def test_servicio_rechaza_valores_invalidos_sin_efectos(bd, mqtt, escritura_habilitada, valor):
    preparar(bd)
    r = ejecutar_cierre_marcaje_real(MARCAJE, "FINAL", 10, pliegos_incorrectos=valor)
    assert r["ok"] is False and "Pliegos incorrectos" in r["mensaje"]
    assert bd.escrituras() == [] and mqtt.publicaciones == []


@pytest.mark.parametrize("valor", [-1, 1.5, "3", "abc", True, 2_147_483_648])
def test_api_rechaza_valores_invalidos_con_422(cliente, bd, mqtt, escritura_habilitada, valor):
    preparar(bd)
    r = cliente.post(URL, json={"marcaje": MARCAJE, "tipo_cierre": "FINAL", "total_usuario": 10,
                                "pliegos_incorrectos": valor})
    assert r.status_code == 422, r.text
    assert bd.escrituras() == [] and mqtt.publicaciones == []


def test_api_contrato_anterior_sin_campo_guarda_null(cliente, bd, escritura_habilitada):
    preparar(bd)
    r = cliente.post(URL, json={"marcaje": MARCAJE, "tipo_cierre": "MD", "total_usuario": 10})
    assert r.status_code == 200, r.text
    assert insert_usuario(bd).rstrip(";").endswith(", NULL)")


def test_api_acepta_valor_valido(cliente, bd, escritura_habilitada):
    preparar(bd)
    r = cliente.post(URL, json={"marcaje": MARCAJE, "tipo_cierre": "MT", "total_usuario": 10,
                                "pliegos_incorrectos": 7})
    assert r.status_code == 200, r.text
    assert insert_usuario(bd).rstrip(";").endswith(", 7)")


def test_fila_f_suma_solo_filas_de_operario(bd, escritura_habilitada):
    preparar(bd)
    bd.responder(r"SUM\(pliegosIncorrectos\)", [(Decimal("35"),)])
    r = ejecutar_cierre_marcaje_real(MARCAJE, "FINAL", 10, pliegos_incorrectos=5)
    assert r["agregado_final"]["pliegosIncorrectos"] == 35
    consulta = [s for s in bd.sql("smartfactory") if "SUM(pliegosIncorrectos)" in s][0]
    assert "estado <> 'F'" in consulta and "numOp = '51151'" in consulta
    assert insert_f(bd).rstrip().endswith(", 35)")


def test_fila_f_null_si_falla_la_suma(bd, escritura_habilitada):
    preparar(bd)
    bd.responder(r"SUM\(pliegosIncorrectos\)", None)
    r = ejecutar_cierre_marcaje_real(MARCAJE, "FINAL", 10, pliegos_incorrectos=5)
    assert r["ok"] is True
    assert insert_f(bd).rstrip().endswith(", NULL)")


def test_improductivo_guarda_null(bd, escritura_habilitada):
    preparar(bd)
    improductivo = {**MARCAJE, "numOp": "12345", "actividad": "COMIDA"}
    bd.responder(r"FROM smartfactory.marcajeactivo", [(12345, "PEG CAJ2", "COMIDA", "M1", MARCAJE["topic"])])
    r = ejecutar_cierre_marcaje_real(improductivo, "MD", 0, pliegos_incorrectos=9)
    assert r["ok"] is True and r["valores"]["pliegosIncorrectos"] is None
    assert insert_usuario(bd).rstrip(";").endswith(", NULL)")


def test_cantidadreal_y_agregado_no_cambian(bd):
    """Regresión: el cálculo de cantidadreal y la consulta del agregado son idénticos con o sin el dato."""
    preparar(bd, cantpliegos=500, suma_mt=120)
    sin = simular_cierre_marcaje(MARCAJE, "FINAL", 10)["simulacion"]
    con = simular_cierre_marcaje(MARCAJE, "FINAL", 10, pliegos_incorrectos=40)["simulacion"]
    for clave in ("cantreal_original", "suma_mt_anterior", "cantreal_calculada", "tiempoinicio",
                  "tiempofinal", "duracion_minutos", "totalUsuario"):
        assert sin["valores"][clave] == con["valores"][clave]
    assert con["valores"]["cantreal_calculada"] == 380
    agregado_historico = (
        "SELECT SUM(cantidadreal), MIN(tiempoinicio), MAX(tiempofinal), SUM(duracion)\n"
        "FROM smartfactory.resumenmarcajes\n"
        "WHERE actividad = 'H TIR FG'\n"
        "  AND numOp = '51151';"
    )
    assert agregado_historico in con["base_datos"]["sql_completo"]
