# SmartFactory Web v20.12

## Corrección incluida

Se corrigieron las conexiones WebSocket del frontend para que funcionen desde computadoras externas.

Antes el frontend intentaba conectarse a:

```text
ws://127.0.0.1:8000/ws/marcajes
ws://127.0.0.1:8000/ws/mqtt
```

Eso fallaba cuando una PC cliente abría el sistema desde la IP del servidor, porque `127.0.0.1` apuntaba a la propia PC cliente.

Ahora se construye dinámicamente usando el host desde donde se abrió la página:

```javascript
function construirUrlWebSocket(ruta) {
    const protocolo = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocolo}//${window.location.host}${ruta}`;
}
```

Rutas locales de huella se mantienen en `127.0.0.1:9001`, ya que el servicio de huella corre localmente en cada PC de marcaje.

## Dependencias

Se agregó `websockets` a `requirements.txt` para soporte WebSocket sin volver a usar `uvicorn[standard]`.
