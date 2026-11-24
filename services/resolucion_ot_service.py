"""
Resolución de OT y tarea al abrir un marcaje (adaptación de PRODIGOS V2).

- Funciones puras (sin BD): `evaluar_elegibilidad_op`, `resolver`.
- Lecturas de Optimus (solo SELECT parametrizado): `leer_op`, `resolver_desde_optimus`.
Diseño: docs/ai/14-resolucion-ot.md (iteraciones 1 y 2).
"""
from typing import Any, Dict, List, Optional

from db.conexion import dtbOptimus1

CLAVES_JOB = ("j_status", "j_state", "j_locked")
CLAVES_OT = ("wo_number", "wo_status", "wo_seq", "wo_title2")
CLAVES_TAREA = ("tk_id", "tk_wonum", "tk_status", "tk_seq")
LARGO_TITULO = 60

OP_IMPRODUCTIVO = "12345"
MAX_OTS = 100
MAX_TAREAS = 500
COLUMNAS_JOB = ("j_number", "j_status", "j_state", "j_locked", "j_title1", "j_quantity")


def _texto(valor: Any) -> Optional[str]:
    return None if valor is None else str(valor).strip()


def _validar_filas(filas: Any, claves: tuple, nombre: str) -> None:
    if not isinstance(filas, list):
        raise ValueError(f"'{nombre}' debe ser una lista.")
    for i, fila in enumerate(filas):
        if not isinstance(fila, dict):
            raise ValueError(f"'{nombre}[{i}]' debe ser un diccionario.")
        faltan = [c for c in claves if c not in fila]
        if faltan:
            raise ValueError(f"'{nombre}[{i}]' no tiene las claves: {', '.join(faltan)}.")


def _rechazo(codigo: str, mensaje: str) -> Dict[str, Any]:
    return {"ok": False, "codigo": codigo, "mensaje": mensaje}


def evaluar_elegibilidad_op(fila: dict) -> Dict[str, Any]:
    """Comprueba en orden: cancelada → completitud → j_state → j_locked."""
    if not isinstance(fila, dict):
        raise ValueError("La fila de job200 debe ser un diccionario.")
    faltan = [c for c in CLAVES_JOB if c not in fila]
    if faltan:
        raise ValueError(f"A la fila de job200 le faltan las claves: {', '.join(faltan)}.")

    status = _texto(fila["j_status"])
    state = _texto(fila["j_state"])
    locked = _texto(fila["j_locked"])

    if status == "X":
        return _rechazo("OP_CANCELADA", "La orden está cancelada. No se puede marcar.")
    if status not in ("N", "C"):
        return _rechazo("OP_COMPLETITUD_DESCONOCIDA",
                           "No se pudo determinar si la orden está abierta. Consulte con su supervisor.")
    if state != "N":
        if state == "R":
            return _rechazo("OP_RESERVADA", "La orden está reservada. No se puede marcar.")
        if state == "S":
            return _rechazo("OP_SUSPENDIDA", "La orden está suspendida. No se puede marcar.")
        return _rechazo("OP_ESTADO_DESCONOCIDO",
                           "No se pudo determinar el estado de la orden. Consulte con su supervisor.")
    if locked != "0":
        if locked == "1":
            return _rechazo("OP_BLOQUEADA", "La orden está bloqueada. No se puede marcar.")
        return _rechazo("OP_BLOQUEO_DESCONOCIDO",
                           "No se pudo determinar si la orden está bloqueada. Consulte con su supervisor.")

    return {"ok": True, "codigo": "OP_ELEGIBLE", "mensaje": "Orden válida para marcar."}


def _clave_nulos_al_final(valor: Any) -> tuple:
    return (valor is None, valor)


def _clave_numero_ot(numero: str) -> tuple:
    # Numéricos primero (por valor) y después los no numéricos (como texto).
    return (0, int(numero), "") if numero.isdigit() else (1, 0, numero)


def _titulo(valor: Any) -> Optional[str]:
    texto = _texto(valor)
    return texto[:LARGO_TITULO] if texto else None


def resolver(ots: list, tareas: list, ot_elegida: Any = None) -> Dict[str, Any]:
    """PRODIGOS §5.3, §5.4 y §6: OT y tarea de la actividad, o rechazo."""
    _validar_filas(ots, CLAVES_OT, "ots")
    _validar_filas(tareas, CLAVES_TAREA, "tareas")

    ots_abiertas = {_texto(o["wo_number"]): o for o in ots if _texto(o["wo_status"]) == "N"}
    candidatas = [
        t for t in tareas
        if _texto(t["tk_status"]) == "N" and _texto(t["tk_wonum"]) in ots_abiertas
    ]

    # Una tarea por OT: menor tk_seq (nulos al final) y, a igualdad, menor tk_id.
    tarea_por_ot: Dict[str, dict] = {}
    for t in sorted(candidatas, key=lambda t: (_clave_nulos_al_final(t["tk_seq"]), t["tk_id"])):
        tarea_por_ot.setdefault(_texto(t["tk_wonum"]), t)

    numeros = sorted(
        tarea_por_ot,
        key=lambda n: (_clave_nulos_al_final(ots_abiertas[n]["wo_seq"]), _clave_numero_ot(n)),
    )
    lista = [
        {
            "numeroOt": n,
            "titulo": _titulo(ots_abiertas[n]["wo_title2"]),
            "secuencia": ots_abiertas[n]["wo_seq"],
        }
        for n in numeros
    ]

    eligio = ot_elegida is not None
    elegida = _texto(ot_elegida)

    if eligio and elegida not in tarea_por_ot:
        return {"ok": False, "codigo": "OT_NO_CANDIDATA",
                "mensaje": "La parte de la orden elegida ya no está disponible para esta actividad. Vuelva a elegir.",
                "ots_candidatas": lista}

    if not numeros:
        return {"ok": True, "estado": "SIN_TAREA", "wo_number": None, "tk_id": None, "titulo_ot": None,
                "ots_candidatas": [], "num_candidatas": 0, "ot_elegida": eligio,
                "mensaje": "La actividad no tiene tareas abiertas en la orden."}

    if len(numeros) > 1 and not eligio:
        return {"ok": False, "codigo": "SELECCION_OT_REQUERIDA",
                "mensaje": "La actividad está en varias partes de la orden. Elija en cuál trabaja.",
                "ots_candidatas": lista}

    if len(numeros) == 1:
        numero, estado, mensaje = numeros[0], "AUTOMATICA", "Parte de la orden asignada automáticamente."
    else:
        numero, estado, mensaje = elegida, "ELEGIDA", "Parte de la orden elegida por el operario."

    return {
        "ok": True,
        "estado": estado,
        "wo_number": numero,
        "tk_id": tarea_por_ot[numero]["tk_id"],
        "titulo_ot": _titulo(ots_abiertas[numero]["wo_title2"]),
        "ots_candidatas": lista,
        "num_candidatas": len(candidatas),
        "ot_elegida": eligio,
        "mensaje": mensaje,
    }


# ---------------------------------------------------------------- lecturas de Optimus

def es_numero_op(texto: Any) -> bool:
    """Solo dígitos ASCII tras strip (j_number es int en Optimus)."""
    valor = "" if texto is None else str(texto).strip()
    return valor.isascii() and valor.isdigit()


def _optimus_no_disponible() -> Dict[str, Any]:
    return _rechazo("OPTIMUS_NO_DISPONIBLE",
                    "No se pudo consultar Optimus. Intente de nuevo o avise a su supervisor.")


def _respuesta_invalida(detalle: str) -> Dict[str, Any]:
    return _rechazo("RESPUESTA_INVALIDA",
                    f"Optimus devolvió datos inesperados ({detalle}). Avise a su supervisor.")


def leer_op(num_op: Any) -> Dict[str, Any]:
    """Valida el número, lee la OP en job200 y evalúa su elegibilidad."""
    if not es_numero_op(num_op):
        return _rechazo("OP_INVALIDA", "Debe ingresar un número de OP válido (solo dígitos).")
    op = str(num_op).strip()

    filas = dtbOptimus1(
        "SELECT j_number, j_status, j_state, j_locked, j_title1, j_quantity "
        "FROM job200 WHERE j_number = %s LIMIT 2",
        (op,),
    ).consultaOptimus()

    if filas is None:
        return _optimus_no_disponible()
    if not filas:
        return _rechazo("OP_INEXISTENTE", f"La OP {op} no existe en Optimus.")
    if len(filas) > 1:
        return _respuesta_invalida("OP duplicada")

    fila = dict(zip(COLUMNAS_JOB, filas[0]))
    elegibilidad = evaluar_elegibilidad_op(fila)
    if not elegibilidad["ok"]:
        return elegibilidad

    return {
        "ok": True,
        "fila": fila,
        "orden": {
            "num_op": str(fila["j_number"]).strip(),
            "descripcion": fila["j_title1"],
            "cantidad": fila["j_quantity"],
        },
    }


def resolver_desde_optimus(num_op: Any, actividad: str, ot_elegida: Any = None) -> Dict[str, Any]:
    """Lee job200, wo y wo_task200 (solo lectura) y resuelve OT y tarea de la actividad."""
    if not es_numero_op(num_op):
        return _rechazo("OP_INVALIDA", "Debe ingresar un número de OP válido (solo dígitos).")
    actividad = "" if actividad is None else str(actividad).strip()
    if not actividad:
        raise ValueError("La actividad es obligatoria para resolver la OT.")
    if ot_elegida is not None and not str(ot_elegida).strip():
        ot_elegida = None

    if str(num_op).strip() == OP_IMPRODUCTIVO:
        return {**resolver([], [], ot_elegida), "orden": None}

    lectura = leer_op(num_op)
    if not lectura["ok"]:
        return lectura
    op = lectura["orden"]["num_op"]

    filas_wo = dtbOptimus1(
        "SELECT wo_number, wo_status, wo_seq, wo_title2 FROM wo WHERE wo_job = %s "
        f"ORDER BY (wo_seq IS NULL), wo_seq, wo_number LIMIT {MAX_OTS + 1}",
        (op,),
    ).consultaOptimus()
    if filas_wo is None:
        return _optimus_no_disponible()
    if len(filas_wo) > MAX_OTS:
        return _respuesta_invalida(f"más de {MAX_OTS} OT")
    ots = [dict(zip(CLAVES_OT, fila)) for fila in filas_wo]

    tareas: List[dict] = []
    if ots:
        marcadores = ", ".join(["%s"] * len(ots))
        filas_tk = dtbOptimus1(
            f"SELECT tk_id, tk_wonum, tk_status, tk_seq FROM wo_task200 "
            f"WHERE tk_wonum IN ({marcadores}) AND tk_code = %s ORDER BY tk_id LIMIT {MAX_TAREAS + 1}",
            (*[o["wo_number"] for o in ots], actividad),
        ).consultaOptimus()
        if filas_tk is None:
            return _optimus_no_disponible()
        if len(filas_tk) > MAX_TAREAS:
            return _respuesta_invalida(f"más de {MAX_TAREAS} tareas")
        tareas = [dict(zip(CLAVES_TAREA, fila)) for fila in filas_tk]

    return {**resolver(ots, tareas, ot_elegida), "orden": lectura["orden"]}
