# Reportes comunitarios opcionales

El mapa y la lectura del canal funcionan sin este Worker.

1. Crear un Cloudflare Worker con `worker.js` y un namespace KV enlazado como REPORTES.
2. Crear un secreto REPORT_SALT largo y aleatorio. Definir ALLOWED_ORIGIN con el origen exacto de la web (por ejemplo https://yottomtnz.github.io, sin ruta).
3. En config.js, reportApi debe contener la URL HTTPS del Worker, sin barra final.
4. Probar GET /reportes desde la web. Solo después se muestra el botón de reportar.

El servidor acepta únicamente Cienfuegos y limita tamaño, tipos y códigos. No publica la IP ni el identificador interno. Una opinión reciente por usuario y circuito. La IP solo se transforma mediante SHA-256 con secreto y fecha; no se almacena en claro. La vigencia es de dos horas.

El límite orientativo de tres envíos/hora usa KV, que no ofrece un contador atómico: para protección contra tráfico simultáneo abusivo, activar reglas de rate limiting de Cloudflare. CORS restringe navegadores, no autentica personas. Los reportes siguen siendo información no verificada y no modifican los estados oficiales.
