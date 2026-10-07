# Mapa de apagones · Cienfuegos

Mapa de los estados reportados por el canal eléctrico de Cienfuegos, con lectura
de texto, imágenes y PDF, procedencia por circuito y ubicaciones verificables.

**Empieza por [LEEME_PRIMERO.txt](LEEME_PRIMERO.txt).** Incluye los cambios, límites,
la configuración de GitHub Actions y los pasos para sustituir la credencial
que estaba expuesta en la versión anterior.

- Rojo: corte reciente reportado. Naranja: programación vigente.
- Verde: restablecimiento explícito reciente. Gris: sin confirmación suficiente.
- Solo Cienfuegos. Los puntos representan localidades, no viviendas individuales.
- El cron solicita actualización cada cinco minutos; su ejecución puede retrasarse.

Vista local: `ABRIR_MAPA.bat`. Pruebas: `PROBAR.bat`.
Publicación: GitHub Pages, Source = GitHub Actions; workflow `mapa.yml`.

Desarrollado por Fraudy Martinez Madruga (YottoMtnz).
Cartografía © OpenStreetMap contributors, ODbL 1.0.
Leaflet y MarkerCluster incluidos con sus licencias en `assets/`.
