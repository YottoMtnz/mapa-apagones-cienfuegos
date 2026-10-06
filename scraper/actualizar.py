"""
Scraper multi-provincia de apagones en Cuba (capa DINÁMICA).
Lee los últimos mensajes de cada canal de Telegram, extrae circuitos afectados y
escribe data/estado_<prov>.json.

Variables de entorno: TG_SESSION, TG_API_ID, TG_API_HASH (GitHub Secrets).
Opcionales: MAX_EDAD_HORAS (def. 12), HEARTBEAT_MIN (def. 60).

Garantías (lo que antes fallaba):
  * Si falla la lectura de una provincia se CONSERVA su estado anterior (antes se
    sobrescribía con afectados vacíos => todo "con servicio" por un fallo de red).
  * Una lista de afectados más vieja que MAX_EDAD_HORAS se descarta (antes un reporte
    de hace días seguía en rojo). Se marca reporte_vencido=true.
  * Un mensaje posterior que dice "sin afectaciones" cierra la lista anterior.
  * estado_datos = "ok" | "sin_reporte_reciente" | "sin_fuente" | "error": el mapa solo
    pinta VERDE con "ok". Matanzas/Pinar/Guantánamo no tienen parser => "sin_fuente".
  * Solo se reescribe el archivo si cambia el contenido, o si la última marca de
    tiempo supera HEARTBEAT_MIN. Evita ~288 commits diarios sin cambios.
"""
import os, json, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone, timedelta
from parsers import PARSERS, SIN_AFECTADOS, SIN_AFECTACION, detectar_tipo, extraer_info_extra, _norm_id
from provincias import PROVINCIAS

CANALES = {
    "pinar-del-rio": "elecpinar",
    "artemisa": "EEArtemisa",
    "la-habana": "EmpresaElectricaDeLaHabana",
    "mayabeque": "electricamayabeque",
    "matanzas": "EmpresaElectricaMatanzas",
    "cienfuegos": "empresaelectricacienfuegos1",
    "villa-clara": "electrico1895",
    "sancti-spiritus": "informateessp",
    "ciego-de-avila": "eecav",
    "camaguey": "empresa_electrica",
    "las-tunas": "eleclastunas",
    "holguin": "elecholguin",
    "granma": "UNE_EEG",
    "santiago-de-cuba": "electricastgo",
    "guantanamo": "elecguantanamo",
}
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_EDAD_H = float(os.environ.get("MAX_EDAD_HORAS", "12"))
HEARTBEAT_MIN = float(os.environ.get("HEARTBEAT_MIN", "60"))


def _ruta(prov):
    return os.path.join(BASE, "data", f"estado_{prov}.json")


def leer_previo(prov):
    try:
        with open(_ruta(prov), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def analizar_mensajes(prov, mensajes, ahora):
    """
    mensajes: iterable de (texto, fecha_utc) de MÁS NUEVO a MÁS VIEJO.
    Devuelve el dict de estado (sin 'actualizado'). Función pura => testeable.
    """
    parser = PARSERS.get(prov)
    est = {
        "schema": 2, "estado_datos": "sin_reporte_reciente",
        "fuente_afectados": parser is not None,
        "reporte_fecha": None, "reporte_vencido": False, "sin_afectaciones": False,
        "programado_fecha": None, "mensajes_leidos": 0,
        "afectados": {}, "programados": {},
        "total_circuitos_afectados": 0, "total_circuitos_programados": 0,
        "mw": None, "hora_inicio": None, "cierre": None, "tiempos": {}, "causas": {},
        "error": None,
    }
    if parser is None:
        est["estado_datos"] = "sin_fuente"
        return est

    afectados_visto = False
    for texto, fecha in mensajes:
        est["mensajes_leidos"] += 1
        if not texto:
            continue
        if not afectados_visto and SIN_AFECTACION.search(texto) and not parser(texto):
            # El mensaje más reciente relevante dice que no hay afectaciones
            afectados_visto = True
            est["sin_afectaciones"] = True
            est["afectados"] = {}
            est["reporte_fecha"] = fecha.isoformat()
            continue
        r = parser(texto)
        if not r:
            continue
        # Expandir marcadores MUN:xxx a circuitos reales (inferencia lógica)
        # Ej: "MUN:vertientes" -> circuitos cuyos lugares mencionan Vertientes
        r_exp = {}
        for cid, zonas in r.items():
            if cid.startswith("MUN:"):
                mun = cid[4:].lower()
                # Buscar en catálogo circuitos con lugares que coincidan
                try:
                    cat = json.load(open(os.path.join(BASE, "data", f"circuitos_{prov}.json")))
                    for rcid, rc in cat.get("circuitos", {}).items():
                        for lug in rc.get("lugares", []):
                            # Normalizar: sin acentos, minúsculas
                            import unicodedata
                            nl = unicodedata.normalize('NFD', lug.lower()).encode('ascii', 'ignore').decode()
                            nm = unicodedata.normalize('NFD', mun).encode('ascii', 'ignore').decode()
                            if nm in nl or nl in nm:
                                if rcid not in r_exp:
                                    r_exp[rcid] = rc.get("lugares", [])
                                break
                except:
                    pass
                # Si no hay match, usar el municipio como zona genérica
                if not any(k for k in r_exp if k != cid):
                    r_exp[cid] = zonas
            else:
                r_exp[cid] = zonas
        r = r_exp
        tipo = detectar_tipo(texto)
        if tipo == "programado" and not est["programados"]:
            est["programados"] = r
            est["programado_fecha"] = fecha.isoformat()
        elif tipo == "actual":
            if not afectados_visto:
                afectados_visto = True
                est["reporte_fecha"] = fecha.isoformat()
                if ahora - fecha > timedelta(hours=MAX_EDAD_H):
                    est["reporte_vencido"] = True      # demasiado viejo: no se muestra como actual
            # Si ya se declaró "sin afectaciones", no mezclar mensajes viejos
            if est.get("sin_afectaciones"):
                continue
            if not est["reporte_vencido"]:
                # Distinguir: "Actualización" (lista completa, reemplaza)
                # vs "avería/continúan" (adicional, se suma)
                t_lower = texto.lower()
                es_actualizacion = "actualizaci" in t_lower
                # Inicializar sets de seguimiento
                if "_deficit_ids" not in est:
                    est["_deficit_ids"] = set()
                    est["_averia_ids"] = set()
                if es_actualizacion:
                    # Solo la actualización MÁS RECIENTE reemplaza.
                    # Las más viejas se ignoran (datos obsoletos).
                    if "_visto_actualizacion" not in est:
                        est["_visto_actualizacion"] = True
                        # Nueva actualización: los no listados se restablecieron
                        # Eliminar del afectados los que eran de déficit pero ya no están
                        for cid in list(est["_deficit_ids"]):
                            if cid not in r and cid in est["afectados"]:
                                del est["afectados"][cid]
                        est["_deficit_ids"] = set(r.keys())
                    # Si ya vimos una actualización más nueva, ignorar esta
                    else:
                        continue
                else:
                    # Avería: se suma
                    est["_averia_ids"].update(r.keys())
                # Merge (sin duplicar)
                for cid, zonas in r.items():
                    if cid not in est["afectados"]:
                        est["afectados"][cid] = zonas
                extra = extraer_info_extra(texto, prov)
                if est["mw"] is None:
                    est["mw"], est["hora_inicio"], est["cierre"] = extra["mw"], extra["hora_inicio"], extra["cierre"]
                for cid in r:
                    nk = _norm_id(cid)
                    if nk in extra["tiempos"] and cid not in est["tiempos"]:
                        est["tiempos"][cid] = extra["tiempos"][nk]
                    if nk in extra["causas"] and cid not in est["causas"]:
                        est["causas"][cid] = extra["causas"][nk]
        # NO hacer break aquí: seguir leyendo para combinar múltiples mensajes
        # (avería + déficit son causas distintas, ambas válidas)

    # Programados viejos (>MAX_EDAD_H) tampoco valen
    if est["programado_fecha"]:
        f = datetime.fromisoformat(est["programado_fecha"])
        if ahora - f > timedelta(hours=MAX_EDAD_H):
            est["programados"] = {}

    est["total_circuitos_afectados"] = len(est["afectados"])
    est["total_circuitos_programados"] = len(est["programados"])
    if est["reporte_fecha"] and not est["reporte_vencido"]:
        f = datetime.fromisoformat(est["reporte_fecha"])
        if ahora - f < timedelta(hours=24):
            est["estado_datos"] = "ok"
    return est


def _igual(a, b):
    ign = {"actualizado"}
    return {k: v for k, v in a.items() if k not in ign} == {k: v for k, v in b.items() if k not in ign}


def guardar(prov, est, ahora):
    # Limpiar campos internos ANTES de comparar (no van al JSON)
    est.pop("_deficit_ids", None)
    est.pop("_averia_ids", None)
    est.pop("_visto_actualizacion", None)
    previo = leer_previo(prov)
    if previo and _igual(previo, est):
        try:
            edad = ahora - datetime.fromisoformat(previo["actualizado"])
            if edad < timedelta(minutes=HEARTBEAT_MIN):
                return False                      # sin cambios y marca reciente: no tocar
        except (KeyError, ValueError):
            pass
    est["actualizado"] = ahora.isoformat()
    with open(_ruta(prov), "w", encoding="utf-8") as f:
        json.dump(est, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return True


def registrar_error(prov, ahora, motivo):
    """Conserva el estado anterior y anota el error. Sin previo, estado 'error' vacío."""
    est = leer_previo(prov) or {
        "schema": 2, "afectados": {}, "programados": {}, "tiempos": {}, "causas": {},
        "fuente_afectados": prov in PARSERS, "reporte_fecha": None,
    }
    est["error"] = motivo
    est["estado_datos"] = "error"
    est["actualizado"] = ahora.isoformat()
    with open(_ruta(prov), "w", encoding="utf-8") as f:
        json.dump(est, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    sesion = os.environ.get("TG_SESSION", "").strip()
    api_id = os.environ.get("TG_API_ID", "").strip()
    api_hash = os.environ.get("TG_API_HASH", "").strip()
    if not (sesion and api_id and api_hash):
        print("ERROR: faltan TG_SESSION, TG_API_ID o TG_API_HASH")
        sys.exit(1)

    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError

    ahora = datetime.now(timezone.utc)
    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
    fallos = 0

    with TelegramClient(StringSession(sesion), int(api_id), api_hash) as client:
        # MODO ESTUDIO: guardar muestras de mensajes por provincia
        # Se activa creando el archivo data/MODO_ESTUDIO (luego se borra)
        if os.path.exists(os.path.join(BASE, "data", "MODO_ESTUDIO")) or os.environ.get("MODO_ESTUDIO") == "1":
            muestras = {}
            for prov in ["cienfuegos"]:
                canal = CANALES.get(prov)
                if not canal:
                    continue
                try:
                    msgs = []
                    for m in client.iter_messages(canal, limit=5):
                        if m.text:
                            msgs.append({
                                "fecha": m.date.astimezone(timezone.utc).isoformat(),
                                "texto": m.text[:800]
                            })
                    muestras[prov] = msgs
                    print(f"ESTUDIO {prov}: {len(msgs)} mensajes")
                except Exception as e:
                    muestras[prov] = [{"error": str(e)}]
                    print(f"ESTUDIO {prov}: ERROR {e}")
            with open(os.path.join(BASE, "data", "estudio_canales.json"), "w") as f:
                json.dump(muestras, f, ensure_ascii=False, indent=1)
            print("Muestras guardadas en data/estudio_canales.json")
            return

        # Solo Cienfuegos (decisión de Fraudy 2026-10-06: pulir una provincia)
        for prov in ["cienfuegos"]:
            canal = CANALES.get(prov)
            if prov in SIN_AFECTADOS or prov not in PARSERS:
                est = analizar_mensajes(prov, [], ahora)
                print(f"{prov}: sin fuente de afectados ({guardar(prov, est, ahora) and 'escrito' or 'igual'})")
                continue
            for intento in (1, 2):
                try:
                    msgs = [(m.text, m.date.astimezone(timezone.utc))
                            for m in client.iter_messages(canal, limit=50)]
                    est = analizar_mensajes(prov, msgs, ahora)
                    cambio = guardar(prov, est, ahora)
                    print(f"{prov}: {len(est['afectados'])} afectados, {len(est['programados'])} programados "
                          f"[{est['estado_datos']}] {'escrito' if cambio else 'sin cambios'}")
                    break
                except FloodWaitError as e:
                    espera = min(int(e.seconds), 60)
                    print(f"{prov}: FloodWait {e.seconds}s; espero {espera}s")
                    time.sleep(espera)
                except Exception as e:
                    if intento == 2:
                        fallos += 1
                        registrar_error(prov, ahora, type(e).__name__)
                        print(f"{prov}: ERROR {type(e).__name__} (se conserva el estado anterior)")
    # Falla el job solo si TODO falló (credenciales caducadas): así se nota en Actions
    if fallos >= len([p for p in PROVINCIAS if p in PARSERS]):
        sys.exit(2)
    print("OK")


if __name__ == "__main__":
    main()
