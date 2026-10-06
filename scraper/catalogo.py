"""
Construcción del catálogo de circuitos (data/circuitos_<prov>.json, schema 2).

Esquema 2 (por provincia):
{
  "schema": 2, "provincia": "holguin",
  "circuitos": {
    "<id canónico>": {
      "lugares": ["..."],                 # nombres de lugar limpios
      "puntos": [ {"lugar","lat","lng","precision","fuente","dudoso"} ],   # SOLO ubicaciones reales
      "ubicado": true|false,              # false => no se dibuja pin; el mapa lo lista aparte
      "revisar": true|false               # algún punto dudoso
    }
  }
}

REGLA DE ORO: un circuito que no se pudo ubicar NO lleva punto. Jamás se pone un pin
en la capital "de relleno" (era el bug nº1: el mapa mentía con confianza).
"""
import json, os, re, statistics, datetime
from normalizar import fold, candidatos, limpiar_lugar, lugar_desde_id
from provincias import PROVINCIAS, provincia_mas_cercana, distancia_km

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

# Nombres comunes que existen en muchas partes: un acierto de Nominatim aquí es sospechoso.
AMBIGUOS = {
    "san jose", "salud", "la salud", "la montana", "santa cruz", "la union", "providencia",
    "santa isabel", "sofia", "la curva", "california", "santa maria", "santa rosa",
    "la caridad", "camilo", "palomo", "vegas", "guatemala", "revolucion", "el salado",
    "san luis", "palma", "mella", "buenos aires", "san fernando", "san ramon", "los pinos",
}
UMBRAL_DISPERSION_KM = 40


def _ruta(nombre):
    return os.path.join(DATA, nombre)


def cargar_json(nombre, defecto):
    try:
        with open(_ruta(nombre), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def guardar_json(nombre, obj):
    with open(_ruta(nombre), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")


def cargar_gazetteer():
    g = cargar_json("gazetteer.json", {})
    return {p: v for p, v in g.items() if not p.startswith("_")}


def clave_cache(prov, lugar):
    return f"{prov}|{fold(lugar)}"


# --------------------------------------------------------------------- resolución
class Resolvedor:
    """Resuelve un nombre de lugar a coordenadas. Orden: gazetteer manual -> caché."""

    def __init__(self, gazetteer=None, cache=None):
        self.gaz = gazetteer if gazetteer is not None else cargar_gazetteer()
        self.cache = cache if cache is not None else cargar_json("geocache.json", {})

    def offline(self, prov, lugar):
        """(lat,lng,precision,fuente) o None. Sin red."""
        g = self.gaz.get(prov, {})
        for cand in candidatos(lugar):          # n-gramas: 'Nicaro Cabonico' -> 'Nicaro'
            k = fold(cand)
            if k in g:
                lat, lng, prec = g[k][0], g[k][1], g[k][2]
                return lat, lng, prec, "gazetteer"
        e = self.cache.get(clave_cache(prov, lugar))   # solo coincidencia EXACTA del lugar
        if e and "lat" in e:
            return e["lat"], e["lng"], "localidad", e.get("fuente", "cache")
        return None


# ------------------------------------------------------------------- construcción
def _marcar_dudosos(prov, puntos):
    reales = [p for p in puntos]
    for p in reales:
        p["dudoso"] = False
        if p["fuente"] != "gazetteer":
            if fold(p["lugar"]) in AMBIGUOS:
                p["dudoso"] = True
            if provincia_mas_cercana(p["lat"], p["lng"]) != prov:
                p["dudoso"] = True
    if len(reales) >= 2:
        if len(reales) == 2:
            d = distancia_km(reales[0]["lat"], reales[0]["lng"], reales[1]["lat"], reales[1]["lng"])
            if d > UMBRAL_DISPERSION_KM:
                for p in reales:
                    if p["fuente"] != "gazetteer":
                        p["dudoso"] = True
        else:
            mlat = statistics.median(p["lat"] for p in reales)
            mlng = statistics.median(p["lng"] for p in reales)
            for p in reales:
                if distancia_km(p["lat"], p["lng"], mlat, mlng) > UMBRAL_DISPERSION_KM and p["fuente"] != "gazetteer":
                    p["dudoso"] = True


def construir_circuito(prov, cid, lugares, resolver_lugar):
    """resolver_lugar(prov, lugar) -> (lat,lng,precision,fuente) | None"""
    lugares = [l for l in (limpiar_lugar(x) for x in (lugares or [])) if l]
    if not lugares:
        pista = lugar_desde_id(prov, cid)       # provincias donde id = nombre
        if pista:
            lugares = [pista]
    puntos, vistos = [], set()
    for lugar in lugares:
        r = resolver_lugar(prov, lugar)
        if not r:
            continue
        lat, lng, prec, fuente = r
        k = (round(lat, 4), round(lng, 4))
        if k in vistos:
            continue
        vistos.add(k)
        puntos.append({"lugar": lugar, "lat": round(lat, 5), "lng": round(lng, 5),
                       "precision": prec, "fuente": fuente})
    _marcar_dudosos(prov, puntos)
    return {
        "lugares": lugares,
        "puntos": puntos,
        "ubicado": bool(puntos),
        "revisar": any(p["dudoso"] for p in puntos),
    }


def informe_provincia(circuitos):
    n = len(circuitos)
    ub = sum(1 for c in circuitos.values() if c["ubicado"])
    return {"total": n, "ubicados": ub, "sin_ubicar": n - ub,
            "con_puntos_dudosos": sum(1 for c in circuitos.values() if c["revisar"])}


def escribir_provincia(prov, circuitos):
    guardar_json(f"circuitos_{prov}.json",
                 {"schema": 2, "provincia": prov, "circuitos": circuitos})


def escribir_informe(informe):
    informe["_generado"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    guardar_json("informe_ubicacion.json", informe)
