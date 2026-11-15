// Ejecutar con: node --test "tests/js/*.test.js"
const test = require("node:test");
const assert = require("node:assert/strict");
const { validarPliegosIncorrectos, escaparHtml } = require("../../static/js/cierre_validacion.js");

test("acepta enteros no negativos y vacío como 0", () => {
    assert.deepEqual(validarPliegosIncorrectos("0"), { ok: true, valor: 0 });
    assert.deepEqual(validarPliegosIncorrectos(" 25 "), { ok: true, valor: 25 });
    assert.deepEqual(validarPliegosIncorrectos(""), { ok: true, valor: 0 });
    assert.deepEqual(validarPliegosIncorrectos(undefined), { ok: true, valor: 0 });
    assert.deepEqual(validarPliegosIncorrectos("2147483647"), { ok: true, valor: 2147483647 });
});

test("rechaza negativos, decimales, exponentes, texto y desbordes", () => {
    for (const valor of ["-1", "1.5", "1,5", "1e3", "abc", "+3", "2147483648", "99999999999999999999"]) {
        assert.equal(validarPliegosIncorrectos(valor).ok, false, valor);
    }
});

test("escaparHtml neutraliza etiquetas", () => {
    assert.equal(escaparHtml("<b>1</b>&\"'"), "&lt;b&gt;1&lt;/b&gt;&amp;&quot;&#39;");
});
