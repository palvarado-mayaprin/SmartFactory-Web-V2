import os
from pathlib import Path

# =========================================================
# SMARTFACTORY WEB - CONFIG PRODUCCIÓN
# =========================================================
# Esta versión carga banderas desde variables de entorno o desde .env.
# Se buscan archivos .env en:
# 1) carpeta actual desde donde se ejecuta uvicorn
# 2) carpeta del proyecto donde está config.py
# 3) carpeta padre del proyecto


def _cargar_env_si_existe():
    posibles_rutas = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]

    for ruta in posibles_rutas:
        if not ruta.exists():
            continue

        try:
            for linea in ruta.read_text(encoding="utf-8").splitlines():
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue

                clave, valor = linea.split("=", 1)
                clave = clave.strip()
                valor = valor.strip().strip('"').strip("'")

                # No sobreescribe variables ya definidas a nivel Windows/servicio.
                os.environ.setdefault(clave, valor)
        except Exception as error:
            print(f"No se pudo cargar .env desde {ruta}: {error}")


_cargar_env_si_existe()


def _flag_activa(nombre: str, default: str = "1") -> bool:
    valor = os.getenv(nombre, default)
    return str(valor).strip().lower() in ("1", "true", "yes", "on", "si", "sí")


# PRODUCCIÓN: por defecto quedan habilitadas en esta versión.
ENABLE_REAL_DB_WRITES = _flag_activa("SMARTFACTORY_ENABLE_REAL_DB_WRITES", "1")
ENABLE_REAL_MQTT_DB_WRITES = _flag_activa("SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES", "1")
ENABLE_REAL_MQTT_PUBLISH = _flag_activa("SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH", "1")

print("SMARTFACTORY FLAGS:")
print(f"  ENABLE_REAL_DB_WRITES={ENABLE_REAL_DB_WRITES}")
print(f"  ENABLE_REAL_MQTT_DB_WRITES={ENABLE_REAL_MQTT_DB_WRITES}")
print(f"  ENABLE_REAL_MQTT_PUBLISH={ENABLE_REAL_MQTT_PUBLISH}")
