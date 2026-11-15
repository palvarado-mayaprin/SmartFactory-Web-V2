/*
 * Validaciones puras del formulario de cierre (v20.24).
 * Sin efectos al cargar: se usa desde app.js y se prueba con `node --test "tests/js/*.test.js"`.
 */

// Máximo de INT con signo en MySQL (columna resumenmarcajes.pliegosIncorrectos).
const PLIEGOS_INCORRECTOS_MAX = 2147483647;

/**
 * Valida el texto del campo "Pliegos incorrectos".
 * Vacío = 0. Solo dígitos: rechaza negativos, decimales, exponentes y texto.
 * @returns {{ok: true, valor: number} | {ok: false, mensaje: string}}
 */
function validarPliegosIncorrectos(texto) {
    const valor = String(texto ?? "").trim();

    if (valor === "") {
        return { ok: true, valor: 0 };
    }

    if (!/^\d+$/.test(valor)) {
        return {
            ok: false,
            mensaje: "Pliegos incorrectos debe ser un número entero mayor o igual a 0, sin decimales."
        };
    }

    const numero = Number(valor);
    if (!Number.isSafeInteger(numero) || numero > PLIEGOS_INCORRECTOS_MAX) {
        return { ok: false, mensaje: "Pliegos incorrectos supera el máximo permitido." };
    }

    return { ok: true, valor: numero };
}

/** Escapa texto para insertarlo con innerHTML / html de SweetAlert. */
function escaparHtml(texto) {
    return String(texto ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = { validarPliegosIncorrectos, escaparHtml, PLIEGOS_INCORRECTOS_MAX };
}
