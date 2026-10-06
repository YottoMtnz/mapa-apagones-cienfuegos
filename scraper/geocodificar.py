"""
Geocodifica circuitos por provincia usando Nominatim (OpenStreetMap).
Lee data/inventario.json, genera data/circuitos_<prov>.json

Uso: python3 scraper/geocodificar.py [provincia] [--solo-malos]
  --solo-malos: solo re-geocodifica puntos inventados o fuera de provincia.

Reglas:
- Nominatim con viewbox limitado a la provincia (bounded=1): nunca devuelve
  un lugar de otra provincia aunque el nombre coincida.
- Se prueban todos los lugares del circuito, no solo el primero.
- Si no se encuentra: se marca aproximado=True con la capital como referencia,
  NUNCA se inventan coordenadas falsas.
"""
import json, os, sys, time, urllib.request, urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (lat_centro, lng_centro, capital, min_lat, max_lat, min_lng, max_lng)
PROVINCIAS = {
    "pinar-del-rio":   (22.42, -83.70, "Pinar del Río",      21.70, 23.05, -84.95, -82.95),
    "artemisa":        (22.82, -82.76, "Artemisa",           22.30, 23.20, -83.25, -82.25),
    "la-habana":       (23.14, -82.37, "La Habana",          22.90, 23.30, -82.65, -82.05),
    "mayabeque":       (22.97, -82.15, "San José de las Lajas", 22.65, 23.30, -82.45, -81.65),
    "matanzas":        (23.05, -81.58, "Matanzas",           22.25, 23.30, -81.95, -80.85),
    "cienfuegos":      (22.15, -80.45, "Cienfuegos",         21.75, 22.55, -80.95, -79.95),
    "villa-clara":     (22.42, -79.90, "Santa Clara",        21.95, 23.05, -80.45, -79.35),
    "sancti-spiritus": (21.93, -79.44, "Sancti Spíritus",    21.50, 22.40, -80.15, -78.85),
    "ciego-de-avila":  (21.85, -78.76, "Ciego de Ávila",     21.45, 22.35, -79.25, -78.25),
    "camaguey":        (21.38, -77.91, "Camagüey",           20.75, 22.05, -78.55, -76.95),
    "las-tunas":       (20.96, -76.95, "Las Tunas",          20.55, 21.45, -77.45, -76.55),
    "holguin":         (20.89, -76.26, "Holguín",            20.35, 21.45, -76.85, -75.75),
    "granma":          (20.38, -76.64, "Bayamo",             19.85, 20.95, -77.35, -75.95),
    "santiago-de-cuba":(20.02, -75.83, "Santiago de Cuba",   19.75, 20.55, -76.35, -75.35),
    "guantanamo":      (20.14, -75.21, "Guantánamo",         19.85, 20.55, -75.45, -74.05),
}

def geocode(query, min_lat, max_lat, min_lng, max_lng):
    """Devuelve (lat, lng) dentro del bbox o None. Usa viewbox bounded."""
    params = {
        "q": query, "format": "json", "limit": 5, "countrycodes": "cu",
        "viewbox": f"{min_lng},{max_lat},{max_lng},{min_lat}",
        "bounded": 1,
    }
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "MapaApagonesCuba/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
            for item in data:
                lat, lng = float(item["lat"]), float(item["lon"])
                if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
                    return lat, lng, item.get("display_name", "")
    except Exception as e:
        print(f"    geocode error: {e}")
    return None

def es_fallback(lat, lng, clat, clng):
    """Detecta si las coords vienen del fallback inventado (múltiplos de 0.002)."""
    dla = round((lat - clat) / 0.002)
    dlo = round((lng - clng) / 0.002)
    return (abs((lat - clat) - dla * 0.002) < 0.00001
            and abs((lng - clng) - dlo * 0.002) < 0.00001
            and abs(dla) <= 50 and abs(dlo) <= 50)

def main():
    args = sys.argv[1:]
    solo = args[0] if args and not args[0].startswith("--") else None
    solo_malos = "--solo-malos" in args

    with open(os.path.join(BASE, "data", "inventario.json")) as f:
        inventario = json.load(f)

    for prov, circuitos in inventario.items():
        if solo and prov != solo:
            continue
        if prov not in PROVINCIAS:
            continue
        clat, clng, capital, minla, maxla, minlo, maxlo = PROVINCIAS[prov]
        out = os.path.join(BASE, "data", f"circuitos_{prov}.json")
        # Cargar existentes para preservar los buenos
        existentes = {}
        if os.path.exists(out):
            try:
                existentes = json.load(open(out))
            except Exception:
                pass
        resultado = {}
        print(f"\n=== {prov}: {len(circuitos)} circuitos ===")
        for cid, lugares in circuitos.items():
            # ¿reusar punto existente?
            ex = existentes.get(cid)
            if solo_malos and isinstance(ex, dict) and ex.get("lat") is not None:
                lat0, lng0 = ex["lat"], ex["lng"]
                dentro = minla <= lat0 <= maxla and minlo <= lng0 <= maxlo
                if dentro and not es_fallback(lat0, lng0, clat, clng) and not ex.get("aproximado"):
                    resultado[cid] = ex
                    continue
            elif not solo_malos and isinstance(ex, dict) and ex.get("lat") is not None:
                lat0, lng0 = ex["lat"], ex["lng"]
                dentro = minla <= lat0 <= maxla and minlo <= lng0 <= maxlo
                if dentro and not es_fallback(lat0, lng0, clat, clng) and not ex.get("aproximado"):
                    resultado[cid] = ex
                    continue

            lat, lng, municipio, aproximado = None, None, "", False
            # Probar cada lugar con viewbox de la provincia
            for lugar in (lugares or []):
                if not lugar or len(lugar) > 60:
                    continue
                for q in (f"{lugar}, {capital}, Cuba", f"{lugar}, Cuba"):
                    r = geocode(q, minla, maxla, minlo, maxlo)
                    time.sleep(1.1)
                    if r:
                        lat, lng = r[0], r[1]
                        municipio = lugar
                        break
                if lat is not None:
                    break
            if lat is None:
                # Sin resultado: capital como referencia HONESTA
                lat, lng, municipio, aproximado = clat, clng, capital, True
            resultado[cid] = {
                "lugares": lugares or [],
                "municipio": municipio,
                "lat": round(lat, 5),
                "lng": round(lng, 5),
                "aproximado": aproximado,
            }
            tag = "APROX" if aproximado else "ok"
            print(f"  [{tag}] {cid}: {municipio} ({lat:.3f},{lng:.3f})")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        print(f"  -> {out}")

if __name__ == "__main__":
    main()
