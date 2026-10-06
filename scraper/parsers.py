"""
Parsers de circuitos afectados por provincia.
Cada parser recibe el texto de un mensaje y devuelve {circuito_id: [lugares]}.

Reglas (aprendidas de errores reales, ver README_IA.md):
- Los ids de circuito pasan SIEMPRE por normalizar.expandir_ids() en las provincias
  donde el id es un nombre. Si no, inventario, estado y mapa no coinciden y el mapa
  muestra un falso "con servicio".
- Los lugares pasan SIEMPRE por normalizar.limpiar_lugar(), que devuelve None para
  basura ("y 51", "33 Kv: 6305", frases enteras...). Mejor lista vacía que lugar basura.
- NUNCA borrar guiones internos del texto (antes "Banes-Banes" -> "BanesBanes").
"""
import re
from normalizar import expandir_ids, limpiar_lugar, fold

_EMOJIS = "⚡⚠❓🔴🟢▶️👉➡️📌🔹✳⚜️🚨🧠🔥✅❌🟠"


def _limpiar(s):
    """Quita emojis y adornos; conserva guiones y caracteres internos."""
    s = "".join(ch for ch in s if ch not in _EMOJIS and ch != "\ufe0f")
    s = re.sub(r"\s+", " ", s).strip()
    return s.strip(" .:;-*_•\"'\n")


def _lugares(lista):
    out = []
    for l in lista:
        v = limpiar_lugar(_limpiar(l))
        if v and v not in out:
            out.append(v)
    return out


def _add(circuitos, prov, nombre, lugares=None):
    """Inserta (expandiendo '1 y 2') con id canónico."""
    for cid in expandir_ids(prov, nombre):
        if cid and cid not in circuitos:
            circuitos[cid] = list(lugares or [])


# --------------------------------------------------------------------- Cienfuegos
def parse_cienfuegos(texto):
    circuitos = {}
    partes = re.split(r'\bC[-_ ]?(\d{1,4})\b', texto, flags=re.IGNORECASE)
    for i in range(1, len(partes), 2):
        num = partes[i]
        lugares_txt = partes[i + 1] if i + 1 < len(partes) else ""
        lugares_txt = lugares_txt.split("\n")[0]
        lugares_txt = re.sub(r'^[^\wáéíóúñÁÉÍÓÚÑ]+', '', lugares_txt)
        lugares = [_limpiar(l) for l in lugares_txt.split(",")]
        lugares = [l for l in lugares if l and len(l) < 60 and not re.search(
            r'(afectaci|deficit|capacidad|generaci|MW|restablec|disculp|ofrecemos|se comunica)', l, re.I)]
        lugares = _lugares(lugares)
        if lugares:
            circuitos[f"C-{num}"] = lugares
    return circuitos


# ---------------------------------------------------------------------- Artemisa
_ART_ID = re.compile(r'(?<![\d:.,/])\b(\d{3,5})\b(?![\d:.,/])(?!\s*(?:MW|mil\b|kv|%|horas?\b))\s*[-–:]?\s*([^\n]{0,80})', re.I)

def parse_artemisa(texto):
    circuitos = {}
    t = texto.lower()
    if "afectados por d" not in t and "ficit de generaci" not in t:
        return circuitos
    for linea in texto.split("\n"):
        # Líneas de resumen (MW, "mil", déficit) no contienen circuitos
        if re.search(r'\bMW\b|\bmil\b|d[eé]ficit|generaci', linea, re.I):
            continue
        for m in _ART_ID.finditer(linea):
            lugar = limpiar_lugar(_limpiar(m.group(2)))
            if lugar and "manipulad" in lugar.lower():
                lugar = None
            cid = m.group(1)
            if cid not in circuitos:
                circuitos[cid] = [lugar] if lugar else []
    return circuitos


# ---------------------------------------------------------------------- Camagüey
def parse_camaguey(texto):
    circuitos = {}
    for m in re.finditer(r'[Ee]l [Cc]ircuito:\s*([A-Z0-9]+)\s*[-–]\s*([^\n]+)', texto):
        resto = re.split(r'\.\s*(?:Se trabaja|Ofrecemos)', m.group(2))[0]
        circuitos[m.group(1)] = _lugares(resto.split(","))
    return circuitos


# ---------------------------------------------------------------- Ciego de Ávila
def parse_ciego_de_avila(texto):
    circuitos = {}
    for m in re.finditer(r'sin servicio el[eé]ctrico el circuito ([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ ]+?)(?:\s+por|\s*,|\s*\n|$)', texto, re.I):
        nombre = _limpiar(m.group(1))
        if nombre and len(nombre) < 50:
            _add(circuitos, "ciego-de-avila", nombre)
    return circuitos


# ------------------------------------------------------------------------ Granma
def parse_granma(texto):
    circuitos = {}
    sec = re.search(r'mayor tiempo de afectaci[óo]n:?\s*\n((?:[•\-\*]\s*[^\n]+\n?)+)', texto, re.I)
    if sec:
        for linea in sec.group(1).strip().split("\n"):
            nombre = _limpiar(re.sub(r'^[•\-\*]\s*', '', linea))
            if nombre and len(nombre) < 60:
                _add(circuitos, "granma", nombre)
    return circuitos


# ----------------------------------------------------------------------- Holguín
def parse_holguin(texto):
    circuitos = {}
    for m in re.finditer(r'📌\s*(.+?)\s*[-–]\s*\d+:\d+\s*Horas', texto, re.I):
        nombre = re.sub(r'\(.*?\)', '', _limpiar(m.group(1))).strip()
        if nombre and len(nombre) < 60:
            _add(circuitos, "holguin", nombre)
    # Formato corto: "Cto 17 y Cto Aeropuerto 1."
    for m in re.finditer(r'\b[Cc]to\.?\s+([A-ZÁÉÍÓÚÑa-záéíóúñ0-9 ]+?)(?=\s*(?:y\s+[Cc]to|[,.]|\n|$))', texto):
        nombre = _limpiar(m.group(1))
        if nombre and len(nombre) < 40 and "hora" not in nombre.lower():
            _add(circuitos, "holguin", nombre)
    return circuitos


# --------------------------------------------------------------------- Las Tunas
def parse_las_tunas(texto):
    circuitos = {}
    # El id DEBE contener un dígito (antes capturaba la palabra "Circuito")
    for m in re.finditer(r'circuito:\s*((?=[A-Z0-9]*\d)[A-Z0-9]+)\s*([^\n]*)', texto, re.I):
        lugar = limpiar_lugar(_limpiar(m.group(2)))
        circuitos[m.group(1)] = [lugar] if lugar else []
    return circuitos


# --------------------------------------------------------------------- Mayabeque
_MAY_RUIDO = re.compile(r'(afectaci|deficit|d[eé]ficit|capacidad|MW|disculp|trabaj|gracias|informa|servicio|restabl|horas?\b|cierre)', re.I)

def parse_mayabeque(texto):
    circuitos = {}
    if "se afecta el servicio en" not in texto.lower():
        return circuitos
    idx = texto.lower().find("se afecta el servicio en")
    seccion = texto[idx + len("se afecta el servicio en"):]
    for m in re.finditer(r'^[^a-zA-Záéíóúñ\d]*([A-ZÁÉÍÓÚÑ0-9][^\n]{2,58})', seccion, re.M):
        nombre = _limpiar(m.group(1))
        if not nombre or len(nombre) >= 60 or _MAY_RUIDO.search(nombre) or len(nombre.split()) > 6:
            continue
        _add(circuitos, "mayabeque", nombre)
    return circuitos


# ------------------------------------------------------------------ Sancti Spíritus
def parse_sancti_spiritus(texto):
    circuitos = {}
    for m in re.finditer(r'👉\s*[Cc]ircuito\s+(\d+)\s+de\s+([^\n(]+)', texto):
        lugar = limpiar_lugar(_limpiar(m.group(2)))
        circuitos[m.group(1)] = [lugar] if lugar else []
    for m in re.finditer(r'[-–]\s*[Cc]ircuito\s+(\d+)\s+de\s+([^:]+):', texto):
        lugar = limpiar_lugar(_limpiar(m.group(2)))
        circuitos.setdefault(m.group(1), [lugar] if lugar else [])
    return circuitos


# ----------------------------------------------------------------- Santiago de Cuba
def parse_santiago_de_cuba(texto):
    circuitos = {}
    for m in re.finditer(r'(?:el circuito|la l[íi]nea)\s+(\d+)\s+(?:de\s+)?([^,.\n]+?)(?=\s+y la l[íi]nea|[,.\n]|$)', texto, re.I):
        lugar = limpiar_lugar(_limpiar(m.group(2)))   # recorta "y la línea ...", "se encuentra ..."
        circuitos[m.group(1)] = [lugar] if lugar else []
    return circuitos


# -------------------------------------------------------------------- Villa Clara
_VC_CTOS = re.compile(r'👉\s*[Cc]tos?\.?\s+(\d+(?:\s*(?:,|y|e)\s*\d+)*)\s+([^\n]+)')

def parse_villa_clara(texto):
    circuitos = {}
    municipio_actual = ""
    for linea in texto.split("\n"):
        mm = re.search(r'[Mm]unicipio\s+([^:]+):', linea)
        if mm:
            municipio_actual = _limpiar(mm.group(1))
        m = _VC_CTOS.search(linea)
        if m:
            nums = re.findall(r'\d+', m.group(1))
            lugar = limpiar_lugar(_limpiar(m.group(2)))
            for n in nums:
                circuitos[n] = [lugar] if lugar else ([municipio_actual] if municipio_actual else [])
    return circuitos


# ----------------------------------------------------------------------- Matanzas
def parse_matanzas_restaurados(texto):
    """Matanzas solo publica circuitos RESTABLECIDOS con nombre."""
    circuitos = {}
    for m in re.finditer(r'[Cc]ircuito\s+([A-Z0-9]+)\s+que da servicio a\s+([^\n.]+)', texto):
        circuitos[m.group(1)] = _lugares(m.group(2).split(","))
    return circuitos


# ---------------------------------------------------------------------- La Habana
def parse_la_habana(texto):
    circuitos = {}
    for m in re.finditer(r'👉\s*([A-Z0-9]+)\s*:\s*([^\n👉✅]+)', texto):
        desc = _limpiar(m.group(2))
        mun = re.search(r'\(([^)]+)\)', desc)
        lugar = limpiar_lugar(mun.group(1).strip() if mun else desc[:50])
        if lugar:
            circuitos[m.group(1)] = [lugar]
    for m in re.finditer(r'✅\s*([A-Z0-9]+)\s*\(([^)]+)\)', texto):
        lugar = limpiar_lugar(_limpiar(m.group(2)))
        if lugar:
            circuitos.setdefault(m.group(1), [lugar])
    return circuitos


PARSERS = {
    "cienfuegos": parse_cienfuegos,
    "artemisa": parse_artemisa,
    "camaguey": parse_camaguey,
    "ciego-de-avila": parse_ciego_de_avila,
    "granma": parse_granma,
    "holguin": parse_holguin,
    "las-tunas": parse_las_tunas,
    "mayabeque": parse_mayabeque,
    "sancti-spiritus": parse_sancti_spiritus,
    "santiago-de-cuba": parse_santiago_de_cuba,
    "villa-clara": parse_villa_clara,
    "la-habana": parse_la_habana,
}

# Provincias SIN parser de afectados: el mapa NO debe mostrar "con servicio" (verde)
# para ellas, porque no sabemos nada. El estado lleva fuente_afectados=false.
SIN_AFECTADOS = {"matanzas", "pinar-del-rio", "guantanamo"}


def _norm_id(s):
    """Clave de comparación para tiempos/causas (sin acentos, sin 'cto')."""
    s = fold(s)
    s = re.sub(r'^(cto\.?|circuito)\s+', '', s)
    return re.sub(r'\s+', ' ', s)


def extraer_info_extra(texto, prov=None):
    """
    Extrae del mensaje: mw, hora_inicio, cierre, tiempos{id}, causas{id}.
    Con prov se canonizan los nombres igual que los parsers (clave consistente).
    """
    info = {"mw": None, "hora_inicio": None, "cierre": None, "tiempos": {}, "causas": {}}

    m = re.search(r'(\d+)\s*MW', texto)
    if m:
        info["mw"] = int(m.group(1))
    m = re.search(r'a partir de las\s*([\d:]+\s*[AP]\.?M\.?)', texto, re.I)
    if m:
        info["hora_inicio"] = m.group(1).strip().rstrip('.')
    m = re.search(r'con cierre(?:\s*a las)?\s*([\d:]+\s*(?:[AP]\.?M\.?|[PpAa][Mm])?)', texto, re.I)
    if m:
        info["cierre"] = m.group(1).strip().rstrip('.')

    def clave(nombre):
        ids = expandir_ids(prov, nombre) if prov else [nombre]
        return [_norm_id(i) for i in ids]

    # "📌Cto Uñas 1- 48:39 Horas(Avería)"
    for m in re.finditer(r'[📌✅]\s*(?:Cto\.?\s+)?(.+?)\s*[-–]\s*(\d+):(\d+)\s*horas?', texto, re.I):
        nombre = re.sub(r'\(.*?\)', '', _limpiar(m.group(1))).strip()
        if not nombre or len(nombre) > 60:
            continue
        resto = texto[m.end():m.end() + 20]
        for key in clave(nombre):
            info["tiempos"][key] = f"{m.group(2)}:{m.group(3)}"
            if re.match(r'\s*\(aver[ií]a\)', resto, re.I):
                info["causas"][key] = "avería"

    # "✅R454 (Guanabacoa) 10horas y 25minutos" (La Habana)
    for m in re.finditer(r'[✅📌]\s*([A-Z]{1,4}\d{1,4})\s*(?:\([^)]*\))?\s*(\d+)\s*horas?\s*y\s*(\d+)\s*min', texto, re.I):
        info["tiempos"][_norm_id(m.group(1))] = f"{m.group(2)}h {m.group(3)}min"
    return info


# Mensaje que declara que NO hay afectaciones (cierra la lista de afectados anterior)
SIN_AFECTACION = re.compile(
    r'(sin afectaciones|no (?:hay|existen|se reportan) afectaciones|'
    r'servicio (?:el[eé]ctrico )?restablecido en (?:su )?totalidad|'
    r'todos los circuitos (?:han sido |fueron )?restablecidos)', re.I)


def detectar_tipo(texto):
    """
    "programado" (futuro) o "actual". Heurística heredada: NO verificada contra
    mensajes reales (ver pendientes en README_IA.md). Conservada tal cual a propósito.
    """
    t = texto.lower()
    futuros = [
        "serán afectados", "seran afectados", "será afectado", "sera afectado",
        "se afectará", "se afectara", "próxim", "proxim", "programa", "planifica",
        "a continuación", "a continuacion",
    ]
    if any(k in t for k in futuros):
        return "programado"
    return "actual"
