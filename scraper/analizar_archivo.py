"""Diagnóstico offline de un estudio íntegro; no modifica el estado del mapa."""
import argparse,json
from datetime import datetime,timezone
from actualizar import analizar_mensajes

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archivo',help='JSON con lista de mensajes o clave cienfuegos')
    ap.add_argument('--fecha',help='Instante de la simulación en ISO 8601; por defecto ahora')
    args=ap.parse_args()
    with open(args.archivo,encoding='utf-8') as f: datos=json.load(f)
    mensajes=datos.get('cienfuegos',[]) if isinstance(datos,dict) else datos
    if not isinstance(mensajes,list): raise SystemExit('Se esperaba una lista de mensajes')
    for m in mensajes:
        # Exportaciones antiguas del proyecto recortaban el cuerpo sin avisar.
        if isinstance(m,dict) and 'id' not in m and len(m.get('texto','')) in (800,1200,1500):
            m['truncado']=True
    ahora=datetime.fromisoformat(args.fecha.replace('Z','+00:00')) if args.fecha else datetime.now(timezone.utc)
    if ahora.tzinfo is None: ahora=ahora.replace(tzinfo=timezone.utc)
    print(json.dumps(analizar_mensajes('cienfuegos',mensajes,ahora),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
