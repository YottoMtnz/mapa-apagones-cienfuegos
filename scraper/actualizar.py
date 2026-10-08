"""Estado eléctrico de Cienfuegos. Texto + OCR, eventos cronológicos y procedencia.
Los módulos provinciales heredados quedan para compatibilidad; main SOLO consulta Cienfuegos.
Variables: TG_SESSION, TG_API_ID, TG_API_HASH; opcionales MAX_MENSAJES, MAX_OCR_POR_CICLO.
"""
import os, json, sys, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone, timedelta
from parsers import PARSERS, SIN_AFECTADOS, SIN_AFECTACION, detectar_tipo, clasificar_mensaje, extraer_info_extra, _norm_id
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
HEARTBEAT_MIN = float(os.environ.get("HEARTBEAT_MIN", "10"))


def _ruta(prov):
    return os.path.join(BASE, "data", f"estado_{prov}.json")


def leer_previo(prov):
    try:
        with open(_ruta(prov), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def analizar_mensajes(prov, mensajes, ahora, catalogo=None):
    from motor_estado import analizar
    if catalogo is None:
        try:
            with open(os.path.join(BASE,'data',f'circuitos_{prov}.json'),encoding='utf-8') as f:
                catalogo=json.load(f).get('circuitos',{})
        except (OSError,ValueError): catalogo={}
    return analizar(prov,mensajes,ahora,catalogo,MAX_EDAD_H)


def _igual(a, b):
    ign = {"actualizado"}
    return {k: v for k, v in a.items() if k not in ign} == {k: v for k, v in b.items() if k not in ign}


def guardar(prov, est, ahora):
    # Limpiar campos internos ANTES de comparar (no van al JSON)
    est.pop("_deficit_ids", None)
    est.pop("_averia_ids", None)
    est.pop("_visto_actualizacion", None)
    est.pop("_actualizacion_fecha", None)
    est.pop("_visto_averias", None)
    est.pop("_averias_fecha", None)
    previo = leer_previo(prov)
    if previo and _igual(previo, est):
        try:
            edad = ahora - datetime.fromisoformat(previo["actualizado"])
            if edad < timedelta(minutes=HEARTBEAT_MIN):
                return False                      # sin cambios y marca reciente: no tocar
        except (KeyError, ValueError):
            pass
    est["actualizado"] = ahora.isoformat()
    with open(_ruta(prov)+".tmp", "w", encoding="utf-8") as f:
        json.dump(est, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(_ruta(prov)+".tmp",_ruta(prov))
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
    with open(_ruta(prov)+".tmp", "w", encoding="utf-8") as f:
        json.dump(est, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(_ruta(prov)+".tmp",_ruta(prov))


def main():
    sesion=os.environ.get('TG_SESSION','').strip()
    api_id=os.environ.get('TG_API_ID','').strip()
    api_hash=os.environ.get('TG_API_HASH','').strip()
    if not (sesion and api_id and api_hash):
        print('ERROR: faltan TG_SESSION, TG_API_ID o TG_API_HASH'); return 1
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError
    from lectura import leer_canal
    ahora=datetime.now(timezone.utc)
    os.makedirs(os.path.join(BASE,'data'),exist_ok=True)
    prov='cienfuegos'  # Alcance deliberado: nunca consultar otras provincias.
    try:
        client=TelegramClient(StringSession(sesion),int(api_id),api_hash,
                              timeout=25,connection_retries=2,request_retries=2,flood_sleep_threshold=0)
        client.connect()
        if not client.is_user_authorized():
            raise RuntimeError('SesionNoAutorizada')
        for intento in range(3):
            try:
                msgs=leer_canal(client,CANALES[prov],ahora,BASE)
                est=analizar_mensajes(prov,msgs,ahora)
                # Límite alcanzado: advertir que pudo faltar historial.
                if len(msgs)>=int(os.environ.get('MAX_MENSAJES','200')):
                    est['historial_limitado']=True
                if os.environ.get('MODO_ESTUDIO')=='1':
                    with open(os.path.join(BASE,'data','estudio_canales.json'),'w',encoding='utf-8') as f:
                        json.dump({prov:msgs},f,ensure_ascii=False,indent=2,default=str)
                guardar(prov,est,ahora)
                print(f"{prov}: {len(est['afectados'])} afectados, {len(est['programados'])} programados, "
                      f"{len(est['pendientes_revision'])} pendientes de revisión [{est['estado_datos']}]")
                return 0
            except FloodWaitError as e:
                # Respetar la espera completa. No recortar 2 horas a 60 segundos y reintentar.
                if e.seconds>30 or intento==2: raise
                time.sleep(e.seconds+1)
            except (OSError,TimeoutError):
                if intento==2: raise
                time.sleep(2**intento)
    except Exception as e:
        registrar_error(prov,ahora,type(e).__name__)
        print('ERROR: '+type(e).__name__+'; se conservan los datos anteriores.'); return 2
    finally:
        if 'client' in locals(): client.disconnect()
    return 2


if __name__=='__main__':
    sys.exit(main())
