// Ejecutar con: node --test "tests/js/*.test.js"
const test = require("node:test");
const assert = require("node:assert/strict");
const { etiquetaOt, construirOpcionesOt } = require("../../static/js/resolucion_ot.js");

test("construirOpcionesOt conserva el orden recibido aunque los números estén desordenados", () => {
    const opciones = construirOpcionesOt([
        { numeroOt: "5184708", titulo: "Tapa" },
        { numeroOt: 5184702, titulo: "Tripa" },
        { numeroOt: "5184705", titulo: null },
    ]);
    assert.ok(opciones instanceof Map);
    assert.deepEqual([...opciones.keys()], ["5184708", "5184702", "5184705"]);
});

test("la etiqueta escapa el título", () => {
    assert.equal(
        etiquetaOt({ numeroOt: 5184702, titulo: "<b>Tripa</b> & lomo" }),
        "&lt;b&gt;Tripa&lt;/b&gt; &amp; lomo<br><small>OT 5184702</small>"
    );
});

test("sin título la etiqueta es «OT n»", () => {
    assert.equal(etiquetaOt({ numeroOt: 5184705, titulo: null }), "OT 5184705");
    assert.equal(etiquetaOt({ numeroOt: 5184705, titulo: "   " }), "OT 5184705");
});
