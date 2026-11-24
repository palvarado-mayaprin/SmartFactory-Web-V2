/*
 * Elección de OT al iniciar un marcaje (docs/ai/14-resolucion-ot.md, iteración 5).
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
 * Etiqueta HTML (escapada) de una OT: el título como texto principal y, debajo y más
 * pequeño, «OT n». Sin título: solo «OT n».
 * @param {{numeroOt: string|number, titulo?: string|null}} ot
 */
function etiquetaOt(ot) {
    const numero = `OT ${escaparHtmlOt(ot?.numeroOt)}`;
    const titulo = String(ot?.titulo ?? "").trim();
    return titulo ? `${escaparHtmlOt(titulo)}<br><small>${numero}</small>` : numero;
}

/**
 * Opciones para el `input: "radio"` de SweetAlert2. Se usa un Map y no un objeto porque
 * JavaScript reordena las claves numéricas y se perdería el orden por wo_seq del servidor.
 * @returns {Map<string, string>} String(numeroOt) → etiqueta HTML escapada, en el orden recibido.
 */
function construirOpcionesOt(ots) {
    if (!Array.isArray(ots)) {
        throw new TypeError("construirOpcionesOt espera una lista de OT.");
    }
    return new Map(ots.map((ot) => [String(ot.numeroOt), etiquetaOt(ot)]));
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = { etiquetaOt, construirOpcionesOt };
}
