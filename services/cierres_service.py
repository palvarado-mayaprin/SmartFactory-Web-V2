from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any

from db.conexion import dtbSmartFactory, dtbOptimus
from config import ENABLE_REAL_DB_WRITES, ENABLE_REAL_MQTT_PUBLISH
from services.marcajes_service import limpiar_sql


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_CANTIDADREAL_NEGATIVA_FILE = LOG_DIR / "cantidadreal_negativos.log"


TIPOS_CIERRE = {
    "FINAL": "Finalización de actividad",
    "MD": "Reporte parcial con detenimiento de máquina",
    "MT": "Reporte parcial sin detenimiento de máquina",
}


def obtener_ultimo_resumen_recurso_usuario(recurso: str, username: str) -> dict[str, Any]:
    """
    Obtiene exactamente el último registro de resumenmarcajes para recurso + usuario.

    Este método se consulta ANTES de cerrar un marcaje improductivo (OP 12345),
    de modo que el registro recién cerrado no desplace al MD productivo que originó
    la pausa. La decisión de reabrir se toma únicamente DESPUÉS de que el cierre
    improductivo termine correctamente.
    """
    recurso_limpio = limpiar_sql(recurso)
    username_limpio = limpiar_sql(username)

    query = f"""
        SELECT *
        FROM smartfactory.resumenmarcajes
        WHERE recurso = '{recurso_limpio}'
          AND username = '{username_limpio}'
        ORDER BY tiempofinal DESC
        LIMIT 1
    """

    filas = dtbSmartFactory(query).consultaSmartFactory()
    if not filas:
        return {
            "ok": True,
            "encontrado": False,
            "registro": None,
        }

    columnas_raw = dtbSmartFactory("SHOW COLUMNS FROM smartfactory.resumenmarcajes").consultaSmartFactory() or []
    columnas = [str(fila[0]) for fila in columnas_raw if fila]
    if not columnas:
        return {
            "ok": False,
            "encontrado": False,
            "registro": None,
            "mensaje": "No fue posible identificar las columnas de resumenmarcajes.",
        }

    registro = dict(zip(columnas, filas[0]))
    return {
        "ok": True,
        "encontrado": True,
        "registro": registro,
    }


def _ahora_sql() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _serializar_json_seguro(valor: Any) -> str:
    try:
        return json.dumps(valor, ensure_ascii=False, default=str, indent=2)
    except Exception:
        return str(valor)


def _log_cantidadreal_negativa(contexto: dict[str, Any]) -> None:
    """
    Registra un diagnóstico detallado cada vez que el cálculo de cantidadreal es negativo.
    El fallo del propio log nunca debe interrumpir el cierre operativo.
    """
    try:
        with LOG_CANTIDADREAL_NEGATIVA_FILE.open("a", encoding="utf-8") as archivo:
            archivo.write("\n" + "=" * 120 + "\n")
            archivo.write(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ALERTA_CANTIDADREAL_NEGATIVA\n"
            )
            archivo.write(_serializar_json_seguro(contexto))
            archivo.write("\n")
    except Exception as error:
        logger.error(f"Fallo al escribir log diagnóstico de cantidadreal negativa: {error}")


def _consultar_diagnostico(query: str) -> dict[str, Any]:
    """Ejecuta una consulta solo para diagnóstico sin afectar el flujo si falla."""
    try:
        resultado = dtbSmartFactory(query).consultaSmartFactory()
        return {
            "ok": True,
            "query": query.strip(),
            "resultado": resultado,
        }
    except Exception as error:
        return {
            "ok": False,
            "query": query.strip(),
            "resultado": None,
            "error": str(error),
        }


def _mac_desde_topic(topic: str | None) -> str:
    if not topic:
        return ""
    return str(topic).split("-", 1)[0].strip()


def _consulta_un_valor(query: str, default: Any = None) -> Any:
    resultado = dtbSmartFactory(query).consultaSmartFactory()
    if not resultado:
        return default
    valor = resultado[0][0]
    if valor is None:
        return default
    return valor


def _obtener_datos_cierre_datossensados(num_op: str, actividad: str, mac: str) -> dict[str, Any]:
    """
    Obtiene en una sola consulta los datos necesarios para simular/cerrar el marcaje.
    Esto evita hacer varias lecturas contra datossensados por cada simulación.
    """
    mac_where = f" AND mac = '{limpiar_sql(mac)}'" if mac else ""
    query = f"""
        SELECT
            COALESCE(
                (
                    SELECT d2.cantpliegos
                    FROM smartfactory.datossensados d2
                    WHERE d2.numOp = '{limpiar_sql(num_op)}'
                      AND d2.actividad = '{limpiar_sql(actividad)}'
                      {mac_where.replace('mac', 'd2.mac')}
                    ORDER BY d2.fechatiempo DESC
                    LIMIT 1
                ),
                0
            ) AS cantreal,
            MIN(fechatiempo) AS tiempo_inicio,
            MAX(fechatiempo) AS tiempo_final,
            COALESCE(TIMESTAMPDIFF(MINUTE, MIN(fechatiempo), MAX(fechatiempo)), 0) AS duracion
        FROM smartfactory.datossensados
        WHERE numOp = '{limpiar_sql(num_op)}'
          AND actividad = '{limpiar_sql(actividad)}'
          {mac_where}
    """
    resultado = dtbSmartFactory(query).consultaSmartFactory()

    if not resultado:
        ahora = _ahora_sql()
        return {
            "cantreal": 0,
            "tiempo_inicio": ahora,
            "tiempo_final": ahora,
            "duracion": 0,
            "query": query,
        }

    fila = resultado[0]
    ahora = _ahora_sql()

    return {
        "cantreal": fila[0] if fila[0] is not None else 0,
        "tiempo_inicio": str(fila[1]) if fila[1] else ahora,
        "tiempo_final": str(fila[2]) if fila[2] else ahora,
        "duracion": int(fila[3] or 0),
        "query": query,
    }


def _obtener_cantreal(num_op: str, actividad: str, mac: str) -> Any:
    mac_where = f" AND mac = '{limpiar_sql(mac)}'" if mac else ""
    query = f"""
        SELECT cantpliegos
        FROM smartfactory.datossensados
        WHERE numOp = '{limpiar_sql(num_op)}'
          AND actividad = '{limpiar_sql(actividad)}'
          {mac_where}
        ORDER BY fechatiempo DESC
        LIMIT 1
    """
    return _consulta_un_valor(query, 0)


def _obtener_tiempo_min(num_op: str, actividad: str, mac: str) -> str:
    mac_where = f" AND mac = '{limpiar_sql(mac)}'" if mac else ""
    query = f"""
        SELECT MIN(fechatiempo)
        FROM smartfactory.datossensados
        WHERE numOp = '{limpiar_sql(num_op)}'
          AND actividad = '{limpiar_sql(actividad)}'
          {mac_where}
    """
    valor = _consulta_un_valor(query, None)
    return str(valor) if valor else _ahora_sql()


def _obtener_tiempo_max(num_op: str, actividad: str, mac: str) -> str:
    mac_where = f" AND mac = '{limpiar_sql(mac)}'" if mac else ""
    query = f"""
        SELECT MAX(fechatiempo)
        FROM smartfactory.datossensados
        WHERE numOp = '{limpiar_sql(num_op)}'
          AND actividad = '{limpiar_sql(actividad)}'
          {mac_where}
    """
    valor = _consulta_un_valor(query, None)
    return str(valor) if valor else _ahora_sql()


def _obtener_duracion_minutos(num_op: str, actividad: str, mac: str) -> int:
    mac_where = f" AND mac = '{limpiar_sql(mac)}'" if mac else ""
    query = f"""
        SELECT TIMESTAMPDIFF(MINUTE, MIN(fechatiempo), MAX(fechatiempo))
        FROM smartfactory.datossensados
        WHERE numOp = '{limpiar_sql(num_op)}'
          AND actividad = '{limpiar_sql(actividad)}'
          {mac_where}
    """
    valor = _consulta_un_valor(query, 0)
    try:
        return int(valor or 0)
    except Exception:
        return 0


def _obtener_wo_tk(num_op: str, recurso: str, actividad: str) -> tuple[Any, Any, str]:
    """
    Busca wo_number/tk_id como el flujo original.
    Primero busca coincidencia exacta de actividad; si no existe, busca por recurso.
    """
    query_exacta = f"""
        SELECT wo_number, MIN(tk_id)
        FROM wo_task200
        INNER JOIN act ON wo_task200.tk_code = act.act_code
        INNER JOIN wo ON wo.wo_number = wo_task200.tk_wonum
        WHERE wo_job = '{limpiar_sql(num_op)}'
          AND act.act_cc = '{limpiar_sql(recurso)}'
          AND tk_code = '{limpiar_sql(actividad)}'
    """
    resultado = dtbOptimus(query_exacta).consultaOptimus()

    if resultado and resultado[0][0] is not None and resultado[0][1] is not None:
        return resultado[0][0], resultado[0][1], query_exacta

    query_recurso = f"""
        SELECT wo_number, MIN(tk_id)
        FROM wo_task200
        INNER JOIN act ON wo_task200.tk_code = act.act_code
        INNER JOIN wo ON wo.wo_number = wo_task200.tk_wonum
        WHERE wo_job = '{limpiar_sql(num_op)}'
          AND act.act_cc = '{limpiar_sql(recurso)}'
    """
    resultado = dtbOptimus(query_recurso).consultaOptimus()

    if resultado and resultado[0][0] is not None:
        return resultado[0][0], 0, query_recurso

    return 0, 0, query_recurso


def _construir_query_suma_mt_anterior(num_op: str, actividad: str) -> str:
    return f"""
        SELECT SUM(cantidadreal)
        FROM smartfactory.resumenmarcajes
        WHERE actividad = '{limpiar_sql(actividad)}'
          AND numOp = '{limpiar_sql(num_op)}'
          AND estado = 'MT'
    """


def _obtener_suma_mt_anterior(num_op: str, actividad: str) -> Any:
    return _consulta_un_valor(_construir_query_suma_mt_anterior(num_op, actividad), 0)


def _obtener_diagnostico_cantidadreal_negativa(
    *,
    marcaje: dict[str, Any],
    tipo_cierre: str,
    total_usuario: Any,
    num_op: str,
    recurso: str,
    actividad: str,
    cantidad: Any,
    username: str,
    topic: str,
    mac: str,
    datos_cierre: dict[str, Any],
    cantreal_original: Any,
    suma_mt_anterior: Any,
    cantreal_calculada: Any,
    wo_number: Any,
    tk_id: Any,
    query_wo_tk: str,
) -> dict[str, Any]:
    mac_where = f" AND mac = '{limpiar_sql(mac)}'" if mac else ""

    query_datossensados_detalle = f"""
        SELECT *
        FROM smartfactory.datossensados
        WHERE numOp = '{limpiar_sql(num_op)}'
          AND actividad = '{limpiar_sql(actividad)}'
          {mac_where}
        ORDER BY fechatiempo ASC
    """

    query_mt_detalle = f"""
        SELECT *
        FROM smartfactory.resumenmarcajes
        WHERE actividad = '{limpiar_sql(actividad)}'
          AND numOp = '{limpiar_sql(num_op)}'
          AND estado = 'MT'
        ORDER BY tiempoinicio ASC
    """

    return {
        "evento": "ALERTA_CANTIDADREAL_NEGATIVA",
        "fecha_diagnostico": _ahora_sql(),
        "tipo_cierre": tipo_cierre,
        "tipo_cierre_nombre": TIPOS_CIERRE.get(tipo_cierre),
        "marcaje_recibido": marcaje,
        "contexto_operativo": {
            "numOp": num_op,
            "recurso": recurso,
            "actividad": actividad,
            "cantidadcot": cantidad,
            "username": username,
            "topic": topic,
            "mac": mac,
            "totalUsuario": total_usuario,
            "wo_number": wo_number,
            "tk_id": tk_id,
        },
        "calculo_cantidadreal": {
            "cantreal_original": cantreal_original,
            "suma_mt_anterior": suma_mt_anterior,
            "formula": f"{cantreal_original} - {suma_mt_anterior}",
            "cantreal_calculada": cantreal_calculada,
            "regla": "cantidadreal = ultimo cantpliegos de datossensados - SUM(cantidadreal de MT anteriores)",
        },
        "datos_cierre_datossensados": {
            "cantreal": datos_cierre.get("cantreal"),
            "tiempo_inicio": datos_cierre.get("tiempo_inicio"),
            "tiempo_final": datos_cierre.get("tiempo_final"),
            "duracion": datos_cierre.get("duracion"),
            "query_calculo": str(datos_cierre.get("query") or "").strip(),
            "estructura_tabla": _consultar_diagnostico("SHOW COLUMNS FROM smartfactory.datossensados"),
            "detalle_completo": _consultar_diagnostico(query_datossensados_detalle),
        },
        "mt_anteriores": {
            "suma_utilizada": suma_mt_anterior,
            "query_suma": _construir_query_suma_mt_anterior(num_op, actividad).strip(),
            "estructura_tabla": _consultar_diagnostico("SHOW COLUMNS FROM smartfactory.resumenmarcajes"),
            "detalle_completo": _consultar_diagnostico(query_mt_detalle),
            "nota": "La lógica vigente filtra MT por numOp + actividad + estado='MT'; no filtra recurso ni MAC.",
        },
        "optimus_wo_tk": {
            "wo_number": wo_number,
            "tk_id": tk_id,
            "query": str(query_wo_tk or "").strip(),
        },
    }


def _construir_mqtt_fin(num_op: str, recurso: str, actividad: str, cantidad: Any, tmp_begin: str, tmp_fin: str) -> str:
    fecha_ini, hora_ini = _separar_fecha_hora_para_mqtt(tmp_begin)
    fecha_fin, hora_fin = _separar_fecha_hora_para_mqtt(tmp_fin)
    return f"[{num_op},{recurso},{actividad},{cantidad},0,{fecha_ini},{hora_ini},{fecha_fin},{hora_fin},0,0]"


def _separar_fecha_hora_para_mqtt(fechatiempo: str) -> tuple[str, str]:
    """
    Convierte 'YYYY-MM-DD HH:MM:SS' a la forma que usan los mensajes actuales.
    Si algo viene raro, devuelve fecha/hora actual.
    """
    try:
        texto = str(fechatiempo).replace("T", " ")
        fecha, hora = texto.split(" ", 1)
        return fecha.replace("-", "/"), hora[:8]
    except Exception:
        ahora = datetime.now()
        return ahora.strftime("%Y/%m/%d"), ahora.strftime("%H:%M:%S")


def simular_cierre_marcaje(marcaje: dict[str, Any], tipo_cierre: str, total_usuario: Any, pausa_improductiva: bool = False) -> dict[str, Any]:
    """
    Simula el cierre de marcaje con las 3 rutas operativas:
    FINAL: finalización completa de actividad.
    MD: reporte parcial con máquina detenida.
    MT: reporte parcial sin detener máquina.

    No ejecuta INSERT, DELETE ni publicación MQTT.
    """
    tipo_cierre = str(tipo_cierre or "").strip().upper()
    pausa_improductiva = bool(pausa_improductiva)
    if tipo_cierre not in TIPOS_CIERRE:
        return {
            "ok": False,
            "mensaje": "Tipo de cierre inválido. Use FINAL, MD o MT.",
        }

    if pausa_improductiva and tipo_cierre != "MD":
        return {
            "ok": False,
            "mensaje": "La pausa por actividad improductiva solo puede ejecutarse como cierre MD.",
        }

    num_op = limpiar_sql(marcaje.get("numOp") or marcaje.get("num_op"))
    recurso = limpiar_sql(marcaje.get("recurso"))
    actividad = limpiar_sql(marcaje.get("actividad"))
    cantidad = limpiar_sql(marcaje.get("cantidad") or 0)
    username = limpiar_sql(marcaje.get("username") or marcaje.get("codigo_usuario"))
    topic = limpiar_sql(marcaje.get("topic"))
    mac = limpiar_sql(marcaje.get("mac") or _mac_desde_topic(topic))
    total_usuario_limpio = limpiar_sql(total_usuario if total_usuario not in (None, "") else 0)

    faltantes = [
        nombre for nombre, valor in {
            "numOp": num_op,
            "recurso": recurso,
            "actividad": actividad,
            "username": username,
            "topic": topic,
        }.items()
        if str(valor or "").strip() == ""
    ]

    if faltantes:
        return {
            "ok": False,
            "mensaje": "No se puede simular el cierre. Faltan campos críticos: " + ", ".join(faltantes),
        }

    datos_cierre = _obtener_datos_cierre_datossensados(num_op, actividad, mac)
    cantreal_original = datos_cierre["cantreal"]
    suma_mt_anterior = _obtener_suma_mt_anterior(num_op, actividad)

    try:
        cantreal_calculada = float(cantreal_original or 0) - float(suma_mt_anterior or 0)
        if cantreal_calculada.is_integer():
            cantreal_calculada = int(cantreal_calculada)
    except Exception:
        cantreal_calculada = cantreal_original or 0

    tmp_begin = datos_cierre["tiempo_inicio"]
    tmp_fin = datos_cierre["tiempo_final"]
    duracion = datos_cierre["duracion"]
    wo_number, tk_id, query_wo_tk = _obtener_wo_tk(num_op, recurso, actividad)

    # Diagnóstico v20.20: solo se ejecutan consultas adicionales cuando la cantidadreal es negativa.
    # El log es informativo y nunca altera, bloquea ni corrige el cierre.
    try:
        if float(cantreal_calculada) < 0:
            logger.error(
                "ANOMALIA: cantidadreal negativa (%s) para OP %s, MAC %s. "
                "cantreal_original: %s, suma_mt_anterior: %s, tipo_cierre: %s, recurso: %s, actividad: %s",
                cantreal_calculada,
                num_op,
                mac,
                cantreal_original,
                suma_mt_anterior,
                tipo_cierre,
                recurso,
                actividad,
            )
            diagnostico_negativo = _obtener_diagnostico_cantidadreal_negativa(
                marcaje=marcaje,
                tipo_cierre=tipo_cierre,
                total_usuario=total_usuario_limpio,
                num_op=num_op,
                recurso=recurso,
                actividad=actividad,
                cantidad=cantidad,
                username=username,
                topic=topic,
                mac=mac,
                datos_cierre=datos_cierre,
                cantreal_original=cantreal_original,
                suma_mt_anterior=suma_mt_anterior,
                cantreal_calculada=cantreal_calculada,
                wo_number=wo_number,
                tk_id=tk_id,
                query_wo_tk=query_wo_tk,
            )
            _log_cantidadreal_negativa(diagnostico_negativo)
    except Exception as error:
        # La trazabilidad no debe introducir una nueva causa de fallo en producción.
        logger.error(f"Fallo al generar diagnóstico de cantidadreal negativa: {error}")

    mensaje_mqtt_fin = _construir_mqtt_fin(num_op, recurso, actividad, cantidad, tmp_begin, tmp_fin)
    publica_mqtt = tipo_cierre in {"FINAL", "MD"}

    insert_usuario_estado = "NULL" if tipo_cierre == "FINAL" else f"'{tipo_cierre}'"

    if pausa_improductiva:
        insert_resumen_usuario = f"""INSERT INTO smartfactory.resumenmarcajes
    (numOp, recurso, actividad, cantidadcot, cantidadreal, username, tiempoinicio, tiempofinal, estado, totalUsuario, wo_number, tk_id, duracion, variable01)
VALUES
    ('{num_op}', '{recurso}', '{actividad}', '{cantidad}', '{cantreal_calculada}', '{username}',
     '{tmp_begin}', '{tmp_fin}', {insert_usuario_estado}, '{total_usuario_limpio}', '{limpiar_sql(wo_number)}', '{limpiar_sql(tk_id)}', '{duracion}', 1);"""
    else:
        # Mantener exactamente el INSERT histórico para FINAL/MD/MT normales.
        # variable01 conserva su DEFAULT NULL al no incluirse en la sentencia.
        insert_resumen_usuario = f"""INSERT INTO smartfactory.resumenmarcajes
    (numOp, recurso, actividad, cantidadcot, cantidadreal, username, tiempoinicio, tiempofinal, estado, totalUsuario, wo_number, tk_id, duracion)
VALUES
    ('{num_op}', '{recurso}', '{actividad}', '{cantidad}', '{cantreal_calculada}', '{username}',
     '{tmp_begin}', '{tmp_fin}', {insert_usuario_estado}, '{total_usuario_limpio}', '{limpiar_sql(wo_number)}', '{limpiar_sql(tk_id)}', '{duracion}');"""

    delete_datossensados = f"""DELETE FROM smartfactory.datossensados
WHERE numOp = '{num_op}'
  AND actividad = '{actividad}'
  AND mac = '{mac}';"""

    delete_marcajeactivo = f"""DELETE FROM smartfactory.marcajeactivo
WHERE numOp = '{num_op}'
  AND actividad = '{actividad}'
  AND username = '{username}';"""

    sql_bloques = [insert_resumen_usuario]

    insert_resumen_final = None
    if tipo_cierre == "FINAL":
        query_agregado_final = f"""SELECT SUM(cantidadreal), MIN(tiempoinicio), MAX(tiempofinal), SUM(duracion)
FROM smartfactory.resumenmarcajes
WHERE actividad = '{actividad}'
  AND numOp = '{num_op}';"""

        insert_resumen_final = f"""/* Luego de insertar el resumen del usuario, se calcula el agregado de la actividad y se inserta el cierre final SMARTFACTORY. */
INSERT INTO smartfactory.resumenmarcajes
    (numOp, recurso, actividad, cantidadcot, cantidadreal, username, tiempoinicio, tiempofinal, duracion, estado, totalUsuario, wo_number, tk_id)
VALUES
    ('{num_op}', '{recurso}', '{actividad}', '{cantidad}', '<SUM(cantidadreal)>', 'SMARTFACTORY',
     '<MIN(tiempoinicio)>', '<MAX(tiempofinal)>', '<SUM(duracion)>', 'F', '{total_usuario_limpio}', '{limpiar_sql(wo_number)}', '{limpiar_sql(tk_id)}');"""
        sql_bloques.append(query_agregado_final)
        sql_bloques.append(insert_resumen_final)

    sql_bloques.append(delete_datossensados)
    sql_bloques.append(delete_marcajeactivo)

    if tipo_cierre == "MT":
        accion_post_cierre = "Solicitar identificación inmediata del siguiente operario. No se publica MQTT de paro."
    elif tipo_cierre == "MD":
        accion_post_cierre = "Máquina detenida. Se publica MQTT de finalización y queda lista para nuevo marcaje posterior."
    else:
        accion_post_cierre = "Actividad finalizada. Se publica MQTT de finalización y se genera resumen final SMARTFACTORY."

    return {
        "ok": True,
        "mensaje": "Simulación de cierre generada correctamente. No se modificó BD ni se publicó MQTT.",
        "simulacion": {
            "fecha_simulacion": _ahora_sql(),
            "accion": "CIERRE_MARCAJE",
            "tipo_cierre": tipo_cierre,
            "tipo_cierre_nombre": TIPOS_CIERRE[tipo_cierre],
            "publica_mqtt": publica_mqtt,
            "accion_post_cierre": accion_post_cierre,
            "mqtt": {
                "topic": topic,
                "payload": mensaje_mqtt_fin if publica_mqtt else "NO SE PUBLICA MQTT PARA MT",
                "publicaria": publica_mqtt,
            },
            "base_datos": {
                "sql_completo": "\n\n".join(sql_bloques),
                "insert_resumen_usuario": insert_resumen_usuario,
                "insert_resumen_final": insert_resumen_final,
                "delete_datossensados": delete_datossensados,
                "delete_marcajeactivo": delete_marcajeactivo,
                "query_wo_tk": query_wo_tk,
                "query_datossensados": datos_cierre["query"],
            },
            "valores": {
                "numOp": num_op,
                "recurso": recurso,
                "actividad": actividad,
                "cantidadcot": cantidad,
                "cantreal_original": cantreal_original,
                "suma_mt_anterior": suma_mt_anterior,
                "cantreal_calculada": cantreal_calculada,
                "username": username,
                "tiempoinicio": tmp_begin,
                "tiempofinal": tmp_fin,
                "duracion_minutos": duracion,
                "estado": None if tipo_cierre == "FINAL" else tipo_cierre,
                "estado_final_smartfactory": "F" if tipo_cierre == "FINAL" else None,
                "totalUsuario": total_usuario_limpio,
                "wo_number": wo_number,
                "tk_id": tk_id,
                "topic": topic,
                "mac": mac,
                "pausa_improductiva": pausa_improductiva,
                "variable01": 1 if pausa_improductiva else None,
            },
            "nota": "v15 solamente simula el cierre. No ejecuta INSERT, DELETE ni publish MQTT.",
        },
    }



def ejecutar_cierre_marcaje_real(marcaje: dict[str, Any], tipo_cierre: str, total_usuario: Any, pausa_improductiva: bool = False) -> dict[str, Any]:
    """
    Ejecuta el cierre real del marcaje según las 3 rutas operativas:
    FINAL: cierre definitivo de actividad, inserta resumen usuario + resumen SMARTFACTORY estado F.
    MD: reporte parcial con máquina detenida, inserta resumen usuario estado MD y publica MQTT de paro.
    MT: reporte parcial sin detener máquina, inserta resumen usuario estado MT y NO publica MQTT de paro.

    Seguridad:
    - Requiere SMARTFACTORY_ENABLE_REAL_DB_WRITES=1 para modificar BD.
    - FINAL/MD requieren SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH=1 para publicar paro al ESP.
    """
    simulacion = simular_cierre_marcaje(marcaje, tipo_cierre, total_usuario, pausa_improductiva=pausa_improductiva)

    if not simulacion.get("ok"):
        return simulacion

    sim = simulacion["simulacion"]
    valores = sim["valores"]
    tipo_cierre = valores.get("estado_final_smartfactory") and "FINAL" or str(sim.get("tipo_cierre") or "").upper()
    tipo_cierre = str(sim.get("tipo_cierre") or tipo_cierre).upper()

    if not ENABLE_REAL_DB_WRITES:
        return {
            "ok": False,
            "modo": "PROTEGIDO_BD",
            "mensaje": (
                "La escritura real en BD está deshabilitada. No se ejecutó INSERT/DELETE. "
                "Active SMARTFACTORY_ENABLE_REAL_DB_WRITES=1 y reinicie uvicorn."
            ),
            "simulacion": sim,
        }

    if sim.get("publica_mqtt") and not ENABLE_REAL_MQTT_PUBLISH:
        return {
            "ok": False,
            "modo": "PROTEGIDO_MQTT",
            "mensaje": (
                "Este cierre requiere publicar MQTT al ESP, pero la publicación real está deshabilitada. "
                "No se modificó la BD para evitar inconsistencias. Active SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH=1."
            ),
            "simulacion": sim,
        }

    num_op = limpiar_sql(valores.get("numOp"))
    recurso = limpiar_sql(valores.get("recurso"))
    actividad = limpiar_sql(valores.get("actividad"))
    username = limpiar_sql(valores.get("username"))
    mac = limpiar_sql(valores.get("mac"))
    topic = limpiar_sql(valores.get("topic"))

    # Validación final: el marcaje aún debe existir en BD antes de cerrar.
    select_marcaje = f"""
        SELECT numOp, recurso, actividad, username, topic
        FROM smartfactory.marcajeactivo
        WHERE numOp = '{num_op}'
          AND recurso = '{recurso}'
          AND actividad = '{actividad}'
          AND username = '{username}'
          AND topic = '{topic}'
        LIMIT 1
    """
    existe = dtbSmartFactory(select_marcaje).consultaSmartFactory()
    if not existe:
        return {
            "ok": False,
            "modo": "NO_ENCONTRADO",
            "mensaje": "No se encontró el marcaje activo en BD al momento de ejecutar el cierre.",
            "select_validacion": select_marcaje,
            "simulacion": sim,
        }

    bd = sim["base_datos"]
    insert_usuario = bd["insert_resumen_usuario"]
    delete_datossensados = bd["delete_datossensados"]
    delete_marcajeactivo = bd["delete_marcajeactivo"]

    queries_ejecutados: list[str] = []

    try:
        # 1. Publicación MQTT de paro ANTES de tocar BD para FINAL y MD.
        #    Esto evita cerrar marcajeactivo / datossensados mientras el ESP sigue enviando datos.
        resultado_mqtt = {
            "ok": True,
            "mensaje": "No aplica publicación MQTT para MT.",
            "publicado": False,
        }

        if sim.get("publica_mqtt"):
            from services.mqtt_service import mqtt_monitor
            mqtt_info = sim.get("mqtt") or {}
            resultado_mqtt = mqtt_monitor.publicar(mqtt_info.get("topic"), mqtt_info.get("payload"))
            resultado_mqtt["publicado"] = bool(resultado_mqtt.get("ok"))

            if not resultado_mqtt.get("ok"):
                return {
                    "ok": False,
                    "modo": "MQTT_NO_PUBLICADO",
                    "mensaje": (
                        "No se ejecutó el cierre real porque primero debe publicarse MQTT de paro al ESP. "
                        "Presione Conectar MQTT y vuelva a intentar."
                    ),
                    "resultado_mqtt": resultado_mqtt,
                    "queries_ejecutados": [],
                    "simulacion": sim,
                    "valores": valores,
                }

        # 2. Insert resumen del usuario.
        dtbSmartFactory(insert_usuario).consultaSmartFactory()
        queries_ejecutados.append(insert_usuario)

        # 3. Si es FINAL, calcular agregado después de insertar usuario e insertar resumen SMARTFACTORY.
        insert_final_ejecutado = None
        agregado_final = None
        if tipo_cierre == "FINAL":
            query_agregado = f"""
                SELECT SUM(cantidadreal), MIN(tiempoinicio), MAX(tiempofinal), SUM(duracion)
                FROM smartfactory.resumenmarcajes
                WHERE actividad = '{actividad}'
                  AND numOp = '{num_op}'
            """
            agregado = dtbSmartFactory(query_agregado).consultaSmartFactory()
            queries_ejecutados.append(query_agregado)

            if agregado:
                total_cantidad = agregado[0][0] if agregado[0][0] is not None else 0
                inicio = agregado[0][1] if agregado[0][1] is not None else valores.get("tiempoinicio")
                fin = agregado[0][2] if agregado[0][2] is not None else valores.get("tiempofinal")
                duracion = agregado[0][3] if agregado[0][3] is not None else 0
            else:
                total_cantidad = valores.get("cantreal_calculada") or 0
                inicio = valores.get("tiempoinicio")
                fin = valores.get("tiempofinal")
                duracion = valores.get("duracion_minutos") or 0

            agregado_final = {
                "cantidadreal": total_cantidad,
                "tiempoinicio": str(inicio),
                "tiempofinal": str(fin),
                "duracion": duracion,
            }

            insert_final_ejecutado = f"""
                INSERT INTO smartfactory.resumenmarcajes
                    (numOp, recurso, actividad, cantidadcot, cantidadreal, username, tiempoinicio, tiempofinal, duracion, estado, totalUsuario, wo_number, tk_id)
                VALUES
                    ('{num_op}', '{recurso}', '{actividad}', '{limpiar_sql(valores.get('cantidadcot'))}', '{limpiar_sql(total_cantidad)}', 'SMARTFACTORY',
                     '{limpiar_sql(inicio)}', '{limpiar_sql(fin)}', '{limpiar_sql(duracion)}', 'F', '{limpiar_sql(valores.get('totalUsuario'))}', '{limpiar_sql(valores.get('wo_number'))}', '{limpiar_sql(valores.get('tk_id'))}')
            """
            dtbSmartFactory(insert_final_ejecutado).consultaSmartFactory()
            queries_ejecutados.append(insert_final_ejecutado)

        # 3. Limpieza temporal operativa.
        dtbSmartFactory(delete_datossensados).consultaSmartFactory()
        queries_ejecutados.append(delete_datossensados)

        # 4. Eliminar marcaje activo.
        dtbSmartFactory(delete_marcajeactivo).consultaSmartFactory()
        queries_ejecutados.append(delete_marcajeactivo)

        # 6. En este punto, si era FINAL/MD, MQTT ya fue publicado correctamente.
        relevo_pendiente = None
        if tipo_cierre == "MT":
            relevo_pendiente = {
                "numOp": valores.get("numOp"),
                "num_ot": f"{valores.get('numOp')}01",
                "descrip": marcaje.get("descrip") or marcaje.get("descripcion") or "RELEVO MT",
                "cantidad": valores.get("cantidadcot"),
                "cantidadcot": valores.get("cantidadcot"),
                "recurso": valores.get("recurso"),
                "actividad": valores.get("actividad"),
                "actividad_nombre": marcaje.get("actividad_nombre") or valores.get("actividad"),
                "topic": valores.get("topic"),
                "mac": valores.get("mac"),
                "operario_anterior": valores.get("username"),
                "tipo_cierre_origen": "MT",
                "tiempofinal_anterior": valores.get("tiempofinal"),
            }

        return {
            "ok": True,
            "mensaje": "Cierre real ejecutado correctamente.",
            "tipo_cierre": tipo_cierre,
            "accion_post_cierre": sim.get("accion_post_cierre"),
            "resultado_mqtt": resultado_mqtt,
            "queries_ejecutados": queries_ejecutados,
            "agregado_final": agregado_final,
            "marcaje_cerrado": marcaje,
            "valores": valores,
            "relevo_pendiente": relevo_pendiente,
        }

    except Exception as error:
        return {
            "ok": False,
            "modo": "ERROR_CIERRE_REAL",
            "mensaje": f"Error ejecutando cierre real: {error}",
            "queries_ejecutados_antes_error": queries_ejecutados,
            "simulacion": sim,
        }
