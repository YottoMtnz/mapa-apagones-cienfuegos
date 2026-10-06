"""
Geocodifica circuitos por provincia usando Nominatim (OpenStreetMap).
Lee data/inventario.json, genera data/circuitos_<prov>.json

Uso: python3 scraper/geocodificar.py [provincia]
Sin argumento: todas las provincias.
"""
import json, os, sys, time, urllib.request, urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Capitales/municipios de referencia por provincia (fallback)
CENTROS = {
    "pinar-del-rio":   (22.42, -83.70, "Pinar del Río"),
    "artemisa":        (22.82, -82.76, "Artemisa"),
    "la-habana":       (23.14, -82.37, "La Habana"),
    "mayabeque":       (22.97, -82.15, "San José de las Lajas"),
    "matanzas":        (23.05, -81.58, "Matanzas"),
    "cienfuegos":      (22.15, -80.45, "Cienfuegos"),
    "villa-clara":     (22.42, -79.90, "Santa Clara"),
    "sancti-spiritus": (21.93, -79.44, "Sancti Spíritus"),
    "ciego-de-avila":  (21.85, -78.76, "Ciego de Ávila"),
    "camaguey":        (21.38, -77.91, "Camagüey"),
    "las-tunas":       (20.96, -76.95, "Las Tunas"),
    "holguin":         (20.89, -76.26, "Holguín"),
    "granma":          (20.38, -76.64, "Bayamo"),
    "santiago-de-cuba":(20.02, -75.83, "Santiago de Cuba"),
    "guantanamo":      (20.14, -75.21, "Guantánamo"),
}

def geocode(query):
    """Devuelve (lat, lng) o None."""
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": query, "format": "json", "limit": 1, "countrycodes": "cu",
    })
    req = urllib.request.Request(url, headers={"User-Agent": "MapaApagonesCuba/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"    geocode error: {e}")
    return None

def main():
    solo = sys.argv[1] if len(sys.argv) > 1 else None
    with open(os.path.join(BASE, "data", "inventario.json")) as f:
        inventario = json.load(f)

    for prov, circuitos in inventario.items():
        if solo and prov != solo:
            continue
        if prov not in CENTROS:
            continue
        clat, clng, capital = CENTROS[prov]
        resultado = {}
        print(f"\n=== {prov}: {len(circuitos)} circuitos ===")
        for cid, lugares in circuitos.items():
            lat, lng, municipio = None, None, ""
            # Intentar geocodificar cada lugar
            for lugar in (lugares or []):
                if not lugar or len(lugar) > 50:
                    continue
                r = geocode(f"{lugar}, {capital}, Cuba")
                time.sleep(1.1)  # respetar rate limit Nominatim
                if r:
                    lat, lng = r
                    municipio = lugar
                    break
            # Fallback: capital de provincia con pequeño desplazamiento
            if lat is None:
                import hashlib
                h = int(hashlib.md5(cid.encode()).hexdigest()[:8], 16)
                lat = clat + ((h % 100) - 50) * 0.002
                lng = clng + ((h // 100 % 100) - 50) * 0.002
                municipio = capital
            resultado[cid] = {
                "lugares": lugares or [],
                "municipio": municipio,
                "lat": round(lat, 5),
                "lng": round(lng, 5),
            }
            print(f"  {cid}: {municipio} ({lat:.3f},{lng:.3f})")
        out = os.path.join(BASE, "data", f"circuitos_{prov}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        print(f"  -> {out}")

if __name__ == "__main__":
    main()
