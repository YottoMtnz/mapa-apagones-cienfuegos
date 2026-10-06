#!/usr/bin/env python3
"""
Migración OFFLINE (sin red) del catálogo al esquema 2. Idempotente.

Qué hace:
  1. Limpia y canoniza data/inventario.json (ids unificados, lugares sin basura,
     duplicados fusionados: 'Cto Uñas 1' + 'Uñas 1' -> 'Uñas 1').
  2. Siembra data/geocache.json con las coordenadas buenas del esquema 1 (Nominatim
     antiguo) descartando las aproximadas / en el centro de la capital.
  3. Regenera data/circuitos_<prov>.json (esquema 2) usando gazetteer.json + caché.
     Lo que no se puede ubicar queda ubicado=false (sin pin). NO se inventa nada.
  4. Escribe data/informe_ubicacion.json.

Uso: python3 scraper/reconstruir_datos.py
Después, con red: python3 scraper/geocodificar.py   (ubica los pendientes)
"""
import glob, os, re, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalizar import expandir_ids, limpiar_lugar, fold
from provincias import PROVINCIAS
import catalogo as cat

# Circuitos que son basura del parser antiguo (no existen de verdad)
IDS_BASURA = {
    "artemisa": {"5040", "13"},      # frase "144 MW" / "mil y 4mil"
    "las-tunas": {"Circuito"},       # palabra capturada como id
}


def limpiar_inventario(inv):
    nuevo = {}
    for prov, circuitos in inv.items():
        if prov not in PROVINCIAS:
            continue
        out = {}
        for raw_id, lugares in (circuitos or {}).items():
            for cid in expandir_ids(prov, raw_id):
                if not cid or cid in IDS_BASURA.get(prov, ()):
                    continue
                lim = [l for l in (limpiar_lugar(x) for x in (lugares or [])) if l]
                previos = out.setdefault(cid, [])
                for l in lim:
                    if l not in previos:
                        previos.append(l)
        nuevo[prov] = out
    return nuevo


def sembrar_desde_esquema1(cache):
    """Lee circuitos_*.json en esquema 1 y vuelca sus puntos buenos al caché."""
    n = 0
    for path in sorted(glob.glob(os.path.join(cat.DATA, "circuitos_*.json"))):
        prov = os.path.basename(path)[len("circuitos_"):-len(".json")]
        if prov not in PROVINCIAS:
            continue
        d = cat.cargar_json(os.path.basename(path), {})
        if d.get("schema") == 2:
            continue
        for cid, info in d.items():
            if not isinstance(info, dict):
                continue
            for pt in info.get("puntos") or []:
                if pt.get("aproximado") or pt.get("lat") is None:
                    continue
                lugar = limpiar_lugar(pt.get("lugar", ""))
                if not lugar:
                    continue
                k = cat.clave_cache(prov, lugar)
                if k not in cache:
                    cache[k] = {"lat": pt["lat"], "lng": pt["lng"], "fuente": "legacy-nominatim"}
                    n += 1
    return n


def main():
    inv_old = cat.cargar_json("inventario.json", {})
    # Cienfuegos tenía inventario vacío pero catálogo con lugares: recuperarlos
    for path in glob.glob(os.path.join(cat.DATA, "circuitos_*.json")):
        prov = os.path.basename(path)[len("circuitos_"):-len(".json")]
        d = cat.cargar_json(os.path.basename(path), {})
        if prov not in PROVINCIAS or d.get("schema") == 2:
            continue
        for cid, info in d.items():
            if isinstance(info, dict):
                inv_old.setdefault(prov, {}).setdefault(cid, list(info.get("lugares") or []))

    inv = limpiar_inventario(inv_old)
    cat.guardar_json("inventario.json", inv)

    cache = cat.cargar_json("geocache.json", {})
    sembrados = sembrar_desde_esquema1(cache)
    cat.guardar_json("geocache.json", cache)

    res = cat.Resolvedor(cache=cache)
    informe = {}
    for prov in PROVINCIAS:
        circuitos = {}
        for cid, lugares in inv.get(prov, {}).items():
            circuitos[cid] = cat.construir_circuito(prov, cid, lugares, res.offline)
        cat.escribir_provincia(prov, circuitos)
        informe[prov] = cat.informe_provincia(circuitos)
        i = informe[prov]
        print(f"{prov:17} total={i['total']:4} ubicados={i['ubicados']:4} "
              f"sin_ubicar={i['sin_ubicar']:4} dudosos={i['con_puntos_dudosos']}")
    cat.escribir_informe(informe)
    print(f"\ncaché sembrado con {sembrados} lugares nuevos -> data/geocache.json")


if __name__ == "__main__":
    main()
