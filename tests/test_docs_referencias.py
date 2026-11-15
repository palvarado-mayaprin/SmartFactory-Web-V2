"""
Consistencia entre CLAUDE.md / docs/ai y el código.

Verifica que:
- existen los archivos citados como `ruta:línea`;
- las líneas citadas no superan la longitud del archivo;
- existen las funciones citadas como `ruta::función` o `modulo::función`;
- no hay enlaces .md rotos;
- todo R-xx / P-xx / M-xx citado está definido en una tabla.

No comprueba que una línea apunte a la instrucción correcta: eso exige revisión humana
(ver docs/ai/12-procedimiento-desarrollo.md §5). docs/ai/auditoria/ es histórico y no se valida.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = [ROOT / "CLAUDE.md", *sorted((ROOT / "docs" / "ai").glob("*.md"))]
SUBDIRS = ("", "services", "api", "db", "realtime", "models", "huella_local", "static/js", "templates")
SIN_VALIDAR = ("logs/", "readme/")  # archivos ignorados o históricos

REF_LINEA = re.compile(r"((?:\.\./)?[\w./-]+\.(?:py|js|html|bat|css|md|example)):(\d+)(?:-(\d+))?((?:,\s*\d+(?:-\d+)?)*)")
REF_FUNC = re.compile(r"((?:\.\./)?[\w./-]+\.py)::(\w+)")
REF_MODULO = re.compile(r"`(\w+)::(\w+)`")
ENLACE = re.compile(r"\]\(([^)#]+\.md)\)")
ID_USADO = re.compile(r"\b([RPM])-(\d{2})\b")
ID_DEFINIDO = re.compile(r"^\|\s*([RPM])-(\d{2})\s*\|", re.M)


def _resolver(ruta: str) -> Path | None:
    for base in (ROOT, ROOT / "docs" / "ai"):
        candidato = (base / ruta).resolve()
        if candidato.exists():
            return candidato
    for sub in SUBDIRS:
        candidato = ROOT / sub / ruta
        if candidato.exists():
            return candidato
    return None


def _define(archivo: Path, nombre: str) -> bool:
    texto = archivo.read_text(encoding="utf-8", errors="replace")
    return re.search(rf"^\s*(?:async\s+)?(?:def|class|function)\s+{nombre}\b|^{nombre}\s*=", texto, re.M) is not None


def _errores() -> list[str]:
    errores: list[str] = []
    definidos = {"R": set(), "P": set(), "M": set()}
    textos = {d: d.read_text(encoding="utf-8") for d in DOCS}
    for texto in textos.values():
        for tipo, num in ID_DEFINIDO.findall(texto):
            definidos[tipo].add(num)

    for doc, texto in textos.items():
        nombre = doc.relative_to(ROOT).as_posix()
        for m in REF_LINEA.finditer(texto):
            ruta = m.group(1)
            if ruta.startswith(SIN_VALIDAR):
                continue
            archivo = _resolver(ruta)
            if archivo is None:
                if not ruta.startswith("../"):  # ../src es externo al repo: se valida si existe
                    errores.append(f"{nombre}: no existe {ruta}")
                continue
            total = len(archivo.read_text(encoding="utf-8", errors="replace").splitlines())
            numeros = [int(m.group(2))] + ([int(m.group(3))] if m.group(3) else []) + [int(n) for n in re.findall(r"\d+", m.group(4) or "")]
            errores += [f"{nombre}: {ruta}:{n} > {total} líneas" for n in numeros if n > total]
        for m in REF_FUNC.finditer(texto):
            archivo = _resolver(m.group(1))
            if archivo is None and not m.group(1).startswith("../"):
                errores.append(f"{nombre}: no existe {m.group(1)}")
            elif archivo is not None and not _define(archivo, m.group(2)):
                errores.append(f"{nombre}: {m.group(2)} no está definida en {m.group(1)}")
        for modulo, funcion in REF_MODULO.findall(texto):
            archivo = _resolver(f"{modulo}.py")
            if archivo is not None and not _define(archivo, funcion):
                errores.append(f"{nombre}: {funcion} no está definida en {modulo}.py")
        for destino in ENLACE.findall(texto):
            if not (doc.parent / destino).resolve().exists():
                errores.append(f"{nombre}: enlace roto {destino}")
        for tipo, num in ID_USADO.findall(texto):
            if num not in definidos[tipo]:
                errores.append(f"{nombre}: {tipo}-{num} citado pero no definido")
    return sorted(set(errores))


def test_referencias_de_documentacion_validas():
    errores = _errores()
    assert not errores, "Referencias rotas en la documentación:\n" + "\n".join(errores)
