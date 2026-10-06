"""
Scraper de canales Empresa Eléctrica (Cienfuegos y Matanzas).
Lee los últimos mensajes, extrae circuitos afectados y actualiza data/estado.json.

Variables de entorno:
  TG_SESSION  - session string de Telethon
  TG_API_ID   - api_id de my.telegram.org
  TG_API_HASH - api_hash de my.telegram.org
  MODO_MUESTRAS - si es "1", solo guarda muestras crudas de Matanzas
"""
import os, re, json, sys
from datetime import datetime, timezone

CANALES = {
    "cienfuegos": "empresaelectricacienfuegos1",
    "matanzas": "EmpresaElectricaMatanzas",
}
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def parsear_circuitos_cf(texto):
    """Cienfuegos: C-47 Elpidio Gómez, Altamira..."""
    circuitos = {}
    patron = re.compile(r'[?¿]?\s*\bC[-_ ]?(\d{1,4})\b\s*([^C\n]{0,250}?)(?=[?¿]?\s*\bC[-_ ]?\d{1,4}\b|$)', re.IGNORECASE)
    for m in patron.finditer(texto):
        num = m.group(1)
        resto = m.group(2).strip(" .:;-\n")
        resto = re.sub(r'[⚡⚠❓🔴🟢▶️*_\-]', '', resto).strip()
        lugares = [l.strip(" .") for l in resto.split(",") if l.strip(" .")]
        lugares = [l for l in lugares if len(l) < 60 and not re.search(r'(afectaci|deficit|capacidad|generaci|MW|restablec|disculp)', l, re.I)]
        if lugares:
            circuitos[f"C-{num}"] = lugares
    return circuitos

def es_reporte_afectados(texto):
    t = texto.lower()
    return any(k in t for k in ["afectados por d", "circuitos afectados", "actualizaci", "deficit de capacidad", "se afecta", "avería", "averia"])

def main():
    sesion = os.environ.get("TG_SESSION", "").strip()
    api_id = os.environ.get("TG_API_ID", "").strip()
    api_hash = os.environ.get("TG_API_HASH", "").strip()
    if not (sesion and api_id and api_hash):
        print("ERROR: faltan TG_SESSION, TG_API_ID o TG_API_HASH")
        sys.exit(1)

    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession

    modo_muestras = True  # siempre guardar muestras de Matanzas por ahora
    resultado = {
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "provincias": {},
    }

    with TelegramClient(StringSession(sesion), int(api_id), api_hash) as client:
        for prov, canal in CANALES.items():
            afectados = {}
            fecha_reporte = None
            total_leidos = 0
            muestras = []
            for msg in client.iter_messages(canal, limit=30):
                total_leidos += 1
                if not msg.text:
                    continue
                if modo_muestras and prov == "matanzas" and len(muestras) < 8:
                    muestras.append({
                        "fecha": msg.date.astimezone(timezone.utc).isoformat(),
                        "texto": msg.text[:1500],
                    })
                if not afectados and es_reporte_afectados(msg.text):
                    if prov == "cienfuegos":
                        circuitos = parsear_circuitos_cf(msg.text)
                    else:
                        circuitos = {}  # parser de Matanzas pendiente
                    if circuitos:
                        afectados = circuitos
                        fecha_reporte = msg.date.astimezone(timezone.utc).isoformat()
            resultado["provincias"][prov] = {
                "fuente": f"https://t.me/{canal}",
                "reporte_fecha": fecha_reporte,
                "mensajes_leidos": total_leidos,
                "afectados": afectados,
                "total_circuitos_afectados": len(afectados),
            }
            if muestras:
                with open(os.path.join(BASE, "data", "muestras_matanzas.json"), "w", encoding="utf-8") as f:
                    json.dump(muestras, f, ensure_ascii=False, indent=2)
                print(f"Muestras Matanzas guardadas: {len(muestras)}")

    # Compatibilidad: estado.json mantiene formato anterior para Cienfuegos
    cf = resultado["provincias"]["cienfuegos"]
    estado_cf = {
        "actualizado": resultado["actualizado"],
        "fuente": cf["fuente"],
        "reporte_fecha": cf["reporte_fecha"],
        "mensajes_leidos": cf["mensajes_leidos"],
        "afectados": cf["afectados"],
        "total_circuitos_afectados": cf["total_circuitos_afectados"],
    }
    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
    with open(os.path.join(BASE, "data", "estado.json"), "w", encoding="utf-8") as f:
        json.dump(estado_cf, f, ensure_ascii=False, indent=2)
    with open(os.path.join(BASE, "data", "estado_provincias.json"), "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"OK: CF={len(cf['afectados'])} circuitos")

if __name__ == "__main__":
    main()
