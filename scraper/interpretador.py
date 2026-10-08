"""Interpretación conservadora por secciones; cada decisión conserva evidencia.
No se infiere que un circuito tenga luz por estar ausente de una lista parcial.
"""
import re, unicodedata
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo
from normalizar import fold, canon_id
from parsers import PARSERS, extraer_info_extra

HABANA = ZoneInfo('America/Havana')
CORTE = re.compile(r'\b(afectad[oa]s?|afectan?|afecta(?:cion(?:es)?)?|sin (?:servicio|corriente|energia|electricidad)|desenergizad[oa]s?|interrumpid[oa]s?|interrupcion(?:es)?|averias?|en fallo|dispar(?:o|ad[oa]s?)|apagones?|fuera de servicio|desconectad[oa]s?|se desconecta|se interrumpe|no (?:tiene|tienen|hay) (?:luz|corriente))\b')
RESTAURA = re.compile(r'\b(restablecid[oa]s?|restablecio|se restablece|se restablecieron|se normaliza|normalizad[oa]s?|energizad[oa]s?|se energiza|recuperad[oa]s?|con servicio|conectad[oa]s?|ya (?:tienen|hay|cuentan con) (?:luz|corriente|servicio))\b')
FUTURO = re.compile(r'\b(programad[oa]s?|programacion|se desconectaran|se interrumpiran|planificad[oa]s?|se afectara|seran? afectad[oa]s?|se interrumpira|se desconectara|manana|proximo|previsto|pronostico)\b')
GLOBAL = re.compile(r'\b(sin afectaciones|no (?:hay|existen|se reportan) afectaciones|todos los circuitos (?:han sido |fueron )?restablecidos|servicio (?:electrico )?restablecido en (?:su )?totalidad)\b')
SNAPSHOT = re.compile(r'\b(actualizacion|estado actual|lista completa|continuan en averia|se mantienen afectados|circuitos afectados por deficit)\b')
RELEVANTE = re.compile(r'circuit|\bcto|afecta|servicio|averia|deficit|programa|electric|corriente|restable|energiza|\b[cs][- ]?\d', re.I)


def normalizar_texto(texto):
    s = unicodedata.normalize('NFKC', texto or '')
    return s.translate(str.maketrans({'–':'-', '—':'-', '−':'-', '\u200b':'', '\ufeff':'', '\xa0':' '})).replace('**','').replace('__','')


def intencion(texto):
    t = fold(texto)
    # El estado anterior explica la reparación; no contradice la reposición actual.
    t = re.sub(r'\bque (?:se encontraba[n]?|estaba[n]?)\b.*$', '', t)
    if re.search(r'\b(cancelad[oa]|se cancela|suspendid[oa])\b', t) and FUTURO.search(t):
        return 'cancelado'
    if re.search(r'\bno (?:se )?(?:ha |han |fue |esta |estan )?(?:restablecid|restablec|energizad|normalizad)', t):
        return 'corte'
    if re.search(r'\bno (?:se )?afect',t) and not GLOBAL.search(t): return None
    if FUTURO.search(t):
        return 'programado'
    # Un trabajo para restablecer NO confirma que ya se restableció.
    if re.search(r'para (?:su )?restablec|restablecer|podr[aá] restablec', t):
        return 'corte' if CORTE.search(t) else None
    if GLOBAL.search(t):
        return 'sin_afectacion'
    if re.search(r'\bno (?:se )?afect', t):
        return None
    if RESTAURA.search(t) and not CORTE.search(t):
        return 'restablecido'
    if RESTAURA.search(t) and CORTE.search(t):
        return 'ambiguo'
    if CORTE.search(t):
        return 'corte'
    if SNAPSHOT.search(t):
        return 'corte'
    return None


def alcance(texto, previo='general'):
    t = fold(texto)
    if re.search(r'averia|disparo|disparad|en fallo', t): return 'averia'
    if re.search(r'emergencia|via libre',t): return 'emergencia'
    if 'deficit' in t or 'generacion' in t: return 'deficit'
    # Convención histórica del canal: "Actualización" = lista de déficit.
    if t.strip(' :.!⚡') == 'actualizacion': return 'deficit'
    return previo


def extraer_circuitos(prov, texto, catalogo):
    resultado = {}
    if prov == 'cienfuegos':
        parcial=re.search(r'\bC\s*[- ]?\s*(\d+)\s*\(\s*(FW|S)\s*-?\s*(\d+)\s*\)',texto,re.I)
        if parcial:
            # Una sección averiada no equivale a todo su circuito sin corriente.
            cid=f'C-{int(parcial[1])}/{parcial[2].upper()}-{int(parcial[3])}'
            lugares=[x.strip(' .\"') for x in texto[parcial.end():].split(',') if x.strip(' .\"')]
            return {cid:lugares}
        for m in re.finditer(r'\b([CS])\s*[-_:]?\s*(\d{1,4})\b', texto, re.I):
            resultado[f'{m[1].upper()}-{int(m[2])}'] = []
        for m in re.finditer(r'\b(?:circuitos?|ctos?\.?)\s*[:#-]?\s*(\d{1,4}(?:\s*[,ye/]\s*\d{1,4})*)(?!\d)', texto, re.I):
            for n in re.findall(r'\d+', m[1]): resultado[f'C-{int(n)}'] = []
    parser = PARSERS.get(prov)
    if parser:
        for cid, lugares in parser(texto).items():
            if not cid.startswith('MUN:'): resultado.setdefault(canon_id(prov,cid), lugares)
    t = fold(texto)
    # Coincidencia exacta de ID conocido; no confundir nombres de pueblos con todos sus circuitos.
    for cid in catalogo:
        k = fold(cid)
        if re.search(r'(?<!\w)'+re.escape(k)+r'(?!\w)', t):
            resultado[cid] = catalogo[cid].get('lugares', [])
    indices = {fold(k):k for k in catalogo}
    return {indices.get(fold(k), k): catalogo.get(indices.get(fold(k),k),{}).get('lugares',v)
            for k,v in resultado.items() if not k.startswith('MUN:')}


def ventana(texto, fecha):
    """Fechas y ventanas horarias simples. No convierte una programación en corte real."""
    local = fecha.astimezone(HABANA)
    dia = local.date(); t = fold(texto); explicita = False
    m = re.search(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b', t)
    try:
        if m:
            year = int(m[3]) if m[3] else local.year
            if year < 100: year += 2000
            dia = dia.replace(year=year,month=int(m[2]),day=int(m[1])); explicita = True
        elif 'manana' in t: dia += timedelta(days=1); explicita = True
        elif re.search(r'\bhoy\b',t): explicita = True
        else:
            meses = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
            m = re.search(r'\b(\d{1,2}) de ('+'|'.join(meses)+r')(?: de (\d{4}))?',t)
            if m:
                dia = dia.replace(year=int(m[3] or local.year),month=meses.index(m[2])+1,day=int(m[1])); explicita = True
    except ValueError:
        return {'inicio':None,'fin':None,'fecha_ambigua':True}
    inicio = datetime.combine(dia,time.min,HABANA) if explicita else None
    fin = datetime.combine(dia+timedelta(days=1),time.min,HABANA) if explicita else fecha+timedelta(hours=12)
    hm = r'(\d{1,2})(?::(\d{2}))?\s*([ap]\.?\s*m\.?)?'
    m = re.search(r'(?:desde|de)\s+(?:las\s+)?'+hm+r'\s*(?:h|horas)?\s*(?:a|hasta|-)\s*(?:las\s+)?'+hm, t)
    if m:
        def hora(h,mi,amp):
            h=int(h); mi=int(mi or 0)
            if amp:
                if not 1<=h<=12: raise ValueError('hora')
                h=h%12+(12 if amp.startswith('p') else 0)
            return time(h,mi)
        try:
            inicio=datetime.combine(dia,hora(*m.groups()[:3]),HABANA)
            fin=datetime.combine(dia,hora(*m.groups()[3:]),HABANA)
            if fin<=inicio: fin+=timedelta(days=1)
        except ValueError: return {'inicio':None,'fin':None,'fecha_ambigua':True}
    return {'inicio':inicio.isoformat() if inicio else None,'fin':fin.isoformat(),'fecha_ambigua':False}


def interpretar(prov, texto, fecha, catalogo=None):
    catalogo = catalogo or {}; texto = normalizar_texto(texto)
    eventos=[]; pendientes=[]; contexto=None; scope='general'; completa=False; encabezado=''
    # Separar cambios de estado en una misma línea conservando sus propios sujetos.
    texto = re.sub(r'(?=[👉📌])', '\n', texto)
    texto = re.sub(r';|\.\s+(?=[A-ZÁÉÍÓÚÑ])|,?\s+(?:mientras(?: que)?|pero)\s+', '\n', texto)
    texto = re.sub(r'\s+y\s+(?=se (?:restable|afecta|energiza)|permanece|continua)', '\n', texto,flags=re.I)
    grupos={}
    for linea in texto.splitlines():
        linea=linea.strip()
        if not linea: continue
        t=fold(linea); ids=extraer_circuitos(prov,linea,catalogo); accion=intencion(linea)
        local_scope=alcance(linea,scope)
        if re.search(r'\bayer\b|\b(?:resumen|balance|reporte) historico\b|\bacumulado de\b',t):
            if RELEVANTE.search(t): pendientes.append({'motivo':'resumen_historico','texto':linea[:300]})
            contexto=None; completa=False
            continue
        if accion=='sin_afectacion' and not ids:
            global_claro = bool(re.search(r'provincia|totalidad|todos los circuitos',t) or GLOBAL.fullmatch(t.strip(' .:!')))
            if local_scope in ('deficit','averia') or global_claro:
                eventos.append({'accion':accion,'circuitos':{},'alcance':local_scope,'completa':global_claro,'texto':linea[:350]})
            else: pendientes.append({'motivo':'restablecimiento_sin_alcance','texto':linea[:300]})
            contexto=None; completa=False
            continue
        if not ids:
            if accion and accion!='ambiguo':
                contexto=accion; scope=local_scope; completa=bool(SNAPSHOT.search(t)); encabezado=linea
                grupos={}
            elif re.search(r'gracias|disculp|informacion nacional|union electrica',t): contexto=None; completa=False
            continue
        accion=accion or contexto
        if accion=='sin_afectacion': accion='restablecido'
        if accion not in ('corte','restablecido','programado','cancelado'):
            pendientes.append({'motivo':'estado_ambiguo' if accion=='ambiguo' else 'sin_estado_explicito','texto':linea[:300],'circuitos':list(ids)})
            continue
        es_completa = (completa if contexto==accion else False) or bool(SNAPSHOT.search(t))
        if re.search(r'\b(parcial|algunos|entre otros|continuara|parte \d)\b',fold(encabezado+' '+linea)):
            es_completa=False
        horario=ventana(encabezado+'\n'+linea,fecha) if accion=='programado' else None
        key=(accion,local_scope,es_completa,str(horario))
        if key not in grupos:
            grupos[key]={'accion':accion,'circuitos':{},'alcance':local_scope,'completa':es_completa,'texto':linea[:350],'textos':{}}
            eventos.append(grupos[key])
        grupos[key]['circuitos'].update(ids)
        grupos[key]['textos'].update({cid:linea[:350] for cid in ids})
        if accion=='programado': grupos[key]['horario']=horario
    # Los parsers provinciales heredados necesitan a veces el encabezado completo.
    if not eventos and prov!='cienfuegos':
        accion=intencion(texto); ids=extraer_circuitos(prov,texto,catalogo)
        if ids and accion in ('corte','restablecido','programado'):
            eventos.append({'accion':accion,'circuitos':ids,'alcance':alcance(texto),'completa':bool(SNAPSHOT.search(fold(texto))),'texto':texto[:350]})
    if not eventos and not pendientes and RELEVANTE.search(fold(texto)):
        pendientes.append({'motivo':'sin_circuitos_identificables','texto':texto[:300]})
    return eventos, pendientes
