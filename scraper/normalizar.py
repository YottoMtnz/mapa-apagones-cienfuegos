"""
Normalización de identificadores de circuito y de nombres de lugar.

Es el punto ÚNICO donde se decide cómo se llama un circuito. Los parsers, el
inventario, el geocodificador, el scraper de estado y el frontend deben coincidir
en la clave; si dos sitios generan claves distintas para el mismo circuito, el
mapa muestra un falso "con servicio" (verde). Por eso todo pasa por canon_id().
"""
import re
import unicodedata

# Provincias donde el id del circuito es un nombre (ver provincias.NOMBRE_ES_LUGAR)
_NOMBRE_ES_LUGAR = {"holguin", "granma", "ciego-de-avila", "mayabeque"}


def fold(s):
    """minúsculas, sin acentos, espacios colapsados. Para comparar/clavear."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


# Correcciones por palabra (clave = palabra sin acentos en minúsculas)
TOKEN_ALIAS = {
    "baguanos": "Báguano", "baguano": "Báguano",
    "tacamara": "Tacámara",
    "aereopuerto": "Aeropuerto",
    "guadalavaca": "Guardalavaca", "gvaca": "Guardalavaca",
    "cabonico": "Cabonico",
    "bio": "Bío",
}

# Correcciones de id completo por provincia (clave = fold(id))
ID_ALIAS = {
    ("holguin", "a. pino"): "Alcides Pino",
    ("mayabeque", "salud 2"): "La Salud 2",
    ("mayabeque", "salud 1"): "La Salud 1",
}

_PREFIJO_CTO = re.compile(r"^(?:cto|ctos|circuito|circuitos)\.?\s+", re.I)


def canon_id(prov, raw):
    """Devuelve el id canónico de un circuito identificado por nombre.
    Para provincias con ids numéricos/códigos solo limpia espacios."""
    s = (raw or "").strip()
    if prov not in _NOMBRE_ES_LUGAR:
        return re.sub(r"\s+", " ", s)
    s = re.sub(r"\(.*?\)", " ", s)                       # "( completo )"
    s = re.sub(r"\bque se encontraba.*$", "", s, flags=re.I)
    s = re.sub(r"\bo\d{2,}\b", "", s)                    # códigos pegados tipo "o275"
    s = s.split(",")[0]                                  # "X, el ramal de Y" -> "X"
    while _PREFIJO_CTO.match(s):
        s = _PREFIJO_CTO.sub("", s, count=1)
    s = re.sub(r"^(?:de|del)\s+", "", s, flags=re.I)     # "de Gaspar"
    s = re.sub(r"(?<=[a-záéíóúñü])(?=[A-ZÁÉÍÓÚÑ])", " ", s)   # "BanesBanes" -> "Banes Banes"
    s = re.sub(r"(?<=[A-Za-zÁ-ú])(?=\d)", " ", s)        # "Aeropuerto1" -> "Aeropuerto 1"
    s = re.sub(r"\s+", " ", s).strip(" .:;-*_\"'")
    # alias por palabra
    palabras = [TOKEN_ALIAS.get(fold(w), w) for w in s.split(" ")]
    s = " ".join(palabras)
    # "4 de Moa" -> "Moa 4"
    m = re.fullmatch(r"(\d+) de (Moa)", s, flags=re.I)
    if m:
        s = f"Moa {m.group(1)}"
    # Holguín: id solo numérico o C<n> -> "Cto <n>"
    if prov == "holguin":
        m = re.fullmatch(r"C?(\d+)", s)
        if m:
            s = f"Cto {m.group(1)}"
    s = ID_ALIAS.get((prov, fold(s)), s)
    return s


def expandir_ids(prov, raw):
    """'Zarzal 1 y 2' -> ['Zarzal 1', 'Zarzal 2']. Devuelve lista de ids canónicos."""
    cid = canon_id(prov, raw)
    if prov in _NOMBRE_ES_LUGAR:
        m = re.fullmatch(r"(.*?)\s*(\d+)\s+y\s+(\d+)", cid)
        if m and m.group(1):
            base = m.group(1).strip()
            return [f"{base} {m.group(2)}", f"{base} {m.group(3)}"]
    return [cid] if cid else []


_STOP = {"de", "del", "la", "el", "los", "las", "y", "e", "sur", "norte", "centro",
         "este", "oeste", "pueblo", "completo", "cto", "circuito"}

_JUNK = re.compile(
    r"(seccionaliz|disparad|quedando|afectaci|deficit|d[eé]ficit|\bMW\b|\bkv\b|"
    r"restablec|disculp|avería|se encuentra|desde .* hasta|ofrecemos|capacidad)", re.I)


ABREVIATURAS = {"s.a.b": "San Antonio de los Baños", "sab": "San Antonio de los Baños",
                "bh": "Bahía Honda"}


def limpiar_lugar(txt):
    """Devuelve un nombre de lugar utilizable o None si es basura del parser."""
    if not txt:
        return None
    s = re.sub(r"\s+", " ", txt).strip(" .:;-*_\"'")
    s = re.sub(r"^(?:de|del)\s+", "", s, flags=re.I)
    if fold(s) in ABREVIATURAS:
        return ABREVIATURAS[fold(s)]
    s = re.sub(r"^(?:seccionalizado|provicional|provisional)\s+(?:de\s+)?", "", s, flags=re.I)
    s = re.sub(r"^circuitos?\s+[\d\s,y]+", "", s, flags=re.I)        # "Circuito 6 Casco" -> "Casco"
    s = re.sub(r"\s+(?:y la l[ií]nea|y el circuito|se encuentra|que\b).*$", "", s, flags=re.I)
    s = re.sub(r"^(?:de|del)\s+", "", s, flags=re.I)                  # "de San Cristóbal"
    s = s.strip(" .:;-*_\"'()")
    if len(s) < 3 or len(s) > 60:
        return None
    if re.fullmatch(r"(?:y\s*)?\d+[\d\sy,]*", s, flags=re.I):          # "y 51", "33"
        return None
    if re.search(r"\d+\s*kv", s, re.I) or _JUNK.search(s):
        return None
    if not re.search(r"[A-Za-zÁ-ú]{3}", s):
        return None
    return s


def lugar_desde_id(prov, cid):
    """Pista de lugar a partir del id (solo para provincias donde id = nombre)."""
    if prov not in _NOMBRE_ES_LUGAR:
        return None
    s = re.sub(r"^Cto\s+\d+$", "", cid)                  # "Cto 17": sin lugar
    s = re.sub(r"\s*\d+(?:\s*y\s*\d+)*$", "", s)         # "Banes 2" -> "Banes"
    s = re.sub(r"^\d+\s+de\s+", "", s)                   # "5 de San José" -> "San José"
    return limpiar_lugar(s)


def candidatos(lugar):
    """Subfrases del lugar, de más larga a más corta, para buscar en gazetteer/caché.
    'Nicaro Cabonico' -> ['Nicaro Cabonico', 'Nicaro', 'Cabonico']"""
    palabras = [w for w in re.split(r"\s+", lugar.strip()) if w]
    vistos, out = set(), []
    n = len(palabras)
    for largo in range(n, 0, -1):
        for i in range(0, n - largo + 1):
            sub = palabras[i:i + largo]
            if largo == 1 and (fold(sub[0]) in _STOP or len(sub[0]) < 4 or sub[0].isdigit()):
                continue
            k = fold(" ".join(sub))
            if k and k not in vistos and not re.fullmatch(r"[\d\s]+", k):
                vistos.add(k)
                out.append(" ".join(sub))
    return out
