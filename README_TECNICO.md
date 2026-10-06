# Mapa de Apagones Cuba — Documentación Técnica

## Arquitectura general

```
Telegram (canales provinciales)
    │  (Telethon, sesión persistente)
    ▼
scraper/actualizar.py  ──►  data/estado_<prov>.json   (dinámico, cada 5 min)
                                │  {afectados, programados, mw, tiempos, causas,
                                │   reporte_fecha, actualizado}
                                ▼
scraper/inventario.py  ──►  data/circuitos_<prov>.json (estático, manual)
scraper/geocodificar.py ──►     │  {lugares[], municipio, lat, lng,
                                │   aproximado, puntos[{lugar,lat,lng,aproximado}]}
                                ▼
                          index.html  ──►  GitHub Pages
                          (Leaflet + OSM, sin Google)
```

## Dos capas de datos separadas

**Capa estática (inventario):** lista completa de circuitos + lugares + coordenadas.
Se construye UNA VEZ con `inventario.py` (lee 100 mensajes/canal) y se geocodifica
con `geocodificar.py` (Nominatim/OpenStreetMap). Las actualizaciones diarias NO
tocan coordenadas, solo colores.

**Capa dinámica (estado):** qué circuitos están afectados AHORA.
`actualizar.py` corre cada 5 min vía GitHub Actions, lee 50 mensajes/canal,
extrae circuitos con `parsers.py` y escribe `estado_<prov>.json`.
La UI solo cambia el color del punto (🔴🟠🟢⚪).

## Parsers por provincia (`scraper/parsers.py`)

Cada provincia tiene su formato. Principio de robustez: **no depender de emojis
o formato decorativo**. Los parsers buscan el identificador del circuito
(`C-31`, números, nombres) sin importar qué símbolo lo preceda (👉, 🧠, 🔥...).

- `parse_cienfuegos`: divide por `\bC[-_ ]?(\d{1,4})\b`, primera línea = lugares.
- `parse_artemisa`: busca `(\d{2,5})` tras cualquier prefijo no-numérico.
- `parse_mayabeque`: líneas con viñeta cualquiera (`*`, `-`, `•`, emoji) tras
  el keyword "se afecta el servicio en".
- `detectar_tipo(texto)`: distingue ACTUAL vs PROGRAMADO por keywords
  ("serán afectados", "a partir de", "programado" → futuro).
- `extraer_info_reporte(texto)`: MW (`(\d+)\s*MW`), hora inicio/cierre,
  tiempos por circuito (`📌Cto X - 48:39 Horas`), causas (`(Avería)`).

## Geocodificación (`scraper/geocodificar.py`)

- Nominatim con `viewbox` + `bounded=1` por provincia: nunca devuelve un lugar
  de otra provincia aunque el nombre coincida.
- Se prueban TODOS los lugares del circuito, no solo el primero.
- Si un lugar no se encuentra: `aproximado=true` con coordenada de referencia.
  La UI los muestra semitransparentes con "📍 Ubicación aproximada".
- **NUNCA se inventan coordenadas.** Sin resultado = marcado honesto.
- `puntos[]`: un punto POR LUGAR (no uno por circuito). Un circuito con 3
  pueblos muestra 3 marcadores separados.
- Validación post-geocodificación: ningún punto real puede caer fuera de su
  provincia.

## UI (`index.html`)

- Leaflet 1.9.4 + OpenStreetMap. **Cero Google** (no funciona en Cuba).
- `L.markerClusterGroup`: agrupa puntos apilados, muestra contador, al tocar
  se expanden (spiderfy).
- Estados: 🔴 sin servicio, 🟠 programado, 🟢 con servicio, ⚪ gris tenue =
  sin datos recientes (>24h sin reporte). El gris evita el "verde engañoso".
- Contadores: circuitos (no puntos). Filtros: Todos / Sin servicio / Programados.
- Auto-refresh cada 5 min (`setInterval`) con cache-busting (`?v=Date.now()`).
- Corrección colaborativa: cada popup tiene "✏️ Mover punto" (drag + confirm,
  se guarda en `localStorage` solo para ese usuario, borde azul) y "📤 Reportar"
  (abre Google Form pre-llenado para revisión del admin).
- Geolocalización: botón ◎, punto azul "Estás aquí", auto-selección provincial.

## Automatización

- `.github/workflows/mapa.yml`: cron `*/5 * * * *` → `actualizar.py` →
  commit+push si hay cambios → GitHub Pages reconstruye (1-3 min).
- **Nota:** GitHub a veces pausa los crons programados sin aviso.
  Mitigación: `scraper/vigilante.py` (cron externo cada 5 min) dispara
  `workflow_dispatch` si el último run tiene >6 min.
- `scraper/vigilante.py` usa credencial `custom.github` (nunca en código).

## Secretos

- `TG_SESSION`, `TG_API_ID`, `TG_API_HASH` → solo GitHub Secrets.
- Nunca en el repo, nunca en el chat, nunca en logs.

## Provincias activas

artemisa, camagüey, ciego-de-avila, cienfuegos, granma, holguín, la-habana,
las-tunas, matanzas, mayabeque, sancti-spíritus, santiago-de-cuba, villa-clara.

Sin fuente: pinar-del-rio (migró a WhatsApp), guantánamo (canal muerto 2022).
