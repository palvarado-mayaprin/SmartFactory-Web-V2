let usuarioActual = null;
let ordenActual = null;
let recursoActual = null;
let actividadesActuales = [];
let ultimaSimulacionMarcaje = null;
let marcajeActivoUsuario = null;
let relevoMtPendiente = null;
let socketMarcajes = null;
let escrituraRealHabilitada = false;
let publicacionMqttRealHabilitada = false;
let usuarioElevadoActual = null;
let tipoUsuarioElevadoActual = "NO";

function log(mensaje, esError = false) {
    const logEventos = document.getElementById("logEventos");
    const linea = document.createElement("div");
    linea.className = esError ? "log-line log-error" : "log-line";
    linea.textContent = `[${new Date().toLocaleTimeString()}] ${mensaje}`;
    logEventos.prepend(linea);
}

function activarPaso(paso) {
    document.getElementById("stepUsuario").classList.remove("active");
    document.getElementById("stepOp").classList.remove("active");
    document.getElementById("stepActividad").classList.remove("active");

    if (paso === 1) document.getElementById("stepUsuario").classList.add("active");
    if (paso === 2) document.getElementById("stepOp").classList.add("active");
    if (paso === 3) document.getElementById("stepActividad").classList.add("active");
}


function cancelarFlujoOperativo() {
    window.location.reload();
}

function construirUrlWebSocket(ruta) {
    const protocolo = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocolo}//${window.location.host}${ruta}`;
}

async function revisarBackend() {
    try {
        const respuesta = await fetch("/api/health");
        const datos = await respuesta.json();
        document.getElementById("estadoSistema").textContent = datos.mensaje;
        log("Backend conectado correctamente.");
    } catch (error) {
        document.getElementById("estadoSistema").textContent = "Backend no disponible";
        log("No se pudo conectar con el backend.", true);
    }
}


async function revisarServicioHuellaLocal() {
    const estado = document.getElementById("estadoHuellaLocal");

    if (!estado) {
        return;
    }

    try {
        const respuesta = await fetch("http://127.0.0.1:9001/api/huella/health");
        const datos = await respuesta.json();

        if (datos.ok) {
            estado.textContent = "Servicio local de huella conectado";
            estado.classList.remove("status-error");
            estado.classList.add("status-ok");
            log("Servicio local de huella conectado.");
        } else {
            throw new Error("Respuesta inválida del servicio local de huella.");
        }
    } catch (error) {
        estado.textContent = "Servicio local de huella no disponible";
        estado.classList.remove("status-ok");
        estado.classList.add("status-error");
        log("Servicio local de huella no disponible. Puede usar identificación manual mientras tanto.", true);
    }
}

async function identificarConHuellaLocal() {
    try {
        log("Solicitando lectura de huella al servicio local...");

        const respuestaHuella = await fetch("http://127.0.0.1:9001/api/huella/identificar", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            }
        });

        const lectura = await respuestaHuella.json();

        if (!respuestaHuella.ok || !lectura.ok) {
            throw new Error(lectura.detail || lectura.mensaje || "No se pudo identificar la huella.");
        }

        document.getElementById("codigoUsuario").value = lectura.codigo_usuario;
        log(`Huella recibida en modo ${lectura.modo}. Usuario detectado: ${lectura.codigo_usuario}`);

        await identificarUsuario();
    } catch (error) {
        log(`Error leyendo huella local: ${error.message}`, true);
        alert("No se pudo conectar con el servicio local de huella. Verifique que esté abierto en esta PC.");
    }
}

async function postJson(url, data) {
    const respuesta = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(data)
    });

    const contenido = await respuesta.json();

    if (!respuesta.ok) {
        let mensaje = contenido.detail || "Error en la solicitud";
        if (typeof mensaje === "object") {
            mensaje = mensaje.mensaje || JSON.stringify(mensaje, null, 2);
        }
        throw new Error(mensaje);
    }

    return contenido;
}

async function identificarUsuario() {
    const codigoUsuario = document.getElementById("codigoUsuario").value.trim();

    if (!codigoUsuario) {
        log("Debe ingresar un código de usuario.", true);

        await Swal.fire({
            icon: "warning",
            title: "Código requerido",
            text: "Debe ingresar un código de usuario.",
            confirmButtonText: "Entendido"
        });

        return;
    }

    try {
        log(`Identificando usuario ${codigoUsuario}...`);

        const datos = await postJson("/api/usuario/identificar-prueba", {
            codigo_usuario: codigoUsuario
        });

        usuarioActual = datos.usuario;
        const nombreUsuario = usuarioActual.username || usuarioActual.code || "usuario";

        document.getElementById("infoUsuario").innerHTML = `
            <strong>Usuario:</strong> ${usuarioActual.username}<br>
            <strong>Código:</strong> ${usuarioActual.code}<br>
            <strong>Recurso:</strong> ${usuarioActual.resource || "Sin recurso"}
        `;

        marcajeActivoUsuario = datos.marcaje_activo || null;

        if (marcajeActivoUsuario) {
            await Swal.fire({
                icon: "info",
                title: `Bienvenido/a ${nombreUsuario}`,
                text: "Tienes un marcaje activo. Por favor selecciona cómo deseas cerrar la actividad.",
                confirmButtonText: "Continuar"
            });

            mostrarPanelCierreMarcajeUsuario(marcajeActivoUsuario);
            document.getElementById("cardOp").classList.add("hidden");
            document.getElementById("cardActividad").classList.add("hidden");
            document.getElementById("cardSimulacion")?.classList.add("hidden");
            activarPaso(1);
            log("Usuario identificado correctamente. Tiene marcaje activo; se bloquea ingreso de nueva OP.", true);
            return;
        }

        document.getElementById("cardCerrarMarcajeUsuario").classList.add("hidden");

        if (relevoMtPendiente) {
            await Swal.fire({
                icon: "success",
                title: `Bienvenido/a ${nombreUsuario}`,
                text: "Existe un relevo MT pendiente. El marcaje de relevo se abrirá automáticamente.",
                confirmButtonText: "Continuar"
            });

            log("Usuario identificado correctamente. Ejecutando relevo MT automático.");
            mostrarPanelRelevoMt(relevoMtPendiente, usuarioActual);
            activarPaso(1);
            await iniciarRelevoMtAutomatico({ confirmar: false });
            return;
        }

        document.getElementById("cardOp").classList.remove("hidden");
        activarPaso(2);
        document.getElementById("numOp").focus();

        await Swal.fire({
            icon: "success",
            title: `Bienvenido/a ${nombreUsuario}`,
            text: "Por favor ingresa orden a trabajar",
            confirmButtonText: "Continuar"
        });

        log("Usuario identificado correctamente. No tiene marcaje activo; puede ingresar OP.");

    } catch (error) {
        console.error(error);

        const mensajeError = error?.detail || error?.message || String(error);
        log(mensajeError, true);

        if (
            mensajeError.includes("Usuario no encontrado") ||
            mensajeError.includes("descontinuado")
        ) {
            await Swal.fire({
                icon: "error",
                title: "Usuario no encontrado o descontinuado",
                text: "Por favor verifica la huella o contacta a un administrador.",
                confirmButtonText: "Entendido"
            });
        } else {
            await Swal.fire({
                icon: "error",
                title: "Error al identificar usuario",
                text: mensajeError || "No se pudo completar la identificación.",
                confirmButtonText: "Entendido"
            });
        }
    }
}

function mostrarPanelCierreMarcajeUsuario(marcaje) {
    const card = document.getElementById("cardCerrarMarcajeUsuario");
    const info = document.getElementById("infoMarcajeActivoUsuario");

    if (!card || !info) {
        log("No se encontró el panel de cierre de marcaje activo.", true);
        return;
    }

    info.innerHTML = `
        <strong>Trabajador:</strong> ${marcaje.username || marcaje.codigo_usuario || "Sin usuario"}<br>
        <strong>OP:</strong> ${marcaje.numOp || "Sin OP"}<br>
        <strong>Recurso:</strong> ${marcaje.recurso || "Sin recurso"}<br>
        <strong>Actividad:</strong> ${marcaje.actividad || "Sin actividad"}<br>
        <strong>Topic:</strong> ${marcaje.topic || "Sin topic"}<br>
        <strong>Modo:</strong> ${marcaje.modo || "No especificado"}
    `;

    card.classList.remove("hidden");
}

async function cerrarMarcajeActivoDelUsuario() {
    // Compatibilidad con versiones anteriores: el cierre ahora usa tipo FINAL/MD/MT
    // y se ejecuta por ejecutarCierreRealMarcajeActivoDelUsuario().
    return ejecutarCierreRealMarcajeActivoDelUsuario();
}


async function simularCierreMarcajeActivoDelUsuario() {
    // Compatibilidad con versiones anteriores: ya no existe etapa de simulación.
    return ejecutarCierreRealMarcajeActivoDelUsuario();
}


function actividadEsArreglo(codigoActividad) {
    return String(codigoActividad || "").toUpperCase().includes("ARR");
}

async function prepararTirajeMismaOrdenDespuesArreglo(contexto) {
    if (!contexto?.usuario?.code || !contexto?.numOp || !contexto?.recurso) {
        log("No se pudo reconstruir el contexto del arreglo cerrado para aperturar tiraje.", true);
        return;
    }

    const confirmacion = await Swal.fire({
        icon: "question",
        title: "¿Desea aperturar tiraje de esta misma orden?",
        text: `OP ${contexto.numOp} · Recurso ${contexto.recurso}`,
        showCancelButton: true,
        confirmButtonText: "Sí",
        cancelButtonText: "No",
        reverseButtons: true
    });

    if (!confirmacion.isConfirmed) {
        log("Apertura de tiraje cancelada por el usuario.");
        return;
    }

    try {
        // Se heredan únicamente usuario, OP y recurso. La OP y sus actividades
        // se reconstruyen nuevamente usando los endpoints normales del flujo.
        usuarioActual = contexto.usuario;
        document.getElementById("codigoUsuario").value = usuarioActual.code;
        document.getElementById("infoUsuario").innerHTML = `
            <strong>Usuario:</strong> ${usuarioActual.username || usuarioActual.code}<br>
            <strong>Código:</strong> ${usuarioActual.code}<br>
            <strong>Recurso:</strong> ${usuarioActual.resource || "Sin recurso"}
        `;

        const datos = await postJson("/api/op/buscar", {
            num_op: contexto.numOp,
            codigo_usuario: usuarioActual.code
        });

        ordenActual = datos.orden;

        const recursosDisponibles = Array.isArray(datos.recursos) ? datos.recursos : [];
        const recursoHeredadoExiste = recursosDisponibles.some(recurso => {
            const codigo = typeof recurso === "string" ? recurso : recurso.codigo;
            return String(codigo || "") === String(contexto.recurso);
        });

        if (!recursoHeredadoExiste) {
            ordenActual = null;
            recursoActual = null;
            actividadesActuales = [];

            document.getElementById("cardActividad")?.classList.add("hidden");
            document.getElementById("cardOp")?.classList.remove("hidden");
            document.getElementById("numOp").value = contexto.numOp;
            activarPaso(2);

            await Swal.fire({
                icon: "warning",
                title: "Recurso no disponible",
                text: `El recurso ${contexto.recurso} del arreglo finalizado ya no está disponible para esta orden. Puede continuar utilizando el flujo normal de búsqueda de OP.`,
                confirmButtonText: "Entendido"
            });
            log(`El recurso heredado ${contexto.recurso} no está disponible para la OP ${contexto.numOp}.`, true);
            return;
        }

        recursoActual = contexto.recurso;

        document.getElementById("infoOrden").innerHTML = `
            <strong>OP:</strong> ${ordenActual.num_op}<br>
            <strong>OT:</strong> ${ordenActual.num_ot}<br>
            <strong>Descripción:</strong> ${ordenActual.descripcion}<br>
            <strong>Cantidad:</strong> ${ordenActual.cantidad}<br>
            <strong>Recurso sugerido:</strong> ${contexto.recurso}
        `;

        document.getElementById("cardOp")?.classList.remove("hidden");
        document.getElementById("numOp").value = contexto.numOp;
        document.getElementById("cardActividad")?.classList.remove("hidden");
        prepararRecursos(recursosDisponibles, contexto.recurso);
        activarPaso(3);

        const datosActividades = await postJson("/api/actividades/recurso", {
            num_ot: ordenActual.num_ot,
            recurso: contexto.recurso
        });

        renderActividades(datosActividades.actividades);
        log(`Tiraje preparado para OP ${contexto.numOp} en recurso ${contexto.recurso}. Seleccione la actividad a realizar.`);
    } catch (error) {
        log(`No se pudo preparar el tiraje de la misma orden: ${error.message}`, true);

        // El cierre FINAL ya terminó correctamente. Ante cualquier error en este
        // flujo posterior no se crea un nuevo marcaje ni se altera el cierre.
        ordenActual = null;
        recursoActual = null;
        actividadesActuales = [];
        document.getElementById("cardActividad")?.classList.add("hidden");
        document.getElementById("cardOp")?.classList.remove("hidden");
        document.getElementById("numOp").value = contexto.numOp;
        activarPaso(2);

        await Swal.fire({
            icon: "error",
            title: "No se pudo preparar el tiraje",
            text: `${error.message}. El cierre anterior fue completado y puede continuar utilizando el flujo normal.`,
            confirmButtonText: "Entendido"
        });
    }
}

async function ejecutarCierreRealMarcajeActivoDelUsuario() {
    if (!marcajeActivoUsuario) {
        log("No hay marcaje activo cargado para ejecutar cierre real.", true);
        return;
    }

    const tipoCierre = document.getElementById("tipoCierreMarcaje").value;
    const totalUsuario = document.getElementById("totalUsuarioCierre").value || 0;

    const confirmacionCierre = await Swal.fire({
        icon: "warning",
        title: "¿Está seguro de cerrar el marcaje?",
        html: `
            <strong>Tipo cierre:</strong> ${tipoCierre}<br>
            <strong>OP:</strong> ${marcajeActivoUsuario.numOp || "Sin OP"}<br>
            <strong>Actividad:</strong> ${marcajeActivoUsuario.actividad || "Sin actividad"}<br>
            <strong>Recurso:</strong> ${marcajeActivoUsuario.recurso || "Sin recurso"}<br><br>
            Al confirmar, se procesará el cierre real del marcaje.
        `,
        showCancelButton: true,
        confirmButtonText: "Sí, cerrar marcaje",
        cancelButtonText: "Cancelar",
        reverseButtons: true
    });

    if (!confirmacionCierre.isConfirmed) {
        log("Cierre de marcaje cancelado por el usuario.", true);
        return;
    }

    // Contexto mínimo para el flujo opcional posterior al cierre FINAL de un arreglo.
    // Se captura antes de limpiar el estado del marcaje y nunca se usa para MT/MD.
    const contextoArregloCerrado = {
        usuario: usuarioActual ? { ...usuarioActual } : null,
        numOp: marcajeActivoUsuario.numOp,
        recurso: marcajeActivoUsuario.recurso,
        actividad: marcajeActivoUsuario.actividad
    };

    try {
        log(`Ejecutando cierre real ${tipoCierre} para OP ${marcajeActivoUsuario.numOp}...`);

        const datos = await postJson("/api/marcajes/ejecutar-cierre-real", {
            marcaje: marcajeActivoUsuario,
            tipo_cierre: tipoCierre,
            total_usuario: totalUsuario
        });

        log(datos.mensaje || "Cierre real ejecutado correctamente.");

        await Swal.fire({
            icon: "success",
            title: "Cierre ejecutado",
            text: `Cierre ${tipoCierre} aplicado correctamente.`,
            confirmButtonText: "Entendido"
        });

        if (datos.marcajes) {
            renderMarcajesActivos(datos.marcajes);
        }

        marcajeActivoUsuario = null;
        usuarioActual = null;
        ordenActual = null;
        recursoActual = null;
        ultimaSimulacionMarcaje = null;

        const cardCerrar = document.getElementById("cardCerrarMarcajeUsuario");
        const cardSimulacionCierre = document.getElementById("cardSimulacionCierre");
        const cardOp = document.getElementById("cardOp");

        if (cardCerrar) cardCerrar.classList.add("hidden");
        if (cardSimulacionCierre) cardSimulacionCierre.classList.add("hidden");
        if (cardOp) cardOp.classList.add("hidden");

        document.getElementById("codigoUsuario").value = "";
        document.getElementById("codigoUsuario").focus();
        activarPaso(1);

        if (tipoCierre === "MT") {
            relevoMtPendiente = datos.relevo_pendiente || construirRelevoPendienteDesdeCierre(datos);
            mostrarPanelRelevoMt(relevoMtPendiente, null);
            log("Cierre MT realizado. Identifique inmediatamente al siguiente operario para abrir el relevo automático.", true);
        } else {
            relevoMtPendiente = null;
            ocultarPanelRelevoMt();
        }

        // Solo después de completar exitosamente TODO el cierre FINAL se ofrece
        // aperturar tiraje si el código de actividad contiene ARR (case-insensitive).
        if (tipoCierre === "FINAL" && actividadEsArreglo(contextoArregloCerrado.actividad)) {
            try {
                await prepararTirajeMismaOrdenDespuesArreglo(contextoArregloCerrado);
            } catch (errorPostCierre) {
                // El flujo de tiraje es posterior y opcional: nunca debe convertir
                // un cierre FINAL ya exitoso en un error de cierre para el usuario.
                log(`Cierre FINAL completado, pero no se pudo abrir el flujo opcional de tiraje: ${errorPostCierre.message}`, true);
            }
        }
    } catch (error) {
        log(error.message, true);
        alert(error.message);
    }
}

function renderSimulacionCierre(simulacion) {
    // v20.5: la pantalla de simulación de cierre fue retirada.
    // Se conserva la función únicamente para compatibilidad con referencias antiguas.
    return;
}


function construirRelevoPendienteDesdeCierre(datos) {
    const valores = datos.valores || {};
    const marcaje = datos.marcaje_cerrado || {};

    return {
        numOp: valores.numOp || marcaje.numOp,
        num_ot: `${valores.numOp || marcaje.numOp}01`,
        descrip: marcaje.descrip || marcaje.descripcion || "RELEVO MT",
        cantidad: valores.cantidadcot || marcaje.cantidad || 0,
        cantidadcot: valores.cantidadcot || marcaje.cantidad || 0,
        recurso: valores.recurso || marcaje.recurso,
        actividad: valores.actividad || marcaje.actividad,
        actividad_nombre: marcaje.actividad_nombre || valores.actividad || marcaje.actividad,
        topic: valores.topic || marcaje.topic,
        mac: valores.mac || marcaje.mac,
        operario_anterior: valores.username || marcaje.username,
        tipo_cierre_origen: "MT",
        tiempofinal_anterior: valores.tiempofinal || null
    };
}

function mostrarPanelRelevoMt(relevo, usuarioEntrante) {
    const card = document.getElementById("cardRelevoMt");
    const info = document.getElementById("infoRelevoMt");

    if (!card || !info || !relevo) {
        return;
    }

    const usuarioTexto = usuarioEntrante
        ? `<br><strong>Operario entrante:</strong> ${usuarioEntrante.username || usuarioEntrante.code}`
        : "<br><strong>Operario entrante:</strong> pendiente de identificación";

    info.innerHTML = `
        <strong>Relevo MT pendiente</strong><br>
        <strong>OP:</strong> ${relevo.numOp || "Sin OP"}<br>
        <strong>Recurso:</strong> ${relevo.recurso || "Sin recurso"}<br>
        <strong>Actividad:</strong> ${relevo.actividad || "Sin actividad"}<br>
        <strong>MAC:</strong> ${relevo.mac || "Sin MAC"}<br>
        <strong>Operario anterior:</strong> ${relevo.operario_anterior || "No especificado"}
        ${usuarioTexto}
    `;

    card.classList.remove("hidden");
    document.getElementById("cardOp")?.classList.add("hidden");
    document.getElementById("cardActividad")?.classList.add("hidden");
    document.getElementById("cardSimulacion")?.classList.add("hidden");
}

function ocultarPanelRelevoMt() {
    const card = document.getElementById("cardRelevoMt");
    if (card) card.classList.add("hidden");
}

function cancelarRelevoMt() {
    relevoMtPendiente = null;
    ocultarPanelRelevoMt();
    document.getElementById("cardOp")?.classList.remove("hidden");
    activarPaso(2);
    log("Relevo MT cancelado. Puede continuar con ingreso manual de OP.", true);
}

async function iniciarRelevoMtAutomatico(opciones = {}) {
    if (!relevoMtPendiente) {
        log("No existe relevo MT pendiente.", true);
        return;
    }

    if (!usuarioActual) {
        log("Primero identifique al operario entrante.", true);
        return;
    }
    if (opciones.confirmar === true) {
        const confirmar = confirm(
            "Se abrirá un nuevo marcaje para el operario entrante usando la misma OP, máquina y actividad.\n\n" +
            `Operario entrante: ${usuarioActual.username || usuarioActual.code}\n` +
            `OP: ${relevoMtPendiente.numOp}\n` +
            `Recurso: ${relevoMtPendiente.recurso}\n` +
            `Actividad: ${relevoMtPendiente.actividad}\n\n` +
            "¿Desea iniciar el marcaje de relevo?"
        );

        if (!confirmar) return;
    }

    try {
        log(`Iniciando relevo MT para ${usuarioActual.code} en OP ${relevoMtPendiente.numOp}...`);

        const datos = await postJson("/api/marcajes/iniciar-relevo-mt-real", {
            relevo: relevoMtPendiente,
            codigo_usuario: usuarioActual.code
        });

        renderMarcajesActivos(datos.marcajes || []);
        log(datos.mensaje || "Marcaje de relevo MT iniciado correctamente.");

        if (datos.resultado_mqtt_inicio) {
            const r = datos.resultado_mqtt_inicio;
            log(`MQTT inicio relevo: ${r.mensaje || "sin mensaje"}${r.topic ? " · " + r.topic : ""}`, !r.ok);
        }

        relevoMtPendiente = null;
        ocultarPanelRelevoMt();
        document.getElementById("cardOp")?.classList.add("hidden");
        document.getElementById("codigoUsuario").value = "";
        document.getElementById("codigoUsuario").focus();
        activarPaso(1);

    } catch (error) {
        log(error.message, true);
        alert(error.message);
    }
}

function cambiarUsuarioDesdeMarcajeActivo() {
    marcajeActivoUsuario = null;
    usuarioActual = null;
    ordenActual = null;
    recursoActual = null;
    ultimaSimulacionMarcaje = null;

    document.getElementById("cardCerrarMarcajeUsuario").classList.add("hidden");
    document.getElementById("cardOp").classList.add("hidden");
    document.getElementById("cardActividad").classList.add("hidden");
    document.getElementById("cardSimulacion")?.classList.add("hidden");
    document.getElementById("codigoUsuario").value = "";
    document.getElementById("codigoUsuario").focus();
    activarPaso(1);
    log("Listo para identificar otro usuario.");
}


async function SeleccionarRecurso() {
    if (!usuarioActual) {
        log("Primero debe identificar un usuario.", true);
        return;
    }

    const select = document.getElementById("ImproductivoSelect");

    const actividad = select.value;

    if (!actividad) {
        log("Debe seleccionar una actividad.", true);
        return;
    }

    try {
        log(`Buscando recursos existentes ...`);

        const datos = await postJson("/api/op/buscarRecursosExistentes", {
            codigo_usuario: usuarioActual.code
        });

        ordenActual = "12345";

        prepararRecursosImproductivo(datos.recursos);

        log("recursos encontrados correctamente.");
    } catch (error) {
        log(error.message, true);
    }
}


function prepararRecursosImproductivo(recursos) {
    const contenedor = document.getElementById("selectorRecursoTiempoImproductivo");
    const select = document.getElementById("recursoSelectImproductivo");
    select.innerHTML = "";

    if (!recursos || recursos.length === 0) {
        contenedor.classList.add("hidden");
        return;
    }

    recursos.forEach(recurso => {
        const codigo = typeof recurso === "string" ? recurso : recurso.codigo;
        const nombre = typeof recurso === "string" ? recurso : recurso.nombre;

        const option = document.createElement("option");
        option.value = codigo;
        option.textContent = `${codigo} - ${nombre}`;

        select.appendChild(option);
    });

    contenedor.classList.remove("hidden");
}


async function marcajeTiempoImproductivo() {

    if (!usuarioActual) {
        log("Debe identificar usuario antes de seleccionar actividad.", true);
        return;
    }

    const select = document.getElementById("ImproductivoSelect");

    const actividad = select.value;
    const descripActividad = select.options[select.selectedIndex].text;

    const selectRecurso = document.getElementById("recursoSelectImproductivo");
    const recurso = selectRecurso.value;
    const recursoTextoCompleto = selectRecurso.options[selectRecurso.selectedIndex].text;

    const confirmacionInicio = await Swal.fire({
        icon: "question",
        title: "¿Está seguro de iniciar el marcaje?",
        html: `
            <strong>Actividad:</strong> ${descripActividad}<br>
            <strong>Recurso:</strong> ${recursoTextoCompleto}<br><br>
            Al confirmar, se creará el marcaje real y se enviará MQTT de inicio.
        `,
        showCancelButton: true,
        confirmButtonText: "Sí, iniciar marcaje",
        cancelButtonText: "Cancelar",
        reverseButtons: true
    });

    if (!confirmacionInicio.isConfirmed) {
        log("Inicio de marcaje cancelado por el usuario.", true);
        return;
    }

    try {
        log(`Iniciando marcaje real: ${actividad} - ${descripActividad}...`);

        const datos = await postJson("/api/marcajes/iniciar-improductivo", {
            num_op: "12345",
            descripcion: "Tiempo Improductivo",
            cantidad: "12345",
            recurso: recurso,
            actividad: actividad,
            actividad_nombre: descripActividad,
            codigo_usuario: usuarioActual.code
        });

        renderMarcajesActivos(datos.marcajes || []);
        log(datos.mensaje || "Marcaje real iniciado correctamente.");

        if (datos.resultado_mqtt_inicio) {
            const r = datos.resultado_mqtt_inicio;
            log(`MQTT inicio: ${r.mensaje || "sin mensaje"}${r.topic ? " · " + r.topic : ""}`, !r.ok);
        }

        await Swal.fire({
            icon: "success",
            title: "Marcaje iniciado",
            text: `OP ${ordenActual} · ${descripActividad}`,
            confirmButtonText: "Entendido"
        });

        usuarioActual = null;
        ordenActual = null;
        recursoActual = null;
        ultimaSimulacionMarcaje = null;
        marcajeActivoUsuario = null;

        document.getElementById("cardOp")?.classList.add("hidden");
        document.getElementById("cardActividad")?.classList.add("hidden");
        document.getElementById("cardCerrarMarcajeUsuario")?.classList.add("hidden");
        document.getElementById("numOp").value = "";
        document.getElementById("codigoUsuario").value = "";
        document.getElementById("codigoUsuario").focus();
        activarPaso(1);

    } catch (error) {
        log(error.message, true);
        await Swal.fire({
            icon: "error",
            title: "No se pudo iniciar el marcaje",
            text: error.message,
            confirmButtonText: "Entendido"
        });
    }

}




async function buscarOp() {
    if (!usuarioActual) {
        log("Primero debe identificar un usuario.", true);
        return;
    }

    const numOp = document.getElementById("numOp").value.trim();

    if (!numOp) {
        log("Debe ingresar una OP.", true);
        return;
    }

    try {
        log(`Buscando OP ${numOp}...`);

        const datos = await postJson("/api/op/buscar", {
            num_op: numOp,
            codigo_usuario: usuarioActual.code
        });

        ordenActual = datos.orden;

        const recursoSugerido = datos.recurso_usuario || "No detectado";

        document.getElementById("infoOrden").innerHTML = `
            <strong>OP:</strong> ${ordenActual.num_op}<br>
            <strong>OT:</strong> ${ordenActual.num_ot}<br>
            <strong>Descripción:</strong> ${ordenActual.descripcion}<br>
            <strong>Cantidad:</strong> ${ordenActual.cantidad}<br>
            <strong>Recurso sugerido:</strong> ${recursoSugerido}
        `;

        document.getElementById("cardActividad").classList.remove("hidden");
        activarPaso(3);

        prepararRecursos(datos.recursos, datos.recurso_usuario);
        renderActividades(datos.actividades_sugeridas);

        log("OP encontrada correctamente.");
    } catch (error) {
        log(error.message, true);
    }
}

function prepararRecursos(recursos, recursoUsuario) {
    recursoActual = recursoUsuario || null;
    const contenedor = document.getElementById("selectorRecurso");
    const select = document.getElementById("recursoSelect");
    select.innerHTML = "";

    if (!recursos || recursos.length === 0) {
        contenedor.classList.add("hidden");
        return;
    }

    recursos.forEach(recurso => {
        const codigo = typeof recurso === "string" ? recurso : recurso.codigo;
        const nombre = typeof recurso === "string" ? recurso : recurso.nombre;

        const option = document.createElement("option");
        option.value = codigo;
        option.textContent = `${codigo} - ${nombre}`;

        if (codigo === recursoUsuario) {
            option.selected = true;
            recursoActual = codigo;
        }

        select.appendChild(option);
    });

    contenedor.classList.remove("hidden");
}

async function cargarActividadesPorRecurso() {
    if (!ordenActual) return;

    const recurso = document.getElementById("recursoSelect").value;
    recursoActual = recurso;

    try {
        log(`Cargando actividades para ${recurso}...`);

        const datos = await postJson("/api/actividades/recurso", {
            num_ot: ordenActual.num_ot,
            recurso: recurso
        });

        renderActividades(datos.actividades);
    } catch (error) {
        log(error.message, true);
    }
}

function renderActividades(actividades) {
    const contenedor = document.getElementById("actividades");
    contenedor.innerHTML = "";

    actividadesActuales = Array.isArray(actividades) ? actividades : [];

    if (!actividadesActuales || actividadesActuales.length === 0) {
        contenedor.innerHTML = `<div class="info-box">No se encontraron actividades cotizadas para este recurso. Puede agregar una actividad no cotizada con el botón superior.</div>`;
        return;
    }

    actividadesActuales.forEach(actividad => {
        const boton = document.createElement("button");
        boton.className = actividad.no_cotizada ? "activity-btn activity-extra" : "activity-btn";
        boton.innerHTML = `<strong>${actividad.nombre}</strong><br><small>${actividad.codigo}${actividad.no_cotizada ? " · No cotizada" : ""}</small>`;
        boton.onclick = () => seleccionarActividad(actividad);
        contenedor.appendChild(boton);
    });
}

async function abrirSelectorActividadNoCotizada() {
    if (!usuarioActual || !ordenActual) {
        log("Debe identificar usuario y buscar OP antes de agregar una actividad no cotizada.", true);
        return;
    }

    const recursoSeleccionado = recursoActual || document.getElementById("recursoSelect")?.value;

    if (!recursoSeleccionado) {
        log("Debe seleccionar un recurso antes de agregar una actividad no cotizada.", true);
        return;
    }

    try {
        log(`Consultando actividades no cotizadas para ${recursoSeleccionado}...`);

        const datos = await postJson("/api/actividades/no-cotizadas", {
            num_ot: ordenActual.num_ot,
            recurso: recursoSeleccionado
        });

        const actividadesNoCotizadas = datos.actividades || [];

        if (actividadesNoCotizadas.length === 0) {
            await Swal.fire({
                icon: "info",
                title: "Sin actividades adicionales",
                text: "No se encontraron actividades no cotizadas disponibles para este recurso.",
                confirmButtonText: "Entendido"
            });
            return;
        }

        const opciones = {};
        actividadesNoCotizadas.forEach((actividad, index) => {
            opciones[index] = `${actividad.nombre} (${actividad.codigo})`;
        });

        const seleccion = await Swal.fire({
            icon: "question",
            title: "Agregar actividad no cotizada",
            text: "Seleccione la actividad que desea agregar al marcaje.",
            input: "select",
            inputOptions: opciones,
            inputPlaceholder: "Seleccione una actividad",
            showCancelButton: true,
            confirmButtonText: "Agregar actividad",
            cancelButtonText: "Cancelar",
            customClass: {
                popup: "swal-actividad-popup",
                input: "swal-actividad-select"
            },
            inputValidator: (value) => {
                if (value === "") {
                    return "Debe seleccionar una actividad.";
                }
            }
        });

        if (!seleccion.isConfirmed) {
            log("Selección de actividad no cotizada cancelada por el usuario.", true);
            return;
        }

        const actividadSeleccionada = actividadesNoCotizadas[Number(seleccion.value)];

        if (!actividadSeleccionada) {
            log("No se pudo obtener la actividad seleccionada.", true);
            return;
        }

        actividadSeleccionada.no_cotizada = true;

        const yaExiste = actividadesActuales.some(a => String(a.codigo) === String(actividadSeleccionada.codigo));
        if (!yaExiste) {
            actividadesActuales.push(actividadSeleccionada);
            renderActividades(actividadesActuales);
        }

        await Swal.fire({
            icon: "success",
            title: "Actividad agregada",
            text: `${actividadSeleccionada.nombre} fue agregada a la lista de actividades disponibles.`,
            confirmButtonText: "Continuar"
        });

        log(`Actividad no cotizada agregada: ${actividadSeleccionada.codigo} - ${actividadSeleccionada.nombre}`);
    } catch (error) {
        log(error.message, true);
        await Swal.fire({
            icon: "error",
            title: "No se pudo cargar la actividad",
            text: error.message,
            confirmButtonText: "Entendido"
        });
    }
}

async function seleccionarActividad(actividad) {
    if (!usuarioActual || !ordenActual) {
        log("Debe identificar usuario y buscar OP antes de seleccionar actividad.", true);
        return;
    }

    const recursoSeleccionado = recursoActual || document.getElementById("recursoSelect")?.value;

    // Texto visible del recurso para confirmación operacional.
    // Se mantiene recursoSeleccionado como código interno para backend/BD/MQTT,
    // pero el Swal muestra el nombre completo que ve el operario en pantalla.
    const recursoSelect = document.getElementById("recursoSelect");
    const recursoTextoCompleto = recursoSelect?.selectedOptions?.[0]?.textContent || recursoSeleccionado || "Sin recurso";

    const confirmacionInicio = await Swal.fire({
        icon: "question",
        title: "¿Está seguro de iniciar el marcaje?",
        html: `
            <strong>OP:</strong> ${ordenActual.num_op}<br>
            <strong>Actividad:</strong> ${actividad.nombre}${actividad.no_cotizada ? " <em>(no cotizada)</em>" : ""}<br>
            <strong>Recurso:</strong> ${recursoTextoCompleto}<br><br>
            Al confirmar, se creará el marcaje real y se enviará MQTT de inicio.
        `,
        showCancelButton: true,
        confirmButtonText: "Sí, iniciar marcaje",
        cancelButtonText: "Cancelar",
        reverseButtons: true
    });

    if (!confirmacionInicio.isConfirmed) {
        log("Inicio de marcaje cancelado por el usuario.", true);
        return;
    }

    try {
        log(`Iniciando marcaje real: ${actividad.codigo} - ${actividad.nombre}...`);

        const datos = await postJson("/api/marcajes/iniciar-real-bd", {
            num_op: ordenActual.num_op,
            num_ot: ordenActual.num_ot,
            descripcion: ordenActual.descripcion,
            cantidad: ordenActual.cantidad,
            recurso: recursoSeleccionado,
            actividad: actividad.codigo,
            actividad_nombre: actividad.nombre,
            codigo_usuario: usuarioActual.code
        });

        renderMarcajesActivos(datos.marcajes || []);
        log(datos.mensaje || "Marcaje real iniciado correctamente.");

        if (datos.resultado_mqtt_inicio) {
            const r = datos.resultado_mqtt_inicio;
            log(`MQTT inicio: ${r.mensaje || "sin mensaje"}${r.topic ? " · " + r.topic : ""}`, !r.ok);
        }

        await Swal.fire({
            icon: "success",
            title: "Marcaje iniciado",
            text: `OP ${ordenActual.num_op} · ${actividad.nombre}`,
            confirmButtonText: "Entendido"
        });

        usuarioActual = null;
        ordenActual = null;
        recursoActual = null;
        ultimaSimulacionMarcaje = null;
        marcajeActivoUsuario = null;

        document.getElementById("cardOp")?.classList.add("hidden");
        document.getElementById("cardActividad")?.classList.add("hidden");
        document.getElementById("cardCerrarMarcajeUsuario")?.classList.add("hidden");
        document.getElementById("numOp").value = "";
        document.getElementById("codigoUsuario").value = "";
        document.getElementById("codigoUsuario").focus();
        activarPaso(1);

    } catch (error) {
        log(error.message, true);
        await Swal.fire({
            icon: "error",
            title: "No se pudo iniciar el marcaje",
            text: error.message,
            confirmButtonText: "Entendido"
        });
    }
}


function renderSimulacionMarcaje(simulacion) {
    // v20.5: la pantalla de simulación de inicio fue retirada.
    // Se conserva la función únicamente para compatibilidad con referencias antiguas.
    return;
}


function copiarTexto(idElemento) {
    const elemento = document.getElementById(idElemento);

    if (!elemento) {
        return;
    }

    navigator.clipboard.writeText(elemento.textContent || "")
        .then(() => log("Texto copiado al portapapeles."))
        .catch(() => log("No se pudo copiar el texto automáticamente.", true));
}


function conectarWebSocketMarcajes() {
    const estado = document.getElementById("wsEstado");

    try {
        socketMarcajes = new WebSocket(construirUrlWebSocket("/ws/marcajes"));

        socketMarcajes.onopen = () => {
            if (estado) {
                estado.textContent = "WS conectado";
                estado.classList.remove("ws-error");
                estado.classList.add("ws-ok");
            }
            log("WebSocket de marcajes conectado.");
        };

        socketMarcajes.onmessage = (event) => {
            const datos = JSON.parse(event.data);

            if (datos.tipo === "MARCAGES_ACTIVOS_ACTUALIZADOS") {
                renderMarcajesActivos(datos.marcajes || []);

                if (datos.mensaje) {
                    log(datos.mensaje);
                }
            }
        };

        socketMarcajes.onclose = () => {
            if (estado) {
                estado.textContent = "WS desconectado";
                estado.classList.remove("ws-ok");
                estado.classList.add("ws-error");
            }
            log("WebSocket de marcajes desconectado. Intentando reconectar...", true);
            setTimeout(conectarWebSocketMarcajes, 3000);
        };

        socketMarcajes.onerror = () => {
            if (estado) {
                estado.textContent = "WS error";
                estado.classList.remove("ws-ok");
                estado.classList.add("ws-error");
            }
        };
    } catch (error) {
        log(`No se pudo abrir WebSocket: ${error.message}`, true);
    }
}

function renderMarcajesActivos(marcajes) {
    const contenedor = document.getElementById("marcajesActivos");

    if (!contenedor) {
        return;
    }

    contenedor.innerHTML = "";

    if (!marcajes || marcajes.length === 0) {
        contenedor.innerHTML = `<div class="empty-live">Sin marcajes activos.</div>`;
        return;
    }

    marcajes.forEach(marcaje => {
        const tarjeta = document.createElement("div");
        tarjeta.className = "active-mark";
        tarjeta.innerHTML = `
            <strong>${marcaje.username} · ${marcaje.recurso}</strong>
            <span>OP: ${marcaje.numOp}</span>
            <span>Actividad: ${marcaje.actividad}</span>
            <span>Inicio: ${marcaje.fecha_inicio}</span>
            <span>MAC: ${marcaje.mac || "No detectada"}</span>
            <span>Conteo MQTT: ${marcaje.conteo_mqtt_actual ?? 0}</span>
            <span>Último delta: ${marcaje.delta_ultimo_mensaje ?? 0}</span>
            <span>Mensajes asociados: ${marcaje.mensajes_mqtt_asociados ?? 0}</span>
            <span>Último MQTT: ${marcaje.ultimo_mqtt_fecha_hora || "Sin datos"}</span>
            ${marcaje.ultima_advertencia_mqtt ? `<span class="mark-warning">${marcaje.ultima_advertencia_mqtt}</span>` : ""}
            <span>Modo: ${marcaje.modo}</span>

            <div class="mark-close-section mark-close-general">
                <span class="mark-close-title">Cierre general</span>
                <span class="mark-close-note">Solo el dueño del marcaje podrá cerrarlo con huella.</span>
                <button class="close-mark-btn" onclick="prepararCierreGeneralDesdeMarcajeActivo()">Preparar cierre</button>
            </div>

            <div class="mark-close-section mark-close-elevated su-admin-only permission-hidden">
                <span class="mark-close-title">Cierre SU / ADMIN</span>
                <span class="mark-close-note">Uso exclusivo para soporte cuando el operario no pueda cerrar.</span>
                <button class="close-mark-btn elevated-close-btn" onclick="prepararCierreDesdeMarcajeTexto('${encodeURIComponent(JSON.stringify(marcaje))}')">Preparar cierre</button>
            </div>
        `;
        contenedor.appendChild(tarjeta);
    });

    aplicarVisibilidadPorRol();
}

async function cargarMarcajesActivosIniciales() {
    try {
        // En v9 intentamos sincronizar primero desde BD. Si falla, usamos el estado en memoria.
        const datos = await postJson("/api/marcajes/sincronizar-desde-bd", {});
        renderMarcajesActivos(datos.marcajes || []);
        log(datos.mensaje || "Marcajes sincronizados desde BD.");
    } catch (error) {
        try {
            const respuesta = await fetch("/api/marcajes/activos-simulados");
            const datos = await respuesta.json();

            if (datos.ok) {
                renderMarcajesActivos(datos.marcajes || []);
            }
            log("No se pudo sincronizar desde BD. Se cargó estado temporal.", true);
        } catch (errorInterno) {
            log("No se pudieron cargar los marcajes activos.", true);
        }
    }
}

async function activarMarcajeSimulado() {
    log("La simulación de marcajes fue retirada en v20.5. Seleccionar una actividad inicia el marcaje real directamente.", true);
}

async function iniciarMarcajeRealBd() {
    log("El botón intermedio REAL BD fue retirado en v20.5. Seleccionar una actividad inicia el marcaje real directamente.", true);
}


async function sincronizarMarcajesDesdeBd() {
    try {
        const datos = await postJson("/api/marcajes/sincronizar-desde-bd", {});
        renderMarcajesActivos(datos.marcajes || []);
        log(datos.mensaje);
    } catch (error) {
        log(error.message, true);
    }
}


async function prepararCierreGeneralDesdeMarcajeActivo() {
    log("Preparando cierre general. Se solicitará huella para validar al dueño del marcaje.", true);

    await Swal.fire({
        icon: "info",
        title: "Preparar cierre",
        text: "Coloque la huella del operario dueño del marcaje para continuar con el cierre.",
        confirmButtonText: "Leer huella"
    });

    return identificarConHuellaLocal();
}

function cerrarMarcajeRealBdDesdeTexto(marcajeTexto) {
    const marcaje = JSON.parse(decodeURIComponent(marcajeTexto));
    return cerrarMarcajeRealBd(marcaje);
}

function prepararCierreDesdeMarcajeTexto(marcajeTexto) {
    const marcaje = JSON.parse(decodeURIComponent(marcajeTexto));
    return prepararCierreDesdeMarcaje(marcaje);
}

function prepararCierreDesdeMarcaje(marcaje) {
    marcajeActivoUsuario = marcaje;

    mostrarPanelCierreMarcajeUsuario(marcajeActivoUsuario);

    const cardOp = document.getElementById("cardOp");
    const cardActividad = document.getElementById("cardActividad");
    const cardSimulacion = document.getElementById("cardSimulacion");
    const cardSimulacionCierre = document.getElementById("cardSimulacionCierre");

    if (cardOp) cardOp.classList.add("hidden");
    if (cardActividad) cardActividad.classList.add("hidden");
    if (cardSimulacion) cardSimulacion.classList.add("hidden");
    if (cardSimulacionCierre) cardSimulacionCierre.classList.add("hidden");

    const totalUsuario = document.getElementById("totalUsuarioCierre");
    if (totalUsuario) totalUsuario.focus();

    activarPaso(1);
    log("Marcaje seleccionado. Ahora debe elegir el tipo de cierre: FINAL, MD o MT.", true);
}


async function cerrarMarcajeRealBd(marcaje) {
    try {
        const datos = await postJson("/api/marcajes/cerrar-real-bd", { marcaje });
        renderMarcajesActivos(datos.marcajes || []);
        log(datos.mensaje);
    } catch (error) {
        log(error.message, true);
        alert(error.message);
    }
}

async function consultarModoPersistencia() {
    try {
        const respuesta = await fetch("/api/marcajes/modo-persistencia");
        const datos = await respuesta.json();
        escrituraRealHabilitada = !!datos.escritura_real_habilitada;
        publicacionMqttRealHabilitada = !!datos.publicacion_mqtt_real_habilitada;

        const estado = document.getElementById("modoPersistenciaEstado");
        if (estado) {
            estado.textContent = `${escrituraRealHabilitada ? "BD real habilitada" : "BD protegida"} · ${publicacionMqttRealHabilitada ? "MQTT publish habilitado" : "MQTT publish protegido"}`;
            estado.classList.toggle("status-ok", escrituraRealHabilitada);
            estado.classList.toggle("status-error", !escrituraRealHabilitada);
        }

        log(datos.mensaje);
    } catch (error) {
        log("No se pudo consultar modo de persistencia.", true);
    }
}

async function cerrarMarcajeSimulado(marcajeId) {
    log("La gestión de marcajes simulados fue retirada en v20.5.", true);
}


revisarBackend();
revisarServicioHuellaLocal();
consultarModoPersistencia();
cargarMarcajesActivosIniciales();
conectarWebSocketMarcajes();
aplicarVisibilidadPorRol();

// =============================
// MQTT en vivo - fase v13
// =============================
let socketMqtt = null;
let mensajesMqttActuales = [];

function conectarWebSocketMqtt() {
    const estado = document.getElementById("mqttWsEstado");

    try {
        socketMqtt = new WebSocket(construirUrlWebSocket("/ws/mqtt"));

        socketMqtt.onopen = () => {
            if (estado) {
                estado.textContent = "WS conectado";
                estado.classList.remove("ws-error");
                estado.classList.add("ws-ok");
            }
            log("WebSocket MQTT conectado.");
        };

        socketMqtt.onmessage = (event) => {
            const datos = JSON.parse(event.data);

            if (datos.tipo === "MQTT_ESTADO") {
                actualizarEstadoMqtt(datos.estado);
                if (datos.mensaje) log(datos.mensaje);
            }

            if (datos.tipo === "MQTT_MENSAJE_RECIBIDO") {
                if (datos.mensaje) {
                    datos.mensaje.asociacion = datos.asociacion || null;
                    datos.mensaje.persistencia_simulada = datos.persistencia_simulada || datos.mensaje.persistencia_simulada || null;
                    mensajesMqttActuales.unshift(datos.mensaje);
                    mensajesMqttActuales = mensajesMqttActuales.slice(0, 25);
                    renderMensajesMqtt(mensajesMqttActuales);

                    if (datos.asociacion && datos.asociacion.asociado) {
                        log(`MQTT asociado: ${datos.mensaje.topic} → ${datos.asociacion.marcaje.username} / ${datos.asociacion.marcaje.recurso}`);
                    } else {
                        log(`MQTT recibido: ${datos.mensaje.topic}`);
                    }
                }
                actualizarEstadoMqtt(datos.estado);
            }
        };

        socketMqtt.onclose = () => {
            if (estado) {
                estado.textContent = "WS desconectado";
                estado.classList.remove("ws-ok");
                estado.classList.add("ws-error");
            }
            log("WebSocket MQTT desconectado. Intentando reconectar...", true);
            setTimeout(conectarWebSocketMqtt, 3000);
        };

        socketMqtt.onerror = () => {
            if (estado) {
                estado.textContent = "WS error";
                estado.classList.remove("ws-ok");
                estado.classList.add("ws-error");
            }
        };
    } catch (error) {
        log(`No se pudo abrir WebSocket MQTT: ${error.message}`, true);
    }
}

function actualizarEstadoMqtt(estado) {
    const texto = document.getElementById("mqttEstadoTexto");

    if (!texto || !estado) return;

    const conectado = estado.conectado ? "conectado" : "desconectado";
    const ejecutando = estado.ejecutando ? "servicio activo" : "servicio detenido";
    const cantidad = estado.cantidad_mensajes || 0;

    texto.textContent = `MQTT ${conectado} · ${ejecutando} · mensajes: ${cantidad}`;

    if (estado.ultimos_mensajes && estado.ultimos_mensajes.length > 0) {
        mensajesMqttActuales = estado.ultimos_mensajes;
        renderMensajesMqtt(mensajesMqttActuales);
    }

    if (estado.ultimo_error) {
        log(`MQTT: ${estado.ultimo_error}`, true);
    }
}

function renderMensajesMqtt(mensajes) {
    const contenedor = document.getElementById("mqttMensajes");

    if (!contenedor) return;

    contenedor.innerHTML = "";

    if (!mensajes || mensajes.length === 0) {
        contenedor.innerHTML = `<div class="empty-live">Sin mensajes MQTT recibidos.</div>`;
        return;
    }

    mensajes.slice(0, 25).forEach(mensaje => {
        const tarjeta = document.createElement("div");
        tarjeta.className = "mqtt-message";
        const asociacion = mensaje.asociacion;
        const textoAsociacion = asociacion && asociacion.asociado
            ? `<span class="mqtt-associated">Asociado a: ${asociacion.marcaje.username} · ${asociacion.marcaje.recurso} · Conteo: ${asociacion.marcaje.conteo_mqtt_actual}</span>`
            : asociacion && asociacion.motivo
                ? `<span class="mqtt-not-associated">${asociacion.motivo}</span>`
                : "";

        const persistencia = mensaje.persistencia_simulada;
        let textoPersistencia = "";

        if (persistencia && persistencia.aplica) {
            const calculo = persistencia.calculo_conglomerado || {};
            textoPersistencia = `
                <span class="mqtt-db-preview">ID mensaje: ${persistencia.idmensaje || "N/A"}</span>
                <span class="mqtt-db-preview">Cant. anterior: ${persistencia.cantpliegos_anterior ?? "Sin anterior"} · Actual: ${persistencia.cantpliegos_actual ?? "N/A"}</span>
                <span class="mqtt-db-preview">Producción calculada: ${calculo.unidadesCalculadasConglomerado ?? "N/A"} (${calculo.tipo_calculo || "N/A"})</span>
                <details class="mqtt-sql-details">
                    <summary>Ver INSERTS simulados</summary>
                    <pre>${persistencia.sql?.mensajes_mqtt || "Sin SQL mensajes_mqtt"}</pre>
                    <pre>${persistencia.sql?.datossensados || "Sin SQL datossensados"}</pre>
                </details>
            `;
        } else if (persistencia && persistencia.motivo) {
            textoPersistencia = `<span class="mqtt-not-associated">Persistencia simulada: ${persistencia.motivo}</span>`;
        }

        tarjeta.innerHTML = `
            <strong>${mensaje.topic || "Sin topic"}</strong>
            <span>${mensaje.payload || ""}</span>
            ${textoAsociacion}
            ${textoPersistencia}
            <span class="mqtt-date">${mensaje.fecha_hora || ""}</span>
        `;
        contenedor.appendChild(tarjeta);
    });
}

async function cargarEstadoMqtt() {
    try {
        const respuesta = await fetch("/api/mqtt/estado");
        const datos = await respuesta.json();
        if (datos.ok) actualizarEstadoMqtt(datos.estado);
    } catch (error) {
        log("No se pudo consultar el estado MQTT.", true);
    }
}

async function iniciarMqttLectura() {
    try {
        log("Iniciando MQTT en modo lectura...");
        const datos = await postJson("/api/mqtt/iniciar", {});
        actualizarEstadoMqtt(datos.estado);
        log(datos.mensaje);
    } catch (error) {
        log(error.message, true);
        alert(`No se pudo iniciar MQTT:\n${error.message}`);
    }
}

async function detenerMqttLectura() {
    try {
        log("Deteniendo MQTT...");
        const datos = await postJson("/api/mqtt/detener", {});
        actualizarEstadoMqtt(datos.estado);
        log(datos.mensaje);
    } catch (error) {
        log(error.message, true);
    }
}

cargarEstadoMqtt();
conectarWebSocketMqtt();


// =====================================================
// EXPOSICIÓN GLOBAL Y EVENTOS DE SEGURIDAD V17.1
// =====================================================
// Algunos navegadores/estados de recarga pueden no resolver correctamente
// funciones llamadas desde onclick inline. Dejamos las funciones críticas
// expuestas explícitamente y además conectamos el botón por addEventListener.
window.simularCierreMarcajeActivoDelUsuario = simularCierreMarcajeActivoDelUsuario;
window.ejecutarCierreRealMarcajeActivoDelUsuario = ejecutarCierreRealMarcajeActivoDelUsuario;
window.cambiarUsuarioDesdeMarcajeActivo = cambiarUsuarioDesdeMarcajeActivo;
window.copiarTexto = copiarTexto;

window.iniciarRelevoMtAutomatico = iniciarRelevoMtAutomatico;
window.cancelarRelevoMt = cancelarRelevoMt;


// =====================================================
// USUARIOS ELEVADOS - v20.3
// =====================================================
async function abrirLoginUsuarioElevado() {
    try {
        const resultado = await Swal.fire({
            title: "Usuarios elevados",
            html: `
                <input id="swalUsuarioElevado" class="swal2-input" placeholder="Nombre de usuario" autocomplete="off">
                <input id="swalPasswordElevado" class="swal2-input" placeholder="Contraseña" type="password" autocomplete="off">
            `,
            focusConfirm: false,
            showCancelButton: true,
            confirmButtonText: "Ingresar",
            cancelButtonText: "Cancelar",
            preConfirm: () => {
                const username = document.getElementById("swalUsuarioElevado").value.trim();
                const password = document.getElementById("swalPasswordElevado").value.trim();

                if (!username || !password) {
                    Swal.showValidationMessage("Debe ingresar usuario y contraseña.");
                    return false;
                }

                return { username, password };
            }
        });

        if (!resultado.isConfirmed || !resultado.value) {
            return;
        }

        log("Validando usuario elevado...");

        const datos = await postJson("/api/auth/usuario-elevado", {
            username: resultado.value.username,
            password: resultado.value.password
        });

        usuarioElevadoActual = datos.usuario_elevado;
        tipoUsuarioElevadoActual = datos.tipo_usuario || "NO";

        actualizarVistaUsuarioElevado();

        if (tipoUsuarioElevadoActual === "ADMIN") {
            await Swal.fire({
                icon: "success",
                title: "Acceso administrador",
                text: "Se habilitó el modo administrador.",
                confirmButtonText: "Continuar"
            });
        } else if (tipoUsuarioElevadoActual === "SU") {
            await Swal.fire({
                icon: "success",
                title: "Acceso soporte",
                text: "Se habilitó el modo soporte para marcajes.",
                confirmButtonText: "Continuar"
            });
        } else {
            await Swal.fire({
                icon: "warning",
                title: "Sin permisos elevados",
                text: "El usuario fue encontrado, pero no tiene permisos elevados.",
                confirmButtonText: "Entendido"
            });
        }

        log(`Usuario elevado validado. Tipo: ${tipoUsuarioElevadoActual}`);

    } catch (error) {
        console.error(error);
        const mensaje = error?.detail || error?.message || "Usuario o contraseña incorrectos";
        log(mensaje, true);

        await Swal.fire({
            icon: "error",
            title: "Acceso denegado",
            text: mensaje,
            confirmButtonText: "Entendido"
        });
    }
}

function aplicarVisibilidadPorRol() {
    const rol = (tipoUsuarioElevadoActual || "NO").toUpperCase();

    document.body.setAttribute("data-role", rol);

    // Marcajes activos: siempre visibles para todos los usuarios.
    // No se ocultan aquí por diseño operativo.

    document.querySelectorAll(".admin-only").forEach((elemento) => {
        elemento.classList.toggle("permission-hidden", rol !== "ADMIN");
    });

    document.querySelectorAll(".su-admin-only").forEach((elemento) => {
        elemento.classList.toggle("permission-hidden", !(rol === "SU" || rol === "ADMIN"));
    });
}

function actualizarVistaUsuarioElevado() {
    const panel = document.getElementById("panelUsuarioElevado");
    const tipo = document.getElementById("tipoUsuarioElevado");
    const detalle = document.getElementById("detalleUsuarioElevado");
    const btnOpciones = document.getElementById("btnOpcionesAvanzadas");
    const btnCancelar = document.getElementById("btnCancelarUsuarioElevado");

    aplicarVisibilidadPorRol();

    if (!panel || !tipo || !detalle) {
        return;
    }

    if (!usuarioElevadoActual || tipoUsuarioElevadoActual === "NO") {
        panel.classList.add("hidden");
        if (btnOpciones) btnOpciones.classList.remove("hidden");
        if (btnCancelar) btnCancelar.classList.add("hidden");
        return;
    }

    panel.classList.remove("hidden");
    tipo.textContent = tipoUsuarioElevadoActual;
    detalle.innerHTML = `
        <strong>Usuario:</strong> ${usuarioElevadoActual.username || "N/A"}<br>
        <strong>Permiso:</strong> ${tipoUsuarioElevadoActual}<br>
        <strong>Marcajes:</strong> ${usuarioElevadoActual.puede_ver_marcajes ? "Sí" : "No"}<br>
        <strong>MQTT:</strong> ${usuarioElevadoActual.puede_ver_mqtt ? "Sí" : "No"}<br>
        <strong>Admin:</strong> ${usuarioElevadoActual.puede_ver_admin ? "Sí" : "No"}
    `;

    if (btnOpciones) btnOpciones.classList.add("hidden");
    if (btnCancelar) btnCancelar.classList.remove("hidden");
}

async function cerrarSesionUsuarioElevado() {
    usuarioElevadoActual = null;
    tipoUsuarioElevadoActual = "NO";
    actualizarVistaUsuarioElevado();

    await Swal.fire({
        icon: "info",
        title: "Modo elevado cerrado",
        text: "Se ocultarán las opciones avanzadas.",
        confirmButtonText: "Entendido"
    });

    log("Modo elevado cerrado.");
}

window.abrirLoginUsuarioElevado = abrirLoginUsuarioElevado;
window.cerrarSesionUsuarioElevado = cerrarSesionUsuarioElevado;
window.aplicarVisibilidadPorRol = aplicarVisibilidadPorRol;
window.prepararCierreGeneralDesdeMarcajeActivo = prepararCierreGeneralDesdeMarcajeActivo;

window.cancelarFlujoOperativo = cancelarFlujoOperativo;
