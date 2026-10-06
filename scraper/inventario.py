"""
Extrae el inventario COMPLETO de circuitos por provincia.
Lee 100 mensajes por canal y guarda todos los circuitos únicos vistos.
Uso: python3 scraper/inventario.py (requiere TG_SESSION, TG_API_ID, TG_API_HASH)
"""
import os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parsers import PARSERS, parse_matanzas_restaurados, SIN_AFECTADOS

CANALES = {
    "pinar-del-rio": "elecpinar",
    "artemisa": "EEArtemisa",
    "la-habana": "ceelh",
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
        print("ERROR: faltan credenciales")
        sys.exit(1)

    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession

    inventario = {}
    with TelegramClient(StringSession(sesion), int(api_id), api_hash) as client:
        for prov, canal in CANALES.items():
            circuitos = {}
            try:
                for msg in client.iter_messages(canal, limit=100):
                    if not msg.text:
                        continue
                    if prov in PARSERS:
                        r = PARSERS[prov](msg.text)
                    elif prov == "matanzas":
                        r = parse_matanzas_restaurados(msg.text)
                    else:
                        continue
                    for cid, lugares in r.items():
                        if cid not in circuitos:
                            circuitos[cid] = lugares
                        elif not circuitos[cid] and lugares:
                            circuitos[cid] = lugares
                print(f"{prov}: {len(circuitos)} circuitos únicos")
            except Exception as e:
                print(f"{prov}: ERROR {type(e).__name__}")
                circuitos = {}
            inventario[prov] = circuitos

    path = os.path.join(BASE, "data", "inventario.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(inventario, f, ensure_ascii=False, indent=2)
    total = sum(len(v) for v in inventario.values())
    print(f"OK: {total} circuitos totales -> {path}")

if __name__ == "__main__":
    main()
