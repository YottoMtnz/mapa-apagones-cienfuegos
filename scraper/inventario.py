"""
Actualiza el inventario de circuitos por provincia (capa ESTÁTICA, manual/ocasional).
Lee 100 mensajes por canal, extrae circuitos con los parsers y los FUSIONA con
data/inventario.json (nunca borra lo que ya había; un fallo de red no vacía la provincia).
Uso: python3 scraper/inventario.py     (requiere TG_SESSION, TG_API_ID, TG_API_HASH)
Después: python3 scraper/geocodificar.py   (ubica los circuitos nuevos)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parsers import PARSERS, parse_matanzas_restaurados
from provincias import PROVINCIAS
from actualizar import CANALES
import catalogo as cat


def main():
    sesion = os.environ.get("TG_SESSION", "").strip()
    api_id = os.environ.get("TG_API_ID", "").strip()
    api_hash = os.environ.get("TG_API_HASH", "").strip()
    if not (sesion and api_id and api_hash):
        sys.exit("ERROR: faltan credenciales")
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession

    inventario = cat.cargar_json("inventario.json", {})
    with TelegramClient(StringSession(sesion), int(api_id), api_hash) as client:
        for prov in ["cienfuegos"]:
            parser = parse_matanzas_restaurados if prov == "matanzas" else PARSERS.get(prov)
            if not parser:
                continue
            try:
                nuevos = {}
                for msg in client.iter_messages(CANALES[prov], limit=100):
                    if msg.text:
                        for cid, lugares in parser(msg.text).items():
                            previos = nuevos.setdefault(cid, [])
                            previos += [l for l in lugares if l not in previos]
            except Exception as e:
                print(f"{prov}: ERROR {type(e).__name__} (se conserva el inventario previo)")
                continue
            destino = inventario.setdefault(prov, {})
            for cid, lugares in nuevos.items():
                previos = destino.setdefault(cid, [])
                previos += [l for l in lugares if l not in previos]
            print(f"{prov}: {len(nuevos)} vistos, {len(destino)} en inventario")
    cat.guardar_json("inventario.json", inventario)
    print("OK -> data/inventario.json")


if __name__ == "__main__":
    main()
