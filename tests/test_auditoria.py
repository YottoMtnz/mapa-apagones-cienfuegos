import unittest, tempfile, json, io, os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import _ruta
from actualizar import analizar_mensajes
from interpretador import interpretar, ventana
from catalogo import Resolvedor
from geocodificar import nominatim
from lectura import leer_canal, ocr_imagen

NOW=datetime(2026,10,7,18,tzinfo=timezone.utc)
CAT={f'C-{i}':{'lugares':[f'Localidad {i}']} for i in (31,32,33,81,82)}

def analizar(*textos):
    return analizar_mensajes('cienfuegos',[(t,NOW-timedelta(minutes=len(textos)-n)) for n,t in enumerate(textos)],NOW,CAT)

class TestLecturaInteligente(unittest.TestCase):
    def test_restauracion_posterior_no_resucita_corte(self):
        e=analizar('Sin servicio C-31','Restablecido C-31')
        self.assertNotIn('C-31',e['afectados']);self.assertIn('C-31',e['confirmados_con_servicio'])
    def test_corte_nuevo_despues_de_restablecer(self):
        e=analizar('Restablecido C-31','Se interrumpe el circuito 31')
        self.assertIn('C-31',e['afectados']);self.assertNotIn('C-31',e['confirmados_con_servicio'])
    def test_variantes_sin_emojis_y_sin_lugar(self):
        for txt in ('Sin corriente C31','Desenergizado c – 31','Sin servicio circuito: 31','Interrupción en Cto. 31'):
            with self.subTest(txt=txt):self.assertIn('C-31',analizar(txt)['afectados'])
    def test_lista_numerica(self):
        self.assertEqual(set(analizar('Sin servicio los circuitos 31, 32 y 33')['afectados']),set(CAT)-{'C-81','C-82'})
    def test_secciones_mixtas(self):
        e=analizar('Sin servicio:\nC-31\nCon servicio:\nC-32\nProgramados para mañana:\nC-33')
        self.assertEqual(set(e['afectados']),{'C-31'});self.assertIn('C-32',e['confirmados_con_servicio']);self.assertIn('C-33',e['programados'])
    def test_misma_linea_dos_estados(self):
        e=analizar('Restablecido C-31; continúa sin servicio C-32')
        self.assertIn('C-31',e['confirmados_con_servicio']);self.assertEqual(set(e['afectados']),{'C-32'})
    def test_negacion_y_trabajo_no_son_restablecimiento(self):
        self.assertIn('C-31',analizar('No se ha restablecido C-31')['afectados'])
        self.assertNotIn('C-31',analizar('Se trabaja para restablecer C-31')['confirmados_con_servicio'])
    def test_no_afectara_no_es_plan(self):
        self.assertFalse(analizar('No se afectará el circuito 31')['programados'])
    def test_sin_afectaciones_deficit_no_borra_averia(self):
        e=analizar('Avería C-31','Sin servicio por déficit C-32','Sin afectaciones por déficit')
        self.assertEqual(set(e['afectados']),{'C-31'});self.assertFalse(e['sin_afectaciones'])
    def test_no_inventa_verde_al_caducar(self):
        e=analizar_mensajes('cienfuegos',[('Sin servicio C-31',NOW-timedelta(hours=13)),('Feliz cumpleaños',NOW)],NOW,CAT)
        self.assertEqual(e['afectados'],{});self.assertFalse(e['confirmados_con_servicio']);self.assertNotEqual(e['estado_datos'],'ok')
    def test_viejo_no_se_reafirma_por_otra_lista(self):
        e=analizar_mensajes('cienfuegos',[('Avería C-31',NOW-timedelta(hours=16)),('Sin servicio C-32',NOW)],NOW,CAT)
        self.assertEqual(set(e['afectados']),{'C-32'})
    def test_sin_afectaciones_antiguo_no_es_verde(self):
        e=analizar_mensajes('cienfuegos',[('Sin afectaciones en la provincia',NOW-timedelta(hours=13))],NOW,CAT)
        self.assertFalse(e['confirmados_con_servicio'])
    def test_generador_y_orden_entrada(self):
        msgs=[('Sin servicio C-31',NOW-timedelta(hours=2)),('Restablecido C-31',NOW)]
        a=analizar_mensajes('cienfuegos',iter(msgs[::-1]),NOW,CAT)
        self.assertNotIn('C-31',a['afectados'])
    def test_ausencia_no_confirma_verde(self):
        e=analizar('Actualización\nC-31','Actualización\nC-32')
        self.assertNotIn('C-31',e['afectados']);self.assertNotIn('C-31',e['confirmados_con_servicio'])
    def test_album_explicito_se_une(self):
        e=analizar_mensajes('cienfuegos',[{'texto':'Actualización\nC-31','fecha':NOW,'id':1,'grupo':10},{'texto':'Actualización\nC-32','fecha':NOW,'id':2,'grupo':10}],NOW,CAT)
        self.assertEqual(set(e['afectados']),{'C-31','C-32'})
    def test_album_incompleto_no_borra_lista(self):
        e=analizar_mensajes('cienfuegos',[{'texto':'Actualización\nC-31','fecha':NOW-timedelta(minutes=20),'id':1},{'texto':'Actualización\nC-32','fecha':NOW,'id':2,'error_lectura':'album_incompleto'}],NOW,CAT)
        self.assertEqual(set(e['afectados']),{'C-31','C-32'})
    def test_ocr_desconocido_pendiente(self):
        e=analizar_mensajes('cienfuegos',[{'texto':'Sin servicio C-999','fecha':NOW,'medio':'imagenes','confianza':83}],NOW,CAT)
        self.assertFalse(e['afectados']);self.assertTrue(e['pendientes_revision'])
    def test_circuito_nuevo_texto_no_desaparece(self):
        e=analizar('Sin servicio C-999');self.assertIn('C-999',e['circuitos_sin_catalogar'])
    def test_municipio_quejas_no_apaga_todo(self):
        e=analizar_mensajes('camaguey',[('Quejas sin servicio:\n🔹Camagüey 165',NOW)],NOW,{'2410':{'lugares':['Camagüey']}})
        self.assertEqual(e['afectados'],{})
    def test_programacion_para_manana_persistente(self):
        e=analizar_mensajes('cienfuegos',[('Programados para mañana:\nC-31',NOW-timedelta(hours=13))],NOW,CAT)
        self.assertIn('C-31',e['programados']);self.assertNotIn('C-31',e['afectados'])
    def test_horarios_por_fila(self):
        e=analizar('Programados para mañana:\nC-31 de 8:00 a 12:00\nC-32 de 14:00 a 18:00')
        self.assertNotEqual(e['horarios']['C-31']['fin'],e['horarios']['C-32']['fin'])
    def test_programacion_vencida_no_se_publica(self):
        e=analizar('Programados hoy de 8:00 a 10:00:\nC-31');self.assertFalse(e['programados'])
    def test_fecha_invalida_pendiente(self):
        e=analizar('Programados para el 32/10/2026:\nC-31');self.assertFalse(e['programados']);self.assertTrue(e['pendientes_revision'])
    def test_ambiguedad_registrada(self):
        e=analizar('C-31');self.assertFalse(e['afectados']);self.assertTrue(e['pendientes_revision'])

class TestGeografiaSegura(unittest.TestCase):
    def test_sin_coincidencias_parciales(self):
        r=Resolvedor(gazetteer={'cienfuegos':{'santa rosa':[22.2,-80.4,'localidad','']}},cache={})
        self.assertIsNone(r.offline('cienfuegos','Santa Rosa del otro pueblo'))
    def test_province_osm_se_reconoce(self):
        data=[{'lat':'22.28','lon':'-80.57','name':'Abreus','category':'boundary','address':{'province':'Cienfuegos'}}]
        with patch('urllib.request.urlopen',return_value=io.StringIO(json.dumps(data))):self.assertIsNotNone(nominatim('Abreus, Cienfuegos, Cuba','cienfuegos'))
    def test_no_acepta_villa_clara_en_caja_compartida(self):
        data=[{'lat':'22.4','lon':'-80.3','name':'Lugar','category':'place','address':{'province':'Villa Clara'}}]
        with patch('urllib.request.urlopen',return_value=io.StringIO(json.dumps(data))):self.assertIsNone(nominatim('Lugar, Cuba','cienfuegos'))
    def test_homonimos_distantes_no_elige_primero(self):
        data=[{'lat':str(lat),'lon':'-80.3','name':'Lugar','category':'place','address':{'province':'Cienfuegos'}} for lat in (22.1,22.4)]
        with patch('urllib.request.urlopen',return_value=io.StringIO(json.dumps(data))):self.assertIsNone(nominatim('Lugar, Cuba','cienfuegos'))

class TestOCRReal(unittest.TestCase):
    @unittest.skipUnless(__import__('shutil').which('tesseract'),'Requiere Tesseract local')
    def test_imagen_sintetica_se_lee_con_motor_real(self):
        from PIL import Image,ImageDraw,ImageFont
        fontpath='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        if not os.path.exists(fontpath):self.skipTest('Falta fuente de prueba')
        im=Image.new('RGB',(1200,340),'white');d=ImageDraw.Draw(im)
        d.multiline_text((40,30),'CIRCUITOS SIN SERVICIO\nC-31 Palmira\nC-32 Cienfuegos',font=ImageFont.truetype(fontpath,40),fill='black',spacing=20)
        b=io.BytesIO();im.save(b,format='PNG');r=ocr_imagen(b.getvalue())
        self.assertGreater(r['confianza'],65);self.assertIn('C-31',r['texto'])
        self.assertEqual(set(analizar(r['texto'])['afectados']),{'C-31','C-32'})

class TestLimiteReal(unittest.TestCase):
    def test_todos_los_puntos_dentro_de_cienfuegos(self):
        from geometria import en_cienfuegos
        p=Path(__file__).resolve().parents[1]/'data/circuitos_cienfuegos.json'
        for cid,c in json.loads(p.read_text())['circuitos'].items():
            for pt in c['puntos']:self.assertTrue(en_cienfuegos(pt['lat'],pt['lng']),cid+'/'+pt['lugar'])
    def test_tres_puntos_antiguos_fuera_se_rechazan(self):
        from geometria import en_cienfuegos
        for lat,lng in ((22.4861,-80.85079),(22.14263,-79.96995),(22.38128,-80.15038)):
            self.assertFalse(en_cienfuegos(lat,lng))

class TestMedios(unittest.TestCase):
    def test_caption_y_ocr_se_combinan_y_cache_se_reutiliza(self):
        from types import SimpleNamespace as N
        m=N(id=10,date=NOW,edit_date=None,text='Actualización de circuitos sin servicio',document=None,photo=N(id=9),media=True,grouped_id=None)
        c=N(iter_messages=lambda *a,**kw:iter([m]),download_media=lambda *a,**kw:b'imagen')
        with tempfile.TemporaryDirectory() as d,patch('lectura.extraer_documento',return_value={'texto':'C-31 Palmira','confianza':90}) as ocr:
            r=leer_canal(c,'canal',NOW,d);leer_canal(c,'canal',NOW,d)
            self.assertEqual(ocr.call_count,1);self.assertIn('Actualización',r[0]['texto']);self.assertIn('C-31',r[0]['texto'])
            m.edit_date=NOW;leer_canal(c,'canal',NOW,d);self.assertEqual(ocr.call_count,2)
    def test_foto_baja_confianza_pendiente_sin_aplicar(self):
        from types import SimpleNamespace as N
        m=N(id=10,date=NOW,edit_date=None,text='',document=None,photo=N(id=9),media=True,grouped_id=None)
        c=N(iter_messages=lambda *a,**kw:iter([m]),download_media=lambda *a,**kw:b'imagen')
        with tempfile.TemporaryDirectory() as d,patch('lectura.extraer_documento',return_value={'texto':'C-31','confianza':20}):
            r=leer_canal(c,'canal',NOW,d)
            self.assertEqual(r[0]['texto'],'');self.assertIn('error_lectura',r[0])
    def test_pdf_con_texto_real(self):
        try:import fitz
        except ImportError:self.skipTest('PyMuPDF opcional en pruebas locales')
        from lectura import extraer_documento
        with fitz.open() as doc:
            p=doc.new_page();p.insert_text((50,50),'CIRCUITOS SIN SERVICIO\nC-31 Palmira\nC-32 Cienfuegos');blob=doc.tobytes()
        r=extraer_documento(blob,'application/pdf');self.assertIn('C-31',r['texto']);self.assertEqual(r['confianza'],100)
