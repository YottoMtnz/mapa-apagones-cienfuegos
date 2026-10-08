"""Texto, fotos, álbumes, documentos de imagen y PDF. OCR local, sin API de pago."""
import csv, hashlib, io, json, os, re, shutil, subprocess, tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from collections import OrderedDict

OCR_VERSION='4'
MAX_BYTES=12*1024*1024

@lru_cache(maxsize=1)
def idiomas():
    exe=shutil.which('tesseract')
    if not exe: raise RuntimeError('OCR_no_instalado')
    r=subprocess.run([exe,'--list-langs'],capture_output=True,text=True,timeout=10,check=True)
    disponibles=set(r.stdout.splitlines()[1:])
    langs=[x for x in ('spa','eng') if x in disponibles]
    if not langs: raise RuntimeError('OCR_sin_idiomas')
    return '+'.join(langs)


def ocr_imagen(blob):
    from PIL import Image, ImageOps, ImageFilter
    Image.MAX_IMAGE_PIXELS=25_000_000
    lang=idiomas()
    with Image.open(io.BytesIO(blob)) as im:
        im=ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((3200,3200))
        if im.width<1800:
            scale=min(2,1800/im.width)
            im=im.resize((int(im.width*scale),int(im.height*scale)))
        im=ImageOps.autocontrast(ImageOps.grayscale(im)).filter(ImageFilter.SHARPEN)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'pagina.png'; im.save(p)
            variantes=[]
            for psm in ('6','11'):
                r=subprocess.run([shutil.which('tesseract'),str(p),'stdout','-l',lang,'--psm',psm,'tsv'],
                                 capture_output=True,text=True,timeout=25,check=True)
                lineas=OrderedDict(); scores=[]
                for row in csv.DictReader(io.StringIO(r.stdout),delimiter='\t'):
                    palabra=(row.get('text') or '').strip()
                    try: conf=float(row.get('conf',-1))
                    except ValueError: continue
                    if not palabra or conf<0: continue
                    key=tuple(row.get(k) for k in ('page_num','block_num','par_num','line_num'))
                    lineas.setdefault(key,[]).append(palabra); scores.extend([conf]*len(palabra))
                txt='\n'.join(' '.join(x) for x in lineas.values())
                score=sum(scores)/len(scores) if scores else 0
                variantes.append({'texto':txt,'confianza':round(score,1),'idiomas':lang,'psm':psm})
                if score>=85 and re.search(r'\b[CS]\s*[- ]?\s*\d',txt,re.I): break
            return max(variantes,key=lambda x:x['confianza']+min(len(x['texto']),500)/100)


def extraer_documento(blob,mime):
    if len(blob)>MAX_BYTES: raise ValueError('archivo_demasiado_grande')
    if mime=='application/pdf':
        import fitz
        partes=[]; scores=[]
        with fitz.open(stream=blob,filetype='pdf') as doc:
            if len(doc)>5: raise ValueError('PDF_mas_de_5_paginas')
            for page in doc:
                txt=page.get_text(sort=True).strip()
                if len(txt)>30: partes.append(txt); scores.append(100)
                else:
                    if page.rect.width*page.rect.height>10_000_000: raise ValueError('PDF_demasiado_grande')
                    pix=page.get_pixmap(matrix=fitz.Matrix(1.7,1.7))
                    ocr=ocr_imagen(pix.tobytes('png')); partes.append(ocr['texto']); scores.append(ocr['confianza'])
        return {'texto':'\n'.join(partes),'confianza':min(scores,default=0)}
    return ocr_imagen(blob)


def leer_canal(client,canal,ahora,base):
    """Relee la ventana para capturar ediciones. Fecha original ordena; edit_date invalida caché."""
    max_msgs=int(os.environ.get('MAX_MENSAJES','200')); max_medios=int(os.environ.get('MAX_OCR_POR_CICLO','16'))
    cache_dir=Path(base)/'.cache'; cache_dir.mkdir(exist_ok=True)
    cache_path=cache_dir/'ocr.json'
    try: cache=json.loads(cache_path.read_text())
    except (OSError,ValueError): cache={}
    registros=[]; nuevos_ocr=0
    corte=ahora-timedelta(days=3)
    for m in client.iter_messages(canal,limit=max_msgs):
        fecha=m.date.astimezone(timezone.utc)
        if fecha<corte: break
        editado=m.edit_date.isoformat() if getattr(m,'edit_date',None) else None
        r={'id':m.id,'texto':m.text or '', 'texto_nativo':m.text or '', 'texto_ocr':'',
           'fecha':fecha.isoformat(),'editado':editado,
           'url':f'https://t.me/{canal}/{m.id}','medio':'texto','confianza':100,
           'grupo':getattr(m,'grouped_id',None)}
        doc=getattr(m,'document',None); photo=getattr(m,'photo',None)
        mime=getattr(doc,'mime_type','') if doc else 'image/jpeg' if photo else ''
        admitido=bool(photo or mime.startswith('image/') or mime=='application/pdf')
        if getattr(m,'media',None) and not admitido and type(m.media).__name__!='MessageMediaWebPage':
            r['error_lectura']='medio_no_compatible'  # vídeos/audio: visible, nunca silencio
        if admitido:
            r['medio']='pdf' if mime=='application/pdf' else 'imagenes'
            media_id=getattr(doc or photo,'id',0)
            key=hashlib.sha256(f'{OCR_VERSION}:{canal}:{m.id}:{media_id}:{editado}'.encode()).hexdigest()
            try:
                if key in cache: resultado=cache[key]
                else:
                    if nuevos_ocr>=max_medios: raise RuntimeError('OCR_pendiente_limite_del_ciclo')
                    size=getattr(doc,'size',0)
                    if size>MAX_BYTES: raise ValueError('archivo_demasiado_grande')
                    nuevos_ocr+=1
                    blob=client.download_media(m,file=bytes)
                    if not blob: raise RuntimeError('medio_no_descargado')
                    resultado=extraer_documento(blob,mime)
                    cache[key]={**resultado,'fecha_cache':ahora.isoformat()}
                # Un OCR dudoso no tiene permiso para transformar el estado del mapa.
                if resultado.get('confianza',0)<65 or len(resultado.get('texto','').strip())<5:
                    r['error_lectura']='OCR_baja_confianza_o_sin_texto'
                else:
                    r['texto_ocr']=resultado['texto']; r['confianza_ocr']=resultado['confianza']
                    r['texto']+='\n'+resultado['texto']; r['confianza']=resultado['confianza']
            except Exception as e:
                # FloodWait debe propagarse para que el actualizador respete la espera.
                if type(e).__name__=='FloodWaitError': raise
                r['error_lectura']=str(e) if str(e) in ('OCR_no_instalado','OCR_sin_idiomas','OCR_pendiente_limite_del_ciclo','archivo_demasiado_grande','PDF_mas_de_5_paginas') else type(e).__name__
        registros.append(r)
    # Conservar solo OCR reciente; ni fotos ni sesión se publican.
    cache={k:v for k,v in cache.items() if v.get('fecha_cache','')>corte.isoformat()}
    temporal=cache_path.with_suffix('.tmp'); temporal.write_text(json.dumps(cache,ensure_ascii=False)); temporal.replace(cache_path)
    # Contexto compartido en un álbum: el pie de foto puede estar en otra foto.
    grupos={}
    for r in registros:
        if r.get('grupo'): grupos.setdefault(r['grupo'],[]).append(r)
    for lote in grupos.values():
        lote.sort(key=lambda x:x['id'])
        completo='\n'.join(x['texto'] for x in lote)
        # Interpretar una sola vez impide que una página posterior borre la anterior.
        primero=lote[0]; primero['texto']=completo
        primero['texto_nativo']='\n'.join(x['texto_nativo'] for x in lote)
        primero['texto_ocr']='\n'.join(x['texto_ocr'] for x in lote)
        primero['confianza_ocr']=min((x.get('confianza_ocr',100) for x in lote),default=100)
        primero['confianza']=min(x['confianza'] for x in lote)
        errores=[x['error_lectura'] for x in lote if x.get('error_lectura')]
        if errores: primero['error_lectura']='album_incompleto: '+', '.join(sorted(set(errores)))
        for x in lote[1:]:
            x['texto']=''; x['texto_nativo']=''; x['texto_ocr']=''; x['album_fragmento']=True
    return registros
