from typing import Dict, Any, List, Tuple

from db.conexion import dtbOptimus1, dtbEntregasDiarias, dtbSmartFactory
from services.usuarios_service import identificar_usuario_prueba


def _limpiar_numero_op(num_op: str) -> str:
    return "".join(ch for ch in str(num_op).strip() if ch.isdigit())


def _normalizar_recurso(fila) -> Tuple[str, str]:
    codigo = str(fila[0]).strip() if fila and fila[0] is not None else ""
    nombre = str(fila[1]).strip() if len(fila) > 1 and fila[1] is not None else codigo
    return codigo, nombre


def obtener_recursos_de_orden(num_ot: str) -> List[Dict[str, str]]:
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

    #orden_trabajo = str(num_ot)[:-2]
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
    op_limpia = _limpiar_numero_op(num_op)

    if not op_limpia:
        return {"ok": False, "mensaje": "Debe ingresar una OP válida."}

    if not (10000 <= int(op_limpia) <= 1_000_000):
        return {"ok": False, "mensaje": "Número de OP fuera del rango permitido."}

    usuario = identificar_usuario_prueba(codigo_usuario)
    if not usuario:
        return {"ok": False, "mensaje": "Usuario no encontrado."}

    num_ot = f"{op_limpia}01"

    query_wo = "SELECT wo_job FROM mayaprin.wo200 WHERE wo_number = %s"
    resultado_wo = dtbOptimus1(query_wo, (num_ot,)).consultaOptimus()

    if not resultado_wo:
        return {"ok": False, "mensaje": "Número de OP incorrecto o no encontrado."}

    num_op_real = str(resultado_wo[0][0])

    query_info = "SELECT j_title1, j_quantity FROM mayaprin.job200 WHERE j_number = %s"
    info_op = dtbOptimus1(query_info, (num_op_real,)).consultaOptimus()

    if not info_op:
        return {"ok": False, "mensaje": "No se encontró información de la orden."}

    descripcion = info_op[0][0]
    cantidad = info_op[0][1]

    recursos = obtener_recursos_de_orden(num_ot)

    recurso_usuario = ""
    usuario_resource = usuario.get("resource") or ""

    for recurso in recursos:
        codigo = recurso["codigo"]
        if codigo and codigo in usuario_resource:
            recurso_usuario = codigo
            break

    actividades_sugeridas = []
    if recurso_usuario:
        actividades_sugeridas = obtener_actividades_por_recurso(num_ot, recurso_usuario)

    return {
        "ok": True,
        "usuario": usuario,
        "orden": {
            "num_op": num_op_real,
            "num_ot": num_ot,
            "descripcion": descripcion,
            "cantidad": cantidad,
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


def obtener_actividades_por_recurso(num_ot: str, recurso: str) -> List[Dict[str, Any]]:
    query = """
        SELECT DISTINCT wo_task200.tk_code, act.act_name
        FROM wo_task200
        INNER JOIN act ON wo_task200.tk_code = act.act_code
        WHERE tk_wonum = %s
          AND act.act_cc = %s
        ORDER BY act.act_name
    """

    resultado = dtbOptimus1(query, (num_ot, recurso)).consultaOptimus()

    if not resultado:
        return []

    return [{"codigo": fila[0], "nombre": fila[1]} for fila in resultado]


def obtener_actividades_no_cotizadas_por_recurso(num_ot: str, recurso: str) -> List[Dict[str, Any]]:
    """
    Devuelve actividades disponibles en mayaprin.act para el recurso,
    excluyendo las actividades ya cotizadas en la OT para ese mismo recurso.

    Equivalente web del popup PyQt de actividad extra/no cotizada:
    - consulta el catálogo general de actividades por recurso;
    - compara contra las actividades cotizadas;
    - devuelve solo las que aún no están visibles en el marcaje.
    """
    query = """
        SELECT DISTINCT act.act_code, act.act_name
        FROM mayaprin.act act
        WHERE act.act_cc = %s
          AND NOT EXISTS (
              SELECT 1
              FROM mayaprin.wo_task200 wt
              INNER JOIN mayaprin.act act_cot ON wt.tk_code = act_cot.act_code
              WHERE wt.tk_wonum = %s
                AND act_cot.act_cc = %s
                AND wt.tk_code = act.act_code
          )
        ORDER BY act.act_name
    """

    resultado = dtbOptimus1(query, (recurso, num_ot, recurso)).consultaOptimus()

    if not resultado:
        return []

    return [
        {"codigo": str(fila[0]).strip(), "nombre": str(fila[1]).strip(), "no_cotizada": True}
        for fila in resultado
        if fila and fila[0] is not None and fila[1] is not None
    ]
