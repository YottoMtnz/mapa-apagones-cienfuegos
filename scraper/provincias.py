"""
Tabla única de provincias (fuente de verdad para scraper, geocodificador y tests).

Cada entrada: centro (lat,lng), capital, caja aproximada (min_lat,max_lat,min_lng,max_lng)
y 'estado_osm' = texto que debe aparecer en address.state de Nominatim.

IMPORTANTE: las cajas se SOLAPAN entre provincias vecinas. Una caja NO prueba que
un punto pertenezca a la provincia; úsala solo como filtro grueso. Para decidir
pertenencia usa `provincia_mas_cercana()` (aprox. Voronoi por centros) y, al
geocodificar online, la comprobación de address.state (ver geocodificar.py).
"""
import math
from normalizar import fold

PROVINCIAS = {
    # id:               (clat,  clng,   capital,                 min_lat, max_lat, min_lng,  max_lng, estado_osm)
    "pinar-del-rio":   (22.42, -83.70, "Pinar del Río",           21.70, 23.05, -84.95, -82.95, "pinar del rio"),
    "artemisa":        (22.82, -82.76, "Artemisa",                22.30, 23.20, -83.25, -82.25, "artemisa"),
    "la-habana":       (23.14, -82.37, "La Habana",               22.90, 23.30, -82.65, -82.05, "habana"),
    "mayabeque":       (22.97, -82.15, "San José de las Lajas",   22.65, 23.30, -82.45, -81.65, "mayabeque"),
    "matanzas": (23.05, -81.58, "Matanzas",                21.90, 23.30, -82.05, -80.50, "matanzas"),
    "cienfuegos":      (22.15, -80.45, "Cienfuegos",              21.75, 22.55, -80.95, -79.95, "cienfuegos"),
    "villa-clara": (22.42, -79.90, "Santa Clara",             21.85, 23.15, -80.75, -78.85, "villa clara"),
    "sancti-spiritus": (21.93, -79.44, "Sancti Spíritus",         21.50, 22.40, -80.15, -78.85, "sancti spiritus"),
    "ciego-de-avila": (21.85, -78.76, "Ciego de Ávila",          21.45, 22.65, -79.30, -78.25, "ciego de avila"),
    "camaguey": (21.38, -77.91, "Camagüey",                20.55, 22.55, -78.60, -76.95, "camaguey"),
    "las-tunas": (20.96, -76.95, "Las Tunas",               20.55, 21.55, -77.75, -76.30, "las tunas"),
    "holguin": (20.89, -76.26, "Holguín",                 20.35, 21.45, -76.85, -74.55, "holguin"),
    "granma": (20.38, -76.64, "Bayamo",                  19.75, 20.95, -77.85, -75.95, "granma"),
    "santiago-de-cuba": (20.02, -75.83, "Santiago de Cuba",      19.75, 20.55, -76.70, -75.35, "santiago de cuba"),
    "guantanamo":      (20.14, -75.21, "Guantánamo",              19.85, 20.55, -75.45, -74.05, "guantanamo"),
}

# Provincias cuyo "circuito" se identifica por NOMBRE de lugar (no por número/código).
# En ellas el nombre del circuito es la mejor pista de ubicación.
NOMBRE_ES_LUGAR = {"holguin", "granma", "ciego-de-avila", "mayabeque"}


def info(prov):
    clat, clng, capital, a, b, c, d, estado = PROVINCIAS[prov]
    return {"centro": (clat, clng), "capital": capital, "bbox": (a, b, c, d), "estado_osm": estado}


def distancia_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lng2 - lng1) * p / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def provincia_mas_cercana(lat, lng):
    """Provincia cuyo centro está más cerca (aprox. Voronoi). No es un polígono real."""
    return min(PROVINCIAS, key=lambda p: distancia_km(lat, lng, PROVINCIAS[p][0], PROVINCIAS[p][1]))


def en_caja(prov, lat, lng):
    _, _, _, a, b, c, d, _ = PROVINCIAS[prov]
    return a <= lat <= b and c <= lng <= d


def es_centro_de_capital(prov, lat, lng, tol_km=1.5):
    """True si el punto está (casi) exactamente en el centro de referencia de la provincia,
    que es lo que dejaba el antiguo fallback 'aproximado'."""
    return distancia_km(lat, lng, PROVINCIAS[prov][0], PROVINCIAS[prov][1]) < tol_km
