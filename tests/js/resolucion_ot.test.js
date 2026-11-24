// Ejecutar con: node --test "tests/js/*.test.js"
const test = require("node:test");
const assert = require("node:assert/strict");
const { construirOpcionesOt } = require("../../static/js/resolucion_ot.js");

test("el Map conserva el orden recibido aunque los números estén desordenados", () => {
    const opciones = construirOpcionesOt([
        { numeroOt: 5184708, titulo: "Tapa" },
        { numeroOt: 5184702, titulo: "Tripa" },
        { numeroOt: 5184705, titulo: "Lomo" },
    ]);
    assert.ok(opciones instanceof Map);
    assert.deepEqual([...opciones.keys()], ["5184708", "5184702", "5184705"]);
});

test("la etiqueta es solo el título, sin número de OT", () => {
    const opciones = construirOpcionesOt([{ numeroOt: 5184702, titulo: "  Tripa  " }]);
    assert.equal(opciones.get("5184702"), "Tripa");
});

test("sin título la etiqueta es «OT n»", () => {
    const opciones = construirOpcionesOt([{ numeroOt: 5184705, titulo: null }, { numeroOt: 5184706, titulo: "  " }]);
    assert.equal(opciones.get("5184705"), "OT 5184705");
    assert.equal(opciones.get("5184706"), "OT 5184706");
});

test("títulos repetidos llevan el número; el resto, solo el título", () => {
    const opciones = construirOpcionesOt([
        { numeroOt: 5184702, titulo: "Tripa" },
        { numeroOt: 5184704, titulo: "Tapa" },
        { numeroOt: 5184707, titulo: "Tripa " },
    ]);
    assert.deepEqual([...opciones.values()], ["Tripa (OT 5184702)", "Tapa", "Tripa (OT 5184707)"]);
});

test("escapa <, >, & y comillas", () => {
    const opciones = construirOpcionesOt([{ numeroOt: 1, titulo: `<b>Tripa</b> & "lomo" 'x'` }]);
    assert.equal(opciones.get("1"), "&lt;b&gt;Tripa&lt;/b&gt; &amp; &quot;lomo&quot; &#39;x&#39;");
});

test("una entrada que no es lista lanza TypeError", () => {
    for (const valor of [null, undefined, "5184702", { numeroOt: 1 }]) {
        assert.throws(() => construirOpcionesOt(valor), TypeError);
    }
});
