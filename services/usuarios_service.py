from typing import Optional, Dict, Any

from db.conexion import dtbOptimus1, dtbSmartFactory
from services.marcajes_estado_service import listar_marcajes_activos_simulados


def _fila_bd_a_marcaje_activo(fila) -> dict:
    topic = fila[6] if len(fila) > 6 else None
    mac = None
    if topic and "-" in str(topic):
        mac = str(topic).split("-", 1)[0].strip()

    return {
        "id": f"REAL_BD|{fila[5]}|{fila[0]}|{fila[3]}|{fila[4]}",
        "modo": "REAL_BD",
        "username": fila[5],
        "codigo_usuario": fila[5],
        "numOp": fila[0],
        "descrip": fila[1],
        "cantidad": fila[2],
        "recurso": fila[3],
        "actividad": fila[4],
        "topic": topic,
        "mac": mac,
        "produccionUnidad": fila[7] if len(fila) > 7 else None,
        "mensaje": "El usuario cuenta con un marcaje activo en BD."
    }


def identificar_usuario_prueba(codigo_usuario: str) -> Optional[Dict[str, Any]]:
    """
    Simula la identificación por huella usando el código del colaborador.
    """
    query = """
        SELECT staf_code, staf_name, staf_resource
        FROM staf
        WHERE staf_discontinued = %s
          AND staf_code = %s
        LIMIT 1
    """
    params = ('0', codigo_usuario.strip())

    resultado = dtbOptimus1(query, params).consultaOptimus()

    if not resultado:
        return None

    return {
        "code": resultado[0][0],
        "username": resultado[0][1],
        "resource": resultado[0][2]
    }


def consultar_marcaje_activo(codigo_usuario: str) -> Optional[Dict[str, Any]]:
    """
    Consulta desde el paso 1 si el usuario ya tiene un marcaje activo.

    Revisa primero el estado vivo en memoria, porque durante las pruebas puede
    existir un marcaje simulado o un marcaje real ya sincronizado sin necesidad
    de volver a consultar BD. Después consulta smartfactory.marcajeactivo como
    fuente persistente.
    """
    codigo_usuario = codigo_usuario.replace("'", "").strip()

    for marcaje in listar_marcajes_activos_simulados():
        if str(marcaje.get("username") or marcaje.get("codigo_usuario") or "").strip() == codigo_usuario:
            return {
                **marcaje,
                "mensaje": "El usuario cuenta con un marcaje activo en el estado vivo."
            }

    query = f"""
        SELECT numOp, descrip, cantidad, recurso, actividad, username, topic, produccionUnidad
        FROM smartfactory.marcajeactivo
        WHERE username = '{codigo_usuario}'
        LIMIT 1
    """

    resultado = dtbSmartFactory(query).consultaSmartFactory()

    if not resultado:
        return None

    return _fila_bd_a_marcaje_activo(resultado[0])
