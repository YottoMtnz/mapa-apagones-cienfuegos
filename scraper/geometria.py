"""Pertenencia al límite real de Cienfuegos (OpenStreetMap), sin provincias por cercanía."""
import json
from pathlib import Path
from functools import lru_cache
@lru_cache(maxsize=1)
def geometria():
    p=Path(__file__).resolve().parents[1]/'data/limite_cienfuegos.geojson'
    if not p.exists():return None
    return json.loads(p.read_text())['geometry']
def _anillo(x,y,ring):
    dentro=False
    for i,a in enumerate(ring):
        b=ring[i-1]
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:dentro=not dentro
    return dentro
def en_cienfuegos(lat,lng):
    g=geometria()
    if not g:return False
    polys=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
    return any(_anillo(lng,lat,p[0]) and not any(_anillo(lng,lat,h) for h in p[1:]) for p in polys)
