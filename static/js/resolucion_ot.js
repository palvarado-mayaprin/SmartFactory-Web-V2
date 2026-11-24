/*
 * Elección de OT al iniciar un marcaje (docs/ai/14-resolucion-ot.md, iteración 5; v20.25.1).
 * Lógica pura, sin efectos al cargar: se usa desde app.js y se prueba con
 * `node --test "tests/js/*.test.js"`. Requiere escaparHtml (cierre_validacion.js).
 */

function escaparHtmlOt(texto) {
    // En el navegador, escaparHtml es global (cierre_validacion.js se carga antes); en node, se importa.
    const escapar = typeof escaparHtml === "function"
        ? escaparHtml
        : require("./cierre_validacion.js").escaparHtml;
    return escapar(texto);
}

/**
 * Texto de una OT para el operario: solo la descripción (wo_title2). El número aparece
 * únicamente si no hay título («OT n») o si el título se repite en la lista («título (OT n)»).
 * Devuelve texto SIN escapar.
 * @param {{numeroOt: string|number, titulo?: string|null}} ot
 * @param {Set<string>} [repetidos] títulos que aparecen en más de una OT
 */
function textoOt(ot, repetidos = new Set()) {
    const numero = `OT ${ot?.numeroOt ?? ""}`;
    const titulo = String(ot?.titulo ?? "").trim();
    if (!titulo) {
        return numero;
    }
    return repetidos.has(titulo) ? `${titulo} (${numero})` : titulo;
}

/**
 * Opciones del `input: "select"` de SweetAlert2: String(numeroOt) → etiqueta escapada,
 * en el MISMO orden recibido (wo_seq del servidor). Es un Map porque un objeto reordenaría
 * las claves numéricas, y escapada porque SweetAlert2 inserta las etiquetas como HTML.
 * @returns {Map<string, string>}
 */
function construirOpcionesOt(ots) {
    if (!Array.isArray(ots)) {
        throw new TypeError("construirOpcionesOt espera una lista de OT.");
    }

    const vistos = new Set();
    const repetidos = new Set();
    for (const ot of ots) {
        const titulo = String(ot?.titulo ?? "").trim();
        if (titulo) {
            (vistos.has(titulo) ? repetidos : vistos).add(titulo);
        }
    }

    return new Map(ots.map((ot) => [String(ot.numeroOt), escaparHtmlOt(textoOt(ot, repetidos))]));
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = { textoOt, construirOpcionesOt };
}
