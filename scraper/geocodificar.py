#!/usr/bin/env python3
"""
Geocodifica los circuitos SIN UBICAR usando Nominatim (OpenStreetMap). Requiere red.

Uso:
  python3 scraper/geocodificar.py                # todas las provincias
  python3 scraper/geocodificar.py holguin        # una provincia
  python3 scraper/geocodificar.py --reintentar   # ignora los 'no encontrado' del caché

Garantías (lo que antes fallaba):
  * Un resultado de Nominatim solo se acepta si address.state corresponde a la
    provincia pedida (las cajas de provincias vecinas se solapan). Si Nominatim no
    devuelve state, se exige además que la provincia más cercana por centro coincida.
  * Si hay varios candidatos se prefieren lugares (class place/boundary) sobre
    comercios, calles u otros POI homónimos.
  * Lo que no se encuentra queda SIN PIN (ubicado=false). Nunca se usa la capital
    como relleno.
  * Todo resultado (positivo o negativo) se guarda en data/geocache.json: no se repiten
    peticiones. Los negativos caducan a los 30 días.
  * 1 petición/segundo máx. (política de Nominatim). Define NOMINATIM_EMAIL con un
    contacto real para el User-Agent.
"""
import json, os, sys, time, datetime, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalizar import fold, candidatos
from provincias import PROVINCIAS, info, provincia_mas_cercana, en_caja
import catalogo as cat

PAUSA_S = 1.1
CADUCA_NEGATIVO_DIAS = 30
CLASES_PREFERIDAS = {"place": 0, "boundary": 1, "landuse": 2, "natural": 2, "highway": 4}


def _ua():
    mail = os.environ.get("NOMINATIM_EMAIL", "").strip()
    return "MapaApagonesCuba/2.0 (" + (mail or "sin-contacto: define NOMINATIM_EMAIL") + ")"


def nominatim(query, prov):
    """Mejor resultado válido para la provincia o None."""
    inf = info(prov)
    a, b, c, d = inf["bbox"]
    params = {"q": query, "format": "jsonv2", "limit": 8, "countrycodes": "cu",
              "addressdetails": 1, "viewbox": f"{c},{b},{d},{a}", "bounded": 1}
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": _ua()})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
    except Exception as e:                         # red caída, 429, etc.: NO cachear
        print(f"    error de red: {type(e).__name__}")
        raise
    validos = []
    for it in data:
        lat, lng = float(it["lat"]), float(it["lon"])
        if not en_caja(prov, lat, lng):
            continue
        state = fold((it.get("address") or {}).get("state", ""))
        if state:
            if inf["estado_osm"] not in state:
                continue                           # homónimo de otra provincia
        elif provincia_mas_cercana(lat, lng) != prov:
            continue
        rank = CLASES_PREFERIDAS.get(it.get("category", it.get("class", "")), 3)
        validos.append((rank, -float(it.get("importance", 0)), lat, lng, it.get("display_name", "")))
    if not validos:
        return None
    validos.sort()
    _, _, lat, lng, nombre = validos[0]
    return lat, lng, nombre


def buscar_lugar(prov, lugar, cache, reintentar=False):
    """(lat,lng,precision,fuente) o None. Usa y alimenta el caché."""
    k = cat.clave_cache(prov, lugar)
    e = cache.get(k)
    if e:
        if "lat" in e:
            return e["lat"], e["lng"], "localidad", e.get("fuente", "cache")
        if not reintentar and "no_encontrado" in e:
            f = datetime.date.fromisoformat(e["no_encontrado"])
            if (datetime.date.today() - f).days < CADUCA_NEGATIVO_DIAS:
                return None
    capital = info(prov)["capital"]
    for q in (f"{lugar}, {capital}, Cuba", f"{lugar}, Cuba"):
        r = nominatim(q, prov)
        time.sleep(PAUSA_S)
        if r:
            cache[k] = {"lat": round(r[0], 5), "lng": round(r[1], 5),
                        "fuente": "nominatim", "display": r[2][:120],
                        "fecha": datetime.date.today().isoformat()}
            return r[0], r[1], "localidad", "nominatim"
    cache[k] = {"no_encontrado": datetime.date.today().isoformat()}
    return None


def main():
    args = sys.argv[1:]
    reintentar = "--reintentar" in args
    solo = next((a for a in args if not a.startswith("--")), None)
    inv = cat.cargar_json("inventario.json", {})
    cache = cat.cargar_json("geocache.json", {})
    res = cat.Resolvedor(cache=cache)
    informe = cat.cargar_json("informe_ubicacion.json", {})

    def resolver(prov, lugar):
        r = res.offline(prov, lugar)                # gazetteer manual y caché positivo
        return r or buscar_lugar(prov, lugar, cache, reintentar)

    for prov in PROVINCIAS:
        if solo and prov != solo:
            continue
        circuitos = inv.get(prov, {})
        if not circuitos:
            continue
        print(f"\n=== {prov}: {len(circuitos)} circuitos ===")
        salida = {}
        try:
            for cid, lugares in circuitos.items():
                salida[cid] = cat.construir_circuito(prov, cid, lugares, resolver)
        except Exception:
            print("  interrumpido por error de red; se guarda lo avanzado (reanudable)")
        finally:
            cat.guardar_json("geocache.json", cache)
        if len(salida) == len(circuitos):
            cat.escribir_provincia(prov, salida)
            informe[prov] = cat.informe_provincia(salida)
            print(f"  -> {informe[prov]}")
    cat.escribir_informe(informe)


if __name__ == "__main__":
    main()
