"""Diagnóstico offline: python scraper/analizar_archivo.py avisos.json.
Entrada: lista de {texto,fecha,id?,url?}; no cambia datos del mapa.
"""
import json,sys
from datetime import datetime,timezone
from actualizar import analizar_mensajes
if len(sys.argv)!=2:raise SystemExit('Uso: python scraper/analizar_archivo.py avisos.json')
with open(sys.argv[1],encoding='utf-8') as f:mensajes=json.load(f)
print(json.dumps(analizar_mensajes('cienfuegos',mensajes,datetime.now(timezone.utc)),ensure_ascii=False,indent=2))
