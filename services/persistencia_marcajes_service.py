from datetime import datetime
from pathlib import Path
from typing import Any

from config import ENABLE_REAL_DB_WRITES, ENABLE_REAL_MQTT_PUBLISH
from db.conexion import dtbSmartFactory
from services.marcajes_service import limpiar_sql, simular_inicio_marcaje, simular_inicio_marcaje_improductivo

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "marcajes_reales.log"


def _log_accion(accion: str, datos: dict[str, Any]) -> None:
    """
    Log plano para auditoría durante la fase v10.
    No reemplaza la BD; solamente deja trazabilidad local de pruebas reales.
    """
    try:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        partes = [f"{k}={v}" for k, v in datos.items()]
        linea = f"{fecha};{accion};" + ";".join(partes) + "\n"
        with open(LOG_FILE, "a", encoding="utf-8") as archivo:
            archivo.write(linea)
    except Exception:
        # El log nunca debe romper el flujo operacional.
        pass


def _extraer_mac_desde_topic(topic: str | None) -> str | None:
    if not topic or "-" not in str(topic):
        return None
    return str(topic).split("-", 1)[0].strip()


def esta_habilitada_escritura_real() -> bool:
    return ENABLE_REAL_DB_WRITES


def esta_habilitada_publicacion_mqtt_real() -> bool:
    return ENABLE_REAL_MQTT_PUBLISH


def construir_marcaje_estado_desde_valores(valores: dict[str, Any], modo: str = "REAL_BD") -> dict[str, Any]:
    topic = valores.get("topic")
    mac = _extraer_mac_desde_topic(topic)
    marcaje_id = f"{modo}|{valores.get('username')}|{valores.get('numOp')}|{valores.get('recurso')}|{valores.get('actividad')}"

    return {
        "id": marcaje_id,
        "modo": modo,
        "fecha_inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "username": valores.get("username"),
        "codigo_usuario": valores.get("username"),
        "numOp": valores.get("numOp"),
        "descrip": valores.get("descrip"),
        "cantidad": valores.get("cantidad"),
        "recurso": valores.get("recurso"),
        "actividad": valores.get("actividad"),
        "topic": topic,
        "mac": mac,
        "produccionUnidad": valores.get("produccionUnidad"),
        "conteo_mqtt_actual": 0,
        "conteo_mqtt_anterior": None,
        "delta_ultimo_mensaje": 0,
        "mensajes_mqtt_asociados": 0,
        "ultimo_topic_mqtt": None,
        "ultimo_payload_mqtt": None,
        "ultimo_mqtt_fecha_hora": None,
        "ultimo_num_op_mqtt": None,
        "ultima_actividad_mqtt": None,
        "ultima_advertencia_mqtt": None,
    }


def listar_marcajes_activos_bd() -> list[dict[str, Any]]:
    query = """
        SELECT numOp, descrip, cantidad, recurso, actividad, username, topic, produccionUnidad
        FROM smartfactory.marcajeactivo
        ORDER BY username, recurso, numOp
    """
    filas = dtbSmartFactory(query).consultaSmartFactory()

    if not filas:
        return []

    marcajes = []
    for fila in filas:
        valores = {
            "numOp": fila[0],
            "descrip": fila[1],
            "cantidad": fila[2],
            "recurso": fila[3],
            "actividad": fila[4],
            "username": fila[5],
            "topic": fila[6],
            "produccionUnidad": fila[7] if len(fila) > 7 else None,
        }
        marcajes.append(construir_marcaje_estado_desde_valores(valores, modo="REAL_BD"))

    return marcajes


def validar_apertura_marcaje_real(valores: dict[str, Any]) -> dict[str, Any]:
    """
    Validaciones operacionales antes de ejecutar INSERT real.

    Reglas de v10:
    1. Un usuario no puede tener más de un marcaje abierto.
    2. Una MAC/recurso no puede tener más de un marcaje abierto simultáneo.
    3. Los campos críticos no pueden venir vacíos.
    """
    username = limpiar_sql(valores.get("username"))
    topic = limpiar_sql(valores.get("topic"))
    recurso = limpiar_sql(valores.get("recurso"))
    actividad = limpiar_sql(valores.get("actividad"))
    num_op = limpiar_sql(valores.get("numOp"))

    faltantes = []
    for nombre, valor in {
        "username": username,
        "topic": topic,
        "recurso": recurso,
        "actividad": actividad,
        "numOp": num_op,
    }.items():
        if valor is None or str(valor).strip() == "":
            faltantes.append(nombre)

    if faltantes:
        return {
            "ok": False,
            "mensaje": "No se puede abrir marcaje real. Faltan campos críticos: " + ", ".join(faltantes),
        }

    query_usuario = f"""
        SELECT numOp, recurso, actividad, username, topic
        FROM smartfactory.marcajeactivo
        WHERE username = '{username}'
        LIMIT 1
    """
    filas_usuario = dtbSmartFactory(query_usuario).consultaSmartFactory()

    if filas_usuario:
        fila = filas_usuario[0]
        return {
            "ok": False,
            "mensaje": "El usuario ya tiene un marcaje activo. Debe cerrarlo antes de abrir otro.",
            "marcaje_existente": {
                "numOp": fila[0],
                "recurso": fila[1],
                "actividad": fila[2],
                "username": fila[3],
                "topic": fila[4],
            },
            "query_validacion": query_usuario,
        }

    query_topic = f"""
        SELECT numOp, recurso, actividad, username, topic
        FROM smartfactory.marcajeactivo
        WHERE topic = '{topic}'
           OR recurso = '{recurso}'
        LIMIT 1
    """
    filas_topic = dtbSmartFactory(query_topic).consultaSmartFactory()

    if filas_topic:
        fila = filas_topic[0]
        return {
            "ok": False,
            "mensaje": "La máquina/recurso ya tiene un marcaje activo. Cierre el marcaje actual antes de abrir otro.",
            "marcaje_existente": {
                "numOp": fila[0],
                "recurso": fila[1],
                "actividad": fila[2],
                "username": fila[3],
                "topic": fila[4],
            },
            "query_validacion": query_topic,
        }

    return {
        "ok": True,
        "mensaje": "Validaciones de apertura real aprobadas.",
    }


def iniciar_marcaje_real_bd(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Ejecuta la apertura real del marcaje en smartfactory.marcajeactivo.

    v10 agrega:
    - validación de duplicados por usuario,
    - validación de duplicados por recurso/topic,
    - logs locales,
    - respuesta clara en modo protegido.
    """
    simulacion = simular_inicio_marcaje(payload)

    if not simulacion.get("ok"):
        return simulacion

    datos_sim = simulacion["simulacion"]
    insert_sql = datos_sim["base_datos"]["insert_marcajeactivo"]
    valores = datos_sim["base_datos"]["valores"]

    validacion = validar_apertura_marcaje_real(valores)
    if not validacion.get("ok"):
        _log_accion("APERTURA_BLOQUEADA", {
            "motivo": validacion.get("mensaje"),
            "username": valores.get("username"),
            "numOp": valores.get("numOp"),
            "recurso": valores.get("recurso"),
            "actividad": valores.get("actividad"),
            "topic": valores.get("topic"),
        })
        return {
            "ok": False,
            "modo": "VALIDACION_BLOQUEADA",
            "mensaje": validacion.get("mensaje"),
            "validacion": validacion,
            "insert_preparado": insert_sql,
            "valores": valores,
        }

    if not ENABLE_REAL_DB_WRITES:
        _log_accion("APERTURA_PROTEGIDA", {
            "username": valores.get("username"),
            "numOp": valores.get("numOp"),
            "recurso": valores.get("recurso"),
            "actividad": valores.get("actividad"),
            "topic": valores.get("topic"),
        })
        return {
            "ok": False,
            "modo": "PROTEGIDO",
            "mensaje": (
                "La escritura real está deshabilitada. Validaciones aprobadas, pero el INSERT no fue ejecutado. "
                "Active SMARTFACTORY_ENABLE_REAL_DB_WRITES=1 y reinicie uvicorn para escribir en BD."
            ),
            "validacion": validacion,
            "insert_preparado": insert_sql,
            "valores": valores,
        }

    resultado = dtbSmartFactory(insert_sql).consultaSmartFactory()

    if resultado is None:
        _log_accion("APERTURA_ERROR_BD", {
            "username": valores.get("username"),
            "numOp": valores.get("numOp"),
            "recurso": valores.get("recurso"),
            "actividad": valores.get("actividad"),
            "topic": valores.get("topic"),
        })
        return {
            "ok": False,
            "mensaje": "No se pudo insertar el marcaje real en smartfactory.marcajeactivo.",
            "insert_ejecutado": insert_sql,
        }

    marcaje = construir_marcaje_estado_desde_valores(valores, modo="REAL_BD")

    # =====================================================
    # v16: publicación MQTT real de INICIO hacia el ESP
    # =====================================================
    mqtt_inicio = datos_sim.get("mqtt", {})
    mqtt_topic = mqtt_inicio.get("topic")
    mqtt_payload = mqtt_inicio.get("payload")

    if ENABLE_REAL_MQTT_PUBLISH:
        try:
            from services.mqtt_service import mqtt_monitor
            resultado_mqtt = mqtt_monitor.publicar(mqtt_topic, mqtt_payload)
        except Exception as error:
            resultado_mqtt = {
                "ok": False,
                "mensaje": f"No se pudo intentar publicación MQTT: {error}",
                "topic": mqtt_topic,
                "payload": mqtt_payload,
            }
    else:
        resultado_mqtt = {
            "ok": False,
            "modo": "PROTEGIDO_MQTT",
            "mensaje": (
                "La publicación MQTT real está deshabilitada. El marcaje sí fue insertado en BD, "
                "pero NO se envió el inicio al ESP. Active SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH=1 "
                "y reinicie uvicorn para publicar mensajes reales."
            ),
            "topic": mqtt_topic,
            "payload": mqtt_payload,
        }

    _log_accion("APERTURA_REAL_OK", {
        "username": valores.get("username"),
        "numOp": valores.get("numOp"),
        "recurso": valores.get("recurso"),
        "actividad": valores.get("actividad"),
        "topic": valores.get("topic"),
        "mqtt_publish_enabled": ENABLE_REAL_MQTT_PUBLISH,
        "mqtt_publish_ok": resultado_mqtt.get("ok"),
    })

    if resultado_mqtt.get("ok"):
        mensaje = "Marcaje real insertado correctamente y MQTT de inicio publicado al ESP."
    else:
        mensaje = "Marcaje real insertado correctamente, pero MQTT de inicio NO fue publicado."

    return {
        "ok": True,
        "mensaje": mensaje,
        "validacion": validacion,
        "resultado_bd": resultado,
        "resultado_mqtt_inicio": resultado_mqtt,
        "marcaje": marcaje,
        "insert_ejecutado": insert_sql,
        "mqtt_inicio": {
            "topic": mqtt_topic,
            "payload": mqtt_payload,
            "publicacion_habilitada": ENABLE_REAL_MQTT_PUBLISH,
        },
    }
    
    
    
def iniciar_marcaje_improductivo_bd(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Ejecuta la apertura real del marcaje en smartfactory.marcajeactivo.

    v10 agrega:
    - validación de duplicados por usuario,
    - validación de duplicados por recurso/topic,
    - logs locales,
    - respuesta clara en modo protegido.
    """
    simulacion = simular_inicio_marcaje_improductivo(payload)

    if not simulacion.get("ok"):
        return simulacion

    datos_sim = simulacion["simulacion"]
    insert_sql = datos_sim["base_datos"]["insert_marcajeactivo"]
    valores = datos_sim["base_datos"]["valores"]

    validacion = validar_apertura_marcaje_real(valores)
    if not validacion.get("ok"):
        _log_accion("APERTURA_BLOQUEADA", {
            "motivo": validacion.get("mensaje"),
            "username": valores.get("username"),
            "numOp": valores.get("numOp"),
            "recurso": valores.get("recurso"),
            "actividad": valores.get("actividad"),
            "topic": valores.get("topic"),
        })
        return {
            "ok": False,
            "modo": "VALIDACION_BLOQUEADA",
            "mensaje": validacion.get("mensaje"),
            "validacion": validacion,
            "insert_preparado": insert_sql,
            "valores": valores,
        }

    if not ENABLE_REAL_DB_WRITES:
        _log_accion("APERTURA_PROTEGIDA", {
            "username": valores.get("username"),
            "numOp": valores.get("numOp"),
            "recurso": valores.get("recurso"),
            "actividad": valores.get("actividad"),
            "topic": valores.get("topic"),
        })
        return {
            "ok": False,
            "modo": "PROTEGIDO",
            "mensaje": (
                "La escritura real está deshabilitada. Validaciones aprobadas, pero el INSERT no fue ejecutado. "
                "Active SMARTFACTORY_ENABLE_REAL_DB_WRITES=1 y reinicie uvicorn para escribir en BD."
            ),
            "validacion": validacion,
            "insert_preparado": insert_sql,
            "valores": valores,
        }

    resultado = dtbSmartFactory(insert_sql).consultaSmartFactory()

    if resultado is None:
        _log_accion("APERTURA_ERROR_BD", {
            "username": valores.get("username"),
            "numOp": valores.get("numOp"),
            "recurso": valores.get("recurso"),
            "actividad": valores.get("actividad"),
            "topic": valores.get("topic"),
        })
        return {
            "ok": False,
            "mensaje": "No se pudo insertar el marcaje real en smartfactory.marcajeactivo.",
            "insert_ejecutado": insert_sql,
        }

    marcaje = construir_marcaje_estado_desde_valores(valores, modo="REAL_BD")

    # =====================================================
    # v16: publicación MQTT real de INICIO hacia el ESP
    # =====================================================
    mqtt_inicio = datos_sim.get("mqtt", {})
    mqtt_topic = mqtt_inicio.get("topic")
    mqtt_payload = mqtt_inicio.get("payload")

    if ENABLE_REAL_MQTT_PUBLISH:
        try:
            from services.mqtt_service import mqtt_monitor
            resultado_mqtt = mqtt_monitor.publicar(mqtt_topic, mqtt_payload)
        except Exception as error:
            resultado_mqtt = {
                "ok": False,
                "mensaje": f"No se pudo intentar publicación MQTT: {error}",
                "topic": mqtt_topic,
                "payload": mqtt_payload,
            }
    else:
        resultado_mqtt = {
            "ok": False,
            "modo": "PROTEGIDO_MQTT",
            "mensaje": (
                "La publicación MQTT real está deshabilitada. El marcaje sí fue insertado en BD, "
                "pero NO se envió el inicio al ESP. Active SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH=1 "
                "y reinicie uvicorn para publicar mensajes reales."
            ),
            "topic": mqtt_topic,
            "payload": mqtt_payload,
        }

    _log_accion("APERTURA_REAL_OK", {
        "username": valores.get("username"),
        "numOp": valores.get("numOp"),
        "recurso": valores.get("recurso"),
        "actividad": valores.get("actividad"),
        "topic": valores.get("topic"),
        "mqtt_publish_enabled": ENABLE_REAL_MQTT_PUBLISH,
        "mqtt_publish_ok": resultado_mqtt.get("ok"),
    })

    if resultado_mqtt.get("ok"):
        mensaje = "Marcaje real insertado correctamente y MQTT de inicio publicado al ESP."
    else:
        mensaje = "Marcaje real insertado correctamente, pero MQTT de inicio NO fue publicado."

    return {
        "ok": True,
        "mensaje": mensaje,
        "validacion": validacion,
        "resultado_bd": resultado,
        "resultado_mqtt_inicio": resultado_mqtt,
        "marcaje": marcaje,
        "insert_ejecutado": insert_sql,
        "mqtt_inicio": {
            "topic": mqtt_topic,
            "payload": mqtt_payload,
            "publicacion_habilitada": ENABLE_REAL_MQTT_PUBLISH,
        },
    }


def cerrar_marcaje_real_bd(marcaje: dict[str, Any]) -> dict[str, Any]:
    """
    Cierra un marcaje real eliminándolo de smartfactory.marcajeactivo.

    v10 usa username + numOp + recurso + actividad + topic si está disponible.
    """
    valores = {
        "username": limpiar_sql(marcaje.get("username") or marcaje.get("codigo_usuario")),
        "numOp": limpiar_sql(marcaje.get("numOp")),
        "recurso": limpiar_sql(marcaje.get("recurso")),
        "actividad": limpiar_sql(marcaje.get("actividad")),
        "topic": limpiar_sql(marcaje.get("topic")),
    }

    condiciones = [
        f"username = '{valores['username']}'",
        f"numOp = '{valores['numOp']}'",
        f"recurso = '{valores['recurso']}'",
        f"actividad = '{valores['actividad']}'",
    ]

    if valores.get("topic"):
        condiciones.append(f"topic = '{valores['topic']}'")

    where_sql = "\n          AND ".join(condiciones)

    select_sql = f"""
        SELECT numOp, recurso, actividad, username, topic
        FROM smartfactory.marcajeactivo
        WHERE {where_sql}
        LIMIT 1
    """

    filas = dtbSmartFactory(select_sql).consultaSmartFactory()

    if not filas:
        return {
            "ok": False,
            "modo": "NO_ENCONTRADO",
            "mensaje": "No se encontró en BD el marcaje real que se intentó cerrar.",
            "select_validacion": select_sql,
            "valores": valores,
        }

    delete_sql = f"""
        DELETE FROM smartfactory.marcajeactivo
        WHERE {where_sql}
        LIMIT 1
    """

    if not ENABLE_REAL_DB_WRITES:
        _log_accion("CIERRE_PROTEGIDO", valores)
        return {
            "ok": False,
            "modo": "PROTEGIDO",
            "mensaje": (
                "La escritura real está deshabilitada. El marcaje existe en BD, pero el DELETE no fue ejecutado. "
                "Active SMARTFACTORY_ENABLE_REAL_DB_WRITES=1 y reinicie uvicorn para escribir en BD."
            ),
            "select_validacion": select_sql,
            "delete_preparado": delete_sql,
            "valores": valores,
        }

    resultado = dtbSmartFactory(delete_sql).consultaSmartFactory()

    if resultado is None:
        _log_accion("CIERRE_ERROR_BD", valores)
        return {
            "ok": False,
            "mensaje": "No se pudo cerrar/eliminar el marcaje real en smartfactory.marcajeactivo.",
            "delete_ejecutado": delete_sql,
        }

    _log_accion("CIERRE_REAL_OK", valores)

    return {
        "ok": True,
        "mensaje": "Marcaje real cerrado correctamente en smartfactory.marcajeactivo.",
        "resultado_bd": resultado,
        "marcaje_cerrado": marcaje,
        "delete_ejecutado": delete_sql,
    }


def iniciar_relevo_mt_real_bd(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Abre un nuevo marcaje real reutilizando OP/recurso/actividad del marcaje cerrado con MT.

    Este flujo se usa para cambio de turno sin detener máquina:
    1. Operario A cierra como MT.
    2. Frontend queda en modo relevo pendiente.
    3. Operario B se identifica.
    4. Backend abre un nuevo marcaje para B con la misma OP/recurso/actividad.

    Internamente reutiliza iniciar_marcaje_real_bd(), por lo que respeta:
    - validaciones de usuario activo,
    - validaciones de recurso/topic activo,
    - escritura protegida por SMARTFACTORY_ENABLE_REAL_DB_WRITES,
    - publicación MQTT protegida por SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH.
    """
    relevo = payload.get("relevo") or {}
    codigo_usuario = limpiar_sql(payload.get("codigo_usuario") or payload.get("username"))

    if not codigo_usuario:
        return {
            "ok": False,
            "modo": "USUARIO_FALTANTE",
            "mensaje": "No se puede iniciar relevo MT. Falta codigo_usuario del operario entrante.",
        }

    # El relevo puede venir desde resultado_cierre["valores"] o desde marcaje_cerrado.
    num_op = relevo.get("numOp") or relevo.get("num_op")
    descripcion = relevo.get("descrip") or relevo.get("descripcion") or "RELEVO MT"
    cantidad = relevo.get("cantidadcot") or relevo.get("cantidad") or 0
    recurso = relevo.get("recurso")
    actividad = relevo.get("actividad")

    faltantes = [
        nombre for nombre, valor in {
            "numOp": num_op,
            "recurso": recurso,
            "actividad": actividad,
        }.items()
        if str(valor or "").strip() == ""
    ]

    if faltantes:
        return {
            "ok": False,
            "modo": "DATOS_RELEVO_INCOMPLETOS",
            "mensaje": "No se puede iniciar relevo MT. Faltan campos: " + ", ".join(faltantes),
            "relevo_recibido": relevo,
        }

    payload_inicio = {
        "num_op": str(num_op),
        "num_ot": str(relevo.get("num_ot") or f"{num_op}01"),
        "descripcion": str(descripcion),
        "cantidad": str(cantidad),
        "recurso": str(recurso),
        "actividad": str(actividad),
        "actividad_nombre": str(relevo.get("actividad_nombre") or actividad),
        "codigo_usuario": codigo_usuario,
    }

    resultado = iniciar_marcaje_real_bd(payload_inicio)

    if not resultado.get("ok"):
        resultado["modo_relevo"] = "MT"
        resultado["payload_inicio_relevo"] = payload_inicio
        return resultado

    return {
        **resultado,
        "modo_relevo": "MT",
        "mensaje": resultado.get("mensaje", "Marcaje de relevo MT abierto correctamente."),
        "payload_inicio_relevo": payload_inicio,
        "relevo_origen": relevo,
    }
