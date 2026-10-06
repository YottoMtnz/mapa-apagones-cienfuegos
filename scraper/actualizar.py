"""
Scraper multi-provincia de apagones en Cuba.
Lee los últimos mensajes de cada canal, extrae circuitos afectados
y actualiza data/estado_<prov>.json

Variables de entorno:
  TG_SESSION  - session string de Telethon
  TG_API_ID   - api_id de my.telegram.org
  TG_API_HASH - api_hash de my.telegram.org
"""
import os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parsers import PARSERS, parse_matanzas_restaurados, detectar_tipo, extraer_info_extra, _norm_id
from datetime import datetime, timezone

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

def main():
    sesion = os.environ.get("TG_SESSION", "").strip()
    api_id = os.environ.get("TG_API_ID", "").strip()
    api_hash = os.environ.get("TG_API_HASH", "").strip()
    if not (sesion and api_id and api_hash):
        print("ERROR: faltan TG_SESSION, TG_API_ID o TG_API_HASH")
        sys.exit(1)

    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession

    ahora = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)

    with TelegramClient(StringSession(sesion), int(api_id), api_hash) as client:
        for prov, canal in CANALES.items():
            afectados = {}
            programados = {}
            fecha_reporte = None
            fecha_programado = None
            total_leidos = 0
            # Info extra del reporte actual
            mw = None; hora_inicio = None; cierre = None
            tiempos = {}; causas = {}
            try:
                for msg in client.iter_messages(canal, limit=50):
                    total_leidos += 1
                    if not msg.text:
                        continue
                    if prov in PARSERS:
                        r = PARSERS[prov](msg.text)
                    elif prov == "matanzas":
                        # Matanzas no publica afectados por nombre; se omite
                        r = {}
                    else:
                        r = {}
                    if r:
                        tipo = detectar_tipo(msg.text)
                        if tipo == "programado" and not programados:
                            programados = r
                            fecha_programado = msg.date.astimezone(timezone.utc).isoformat()
                        elif tipo == "actual" and not afectados:
                            afectados = r
                            fecha_reporte = msg.date.astimezone(timezone.utc).isoformat()
                            # Extraer MW, tiempos, causas, horarios del reporte
                            extra = extraer_info_extra(msg.text)
                            mw = extra["mw"]; hora_inicio = extra["hora_inicio"]; cierre = extra["cierre"]
                            # Mapear tiempos/causas a los IDs reales del parser
                            for cid in r:
                                nk = _norm_id(cid)
                                if nk in extra["tiempos"]:
                                    tiempos[cid] = extra["tiempos"][nk]
                                if nk in extra["causas"]:
                                    causas[cid] = extra["causas"][nk]
                    if afectados and programados:
                        break
            except Exception as e:
                print(f"ERROR {prov}: {type(e).__name__}")
            estado = {
                "actualizado": ahora,
                "reporte_fecha": fecha_reporte,
                "programado_fecha": fecha_programado,
                "mensajes_leidos": total_leidos,
                "afectados": afectados,
                "programados": programados,
                "total_circuitos_afectados": len(afectados),
                "total_circuitos_programados": len(programados),
                "mw": mw,
                "hora_inicio": hora_inicio,
                "cierre": cierre,
                "tiempos": tiempos,
                "causas": causas,
            }
            path = os.path.join(BASE, "data", f"estado_{prov}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(estado, f, ensure_ascii=False, indent=2)
            print(f"{prov}: {len(afectados)} afectados, {len(programados)} programados")

    # Compatibilidad: estado.json = Cienfuegos
    import shutil
    shutil.copy(
        os.path.join(BASE, "data", "estado_cienfuegos.json"),
        os.path.join(BASE, "data", "estado.json"),
    )
    print("OK")

if __name__ == "__main__":
    main()
