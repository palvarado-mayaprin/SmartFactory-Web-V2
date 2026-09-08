from typing import Optional, Dict, Any

from db.conexion import dtbSmartFactory


def _limpiar_sql(valor: str) -> str:
    """
    Limpieza básica para mantener compatibilidad con la clase dtbSmartFactory actual,
    que en este proyecto recibe queries construidos como string.

    Nota futura: migrar a consultas parametrizadas o contraseñas con hash.
    """
    return str(valor or "").replace("'", "''").strip()


def validar_usuario_elevado(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Valida credenciales contra smartfactory.superusuarios.

    Compatibilidad con PyQt original:
    - Si existe registro, el tipo de usuario viene en la posición 8.
    - Valores esperados: ADMIN, SU, NO u otros según tabla.
    """
    username_limpio = _limpiar_sql(username)
    password_limpio = _limpiar_sql(password)

    if not username_limpio or not password_limpio:
        return None

    query = f"""
        SELECT *
        FROM smartfactory.superusuarios
        WHERE username = '{username_limpio}'
          AND password = '{password_limpio}'
        LIMIT 1
    """

    resultado = dtbSmartFactory(query).consultaSmartFactory()

    if not resultado:
        return None

    fila = resultado[0]
    tipo_usuario = "NO"

    if len(fila) > 8 and fila[8] is not None:
        tipo_usuario = str(fila[8]).strip().upper()

    # Se devuelven nombres si existen, sin depender rígidamente de las posiciones.
    # Esto evita romper si la tabla tiene más columnas de las necesarias.
    return {
        "username": username_limpio,
        "tipo_usuario": tipo_usuario,
        "puede_ver_marcajes": tipo_usuario in {"ADMIN", "SU"},
        "puede_ver_mqtt": tipo_usuario == "ADMIN",
        "puede_ver_admin": tipo_usuario == "ADMIN",
        "mensaje": "Usuario elevado validado correctamente.",
    }
