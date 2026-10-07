#!/usr/bin/env python3
"""Revisa si hay formatos de mensajes no parseados en el estado del mapa."""
import json, urllib.request, sys

URL = "https://yottomtnz.github.io/mapa-apagones-cienfuegos/data/estado_cienfuegos.json"
try:
    with urllib.request.urlopen(URL, timeout=20) as r:
        e = json.load(r)
except Exception as ex:
    print(f"ERROR fetching: {ex}")
    sys.exit(1)

sosp = e.get("formatos_sospechosos", [])
if sosp:
    print(f"ALERTA: {len(sosp)} formato(s) no parseado(s):")
    for s in sosp:
        print(f"--- {s.get('fecha')} ---")
        print(s.get('texto', '')[:300])
        print()
else:
    print("OK: sin formatos sospechosos")
