from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from config import ENABLE_REAL_MQTT_DB_WRITES

try:
    from db.conexion import dtbSmartFactory
except Exception:  # pragma: no cover
    dtbSmartFactory = None


COLUMNAS_ESPERADAS_DATOS = 8
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "mqtt_persistencia.log"
LOG_ALERTA_CONGLOMERADO_FILE = LOG_DIR / "mqtt_conglomerado_alertas.log"
UMBRAL_ALERTA_UNIDADES_CONGLOMERADO = 48


def _serializar_json_seguro(valor: Any) -> str:
    try:
        return json.dumps(valor, ensure_ascii=False, default=str, indent=2)
    except Exception:
        return str(valor)


def _log_alerta_conglomerado(contexto: dict[str, Any]) -> None:
    """
    Registra diagnóstico detallado cuando unidadesCalculadasConglomerado supera el umbral esperado.
    Este log ayuda a auditar querys, respuestas y cálculo realizado sin detener la operación.
    """
    try:
        with LOG_ALERTA_CONGLOMERADO_FILE.open("a", encoding="utf-8") as archivo:
            archivo.write("\n" + "=" * 120 + "\n")
            archivo.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ALERTA_CONGLOMERADO_MAYOR_A_{UMBRAL_ALERTA_UNIDADES_CONGLOMERADO}\n")
            archivo.write(_serializar_json_seguro(contexto))
            archivo.write("\n")
    except Exception:
        pass


def _log(linea: str) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as archivo:
            archivo.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {linea}\n")
    except Exception:
        pass


def _limpiar(valor: Any) -> str:
    return "" if valor is None else str(valor).strip()


def _escape_sql(valor: Any) -> str:
    """
    Se usa porque la clase actual dtbSmartFactory recibe un query string.
    En una futura capa repository conviene migrar a cursor.execute(query, params).
    """
    texto = _limpiar(valor)
    return texto.replace("'", "''")


def _a_entero(valor: Any, default: int | None = None) -> int | None:
    try:
        return int(float(str(valor).strip()))
    except Exception:
        return default


def _parsear_payload_datos(payload: str) -> dict[str, Any]:
    partes = [_limpiar(p) for p in str(payload or "").split(",")]

    if len(partes) < COLUMNAS_ESPERADAS_DATOS:
        return {
            "ok": False,
            "motivo": (
                "Payload DATOS incompleto. Se esperaban 8 campos: "
                "numOp,cantpliegos,actividad,actividadreal,velocidadreal,fecha,tiempo,unidadesSensadasPeriodo."
            ),
            "partes": partes,
        }

    num_op = partes[0]
    if num_op == "N/A":
        num_op = "100"

    fecha = partes[5]
    tiempo = partes[6]
    fechatiempo = f"{fecha} {tiempo}"

    return {
        "ok": True,
        "numOp": num_op,
        "cantpliegos": partes[1],
        "actividad": partes[2],
        "actividadreal": partes[3],
        "velocidadreal": partes[4],
        "fecha": fecha,
        "tiempo": tiempo,
        "fechatiempo": fechatiempo,
        "unidadesSensadasPeriodo": partes[7],
        "partes": partes,
    }


def _buscar_cantpliegos_anterior(mac: str) -> dict[str, Any]:
    if dtbSmartFactory is None:
        return {
            "ok": False,
            "cantpliegos_anterior": None,
            "motivo": "No se pudo importar dtbSmartFactory; no se consultó cantpliegos anterior.",
        }

    mac_limpia = _escape_sql(mac)
    query = f"""
        SELECT cantpliegos
        FROM smartfactory.mensajes_mqtt
        WHERE mac = '{mac_limpia}'
        ORDER BY fechatiempo DESC
        LIMIT 1
    """

    try:
        resultado = dtbSmartFactory(query).consultaSmartFactory()
        if not resultado:
            return {
                "ok": True,
                "cantpliegos_anterior": None,
                "query": query.strip(),
                "resultado_query": resultado,
                "motivo": "No existe mensaje anterior para esta MAC.",
            }

        anterior = _a_entero(resultado[0][0], None)
        return {
            "ok": True,
            "cantpliegos_anterior": anterior,
            "query": query.strip(),
            "resultado_query": resultado,
            "motivo": "Cantpliegos anterior consultado correctamente.",
        }
    except Exception as error:
        return {
            "ok": False,
            "cantpliegos_anterior": None,
            "query": query.strip(),
            "resultado_query": None,
            "motivo": f"Error consultando cantpliegos anterior: {error}",
        }


def _calcular_unidades_conglomerado(actual: int | None, anterior: int | None) -> dict[str, Any]:
    if actual is None:
        return {
            "ok": False,
            "unidadesCalculadasConglomerado": None,
            "motivo": "No se pudo convertir cantpliegos actual a número.",
            "tipo_calculo": "ERROR",
        }

    if anterior is None:
        return {
            "ok": True,
            "unidadesCalculadasConglomerado": actual,
            "motivo": "No existe cantpliegos anterior; se toma el actual como producción calculada inicial.",
            "tipo_calculo": "SIN_ANTERIOR",
        }

    if actual >= anterior:
        return {
            "ok": True,
            "unidadesCalculadasConglomerado": actual - anterior,
            "motivo": "Cálculo normal: actual - anterior.",
            "tipo_calculo": "DIFERENCIA",
        }

    return {
        "ok": True,
        "unidadesCalculadasConglomerado": actual,
        "motivo": "Reset detectado: actual menor que anterior; se toma actual como producción.",
        "tipo_calculo": "RESET",
    }


def _armar_insert_mensajes_mqtt(datos: dict[str, Any], mac: str, idmensaje: str, unidades_calculadas: int | None) -> str:
    return f"""
INSERT IGNORE INTO smartfactory.mensajes_mqtt
    (idmensaje, numOp, cantpliegos, actividad, actividadreal, velocidadreal, fecha, tiempo, fechatiempo, mac, unidadesSensadasPeriodo, unidadesCalculadasConglomerado)
VALUES
    ('{_escape_sql(idmensaje)}', '{_escape_sql(datos['numOp'])}', '{_escape_sql(datos['cantpliegos'])}', '{_escape_sql(datos['actividad'])}', '{_escape_sql(datos['actividadreal'])}', '{_escape_sql(datos['velocidadreal'])}', '{_escape_sql(datos['fecha'])}', '{_escape_sql(datos['tiempo'])}', '{_escape_sql(datos['fechatiempo'])}', '{_escape_sql(mac)}', '{_escape_sql(datos['unidadesSensadasPeriodo'])}', {unidades_calculadas if unidades_calculadas is not None else 'NULL'});
""".strip()


def _armar_insert_datossensados(datos: dict[str, Any], mac: str, idmensaje: str) -> str:
    return f"""
INSERT IGNORE INTO smartfactory.datossensados
    (idmensaje, numOp, cantpliegos, actividad, actividadreal, velocidadreal, fecha, tiempo, fechatiempo, mac, unidadesSensadasPeriodo)
VALUES
    ('{_escape_sql(idmensaje)}', '{_escape_sql(datos['numOp'])}', '{_escape_sql(datos['cantpliegos'])}', '{_escape_sql(datos['actividad'])}', '{_escape_sql(datos['actividadreal'])}', '{_escape_sql(datos['velocidadreal'])}', '{_escape_sql(datos['fecha'])}', '{_escape_sql(datos['tiempo'])}', '{_escape_sql(datos['fechatiempo'])}', '{_escape_sql(mac)}', '{_escape_sql(datos['unidadesSensadasPeriodo'])}');
""".strip()


def _ejecutar_query(query: str, nombre: str) -> dict[str, Any]:
    if dtbSmartFactory is None:
        return {
            "ok": False,
            "tabla": nombre,
            "resultado": None,
            "motivo": "No se pudo importar dtbSmartFactory.",
        }

    try:
        resultado = dtbSmartFactory(query).consultaSmartFactory()
        ok = resultado is not None
        if ok:
            _log(f"OK {nombre} | {query.replace(chr(10), ' ')}")
        else:
            _log(f"ERROR {nombre} | dtbSmartFactory retornó None | {query.replace(chr(10), ' ')}")
        return {
            "ok": ok,
            "tabla": nombre,
            "resultado": resultado,
            "motivo": "Query ejecutado." if ok else "dtbSmartFactory retornó None.",
        }
    except Exception as error:
        _log(f"EXCEPTION {nombre} | {error} | {query.replace(chr(10), ' ')}")
        return {
            "ok": False,
            "tabla": nombre,
            "resultado": None,
            "motivo": f"Error ejecutando query: {error}",
        }


def procesar_persistencia_mqtt(topic: str, payload: str, mac: str | None, tipo: str | None) -> dict[str, Any]:
    """
    Fase v14: prepara y, si está habilitado, ejecuta persistencia MQTT real.

    Variables de seguridad:
    - SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES=1 habilita INSERT real de MQTT.
    - Por defecto solo simula.

    Requisitos de BD:
    - smartfactory.mensajes_mqtt.unidadesCalculadasConglomerado
    - smartfactory.datossensados.idmensaje
    - Para que INSERT IGNORE evite duplicados en datossensados, idmensaje debe tener UNIQUE KEY.
    """
    if not mac and topic and "-" in topic:
        mac = topic.split("-", 1)[0].strip()

    if not tipo and topic and "-" in topic:
        tipo = topic.split("-", 1)[1].strip()

    modo = "PERSISTENCIA_MQTT_REAL" if ENABLE_REAL_MQTT_DB_WRITES else "SIMULACION_MQTT_DB"

    if tipo != "DATOS":
        return {
            "ok": True,
            "aplica": False,
            "modo": modo,
            "escritura_real_habilitada": ENABLE_REAL_MQTT_DB_WRITES,
            "motivo": "El topic no es DATOS; no se arma persistencia operativa.",
            "topic": topic,
            "payload": payload,
            "mac": mac,
            "tipo": tipo,
        }

    if not mac:
        return {
            "ok": False,
            "aplica": False,
            "modo": modo,
            "escritura_real_habilitada": ENABLE_REAL_MQTT_DB_WRITES,
            "motivo": "No se pudo extraer MAC del topic.",
            "topic": topic,
            "payload": payload,
        }

    datos = _parsear_payload_datos(payload)
    if not datos.get("ok"):
        return {
            "ok": False,
            "aplica": False,
            "modo": modo,
            "escritura_real_habilitada": ENABLE_REAL_MQTT_DB_WRITES,
            "motivo": datos.get("motivo"),
            "topic": topic,
            "payload": payload,
            "mac": mac,
            "tipo": tipo,
            "payload_parseado": datos,
        }

    idmensaje = f"{mac} {datos['fecha']} {datos['tiempo']}"
    actual = _a_entero(datos.get("cantpliegos"), None)
    consulta_anterior = _buscar_cantpliegos_anterior(mac)
    anterior = consulta_anterior.get("cantpliegos_anterior")
    calculo = _calcular_unidades_conglomerado(actual, anterior)
    unidades_calculadas = calculo.get("unidadesCalculadasConglomerado")

    insert_mensajes = _armar_insert_mensajes_mqtt(datos, mac, idmensaje, unidades_calculadas)

    # Regla operativa v20.18:
    # numOp = 100 se conserva en mensajes_mqtt como historico/auditoria,
    # pero NO se inserta en datossensados porque datossensados es temporal operacional.
    omitir_datossensados = str(datos.get("numOp", "")).strip() == "100"
    insert_datos = None if omitir_datossensados else _armar_insert_datossensados(datos, mac, idmensaje)

    ejecucion = {
        "ejecutado": False,
        "mensajes_mqtt": None,
        "datossensados": None,
        "ok_general": None,
        "motivo": "Modo protegido: no se ejecutaron INSERTS reales.",
    }

    if ENABLE_REAL_MQTT_DB_WRITES:
        resultado_mensajes = _ejecutar_query(insert_mensajes, "mensajes_mqtt")

        if omitir_datossensados:
            resultado_datos = {
                "ok": True,
                "omitido": True,
                "motivo": "numOp=100: no se inserta en datossensados; solo se conserva en mensajes_mqtt.",
            }
        else:
            resultado_datos = _ejecutar_query(insert_datos, "datossensados")

        ok_general = bool(resultado_mensajes.get("ok") and resultado_datos.get("ok"))
        ejecucion = {
            "ejecutado": True,
            "mensajes_mqtt": resultado_mensajes,
            "datossensados": resultado_datos,
            "ok_general": ok_general,
            "motivo": "INSERT MQTT ejecutado; datossensados omitido por numOp=100." if omitir_datossensados and ok_general else ("INSERTS MQTT ejecutados." if ok_general else "Uno o más INSERTS MQTT fallaron."),
        }
    else:
        _log(f"SIMULACION | {idmensaje} | mac={mac} | actual={actual} | anterior={anterior} | calculado={unidades_calculadas}")

    if unidades_calculadas is not None and unidades_calculadas > UMBRAL_ALERTA_UNIDADES_CONGLOMERADO:
        _log_alerta_conglomerado({
            "motivo": "unidadesCalculadasConglomerado supera el umbral esperado antes de insertar/guardar.",
            "umbral": UMBRAL_ALERTA_UNIDADES_CONGLOMERADO,
            "fecha_proceso": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modo": modo,
            "escritura_real_habilitada": ENABLE_REAL_MQTT_DB_WRITES,
            "topic": topic,
            "payload_original": payload,
            "mac": mac,
            "tipo": tipo,
            "idmensaje": idmensaje,
            "payload_parseado": datos,
            "valores_calculo": {
                "cantpliegos_actual_raw": datos.get("cantpliegos"),
                "cantpliegos_actual_entero": actual,
                "cantpliegos_anterior_entero": anterior,
                "operacion_normal_actual_menos_anterior": None if actual is None or anterior is None else actual - anterior,
                "unidadesCalculadasConglomerado": unidades_calculadas,
            },
            "consulta_anterior": consulta_anterior,
            "calculo_conglomerado": calculo,
            "querys_armados": {
                "buscar_cantpliegos_anterior": consulta_anterior.get("query"),
                "insert_mensajes_mqtt": insert_mensajes,
                "insert_datossensados": insert_datos,
                "datossensados_omitido_por_numOp_100": omitir_datossensados,
            },
            "respuestas_querys": {
                "buscar_cantpliegos_anterior": consulta_anterior.get("resultado_query"),
                "insert_mensajes_mqtt": ejecucion.get("mensajes_mqtt"),
                "insert_datossensados": ejecucion.get("datossensados"),
            },
            "nota": "Este log no bloquea la operación; solo deja trazabilidad para diagnosticar cálculos anómalos.",
        })

    return {
        "ok": True,
        "aplica": True,
        "modo": modo,
        "escritura_real_habilitada": ENABLE_REAL_MQTT_DB_WRITES,
        "fecha_proceso": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "topic": topic,
        "payload": payload,
        "mac": mac,
        "tipo": tipo,
        "idmensaje": idmensaje,
        "payload_parseado": datos,
        "cantpliegos_actual": actual,
        "cantpliegos_anterior": anterior,
        "consulta_anterior": consulta_anterior,
        "calculo_conglomerado": calculo,
        "sql": {
            "mensajes_mqtt": insert_mensajes,
            "datossensados": insert_datos,
            "datossensados_omitido_por_numOp_100": omitir_datossensados,
        },
        "valores": {
            "idmensaje": idmensaje,
            "numOp": datos["numOp"],
            "cantpliegos": datos["cantpliegos"],
            "actividad": datos["actividad"],
            "actividadreal": datos["actividadreal"],
            "velocidadreal": datos["velocidadreal"],
            "fecha": datos["fecha"],
            "tiempo": datos["tiempo"],
            "fechatiempo": datos["fechatiempo"],
            "mac": mac,
            "unidadesSensadasPeriodo": datos["unidadesSensadasPeriodo"],
            "unidadesCalculadasConglomerado": unidades_calculadas,
        },
        "ejecucion": ejecucion,
        "nota": (
            "Fase v14: escritura real habilitada para MQTT." if ENABLE_REAL_MQTT_DB_WRITES
            else "Fase v14: modo protegido. No se ejecutó ningún INSERT."
        ),
    }


# Alias para mantener compatibilidad con el frontend/código v13.
def simular_persistencia_mqtt(topic: str, payload: str, mac: str | None, tipo: str | None) -> dict[str, Any]:
    return procesar_persistencia_mqtt(topic, payload, mac, tipo)
