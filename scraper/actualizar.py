"""Estado eléctrico de Cienfuegos. Texto + OCR, eventos cronológicos y procedencia.
Los módulos provinciales heredados quedan para compatibilidad; main SOLO consulta Cienfuegos.
Variables: TG_SESSION, TG_API_ID, TG_API_HASH; opcionales MAX_MENSAJES, MAX_OCR_POR_CICLO.
"""
import os, json, sys, time
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
    """Reproduce eventos por fecha de publicación (las ediciones sustituyen el contenido).
    Acepta tuplas antiguas o registros con texto/fecha/id/url/ocr. Nunca vence a verde.
    """
    from interpretador import interpretar
    if catalogo is None:
        try:
            with open(os.path.join(BASE,'data',f'circuitos_{prov}.json'),encoding='utf-8') as f:
                catalogo=json.load(f).get('circuitos',{})
        except (OSError,ValueError): catalogo={}
    est={"schema":3,"estado_datos":"sin_reporte_reciente","fuente_afectados":prov in PARSERS,
         "reporte_fecha":None,"reporte_vencido":False,"sin_afectaciones":False,
         "programado_fecha":None,"mensajes_leidos":0,"afectados":{},"programados":{},
         "confirmados_con_servicio":{},"evidencias":{},"horarios":{},"cobertura":"parcial",
         "mw":None,"hora_inicio":None,"cierre":None,"tiempos":{},"causas":{},"error":None,
         "pendientes_revision":[],"lectura":{"texto":0,"imagenes":0,"pdf":0,"no_leidos":0}}
    if prov not in PARSERS:
        est['estado_datos']='sin_fuente'; return est
    registros=[]
    for ix,m in enumerate(mensajes):
        if isinstance(m,dict): r=dict(m)
        else: r={'texto':m[0] or '', 'fecha':m[1]}
        f=r.get('fecha')
        if isinstance(f,str): f=datetime.fromisoformat(f.replace('Z','+00:00'))
        if not f: continue
        if f.tzinfo is None: f=f.replace(tzinfo=timezone.utc)
        r['fecha']=f; r.setdefault('id',ix); registros.append(r)
    registros.sort(key=lambda r:(r['fecha'],r['id']))
    activos={}; verdes={}; planes={}; evidencia={}; ultima=None; ultima_global=None
    snapshot_grupos={}
    for r in registros:
        fecha=r['fecha']; est['mensajes_leidos']+=1
        medio=r.get('medio','texto'); est['lectura'][medio if medio in ('texto','imagenes','pdf') else 'texto']+=1
        if r.get('error_lectura'):
            est['lectura']['no_leidos']+=1
            est['lectura_incompleta_desde']=fecha.isoformat()
            est['pendientes_revision'].append({'id':r['id'],'url':r.get('url'),'fecha':fecha.isoformat(),'motivo':r['error_lectura']})
        if fecha>ahora+timedelta(minutes=5): continue
        texto=r.get('texto','')
        eventos,pendientes=interpretar(prov,texto,fecha,catalogo)
        for q in pendientes:
            est['pendientes_revision'].append({**q,'id':r['id'],'url':r.get('url'),'fecha':fecha.isoformat()})
        for ev in eventos:
            action=ev['accion']; ids=ev['circuitos']; scope=ev['alcance']
            if r.get('error_lectura'):
                ev['completa']=False
                if action=='sin_afectacion': continue
            if medio in ('imagenes','pdf') and r.get('confianza',100)<100:
                desconocidos=set(ids)-set(catalogo)
                if desconocidos:
                    est['pendientes_revision'].append({'id':r['id'],'url':r.get('url'),'motivo':'OCR_circuito_no_catalogado','circuitos':sorted(desconocidos)})
                    ids={k:v for k,v in ids.items() if k in catalogo};ev['completa']=False
                if not ids and action!='sin_afectacion': continue
            if action=='programado':
                horario=ev.get('horario',{})
                if horario.get('fecha_ambigua'):
                    est['pendientes_revision'].append({'id':r['id'],'motivo':'fecha_ambigua','url':r.get('url')}); continue
                fin=horario.get('fin')
                if fin and datetime.fromisoformat(fin)<=ahora: continue
                if ahora-fecha>timedelta(days=7): continue
            elif ahora-fecha>timedelta(hours=MAX_EDAD_H):
                est['reporte_vencido']=True; continue
            prueba={'fecha':fecha.isoformat(),'mensaje_id':r['id'],'url':r.get('url'),
                    'medio':medio,'editado':r.get('editado'),'confianza':r.get('confianza',100),'texto':ev['texto']}
            if action in ('corte','restablecido','sin_afectacion'):
                ultima=fecha
            if action=='cancelado':
                for cid in ids: planes.pop(cid,None)
                continue
            if action=='programado':
                for cid,z in ids.items(): planes[cid]=(z,prueba,ev.get('horario',{}))
                est['programado_fecha']=fecha.isoformat(); continue
            if action=='sin_afectacion':
                for cid in list(activos):
                    if scope=='general': activos.pop(cid,None)
                    else:
                        activos[cid].pop(scope,None)
                        if not activos[cid]: activos.pop(cid,None)
                if scope=='general':
                    ultima_global=prueba
                    verdes={cid:prueba for cid in catalogo}
                continue
            if action=='restablecido':
                for cid in ids:
                    activos.pop(cid,None); verdes[cid]=prueba; evidencia[cid]=prueba
                continue
            if ev['completa']:
                # Solo unir fragmentos con el MISMO álbum, nunca por cercanía horaria.
                grupo=r.get('grupo'); key=(scope,grupo) if grupo else None
                unir=key is not None and key in snapshot_grupos
                if not unir:
                    for cid in list(activos):
                        if scope=='general': activos.pop(cid,None)
                        else:
                            activos[cid].pop(scope,None)
                            if not activos[cid]: activos.pop(cid,None)
                if key: snapshot_grupos[key]=True
            for cid,z in ids.items():
                activos.setdefault(cid,{})[scope]=(z,prueba)
                verdes.pop(cid,None); evidencia[cid]=prueba
            extra=extraer_info_extra(texto,prov)
            for name in ('mw','hora_inicio','cierre'):
                if extra.get(name) is not None: est[name]=extra[name]
            for cid in ids:
                nk=_norm_id(cid)
                for name in ('tiempos','causas'):
                    if nk in extra[name]: est[name][cid]=extra[name][nk]
    for cid,causas in activos.items():
        z,prueba=max(causas.values(),key=lambda x:x[1]['fecha'])
        est['afectados'][cid]=z; est['evidencias'][cid]=prueba
        est['causas'][cid]=' / '.join('avería' if x=='averia' else 'déficit' if x=='deficit' else 'sin precisar' for x in causas)
    est['confirmados_con_servicio']={cid:p for cid,p in verdes.items() if cid not in activos}
    for cid,(z,p,h) in planes.items():
        est['programados'][cid]=z; est['horarios'][cid]=h
        if cid not in est['evidencias']: est['evidencias'][cid]=p
    est['evidencias'].update({cid:p for cid,p in est['confirmados_con_servicio'].items() if cid not in est['evidencias']})
    if ultima:
        est['reporte_fecha']=ultima.isoformat(); est['reporte_vencido']=False; est['estado_datos']='ok'
    est['sin_afectaciones']=bool(ultima_global and not activos)
    if ultima_global: est['cobertura']='provincial'; est['evidencia_global']=ultima_global
    est['total_circuitos_afectados']=len(est['afectados'])
    est['total_circuitos_programados']=len(est['programados'])
    est['pendientes_revision']=est['pendientes_revision'][-40:]
    est['circuitos_sin_catalogar']=sorted((set(est['afectados'])|set(est['programados']))-set(catalogo))
    return est


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
