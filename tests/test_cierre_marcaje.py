"""Cierres FINAL/MD/MT y cantidadreal (docs/ai/04 §0, §4-6; docs/ai/05)."""
import pytest

from services.cierres_service import ejecutar_cierre_marcaje_real, simular_cierre_marcaje

MAC = "AABBCCDDEEFF"
MARCAJE = {
    "id": "REAL_BD|M1|51151|PEG CAJ2|H TIR FG", "numOp": "51151", "recurso": "PEG CAJ2",
    "actividad": "H TIR FG", "cantidad": 1000, "username": "M1", "topic": f"{MAC}-OP", "mac": MAC,
}
FILA_ACTIVA = [(51151, "PEG CAJ2", "H TIR FG", "M1", f"{MAC}-OP")]


def preparar(bd, cantpliegos=500, suma_mt=None):
    bd.responder(r"estado = 'MT'", [(suma_mt,)])  # suma de MT anteriores
    bd.responder(r"COALESCE", [(cantpliegos, "2026-10-12 08:00:00", "2026-10-12 09:00:00", 60)])
    bd.responder(r"SUM\(cantidadreal\), MIN\(tiempoinicio\)", [(cantpliegos, "2026-10-12 08:00:00", "2026-10-12 09:00:00", 60)])
    bd.responder(r"FROM wo_task200", [(5115101, 7)], origen="optimus")
    bd.responder(r"FROM smartfactory.marcajeactivo", FILA_ACTIVA)
    return bd


def test_flags_desactivados_no_hacen_nada(bd, mqtt):
    preparar(bd)
    r = ejecutar_cierre_marcaje_real(MARCAJE, "FINAL", 0)
    assert r["ok"] is False and r["modo"] == "PROTEGIDO_BD"
    assert bd.escrituras() == [] and mqtt.publicaciones == []


def test_final_orden_de_efectos(bd, escritura_habilitada):
    preparar(bd)
    r = ejecutar_cierre_marcaje_real(MARCAJE, "FINAL", 0)
    assert r["ok"] is True
    assert bd.secuencia() == [
        f"MQTT {MAC}-OP",
        "INSERT INTO smartfactory.resumenmarcajes",   # fila del usuario
        "INSERT INTO smartfactory.resumenmarcajes",   # agregado SMARTFACTORY / F
        "DELETE FROM smartfactory.datossensados",
        "DELETE FROM smartfactory.marcajeactivo",
    ]
    paro = [e for e in bd.eventos if e[0] == "MQTT"][0][2]
    assert paro == "[51151,PEG CAJ2,H TIR FG,1000,0,2026/10/12,08:00:00,2026/10/12,09:00:00,0,0]"
    fila_usuario, fila_f = [s for s in bd.escrituras() if "resumenmarcajes" in s]
    assert "'500', 'M1'" in fila_usuario and "NULL" in fila_usuario
    assert "'SMARTFACTORY'" in fila_f and "'F'" in fila_f


def test_mt_no_publica_y_devuelve_relevo(bd, mqtt, escritura_habilitada):
    preparar(bd)
    r = ejecutar_cierre_marcaje_real(MARCAJE, "MT", 0)
    assert r["ok"] is True
    assert mqtt.publicaciones == []
    assert "'MT'" in bd.escrituras()[0]
    assert {k: r["relevo_pendiente"][k] for k in ("numOp", "recurso", "actividad", "mac")} == {
        "numOp": "51151", "recurso": "PEG CAJ2", "actividad": "H TIR FG", "mac": MAC}


def test_pausa_improductiva_solo_con_md(bd, escritura_habilitada):
    preparar(bd)
    r = ejecutar_cierre_marcaje_real(MARCAJE, "FINAL", 5, pausa_improductiva=True)
    assert r["ok"] is False and "solo puede ejecutarse como cierre MD" in r["mensaje"]
    assert bd.escrituras() == []


def test_md_por_pausa_marca_variable01(bd, escritura_habilitada):
    preparar(bd)
    assert ejecutar_cierre_marcaje_real(MARCAJE, "MD", 5, pausa_improductiva=True)["ok"] is True
    insert = bd.escrituras()[0]
    assert "variable01" in insert and "'MD'" in insert and insert.rstrip(";").endswith(", 1)")


def test_publicacion_fallida_aborta_sin_tocar_bd(bd, mqtt, escritura_habilitada):
    preparar(bd)
    mqtt.resultado = {"ok": False, "mensaje": "sin conexión (doble)"}
    r = ejecutar_cierre_marcaje_real(MARCAJE, "MD", 0)
    assert r["ok"] is False and r["modo"] == "MQTT_NO_PUBLICADO"
    assert bd.escrituras() == []


@pytest.mark.caracterizacion
def test_insert_resumen_fallido_aborta_sin_delete(bd, mqtt, escritura_habilitada):
    """R-01 (parcial, decisión Fase 6, 2026-11-14): si falla el INSERT del operario se aborta
    antes del agregado y de los DELETE; el paro MQTT (MD) ya se publicó y se avisa."""
    preparar(bd)
    bd.responder(r"INSERT INTO smartfactory.resumenmarcajes", None)
    r = ejecutar_cierre_marcaje_real(MARCAJE, "MD", 0)
    assert r["ok"] is False and r["modo"] == "INSERT_RESUMEN_FALLIDO"
    assert "paro MQTT ya fue publicado" in r["mensaje"]
    assert not any(s.startswith("DELETE") for s in bd.escrituras())
    assert len(mqtt.publicaciones) == 1


@pytest.mark.caracterizacion
def test_cantidadreal_resta_mt_sin_filtrar_recurso_y_puede_ser_negativa(bd, tmp_path):
    """R-02 / N1: la suma de MT no filtra recurso; el negativo se guarda y se registra en el log."""
    preparar(bd, cantpliegos=0, suma_mt=1)
    sim = simular_cierre_marcaje(MARCAJE, "FINAL", 0)["simulacion"]
    assert sim["valores"]["cantreal_calculada"] == -1
    consulta_mt = [s for s in bd.sql("smartfactory") if "estado = 'MT'" in s][0]
    assert "recurso" not in consulta_mt and "mac" not in consulta_mt
    assert (tmp_path / "cantidadreal_negativos.log").exists()


@pytest.mark.caracterizacion
def test_agregado_final_no_excluye_filas_f(bd, escritura_habilitada):
    """R-13 / N8: el agregado FINAL suma todas las filas de numOp+actividad, incluidas las 'F'."""
    preparar(bd)
    ejecutar_cierre_marcaje_real(MARCAJE, "FINAL", 0)
    agregado = [s for s in bd.sql("smartfactory") if "MIN(tiempoinicio)" in s][0]
    assert "estado" not in agregado and "recurso" not in agregado


def test_api_cierre_quita_el_marcaje_de_memoria(cliente, bd, escritura_habilitada):
    from services import marcajes_estado_service as estado

    estado.agregar_o_actualizar_marcaje_estado(dict(MARCAJE))
    preparar(bd)
    r = cliente.post("/api/marcajes/ejecutar-cierre-real",
                     json={"marcaje": MARCAJE, "tipo_cierre": "FINAL", "total_usuario": 0})
    assert r.status_code == 200, r.text
    assert r.json()["marcajes"] == []
