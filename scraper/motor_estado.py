"""Reconciliación por causa y procedencia; ausencia en lista completa != confirmación."""
import re
from datetime import datetime, timedelta, timezone
from interpretador import interpretar, alcance, RELEVANTE
from normalizar import fold
from parsers import PARSERS


def lista_cerrada(texto):
    """El formato real del canal cierra la lista provincial con el total actual MW."""
    t=fold(texto)
    return bool(re.search(r'actualizacion.*circuitos.*deficit',t) and
                re.search(r'en este momento.*afectacion total de\s+\d+(?:[.,]\d+)?\s*mw.*provincia',t,re.S))


def componentes(r, prov, catalogo):
    """Nunca rebajar texto original a la confianza del OCR de una imagen decorativa."""
    fecha=r['fecha']; medio=r.get('medio','texto'); error=r.get('error_lectura')
    if 'texto_nativo' not in r:
        partes=[(r.get('texto',''),medio,r.get('confianza',100),True)]
    else:
        nativo=r.get('texto_nativo',''); ocr=r.get('texto_ocr','')
        en,_=interpretar(prov,nativo,fecha,catalogo)
        partes=[(nativo,'texto',100,True)]
        if ocr:
            # Una cabecera sin sujetos aporta contexto a las filas de una imagen.
            partes.append((ocr if en else nativo+'\n'+ocr,medio,r.get('confianza_ocr',0),not en))
    eventos=[]; pendientes=[]; nativos=set()
    for texto,fuente,conf,puede_reemplazar in partes:
        if not texto.strip(): continue
        evs,qs=interpretar(prov,texto,fecha,catalogo)
        pendientes.extend(qs)
        ids_ilegibles=bool(re.search(r'\b[CS]\s*[-_:]\s*(?!\d)[A-Za-z0-9]+',texto))
        if ids_ilegibles: pendientes.append({'motivo':'codigo_de_circuito_ilegible','texto':texto[:250]})
        for ev in evs:
            ev={**ev,'circuitos':dict(ev['circuitos']),'medio':fuente,'confianza':conf}
            es_ocr=fuente!='texto'
            if es_ocr:
                if not lista_cerrada(texto): ev['completa']=False
                ev['circuitos']={k:v for k,v in ev['circuitos'].items() if k not in nativos}
                desconocidos={k for k in ev['circuitos'] if k not in catalogo}
                if desconocidos:
                    pendientes.append({'motivo':'OCR_circuito_no_catalogado','circuitos':sorted(desconocidos)})
                    ev['circuitos']={k:v for k,v in ev['circuitos'].items() if k not in desconocidos}
                    ev['completa']=False
                if conf<85: ev['completa']=False
                if conf<65: continue
                if conf<85 and ev['accion'] in ('restablecido','sin_afectacion'):
                    pendientes.append({'motivo':'OCR_restablecimiento_por_confirmar','circuitos':list(ev['circuitos'])})
                    continue
            else:
                nativos.update(ev['circuitos'])
            if not puede_reemplazar or r.get('truncado') or r.get('incompleto'):
                ev['completa']=False
            if ids_ilegibles or any(q.get('motivo') in ('estado_ambiguo','sin_estado_explicito') for q in qs):
                ev['completa']=False
            if error and not (fuente=='texto' and lista_cerrada(texto)):
                ev['completa']=False
                if ev['accion']=='sin_afectacion': continue
            # En una foto, una lista sin cierre puede continuar dentro de la imagen.
            if fuente=='texto' and medio!='texto' and not lista_cerrada(texto):
                ev['completa']=False
            if ev['circuitos'] or ev['accion']=='sin_afectacion': eventos.append(ev)
    return eventos,pendientes


def analizar(prov,mensajes,ahora,catalogo,max_edad_h=12):
    ahora=ahora.astimezone(timezone.utc)
    est={'schema':4,'estado_datos':'sin_reporte_reciente','fuente_afectados':prov in PARSERS,
         'reporte_fecha':None,'reporte_vencido':False,'sin_afectaciones':False,
         'programado_fecha':None,'mensajes_leidos':0,'afectados':{},'programados':{},
         'confirmados_con_servicio':{},'restablecimientos_probables':{},'afectaciones_parciales':{},
         'evidencias':{},'horarios':{},'cobertura':'parcial','mw':None,'hora_inicio':None,
         'cierre':None,'tiempos':{},'causas':{},'error':None,'pendientes_revision':[],
         'lectura':{'texto':0,'imagenes':0,'pdf':0,'no_leidos':0},'listas_completas':{},
         'transiciones':[]}
    if prov not in PARSERS: est['estado_datos']='sin_fuente'; return est
    limite=ahora-timedelta(hours=max_edad_h)
    registros={}
    for ix,m in enumerate(mensajes):
        r=dict(m) if isinstance(m,dict) else {'texto':m[0] or '','fecha':m[1]}
        f=r.get('fecha')
        if isinstance(f,str): f=datetime.fromisoformat(f.replace('Z','+00:00'))
        if not f: continue
        if f.tzinfo is None: f=f.replace(tzinfo=timezone.utc)
        if f>ahora+timedelta(minutes=5): continue
        r['fecha']=f.astimezone(timezone.utc); r.setdefault('id',ix)
        # Exportaciones repetidas: la última versión editada del mismo mensaje gana.
        key=(r.get('canal',prov),r['id'])
        previo=registros.get(key)
        if previo is None or (r.get('editado') or '') >= (previo.get('editado') or ''):
            registros[key]=r
    activos={}; verdes={}; probables={}; planes={}; ultima=None; global_prueba=None
    grupos=set(); bloqueo=None

    def quitar_plan(cid,fecha):
        if cid not in planes: return
        inicio=planes[cid][2].get('inicio')
        if not inicio or datetime.fromisoformat(inicio)<=fecha: planes.pop(cid,None)

    def cerrar(ids,scope,prueba,explicito=False):
        for cid in ids:
            causas=activos.get(cid,{})
            antes=causas.copy()
            if scope=='general' and explicito: causas.clear()
            else: causas.pop(scope,None)
            if not causas: activos.pop(cid,None)
            if antes and (scope in antes or (scope=='general' and explicito)):
                previa=max(antes.values(),key=lambda v:v[1]['fecha'])[1]
                est['transiciones'].append({'circuito':cid,'tipo':'restablecido' if explicito else 'salida_lista',
                     'alcance':scope,'fecha':prueba['fecha'],'mensaje_id':prueba['mensaje_id'],
                     'aviso_anterior':previa.get('url'),'aviso_actual':prueba.get('url')})
                if not explicito:
                    probables[cid]={**prueba,'tipo':'inferido','motivo':'ausente_en_lista_completa',
                        'alcance':scope,'primera_salida':prueba['fecha'],'listas_consecutivas':1,
                        'aviso_anterior':previa,'lugares':antes.get(scope,next(iter(antes.values())))[0]}

    for r in sorted(registros.values(),key=lambda x:(x['fecha'],str(x['id']).zfill(12))):
        fecha=r['fecha']; est['mensajes_leidos']+=1
        medio=r.get('medio','texto'); est['lectura'][medio if medio in est['lectura'] else 'texto']+=1
        nativo=r.get('texto_nativo',r.get('texto',''))
        if r.get('error_lectura'):
            est['lectura']['no_leidos']+=1
            est['pendientes_revision'].append({'id':r['id'],'url':r.get('url'),'fecha':fecha.isoformat(),'motivo':r['error_lectura']})
            ev_nativos,_=interpretar(prov,nativo,fecha,catalogo)
            aviso_individual_legible=bool(ev_nativos and all(e['circuitos'] and not e['completa'] for e in ev_nativos))
            if not r.get('album_fragmento') and RELEVANTE.search(fold(nativo)) and not lista_cerrada(nativo) and not aviso_individual_legible:
                bloqueo=fecha
                est['lectura_incompleta_desde']=fecha.isoformat()
        eventos,pendientes=componentes(r,prov,catalogo)
        est['pendientes_revision'].extend({**q,'id':r['id'],'url':r.get('url'),'fecha':fecha.isoformat()} for q in pendientes)
        for ev in eventos:
            action=ev['accion']; ids=ev['circuitos']; scope=ev['alcance']
            # Una sección puede volver a citarse sin el número del circuito padre.
            for cid in list(ids):
                if cid.startswith('S-'):
                    candidatos=[k for k in activos if k.endswith('/'+cid)]
                    if len(candidatos)==1: ids[candidatos[0]]=ids.pop(cid)
            prueba={'fecha':fecha.isoformat(),'mensaje_id':r['id'],'url':r.get('url'),
                    'medio':ev['medio'],'editado':r.get('editado'),'confianza':ev['confianza'],'texto':ev['texto']}
            if action=='cancelado':
                for cid in ids: planes.pop(cid,None)
                continue
            if action=='programado':
                h=ev.get('horario',{})
                if h.get('fecha_ambigua'):
                    est['pendientes_revision'].append({'id':r['id'],'motivo':'fecha_ambigua','url':r.get('url')}); continue
                if (h.get('fin') and datetime.fromisoformat(h['fin'])<=ahora) or ahora-fecha>timedelta(days=7): continue
                for cid,z in ids.items(): planes[cid]=(z,prueba,h)
                est['programado_fecha']=fecha.isoformat(); continue
            if fecha>=limite: ultima=fecha
            else: est['reporte_vencido']=True
            if action=='sin_afectacion':
                cerrar(list(activos),scope,prueba,scope=='general')
                if scope=='general':
                    global_prueba=prueba; verdes={cid:prueba for cid in catalogo}; probables.clear()
                continue
            if action=='restablecido':
                for cid in ids:
                    objetivos=[cid]+([k for k in activos if k.startswith(cid+'/')] if scope=='general' else [])
                    cerrar(objetivos,scope,prueba,True)
                    if cid not in activos:
                        verdes[cid]={**prueba,'texto':ev.get('textos',{}).get(cid,ev['texto'])}
                        probables.pop(cid,None)
                    quitar_plan(cid,fecha)
                continue
            if ev['completa']:
                grupo=r.get('grupo'); key=(scope,grupo) if grupo else None
                if key is None or key not in grupos:
                    # Comparar dentro de la MISMA causa; una lista de déficit no borra averías.
                    for cid,p in probables.items():
                        if p['alcance']==scope and cid not in ids and p['mensaje_id']!=r['id']:
                            p.update({**prueba,'listas_consecutivas':p['listas_consecutivas']+1})
                    cerrar([cid for cid,cs in activos.items() if scope in cs and cid not in ids],scope,prueba)
                    est['listas_completas'][scope]={**prueba,'circuitos':list(ids)}
                if key: grupos.add(key)
            for cid,z in ids.items():
                evidencia={**prueba,'texto':ev.get('textos',{}).get(cid,ev['texto'])}
                activos.setdefault(cid,{})[scope]=(z,evidencia)
                verdes.pop(cid,None); probables.pop(cid,None); quitar_plan(cid,fecha)
            # Solo el total ACTUAL provincial, nunca el primer MW de un balance de ayer/SEN.
            mw=re.search(r'en este momento.*?afectacion total de\s+(\d+(?:[.,]\d+)?)\s*mw',fold(nativo),re.S)
            if mw and fecha>=limite:
                est['mw']=float(mw[1].replace(',','.')); est['mw_fecha']=fecha.isoformat()

    parciales={}
    for cid,causas in activos.items():
        actuales={s:v for s,v in causas.items() if v[1]['fecha']>=limite.isoformat()}
        if '/' in cid:
            padre=cid.split('/')[0]; z,p=max(causas.values(),key=lambda v:v[1]['fecha'])
            parciales.setdefault(padre,[]).append({'seccion':cid,'lugares':z,'evidencia':p,'vigente':bool(actuales)})
            continue
        if not actuales: continue
        z,p=max(actuales.values(),key=lambda v:v[1]['fecha'])
        est['afectados'][cid]=z; est['evidencias'][cid]=p
        est['causas'][cid]=' / '.join({'averia':'avería','deficit':'déficit','emergencia':'emergencia'}.get(s,'sin precisar') for s in actuales)
    est['afectaciones_parciales']=parciales
    def positivo_vigente(cid,p):
        return (cid not in activos and cid not in parciales and '/' not in cid and
                p['fecha']>=limite.isoformat() and (not bloqueo or p['fecha']>=bloqueo.isoformat()))
    est['confirmados_con_servicio']={cid:p for cid,p in verdes.items() if positivo_vigente(cid,p)}
    est['restablecimientos_probables']={cid:p for cid,p in probables.items() if positivo_vigente(cid,p) and cid not in verdes}
    for cid,(z,p,h) in planes.items():
        est['programados'][cid]=z; est['horarios'][cid]=h
        est['evidencias'].setdefault(cid,p)
    for campo in ('confirmados_con_servicio','restablecimientos_probables'):
        for cid,p in est[campo].items(): est['evidencias'].setdefault(cid,p)
    if ultima:
        est.update(reporte_fecha=ultima.isoformat(),reporte_vencido=False,estado_datos='ok')
    est['sin_afectaciones']=bool(global_prueba and global_prueba['fecha']>=limite.isoformat() and not activos)
    if global_prueba and global_prueba['fecha']>=limite.isoformat():
        est['cobertura']='provincial'; est['evidencia_global']=global_prueba
    est['total_circuitos_afectados']=len(est['afectados'])
    est['total_circuitos_programados']=len(est['programados'])
    est['total_restablecimientos_probables']=len(est['restablecimientos_probables'])
    est['pendientes_revision']=est['pendientes_revision'][-60:]
    est['transiciones']=est['transiciones'][-100:]
    est['circuitos_sin_catalogar']=sorted((set(est['afectados'])|set(est['programados'])|set(est['restablecimientos_probables'])|set(parciales))-set(catalogo))
    return est
