# Arquitectura de la versión 3.0

`lectura.py` consulta únicamente el canal de Cienfuegos, descarga imágenes/PDF
transitoriamente, aplica OCR y reutiliza `.cache/ocr.json`. Las credenciales solo
se leen del entorno. Se relee la ventana de mensajes para detectar ediciones.

`interpretador.py` extrae IDs, intención, ámbito y ventanas temporales por sección.
`actualizar.py` reproduce eventos cronológicamente y publica estado schema 3.
Las causas de déficit y avería son independientes. Un estado desconocido o vencido
nunca equivale a electricidad confirmada. Los mensajes ambiguos se registran.

`index.html` combina el catálogo schema 2 y estado schema 3. También degrada por
antigüedad en el navegador, aunque el cron se haya detenido. Los IDs detectados
sin coordenadas aparecen en la lista de pendientes. Datos antiguos schema 2 no
permiten inferir verde por omisión. La vista permanece en Cienfuegos.

`geometria.py` comprueba pertenencia al polígono real de la provincia.
`geocodificar.py` acepta nombres exactos, categoría de localidad y provincia
explícita; rechaza homónimos distantes. `gazetteer.json` contiene referencias OSM.
Las coordenadas viejas no verificadas conservan la indicación de incertidumbre.

`mapa.yml` instala OCR español, ejecuta pruebas, actualiza JSON, guarda cambios y
publica directamente Pages mediante un artefacto limitado a Cienfuegos. El modo
estudio genera muestras locales al runner, excluidas del sitio público.

Los módulos opcionales Worker y Apps Script no envían mensajes a Telegram. Su
configuración y las limitaciones de rate limiting están en LEEME_PRIMERO.txt y
worker/DESPLEGAR.md. No contienen secretos precargados.

Referencias técnicas:
- https://docs.telethon.dev/en/stable/modules/client.html
- https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html
- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- https://www.openstreetmap.org/relation/1854632
