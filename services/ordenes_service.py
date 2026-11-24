from typing import Dict, Any, List, Tuple

from db.conexion import dtbOptimus1, dtbEntregasDiarias, dtbSmartFactory
from services.resolucion_ot_service import es_numero_op, leer_op
from services.usuarios_service import identificar_usuario_prueba


def _normalizar_recurso(fila) -> Tuple[str, str]:
    codigo = str(fila[0]).strip() if fila and fila[0] is not None else ""
    nombre = str(fila[1]).strip() if len(fila) > 1 and fila[1] is not None else codigo
    return codigo, nombre


def obtener_recursos_de_orden() -> List[Dict[str, str]]:
    """
    Replica la lógica actual de PyQt:
    1. Obtiene recursos cotizados desde Optimus.
    2. Complementa recursos programados desde entregasDiarias.dbo.relacionalProgramacion.
    3. Elimina duplicados y ordena por código.
    """
    query_optimus = """
        SELECT DISTINCT act.act_cc, cc_name
        FROM wo200
        INNER JOIN wo_task200 ON wo200.wo_number = wo_task200.tk_wonum
        INNER JOIN act ON wo_task200.tk_code = act.act_code
        INNER JOIN cc ON act.act_cc = cc.cc_code
        ORDER BY 1
    """
    recursos_optimus_raw = dtbOptimus1(query_optimus).consultaOptimus() or []
    
    print(recursos_optimus_raw)

    #orden_trabajo = str(num_op)
    #query_prodigos = f"""
    #    SELECT DISTINCT(recurso), recursoNombre
    #    FROM entregasDiarias.dbo.relacionalProgramacion
    #    WHERE numOp = '{orden_trabajo}'
    #    ORDER BY 1
    #"""
    #recursos_prodigos_raw = dtbEntregasDiarias(query_prodigos).consultaEntregasDiarias() or []

    recursos = {}

    for fila in recursos_optimus_raw:
        codigo, nombre = _normalizar_recurso(fila)
        if codigo:
            recursos[codigo] = nombre

    #for fila in recursos_prodigos_raw:
    #    codigo, nombre = _normalizar_recurso(fila)
    #    if codigo and codigo not in recursos:
    #        recursos[codigo] = nombre

    return [
        {"codigo": codigo, "nombre": nombre}
        for codigo, nombre in sorted(recursos.items(), key=lambda item: item[0].lower())
    ]
    
    
def obtener_recursos_existentes_improductivo() -> List[Dict[str, str]]:
    """
    Obtiene los recursos existentes en smf
    """
    query = """
        SELECT recurso,
                descripcion
        FROM smartfactory.macdirectorio
    """

    recursos_smf_raw = dtbSmartFactory(query).consultaSmartFactory()

    if not recursos_smf_raw:
        return []

    recursos = {}

    for fila in recursos_smf_raw:
        codigo, nombre = _normalizar_recurso(fila)
        if codigo:
            recursos[codigo] = nombre

    return [
        {"codigo": codigo, "nombre": nombre}
        for codigo, nombre in sorted(recursos.items(), key=lambda item: item[0].lower())
    ]



def buscar_orden_produccion(num_op: str, codigo_usuario: str) -> Dict[str, Any]:
    """
    Migra la lógica base de ingreso de OP, separada de la interfaz.
    """
    # Sin rango 10 000-1 000 000 (P-20): la OP debe ser numérica, existir y ser elegible.
    lectura = leer_op(num_op)
    if not lectura["ok"]:
        return lectura

    usuario = identificar_usuario_prueba(codigo_usuario)
    if not usuario:
        return {"ok": False, "mensaje": "Usuario no encontrado."}

    orden = lectura["orden"]
    num_op_real = orden["num_op"]

    recursos = obtener_recursos_de_orden()

    recurso_usuario = ""
    usuario_resource = usuario.get("resource") or ""

    for recurso in recursos:
        codigo = recurso["codigo"]
        if codigo and codigo in usuario_resource:
            recurso_usuario = codigo
            break

    actividades_sugeridas = []
    if recurso_usuario:
        actividades_sugeridas = obtener_actividades_por_recurso(num_op_real, recurso_usuario)

    return {
        "ok": True,
        "usuario": usuario,
        "orden": {
            "num_op": num_op_real,
            "descripcion": orden["descripcion"],
            "cantidad": orden["cantidad"],
        },
        "recursos": recursos,
        "recurso_usuario": recurso_usuario,
        "actividades_sugeridas": actividades_sugeridas,
        "siguiente_paso": "seleccionar_actividad" if recurso_usuario else "seleccionar_recurso",
    }
    
    
def buscar_recursos_improductivo(codigo_usuario: str) -> Dict[str, Any]:
    """
    busca encontrar los recursos que cuentan con smf
    """
    
    usuario = identificar_usuario_prueba(codigo_usuario)
    if not usuario:
        return {"ok": False, "mensaje": "Usuario no encontrado."}

    recursos = obtener_recursos_existentes_improductivo()

    return {
        "ok": True,
        "usuario": usuario,
        "recursos": recursos,
    }


def _validar_num_op(num_op: str) -> str:
    if not es_numero_op(num_op):
        raise ValueError("El número de OP debe contener solo dígitos.")
    return str(num_op).strip()


def obtener_actividades_por_recurso(num_op: str, recurso: str) -> List[Dict[str, Any]]:
    """
    Actividades vigentes del centro de costo con alguna tarea en CUALQUIER OT de la OP
    (sin filtrar el estado de la tarea). docs/ai/14-resolucion-ot.md §2.2.
    """
    op = _validar_num_op(num_op)
    query = """
        SELECT act.act_code, act.act_name
        FROM act
        WHERE act.act_cc = %s
          AND act.act_discont = '0'
          AND EXISTS (
              SELECT 1
              FROM wo_task200 wt
              INNER JOIN wo ON wo.wo_number = wt.tk_wonum
              WHERE wo.wo_job = %s
                AND wt.tk_code = act.act_code
          )
        ORDER BY act.act_name
    """

    resultado = dtbOptimus1(query, (recurso, op)).consultaOptimus()

    if not resultado:
        return []

    return [{"codigo": fila[0], "nombre": fila[1]} for fila in resultado]


def obtener_actividades_no_cotizadas_por_recurso(num_op: str, recurso: str) -> List[Dict[str, Any]]:
    """
    Actividades vigentes del centro de costo SIN tarea en ninguna OT de la OP.

    Equivalente web del popup PyQt de actividad extra/no cotizada: catálogo del
    recurso menos las actividades cotizadas (docs/ai/14-resolucion-ot.md §2.2).
    """
    op = _validar_num_op(num_op)
    query = """
        SELECT act.act_code, act.act_name
        FROM act
        WHERE act.act_cc = %s
          AND act.act_discont = '0'
          AND NOT EXISTS (
              SELECT 1
              FROM wo_task200 wt
              INNER JOIN wo ON wo.wo_number = wt.tk_wonum
              WHERE wo.wo_job = %s
                AND wt.tk_code = act.act_code
          )
        ORDER BY act.act_name
    """

    resultado = dtbOptimus1(query, (recurso, op)).consultaOptimus()

    if not resultado:
        return []

    return [
        {"codigo": str(fila[0]).strip(), "nombre": str(fila[1]).strip(), "no_cotizada": True}
        for fila in resultado
        if fila and fila[0] is not None and fila[1] is not None
    ]
