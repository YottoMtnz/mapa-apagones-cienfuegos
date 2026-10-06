"""
Scraper del canal Empresa Eléctrica Cienfuegos (@empresaelectricacienfuegos1).
Lee los últimos mensajes, extrae circuitos afectados y actualiza data/estado.json.

Variables de entorno:
  TG_SESSION  - session string de Telethon
  TG_API_ID   - api_id de my.telegram.org
  TG_API_HASH - api_hash de my.telegram.org
"""
import os, re, json, sys
from datetime import datetime, timezone

CANAL = "empresaelectricacienfuegos1"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTADO_PATH = os.path.join(BASE, "data", "estado.json")

def parsear_circuitos(texto):
    """Extrae {circuito: [lugares]} de un mensaje del canal."""
    circuitos = {}
    # Ej: "C-47 Elpidio Gómez, Altamira, La Peseta." / "?C-42 Viet Nam, Real Campiña, Guanito."
    patron = re.compile(r'[?¿]?\s*\bC[-_ ]?(\d{1,4})\b\s*([^C\n]{0,250}?)(?=[?¿]?\s*\bC[-_ ]?\d{1,4}\b|$)', re.IGNORECASE)
    for m in patron.finditer(texto):
        num = m.group(1)
        resto = m.group(2).strip(" .:;-\n")
        resto = re.sub(r'[⚡⚠❓🔴🟢▶️*_\-]', '', resto).strip()
        lugares = [l.strip(" .") for l in resto.split(",") if l.strip(" .")]
        # Filtrar líneas que no son lugares (avisos generales)
        lugares = [l for l in lugares if len(l) < 60 and not re.search(r'(afectaci|deficit|capacidad|generaci|MW|restablec|disculp)', l, re.I)]
        if lugares:
            circuitos[f"C-{num}"] = lugares
    return circuitos

def es_reporte_afectados(texto):
    t = texto.lower()
    return any(k in t for k in ["afectados por d", "circuitos afectados", "actualizaci", "deficit de capacidad"])

def main():
    sesion = os.environ.get("TG_SESSION", "").strip()
    api_id = os.environ.get("TG_API_ID", "").strip()
    api_hash = os.environ.get("TG_API_HASH", "").strip()
    if not (sesion and api_id and api_hash):
        print("ERROR: faltan TG_SESSION, TG_API_ID o TG_API_HASH")
        sys.exit(1)

    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession

    afectados = {}
    fecha_reporte = None
    total_leidos = 0

    with TelegramClient(StringSession(sesion), int(api_id), api_hash) as client:
        for msg in client.iter_messages(CANAL, limit=30):
            total_leidos += 1
            if not msg.text:
                continue
            if es_reporte_afectados(msg.text):
                circuitos = parsear_circuitos(msg.text)
                if circuitos:
                    afectados = circuitos
                    fecha_reporte = msg.date.astimezone(timezone.utc).isoformat()
                    break

    estado = {
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "fuente": "https://t.me/empresaelectricacienfuegos1",
        "reporte_fecha": fecha_reporte,
        "mensajes_leidos": total_leidos,
        "afectados": afectados,
        "total_circuitos_afectados": len(afectados),
    }
    os.makedirs(os.path.dirname(ESTADO_PATH), exist_ok=True)
    with open(ESTADO_PATH, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)
    print(f"OK: {len(afectados)} circuitos afectados -> {ESTADO_PATH}")

if __name__ == "__main__":
    main()
