"""
Parsers de circuitos afectados por provincia.
Cada parser recibe el texto de un mensaje y devuelve {circuito_id: [lugares]}.
"""
import re

def _limpiar(s):
    s = re.sub(r'[⚡⚠❓🔴🟢▶️👉➡️📌🔹✳⚜️🚨*_\-]', '', s).strip()
    s = re.sub(r'\s+', ' ', s)
    return s.strip(" .:;-\n\"'")

def parse_cienfuegos(texto):
    circuitos = {}
    patron = re.compile(r'[?¿]?\s*\bC[-_ ]?(\d{1,4})\b\s*([^C\n]{0,250}?)(?=[?¿]?\s*\bC[-_ ]?\d{1,4}\b|$)', re.IGNORECASE)
    for m in patron.finditer(texto):
        lugares = [_limpiar(l) for l in m.group(2).split(",")]
        lugares = [l for l in lugares if l and len(l) < 60 and not re.search(r'(afectaci|deficit|capacidad|generaci|MW|restablec|disculp)', l, re.I)]
        if lugares:
            circuitos[f"C-{m.group(1)}"] = lugares
    return circuitos

def parse_artemisa(texto):
    circuitos = {}
    if "afectados por d" not in texto.lower() and "ficit de generaci" not in texto.lower():
        return circuitos
    for m in re.finditer(r'➡️\s*(\d{2,5})\s*([^\n➡️]*)', texto):
        lugar = _limpiar(m.group(2))
        # Filtrar notas como "(manipulado)" que no son lugares
        if re.fullmatch(r'\(?[^a-zA-Záéíóúñ]*\)?', lugar) or "manipulado" in lugar.lower():
            lugar = ""
        circuitos[m.group(1)] = [lugar] if lugar else []
    return circuitos

def parse_camaguey(texto):
    circuitos = {}
    for m in re.finditer(r'[Ee]l [Cc]ircuito:\s*([A-Z0-9]+)\s*[-–]\s*([^\n]+)', texto):
        # Cortar en el primer punto seguido de texto de disculpa
        resto = re.split(r'\.\s*(?:Se trabaja|Ofrecemos)', m.group(2))[0]
        lugares = [_limpiar(l) for l in resto.split(",")]
        lugares = [l for l in lugares if l]
        circuitos[m.group(1)] = lugares
    return circuitos

def parse_ciego_de_avila(texto):
    circuitos = {}
    for m in re.finditer(r'sin servicio el[eé]ctrico el circuito ([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ ]+?)(?:\s+por|\s*,|\s*\n|$)', texto, re.I):
        nombre = _limpiar(m.group(1))
        if nombre and len(nombre) < 50:
            circuitos[nombre] = []
    return circuitos

def parse_granma(texto):
    circuitos = {}
    # Usar la lista de "mayor tiempo de afectación" como fuente de verdad
    sec = re.search(r'mayor tiempo de afectaci[óo]n:?\s*\n((?:[•\-\*]\s*[^\n]+\n?)+)', texto, re.I)
    if sec:
        for linea in sec.group(1).strip().split("\n"):
            nombre = _limpiar(re.sub(r'^[•\-\*]\s*', '', linea))
            if nombre and len(nombre) < 60:
                circuitos[nombre] = []
    return circuitos

def parse_holguin(texto):
    circuitos = {}
    for m in re.finditer(r'📌\s*(.+?)\s*[-–]\s*\d+:\d+\s*Horas', texto, re.I):
        nombre = _limpiar(m.group(1))
        nombre = re.sub(r'\(.*?\)', '', nombre).strip()
        if nombre and len(nombre) < 60:
            circuitos[nombre] = []
    # Formato corto: Cto 17 y Cto Aeropuerto 1.
    for m in re.finditer(r'\b[Cc]to\.?\s+([A-ZÁÉÍÓÚÑa-záéíóúñ0-9 ]+?)(?=\s*(?:y\s+[Cc]to|[,.]|\n|$))', texto):
        nombre = _limpiar(m.group(1))
        if nombre and len(nombre) < 40 and "hora" not in nombre.lower():
            circuitos[nombre] = []
    return circuitos

def parse_las_tunas(texto):
    circuitos = {}
    for m in re.finditer(r'circuito:\s*([A-Z0-9]+)\s*([^\n]*)', texto, re.I):
        lugar = _limpiar(m.group(2))
        circuitos[m.group(1)] = [lugar] if lugar else []
    return circuitos

def parse_mayabeque(texto):
    circuitos = {}
    if "se afecta el servicio en" not in texto.lower():
        return circuitos
    # Líneas que empiezan con * después del keyword
    idx = texto.lower().find("se afecta el servicio en")
    seccion = texto[idx:]
    for m in re.finditer(r'^\s*\*\s*([^\n*]+)', seccion, re.M):
        nombre = _limpiar(m.group(1))
        if nombre and len(nombre) < 60 and not re.search(r'(afectaci|deficit|capacidad|MW)', nombre, re.I):
            circuitos[nombre] = []
    return circuitos

def parse_sancti_spiritus(texto):
    circuitos = {}
    for m in re.finditer(r'👉\s*[Cc]ircuito\s+(\d+)\s+de\s+([^\n(]+)', texto):
        lugar = _limpiar(m.group(2))
        circuitos[m.group(1)] = [lugar] if lugar else []
    for m in re.finditer(r'[-–]\s*[Cc]ircuito\s+(\d+)\s+de\s+([^:]+):', texto):
        lugar = _limpiar(m.group(2))
        circuitos.setdefault(m.group(1), [lugar] if lugar else [])
    return circuitos

def parse_santiago_de_cuba(texto):
    circuitos = {}
    for m in re.finditer(r'(?:el circuito|la l[íi]nea)\s+(\d+)\s+(?:de\s+)?([^,.\n]+)', texto, re.I):
        lugar = _limpiar(m.group(2))
        if "manipulaci" not in lugar.lower():
            circuitos[m.group(1)] = [lugar] if lugar else []
    return circuitos

def parse_villa_clara(texto):
    circuitos = {}
    municipio_actual = ""
    for linea in texto.split("\n"):
        mm = re.search(r'[Mm]unicipio\s+([^:]+):', linea)
        if mm:
            municipio_actual = _limpiar(mm.group(1))
        m = re.search(r'👉\s*[Cc]tos?\.?\s+([\d,\s]+(?:y\s+\d+)?)\s+([^\n]+)', linea)
        if m:
            nums = re.findall(r'\d+', m.group(1))
            lugar = _limpiar(m.group(2))
            for n in nums:
                circuitos[n] = [lugar] if lugar else ([municipio_actual] if municipio_actual else [])
    return circuitos

def parse_matanzas_restaurados(texto):
    """Matanzas solo publica circuitos RESTABLECIDOS con nombre."""
    circuitos = {}
    for m in re.finditer(r'[Cc]ircuito\s+([A-Z0-9]+)\s+que da servicio a\s+([^\n.]+)', texto):
        lugares = [_limpiar(l) for l in m.group(2).split(",")]
        lugares = [l for l in lugares if l]
        circuitos[m.group(1)] = lugares
    return circuitos

def parse_la_habana(texto):
    circuitos = {}
    # Formato 1: 👉AL52: Zonas: 6; 7; 8... / 👉2073: Calle 256...
    for m in re.finditer(r'👉\s*([A-Z0-9]+)\s*:\s*([^\n👉✅]+)', texto):
        desc = _limpiar(m.group(2))
        # Extraer municipio entre paréntesis si existe
        mun = re.search(r'\(([^)]+)\)', desc)
        lugar = mun.group(1).strip() if mun else desc[:50]
        if lugar and len(lugar) < 60:
            circuitos[m.group(1)] = [lugar]
    # Formato 2: ✅D740 (Lisa) 13 horas...
    for m in re.finditer(r'✅\s*([A-Z0-9]+)\s*\(([^)]+)\)', texto):
        lugar = _limpiar(m.group(2))
        if lugar and len(lugar) < 50:
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

# Provincias sin parser de afectados (inactivas o sin formato)
SIN_AFECTADOS = {"matanzas", "pinar-del-rio", "guantanamo"}

def _norm_id(s):
    """Normaliza un ID de circuito para comparar (minúsculas, sin prefijos)."""
    s = s.lower().strip()
    s = re.sub(r'^(cto\.?|circuito)\s+', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s

def extraer_info_extra(texto):
    """
    Extrae información adicional del mensaje:
    - mw: MW afectados/servidos (int)
    - hora_inicio: "a partir de las 3:07 AM"
    - cierre: "con cierre a las 4:11 PM"
    - tiempos: {id_normalizado: "48:39" o "10h 25min"}
    - causas: {id_normalizado: "avería"}
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

    # Patrón "📌Cto Uñas 1- 48:39 Horas(Avería)" (Holguín y similares)
    for m in re.finditer(r'[📌✅]\s*(?:Cto\.?\s+)?(.+?)\s*[-–]\s*(\d+):(\d+)\s*horas?', texto, re.I):
        nombre = _limpiar(m.group(1))
        nombre = re.sub(r'\(.*?\)', '', nombre).strip()
        if not nombre or len(nombre) > 60:
            continue
        key = _norm_id(nombre)
        info["tiempos"][key] = f"{m.group(2)}:{m.group(3)}"
        # ¿(Avería) después?
        resto = texto[m.end():m.end()+20]
        if re.match(r'\s*\(aver[ií]a\)', resto, re.I):
            info["causas"][key] = "avería"

    # Patrón "✅R454 (Guanabacoa) 10horas y 25minutos" (La Habana)
    for m in re.finditer(r'[✅📌]\s*([A-Z]{1,4}\d{1,4})\s*(?:\([^)]*\))?\s*(\d+)\s*horas?\s*y\s*(\d+)\s*min', texto, re.I):
        key = _norm_id(m.group(1))
        info["tiempos"][key] = f"{m.group(2)}h {m.group(3)}min"

    return info

def detectar_tipo(texto):
    """
    Detecta si el reporte es de apagones ACTUALES o PROGRAMADOS (futuros).
    Devuelve "programado" o "actual".
    """
    t = texto.lower()
    # Futuro / programado
    futuros = [
        "serán afectados", "seran afectados",
        "será afectado", "sera afectado",
        "se afectará", "se afectara",
        "próxim", "proxim",
        "programa", "planifica",
        "a continuación", "a continuacion",
    ]
    if any(k in t for k in futuros):
        return "programado"
    return "actual"
