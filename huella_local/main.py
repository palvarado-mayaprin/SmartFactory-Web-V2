from __future__ import annotations

import os
import socket
import subprocess
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

HUELLA_HOST = os.getenv("SMARTFACTORY_HUELLA_HOST", "127.0.0.1")
HUELLA_PORT = int(os.getenv("SMARTFACTORY_HUELLA_PORT", "8888"))
HUELLA_COMANDO = os.getenv("SMARTFACTORY_HUELLA_COMANDO", "enrollFingerPrint")
HUELLA_TIMEOUT_SEGUNDOS = float(os.getenv("SMARTFACTORY_HUELLA_TIMEOUT_SEGUNDOS", "30"))
HUELLA_REINTENTOS_CONEXION = int(os.getenv("SMARTFACTORY_HUELLA_REINTENTOS_CONEXION", "12"))
HUELLA_ESPERA_REINTENTO = float(os.getenv("SMARTFACTORY_HUELLA_ESPERA_REINTENTO", "0.5"))

# IMPORTANTE:
# El ejecutable EnrollmentSample CS.exe parece comportarse como servidor socket de una sola lectura.
# Para imitar el flujo anterior de PyQt, por defecto se reinicia el .exe antes de cada lectura.
HUELLA_REINICIAR_EXE_ANTES_LECTURA = os.getenv(
    "SMARTFACTORY_HUELLA_REINICIAR_EXE_ANTES_LECTURA",
    "1",
).strip() == "1"

# Modo por defecto: REAL. Si necesitas volver a simulación:
# $env:SMARTFACTORY_HUELLA_MODO="SIMULACION"
HUELLA_MODO = os.getenv("SMARTFACTORY_HUELLA_MODO", "REAL").upper().strip()
HUELLA_USUARIO_SIMULADO = os.getenv("SMARTFACTORY_HUELLA_USUARIO", "M2013")

# Variantes de comando que se probarán si el .exe corta conexión.
# El código original enviaba enrollFingerPrint sin salto de línea.
COMANDOS_PRUEBA = [
    HUELLA_COMANDO,
    HUELLA_COMANDO + "\n",
    HUELLA_COMANDO + "\r\n",
]


app = FastAPI(
    title="SmartFactory Huella Local Service",
    version="19.4.0",
    description="Servicio local de huella con integración robusta a EnrollmentSample CS.exe por socket TCP.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Lock global para evitar lecturas simultáneas del lector.
# El .exe / SDK biométrico no debe recibir dos solicitudes al mismo tiempo.
LECTURA_HUELLA_LOCK = threading.Lock()


def _json_seguro(valor: Any) -> Any:
    """
    Convierte cualquier respuesta interna a tipos serializables por FastAPI/JSON.
    Evita errores de jsonable_encoder cuando alguna función devuelve objetos
    de proceso, socket, Path, Exception, bytes, etc.
    """
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor

    if isinstance(valor, bytes):
        return valor.decode("utf-8", errors="replace")

    if isinstance(valor, Path):
        return str(valor)

    if isinstance(valor, Exception):
        return str(valor)

    if isinstance(valor, dict):
        return {str(k): _json_seguro(v) for k, v in valor.items()}

    if isinstance(valor, (list, tuple, set)):
        return [_json_seguro(v) for v in valor]

    return str(valor)


def _respuesta_identificacion_segura(resultado: dict[str, Any]) -> dict[str, Any]:
    """Normaliza la respuesta final del endpoint /api/huella/identificar."""
    resultado_seguro = _json_seguro(resultado)

    if not isinstance(resultado_seguro, dict):
        return {
            "ok": False,
            "modo": "REAL",
            "mensaje": "La lectura de huella devolvió una respuesta inválida.",
            "raw": str(resultado_seguro),
        }

    return {
        "ok": bool(resultado_seguro.get("ok", False)),
        "modo": str(resultado_seguro.get("modo", HUELLA_MODO)),
        "mensaje": str(resultado_seguro.get("mensaje", "")),
        "codigo_usuario": str(resultado_seguro.get("codigo_usuario", "")),
        "raw": str(resultado_seguro.get("raw", "")),
        "datos": [str(x) for x in resultado_seguro.get("datos", [])],
        "fecha_identificacion": str(
            resultado_seguro.get("fecha_identificacion")
            or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Diagnóstico resumido y seguro. No se devuelve el objeto interno completo
        # para evitar referencias circulares y errores de serialización.
        "intentos": resultado_seguro.get("intentos", []),
        "comando_enviado_repr": str(resultado_seguro.get("comando_enviado_repr", "")),
    }

# ============================================================
# UTILIDADES DE RUTA / PROCESO
# ============================================================

def _ruta_base_proyecto() -> Path:
    return Path(__file__).resolve().parents[1]


def _obtener_ruta_exe() -> Path | None:
    ruta_env = os.getenv("SMARTFACTORY_ENROLLMENT_EXE_PATH")
    if ruta_env:
        ruta = Path(ruta_env)
        if ruta.exists():
            return ruta

    src_web = _ruta_base_proyecto()
    candidatos = [
        src_web.parent / "src" / "servicios" / "Enrollment" / "bin" / "Debug" / "EnrollmentSample CS.exe",
        src_web / "servicios" / "Enrollment" / "bin" / "Debug" / "EnrollmentSample CS.exe",
        src_web / "Enrollment" / "bin" / "Debug" / "EnrollmentSample CS.exe",
    ]

    for ruta in candidatos:
        if ruta.exists():
            return ruta

    return None


def _socket_escuchando_sin_tocar() -> bool:
    """
    Verifica si el puerto está LISTENING sin abrir una conexión TCP.

    Nota importante:
    La v19.1 usaba socket.create_connection para revisar el puerto.
    Eso puede consumir la conexión de EnrollmentSample CS.exe y dejarlo inestable.
    Por eso aquí se usa netstat.
    """
    if os.name == "nt":
        try:
            salida = subprocess.check_output(
                ["netstat", "-ano"],
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            puerto = f":{HUELLA_PORT}"
            for linea in salida.splitlines():
                linea_upper = linea.upper()
                if puerto in linea and "LISTENING" in linea_upper:
                    return True
            return False
        except Exception:
            # Fallback solo si netstat falla.
            pass

    # Fallback para otros entornos. En Windows se evita salvo error de netstat.
    try:
        with socket.create_connection((HUELLA_HOST, HUELLA_PORT), timeout=0.5):
            return True
    except OSError:
        return False


def _matar_exe_enrollment() -> dict[str, Any]:
    """Cierra EnrollmentSample CS.exe si está abierto."""
    if os.name != "nt":
        return {"ok": True, "mensaje": "No es Windows; no se ejecutó taskkill."}

    try:
        resultado = subprocess.run(
            ["taskkill", "/IM", "EnrollmentSample CS.exe", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5,
        )

        # taskkill devuelve 128 si no existe el proceso; no es fatal.
        return {
            "ok": True,
            "returncode": resultado.returncode,
            "stdout": resultado.stdout.strip(),
            "stderr": resultado.stderr.strip(),
            "mensaje": "Intento de cierre de EnrollmentSample CS.exe ejecutado.",
        }
    except Exception as e:
        return {"ok": False, "mensaje": f"No se pudo cerrar EnrollmentSample CS.exe: {e}"}


def _abrir_exe() -> dict[str, Any]:
    ruta_exe = _obtener_ruta_exe()
    if not ruta_exe:
        return {
            "ok": False,
            "mensaje": "No se encontró EnrollmentSample CS.exe. Configure SMARTFACTORY_ENROLLMENT_EXE_PATH.",
            "ruta_buscada": str(_ruta_base_proyecto().parent / "src" / "servicios" / "Enrollment" / "bin" / "Debug" / "EnrollmentSample CS.exe"),
        }

    try:
        startupinfo = None
        creationflags = 0

        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(
            [str(ruta_exe)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            cwd=str(ruta_exe.parent),
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

        return {
            "ok": True,
            "mensaje": "EnrollmentSample CS.exe fue iniciado.",
            "ruta_exe": str(ruta_exe),
        }

    except Exception as e:
        return {
            "ok": False,
            "mensaje": f"No se pudo abrir EnrollmentSample CS.exe: {e}",
            "ruta_exe": str(ruta_exe),
        }


def _preparar_exe_para_lectura(forzar_reinicio: bool = False) -> dict[str, Any]:
    """
    Prepara el .exe antes de pedir lectura.

    Si forzar_reinicio=True, cierra y abre el .exe para imitar el flujo anterior de PyQt.
    Si no, solo abre si el puerto no está escuchando.
    """
    acciones: list[dict[str, Any]] = []

    if forzar_reinicio:
        acciones.append({"accion": "cerrar_exe", "resultado": _matar_exe_enrollment()})
        time.sleep(0.7)

    if not _socket_escuchando_sin_tocar():
        acciones.append({"accion": "abrir_exe", "resultado": _abrir_exe()})
    else:
        acciones.append({
            "accion": "verificar_socket",
            "resultado": {
                "ok": True,
                "mensaje": f"El servicio de huella ya escucha en {HUELLA_HOST}:{HUELLA_PORT}.",
            },
        })

    for _ in range(HUELLA_REINTENTOS_CONEXION):
        if _socket_escuchando_sin_tocar():
            return {
                "ok": True,
                "socket_escuchando": True,
                "acciones": acciones,
            }
        time.sleep(HUELLA_ESPERA_REINTENTO)

    return {
        "ok": False,
        "socket_escuchando": False,
        "acciones": acciones,
        "mensaje": f"EnrollmentSample CS.exe no quedó escuchando en {HUELLA_HOST}:{HUELLA_PORT}.",
    }


# ============================================================
# COMUNICACIÓN SOCKET
# ============================================================

def _normalizar_respuesta(user_raw: str) -> dict[str, Any]:
    user_raw_limpio = user_raw.replace("?", "ñ")
    user_list = [item.strip().replace("?", "ñ") for item in user_raw.split(",")]
    codigo_usuario = user_list[0] if user_list and user_list[0] else ""

    if not codigo_usuario:
        return {
            "ok": False,
            "modo": "REAL",
            "mensaje": "El lector respondió, pero no devolvió código de usuario.",
            "raw": user_raw_limpio,
            "datos": user_list,
        }

    return {
        "ok": True,
        "modo": "REAL",
        "codigo_usuario": codigo_usuario,
        "raw": user_raw_limpio,
        "datos": user_list,
        "fecha_identificacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mensaje": "Huella real leída correctamente desde EnrollmentSample CS.exe.",
    }


def _enviar_comando_socket(comando: str) -> dict[str, Any]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.settimeout(HUELLA_TIMEOUT_SEGUNDOS)
            client.connect((HUELLA_HOST, HUELLA_PORT))
            client.sendall(comando.encode("utf-8"))
            response = client.recv(4096)

        user_raw = response.decode("utf-8", errors="replace").strip()
        respuesta = _normalizar_respuesta(user_raw)
        respuesta["comando_enviado_repr"] = repr(comando)
        return respuesta

    except socket.timeout:
        return {
            "ok": False,
            "modo": "REAL",
            "mensaje": "Tiempo de espera agotado leyendo huella. Verifique lector/EnrollmentSample CS.exe.",
            "comando_enviado_repr": repr(comando),
        }
    except ConnectionRefusedError:
        return {
            "ok": False,
            "modo": "REAL",
            "mensaje": f"No se pudo conectar a {HUELLA_HOST}:{HUELLA_PORT}. El exe no está escuchando.",
            "comando_enviado_repr": repr(comando),
        }
    except ConnectionResetError as e:
        return {
            "ok": False,
            "modo": "REAL",
            "mensaje": f"El .exe aceptó la conexión pero la cerró antes de responder: {e}",
            "comando_enviado_repr": repr(comando),
            "tipo_error": "ConnectionResetError",
        }
    except Exception as e:
        return {
            "ok": False,
            "modo": "REAL",
            "mensaje": f"Error comunicando con EnrollmentSample CS.exe: {e}",
            "comando_enviado_repr": repr(comando),
            "tipo_error": type(e).__name__,
        }


def _identificar_real() -> dict[str, Any]:
    """
    Identificación real robusta.
    - Reinicia el .exe antes de leer, para imitar el flujo PyQt original.
    - Prueba variantes de comando si el socket se corta.
    """
    intentos: list[dict[str, Any]] = []

    for idx, comando in enumerate(COMANDOS_PRUEBA, start=1):
        preparacion = _preparar_exe_para_lectura(
            forzar_reinicio=HUELLA_REINICIAR_EXE_ANTES_LECTURA or idx > 1
        )

        if not preparacion.get("ok"):
            intentos.append({
                "intento": idx,
                "comando_repr": repr(comando),
                "preparacion_ok": bool(preparacion.get("ok", False)),
                "socket_escuchando": bool(preparacion.get("socket_escuchando", False)),
                "resultado_ok": False,
                "codigo_usuario": "",
                "raw": "",
                "mensaje": str(preparacion.get("mensaje", "No se pudo preparar el ejecutable.")),
            })
            continue

        resultado = _enviar_comando_socket(comando)
        intentos.append({
            "intento": idx,
            "comando_repr": repr(comando),
            "preparacion_ok": bool(preparacion.get("ok", False)),
            "socket_escuchando": bool(preparacion.get("socket_escuchando", False)),
            "resultado_ok": bool(resultado.get("ok", False)),
            "codigo_usuario": str(resultado.get("codigo_usuario", "")),
            "raw": str(resultado.get("raw", "")),
            "mensaje": str(resultado.get("mensaje", "")),
        })

        if resultado.get("ok"):
            resultado["intentos"] = intentos
            return resultado

        # Si el .exe cortó conexión, se reinicia en el siguiente ciclo.
        time.sleep(0.5)

    return {
        "ok": False,
        "modo": "REAL",
        "mensaje": "No se pudo leer la huella con ninguna variante de comando.",
        "intentos": intentos,
    }


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/api/huella/health")
def health_check():
    ruta_exe = _obtener_ruta_exe()
    escuchando = _socket_escuchando_sin_tocar()

    return {
        "ok": True,
        "servicio": "SmartFactory Huella Local Service",
        "version": "19.4.0",
        "modo": HUELLA_MODO,
        "host_socket": HUELLA_HOST,
        "port_socket": HUELLA_PORT,
        "comando": HUELLA_COMANDO,
        "socket_escuchando": escuchando,
        "exe_encontrado": ruta_exe is not None,
        "ruta_exe": str(ruta_exe) if ruta_exe else None,
        "reiniciar_exe_antes_lectura": HUELLA_REINICIAR_EXE_ANTES_LECTURA,
        "mensaje": "Servicio local de huella disponible. Health no abre conexión TCP al .exe.",
    }


@app.get("/api/huella/diagnostico")
def diagnostico_huella():
    ruta_exe = _obtener_ruta_exe()
    return {
        "ok": True,
        "version": "19.4.0",
        "modo": HUELLA_MODO,
        "host_socket": HUELLA_HOST,
        "port_socket": HUELLA_PORT,
        "comando_base": HUELLA_COMANDO,
        "comandos_prueba": [repr(c) for c in COMANDOS_PRUEBA],
        "socket_escuchando": _socket_escuchando_sin_tocar(),
        "exe_encontrado": ruta_exe is not None,
        "ruta_exe": str(ruta_exe) if ruta_exe else None,
        "nota": "Este endpoint no toca el socket; solo diagnostica configuración.",
    }


@app.post("/api/huella/reiniciar-exe")
def reiniciar_exe():
    cerrar = _matar_exe_enrollment()
    time.sleep(0.7)
    abrir = _abrir_exe()
    preparado = _preparar_exe_para_lectura(forzar_reinicio=False)
    return {
        "ok": preparado.get("ok", False),
        "cerrar": cerrar,
        "abrir": abrir,
        "preparado": preparado,
    }


@app.post("/api/huella/probar-comando")
def probar_comando(data: dict[str, Any] | None = None):
    """
    Prueba un comando puntual contra el .exe.
    Body opcional:
    {
        "comando": "enrollFingerPrint",
        "reiniciar_exe": true
    }
    """
    data = data or {}
    comando = str(data.get("comando") or HUELLA_COMANDO)
    reiniciar_exe = bool(data.get("reiniciar_exe", True))

    preparacion = _preparar_exe_para_lectura(forzar_reinicio=reiniciar_exe)
    if not preparacion.get("ok"):
        return {
            "ok": False,
            "mensaje": "No se pudo preparar EnrollmentSample CS.exe.",
            "preparacion": preparacion,
        }

    resultado = _enviar_comando_socket(comando)
    return {
        "ok": resultado.get("ok", False),
        "preparacion": preparacion,
        "resultado": resultado,
    }


@app.post("/api/huella/identificar")
def identificar_huella():
    """
    Endpoint principal de lectura de huella.

    v19.4:
    - Evita lecturas simultáneas.
    - Normaliza la respuesta para que FastAPI siempre pueda serializar JSON.
    - Mantiene detalle de diagnóstico, pero convertido a tipos simples.
    """
    if not LECTURA_HUELLA_LOCK.acquire(blocking=False):
        return {
            "ok": False,
            "modo": HUELLA_MODO,
            "mensaje": "Ya hay una lectura de huella en proceso en esta PC.",
            "codigo_usuario": "",
            "raw": "",
            "datos": [],
            "fecha_identificacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    try:
        if HUELLA_MODO == "SIMULACION":
            return {
                "ok": True,
                "modo": "SIMULACION",
                "codigo_usuario": HUELLA_USUARIO_SIMULADO,
                "fecha_identificacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mensaje": "Huella simulada leída correctamente.",
                "raw": HUELLA_USUARIO_SIMULADO,
                "datos": [HUELLA_USUARIO_SIMULADO],
            }

        resultado = _identificar_real()
        resultado_seguro = _respuesta_identificacion_segura(resultado)
        print("[HUELLA] Resultado seguro:", resultado_seguro)
        return resultado_seguro

    except Exception as e:
        print("[HUELLA] Error general en identificar_huella:", e)
        return {
            "ok": False,
            "modo": HUELLA_MODO,
            "mensaje": f"Error general leyendo huella: {e}",
            "codigo_usuario": "",
            "raw": "",
            "datos": [],
            "fecha_identificacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    finally:
        LECTURA_HUELLA_LOCK.release()
