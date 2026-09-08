from datetime import datetime
from typing import Dict, Any, Optional

from db.conexion import dtbSmartFactory
from services.usuarios_service import consultar_marcaje_activo


def limpiar_sql(valor: Any) -> str:
    """
    Limpieza básica para construir textos SQL de PREVIEW.

    IMPORTANTE:
    Esta función se usa solamente para mostrar la simulación.
    Cuando activemos el INSERT real, lo correcto será usar consultas parametrizadas
    si la clase de conexión lo permite.
    """
    if valor is None:
        return ""
    return str(valor).strip().replace("'", "''")


def obtener_mac_por_recurso(recurso: str) -> Optional[str]:
    """
    Busca la MAC del sensor/dispositivo asociado al recurso.
    """
    recurso_limpio = limpiar_sql(recurso)

    query = f"""
        SELECT mac
        FROM smartfactory.macdirectorio
        WHERE recurso = '{recurso_limpio}'
        LIMIT 1
    """

    resultado = dtbSmartFactory(query).consultaSmartFactory()

    if not resultado:
        return None

    return str(resultado[0][0]).strip()




def consultar_marcaje_activo_por_recurso_o_topic(recurso: str, topic: str | None = None) -> Optional[Dict[str, Any]]:
    """
    Consulta si una máquina/recurso ya tiene un marcaje activo.

    Esta validación se ejecuta desde la preparación/simulación del marcaje,
    no solo desde el INSERT real, para evitar que el usuario llegue a armar
    un mensaje válido sobre una máquina que ya está ocupada.
    """
    recurso_limpio = limpiar_sql(recurso)
    topic_limpio = limpiar_sql(topic) if topic else ""

    condiciones = [f"recurso = '{recurso_limpio}'"]

    if topic_limpio:
        condiciones.append(f"topic = '{topic_limpio}'")

    where_sql = " OR ".join(condiciones)

    query = f"""
        SELECT numOp, recurso, actividad, username, topic
        FROM smartfactory.marcajeactivo
        WHERE {where_sql}
        LIMIT 1
    """

    resultado = dtbSmartFactory(query).consultaSmartFactory()

    if not resultado:
        return None

    fila = resultado[0]

    return {
        "numOp": fila[0],
        "recurso": fila[1],
        "actividad": fila[2],
        "username": fila[3],
        "topic": fila[4],
        "mensaje": "La máquina/recurso ya cuenta con un marcaje activo.",
    }


def consultar_marcaje_temporal_por_recurso_o_topic(recurso: str, topic: str | None = None) -> Optional[Dict[str, Any]]:
    """
    Consulta el estado temporal en memoria para bloquear duplicados simulados.

    Esto ayuda durante pruebas porque puede existir un marcaje simulado que aún
    no está en smartfactory.marcajeactivo, pero operacionalmente debe bloquear
    que la misma máquina se vuelva a preparar.
    """
    try:
        from services.marcajes_estado_service import listar_marcajes_activos_simulados
    except Exception:
        return None

    recurso_limpio = str(recurso or "").strip()
    topic_limpio = str(topic or "").strip()

    for marcaje in listar_marcajes_activos_simulados():
        mismo_recurso = str(marcaje.get("recurso") or "").strip() == recurso_limpio
        mismo_topic = bool(topic_limpio) and str(marcaje.get("topic") or "").strip() == topic_limpio

        if mismo_recurso or mismo_topic:
            return {
                "numOp": marcaje.get("numOp"),
                "recurso": marcaje.get("recurso"),
                "actividad": marcaje.get("actividad"),
                "username": marcaje.get("username"),
                "topic": marcaje.get("topic"),
                "modo": marcaje.get("modo"),
                "mensaje": "La máquina/recurso ya cuenta con un marcaje activo en memoria.",
            }

    return None


def seleccionar_produccion_unidad(codigo_actividad: str) -> str:
    """
    Equivalente inicial de seleccionProduccionUnidad().

    IMPORTANTE:
    De momento retorna un valor por defecto porque la regla exacta debe revisarse
    contra la función actual de PyQt. Este punto queda aislado aquí para cambiarlo
    sin tocar API ni frontend.
    """
    return "UNIDAD"


def construir_mensaje_mqtt_inicio(payload: Dict[str, Any]) -> str:
    """
    Construye el mensaje que se publicaría al topic MQTT para iniciar la OP.

    Se conserva la estructura usada en PyQt:
    numOp,recurso,actividad,cantidad,100,fechaInicio,horaInicio,fechaFinal,horaFinal,0,1

    Por ahora se dejan las fechas históricas quemadas como en el flujo actual,
    porque esta fase es únicamente de validación. En la fase real definimos
    si deben ser hora actual, turno o valores calculados.
    """
    return (
        f"{payload['num_op']},"
        f"{payload['recurso']},"
        f"{payload['actividad']},"
        f"{payload['cantidad']},"
        "100,2024/10/09,08:31:55,2024/10/09,18:30:55,0,1"
    )


def construir_insert_marcajeactivo(payload: Dict[str, Any], topic: str, produccion_unidad: str) -> str:
    """
    Construye el texto SQL que se insertaría en smartfactory.marcajeactivo.
    NO ejecuta el INSERT.
    """
    num_op = limpiar_sql(payload["num_op"])
    descripcion = limpiar_sql(payload["descripcion"])
    cantidad = limpiar_sql(payload["cantidad"])
    recurso = limpiar_sql(payload["recurso"])
    actividad = limpiar_sql(payload["actividad"])
    codigo_usuario = limpiar_sql(payload["codigo_usuario"])
    topic_limpio = limpiar_sql(topic)
    produccion_unidad_limpio = limpiar_sql(produccion_unidad)

    return f"""INSERT INTO smartfactory.marcajeactivo
    (numOp, descrip, cantidad, recurso, actividad, username, topic, produccionUnidad)
VALUES
    ('{num_op}',
     '{descripcion}',
     '{cantidad}',
     '{recurso}',
     '{actividad}',
     '{codigo_usuario}',
     '{topic_limpio}',
     '{produccion_unidad_limpio}');"""


def preparar_inicio_marcaje(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida y prepara la información necesaria para iniciar un marcaje.

    Esta versión NO inserta en marcajeactivo y NO publica MQTT todavía.
    Sirve para validar el flujo de forma segura antes de activar escritura real.
    """
    codigo_usuario = str(payload["codigo_usuario"]).strip()
    recurso = str(payload["recurso"]).strip()
    actividad = str(payload["actividad"]).strip()

    marcaje_activo = consultar_marcaje_activo(codigo_usuario)
    if marcaje_activo:
        return {
            "ok": False,
            "mensaje": "El usuario ya tiene un marcaje activo. Debe cerrarlo antes de iniciar otro.",
            "marcaje_activo": marcaje_activo,
        }

    mac = obtener_mac_por_recurso(recurso)
    if not mac:
        return {
            "ok": False,
            "mensaje": "No existe sensor/MAC asignado a este recurso.",
        }

    topic = f"{mac}-OP"

    marcaje_maquina_bd = consultar_marcaje_activo_por_recurso_o_topic(recurso, topic)
    if marcaje_maquina_bd:
        return {
            "ok": False,
            "mensaje": "La máquina/recurso ya tiene un marcaje activo. Debe cerrarlo antes de iniciar otro.",
            "marcaje_activo": marcaje_maquina_bd,
            "bloqueo": "RECURSO_O_TOPIC_BD",
        }

    marcaje_maquina_temporal = consultar_marcaje_temporal_por_recurso_o_topic(recurso, topic)
    if marcaje_maquina_temporal:
        return {
            "ok": False,
            "mensaje": "La máquina/recurso ya tiene un marcaje activo en el estado temporal. Cierre ese marcaje antes de preparar otro.",
            "marcaje_activo": marcaje_maquina_temporal,
            "bloqueo": "RECURSO_O_TOPIC_MEMORIA",
        }

    produccion_unidad = seleccionar_produccion_unidad(actividad)
    mensaje_mqtt_preview = construir_mensaje_mqtt_inicio(payload)
    insert_marcajeactivo_preview = construir_insert_marcajeactivo(payload, topic, produccion_unidad)

    return {
        "ok": True,
        "mensaje": "Marcaje preparado correctamente. Aún no se insertó en BD ni se publicó MQTT.",
        "preview": {
            "num_op": payload["num_op"],
            "num_ot": payload["num_ot"],
            "descripcion": payload["descripcion"],
            "cantidad": payload["cantidad"],
            "recurso": recurso,
            "actividad": actividad,
            "actividad_nombre": payload["actividad_nombre"],
            "codigo_usuario": codigo_usuario,
            "mac": mac,
            "topic": topic,
            "produccion_unidad": produccion_unidad,
            "mensaje_mqtt_preview": mensaje_mqtt_preview,
            "insert_marcajeactivo_preview": insert_marcajeactivo_preview,
        }
    }
    
def preparar_inicio_marcaje_improductivo(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida y prepara la información necesaria para iniciar un marcaje.

    Esta versión NO inserta en marcajeactivo y NO publica MQTT todavía.
    Sirve para validar el flujo de forma segura antes de activar escritura real.
    """
    codigo_usuario = str(payload["codigo_usuario"]).strip()
    recurso = str(payload["recurso"]).strip()
    actividad = str(payload["actividad"]).strip()

    marcaje_activo = consultar_marcaje_activo(codigo_usuario)
    if marcaje_activo:
        return {
            "ok": False,
            "mensaje": "El usuario ya tiene un marcaje activo. Debe cerrarlo antes de iniciar otro.",
            "marcaje_activo": marcaje_activo,
        }

    mac = obtener_mac_por_recurso(recurso)
    if not mac:
        return {
            "ok": False,
            "mensaje": "No existe sensor/MAC asignado a este recurso.",
        }

    topic = f"{mac}-OP"

    marcaje_maquina_bd = consultar_marcaje_activo_por_recurso_o_topic(recurso, topic)
    if marcaje_maquina_bd:
        return {
            "ok": False,
            "mensaje": "La máquina/recurso ya tiene un marcaje activo. Debe cerrarlo antes de iniciar otro.",
            "marcaje_activo": marcaje_maquina_bd,
            "bloqueo": "RECURSO_O_TOPIC_BD",
        }

    marcaje_maquina_temporal = consultar_marcaje_temporal_por_recurso_o_topic(recurso, topic)
    if marcaje_maquina_temporal:
        return {
            "ok": False,
            "mensaje": "La máquina/recurso ya tiene un marcaje activo en el estado temporal. Cierre ese marcaje antes de preparar otro.",
            "marcaje_activo": marcaje_maquina_temporal,
            "bloqueo": "RECURSO_O_TOPIC_MEMORIA",
        }

    produccion_unidad = seleccionar_produccion_unidad(actividad)
    mensaje_mqtt_preview = construir_mensaje_mqtt_inicio(payload)
    insert_marcajeactivo_preview = construir_insert_marcajeactivo(payload, topic, produccion_unidad)

    return {
        "ok": True,
        "mensaje": "Marcaje preparado correctamente. Aún no se insertó en BD ni se publicó MQTT.",
        "preview": {
            "num_op": payload["num_op"],
            "recurso": recurso,
            "actividad": actividad,
            "actividad_nombre": payload["actividad_nombre"],
            "codigo_usuario": codigo_usuario,
            "mac": mac,
            "topic": topic,
            "produccion_unidad": produccion_unidad,
            "mensaje_mqtt_preview": mensaje_mqtt_preview,
            "insert_marcajeactivo_preview": insert_marcajeactivo_preview,
        }
    }


def simular_inicio_marcaje(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Modo simulación del inicio de marcaje.

    Devuelve todo lo que se enviaría/publicaría/insertaría, pero NO ejecuta:
    - NO INSERT en smartfactory.marcajeactivo
    - NO publicación MQTT
    """
    resultado = preparar_inicio_marcaje(payload)

    if not resultado["ok"]:
        return resultado

    preview = resultado["preview"]

    return {
        "ok": True,
        "mensaje": "Simulación generada correctamente. No se realizó ningún cambio en BD ni MQTT.",
        "simulacion": {
            "fecha_simulacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "accion": "INICIO_MARCAJE",
            "tabla_objetivo": "smartfactory.marcajeactivo",
            "mqtt": {
                "topic": preview["topic"],
                "payload": preview["mensaje_mqtt_preview"],
            },
            "base_datos": {
                "insert_marcajeactivo": preview["insert_marcajeactivo_preview"],
                "valores": {
                    "numOp": preview["num_op"],
                    "descrip": preview["descripcion"],
                    "cantidad": preview["cantidad"],
                    "recurso": preview["recurso"],
                    "actividad": preview["actividad"],
                    "username": preview["codigo_usuario"],
                    "topic": preview["topic"],
                    "produccionUnidad": preview["produccion_unidad"],
                },
            },
            "nota": "Esta simulación solamente arma los textos. No ejecuta INSERT ni publica en MQTT.",
        },
    }
    
    
def simular_inicio_marcaje_improductivo(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Modo simulación del inicio de marcaje.

    Devuelve todo lo que se enviaría/publicaría/insertaría, pero NO ejecuta:
    - NO INSERT en smartfactory.marcajeactivo
    - NO publicación MQTT
    """
    resultado = preparar_inicio_marcaje_improductivo(payload)

    if not resultado["ok"]:
        return resultado

    preview = resultado["preview"]

    return {
        "ok": True,
        "mensaje": "Simulación generada correctamente. No se realizó ningún cambio en BD ni MQTT.",
        "simulacion": {
            "fecha_simulacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "accion": "INICIO_MARCAJE",
            "tabla_objetivo": "smartfactory.marcajeactivo",
            "mqtt": {
                "topic": preview["topic"],
                "payload": preview["mensaje_mqtt_preview"],
            },
            "base_datos": {
                "insert_marcajeactivo": preview["insert_marcajeactivo_preview"],
                "valores": {
                    "numOp": preview["num_op"],
                    "recurso": preview["recurso"],
                    "actividad": preview["actividad"],
                    "username": preview["codigo_usuario"],
                    "topic": preview["topic"],
                    "produccionUnidad": preview["produccion_unidad"],
                },
            },
            "nota": "Esta simulación solamente arma los textos. No ejecuta INSERT ni publica en MQTT.",
        },
    }
