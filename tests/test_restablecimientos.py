"""Regresiones motivadas por publicaciones reales de empresaelectricacienfuegos1.
IDs de dos listas consecutivas observadas el 7/oct; horas sintéticas solo para replay.
Fuente: https://telemetr.io/es/channels/1713779531-empresaelectricacienfuegos1/posts
Otros casos reproducen fallos de estado_cienfuegos.json del repositorio del usuario.
"""
import unittest
from datetime import datetime,timedelta,timezone
import _ruta
from actualizar import analizar_mensajes

NOW=datetime(2026,10,8,1,tzinfo=timezone.utc)
CAT={f'C-{n}':{'lugares':[f'Zona {n}']} for n in range(1,500)}
ANTES=[85,52,35,44,73,42,31,88,58,56,82,39,75,33,80,19,65,66,91,2,3,69,26,90,67,15,27,28,407,89,94]
DESPUES=[52,35,73,42,31,88,58,56,82,39,75,33,80,19,65,66,91,2,3,69,26,90,67,15,27,28,407,89,94]

def lista(ids):
    return 'Actualización de los circuitos afectados por déficit de generación\n'+'\n'.join(f'👉C-{n}' for n in ids)+'\nEn este momento tenemos una afectación total de 35 MW en la provincia.'

def replay(*mensajes):
    rs=[]
    for i,m in enumerate(mensajes):
        r={'texto':m} if isinstance(m,str) else dict(m)
        r.setdefault('fecha',NOW-timedelta(minutes=len(mensajes)-i))
        r.setdefault('id',i+1);r.setdefault('url',f'https://t.me/empresaelectricacienfuegos1/{i+1}');rs.append(r)
    return analizar_mensajes('cienfuegos',rs,NOW,CAT)

class TestRestablecimientos(unittest.TestCase):
    def test_transicion_real_no_acumula_dos_listas(self):
        e=replay(lista(ANTES),lista(DESPUES))
        self.assertEqual(set(e['afectados']),{f'C-{n}' for n in DESPUES})
        self.assertEqual(set(e['restablecimientos_probables']),{'C-85','C-44'})
        self.assertFalse(e['confirmados_con_servicio'])
        self.assertTrue(e['restablecimientos_probables']['C-85']['aviso_anterior']['url'])
    def test_foto_decorativa_ilegible_no_impide_reemplazo(self):
        txt=lista(DESPUES)
        e=replay(lista(ANTES),{'texto':txt,'texto_nativo':txt,'texto_ocr':'','medio':'imagenes','error_lectura':'OCR_baja_confianza_o_sin_texto'})
        self.assertEqual(len(e['afectados']),29);self.assertIn('C-85',e['restablecimientos_probables'])
        self.assertNotIn('lectura_incompleta_desde',e)
    def test_caption_de_circuito_nuevo_no_se_filtra_como_ocr(self):
        e=replay({'texto_nativo':'Sin servicio C-1770','texto_ocr':'','texto':'Sin servicio C-1770','medio':'imagenes','confianza':81})
        self.assertIn('C-1770',e['afectados']);self.assertIn('C-1770',e['circuitos_sin_catalogar'])
    def test_centro_historico_es_un_lugar(self):
        e=replay('Actualización\n👉C-65 Centro histórico, Reina (Aduana)')
        self.assertIn('C-65',e['afectados'])
    def test_intento_de_restaurar_con_fallo_no_es_reposicion(self):
        e=replay(lista([31,52]),'Al momento de restablecer por déficit, se encuentra en fallo el circuito:\nC-31 Horquita',lista([52]))
        self.assertIn('C-31',e['afectados']);self.assertEqual(e['causas']['C-31'],'avería')
        self.assertNotIn('C-31',e['restablecimientos_probables'])
    def test_averia_aparte_no_se_borra_por_restablecer_deficit(self):
        e=replay('Avería C-31',lista([31]),'Restablecido por déficit C-31')
        self.assertIn('C-31',e['afectados']);self.assertFalse(e['confirmados_con_servicio'])
    def test_restauracion_expresa_pasa_probable_a_confirmado(self):
        e=replay(lista([31,32]),lista([32]),'Restablecido C-31')
        self.assertIn('C-31',e['confirmados_con_servicio']);self.assertNotIn('C-31',e['restablecimientos_probables'])
    def test_vuelve_a_lista_vuelve_a_rojo(self):
        e=replay(lista([31,32]),lista([32]),lista([31,32]))
        self.assertIn('C-31',e['afectados']);self.assertFalse(e['restablecimientos_probables'])
    def test_aviso_suelto_no_cierra_la_lista(self):
        e=replay(lista([31,32]),'Sin servicio por déficit C-33')
        self.assertEqual(len(e['afectados']),3);self.assertFalse(e['restablecimientos_probables'])
    def test_lista_truncada_no_infiere_salidas(self):
        e=replay(lista([31,32]),{'texto':lista([32]),'truncado':True})
        self.assertIn('C-31',e['afectados']);self.assertFalse(e['restablecimientos_probables'])
    def test_lista_parcial_explicita_no_cierra(self):
        e=replay(lista([31,32]),'Actualización parcial por déficit:\nC-32')
        self.assertIn('C-31',e['afectados'])
    def test_ocr_incompleto_no_infiere_salidas(self):
        e=replay(lista([31,32]),{'texto_nativo':'Actualización por déficit','texto_ocr':'C-32','medio':'imagenes','confianza_ocr':80})
        self.assertIn('C-31',e['afectados']);self.assertFalse(e['restablecimientos_probables'])
    def test_averia_vencida_no_se_convierte_en_probable(self):
        e=replay({'texto':'Avería C-31','fecha':NOW-timedelta(hours=20)},lista([31,32]),lista([32]))
        self.assertNotIn('C-31',e['afectados']);self.assertNotIn('C-31',e['restablecimientos_probables'])
    def test_silencio_y_vencimiento_no_restablecen(self):
        e=replay({'texto':lista([31]),'fecha':NOW-timedelta(hours=13)},'Tenemos problemas técnicos para publicar')
        self.assertFalse(e['afectados']);self.assertFalse(e['restablecimientos_probables']);self.assertFalse(e['confirmados_con_servicio'])
    def test_aviso_previo_se_consume_al_confirmar_corte(self):
        e=replay('Será afectado por déficit C-31',lista([31]),lista([32]))
        self.assertNotIn('C-31',e['programados']);self.assertIn('C-31',e['restablecimientos_probables'])
    def test_plan_futuro_no_se_elimina_por_corte_actual(self):
        e=replay('Programados para mañana:\nC-31',lista([31]))
        self.assertIn('C-31',e['programados'])
    def test_seccion_no_apaga_circuito_completo(self):
        e=replay('En avería:\nC-90 (FW1558) La Pollera',lista([90,32]),lista([32]))
        self.assertNotIn('C-90',e['afectados']);self.assertNotIn('C-90',e['restablecimientos_probables'])
        self.assertEqual(e['afectaciones_parciales']['C-90'][0]['seccion'],'C-90/FW-1558')
    def test_restablecimiento_total_cierra_seccion(self):
        e=replay('En avería:\nC-90 (S-9092) Zona','Restablecido C-90')
        self.assertIn('C-90',e['confirmados_con_servicio']);self.assertFalse(e['afectaciones_parciales'])
    def test_restablecimiento_de_seccion_con_id_corto(self):
        e=replay('En avería:\nC-90 (S-9092) Zona','Restablecido S-9092')
        self.assertFalse(e['afectaciones_parciales']);self.assertNotIn('C-90',e['confirmados_con_servicio'])
    def test_texto_evidencia_corresponde_a_cada_circuito(self):
        e=replay(lista([31,32]))
        self.assertIn('C-32',e['evidencias']['C-32']['texto']);self.assertNotIn('C-31',e['evidencias']['C-32']['texto'])
    def test_lista_repetida_refresca_probable_sin_volverlo_confirmado(self):
        e=replay(lista([31,32]),lista([32]),lista([32]))
        self.assertEqual(e['restablecimientos_probables']['C-31']['listas_consecutivas'],2)
        self.assertFalse(e['confirmados_con_servicio'])
    def test_lectura_pertinente_fallida_suspende_deduccion(self):
        e=replay(lista([31,32]),lista([32]),{'texto_nativo':'Lista de circuitos afectados en imagen','texto':'Lista de circuitos afectados en imagen','medio':'imagenes','error_lectura':'OCR_pendiente'})
        self.assertFalse(e['restablecimientos_probables'])
    def test_edicion_reemplaza_no_suma_versiones(self):
        e=replay({'id':7,'texto':lista([31]),'editado':'2026-10-08T00:00:00+00:00'},
                 {'id':7,'texto':lista([32]),'editado':'2026-10-08T00:05:00+00:00'})
        self.assertEqual(set(e['afectados']),{'C-32'});self.assertEqual(e['mensajes_leidos'],1)
    def test_mw_no_es_total_historico_o_nacional(self):
        e=replay('En el día de ayer afectación 80 MW\nEn el país 1778 MW\nEn fallo:\nC-31')
        self.assertIsNone(e['mw'])
    def test_restauracion_con_descripcion_de_la_falla_anterior(self):
        e=replay('En fallo C-31','Restablecido C-31, que estaba en fallo')
        self.assertIn('C-31',e['confirmados_con_servicio']);self.assertFalse(e['afectados'])
    def test_ocr_dudoso_no_pinta_verde(self):
        e=replay('Sin servicio C-31',{'texto_nativo':'','texto_ocr':'Restablecido C-31','medio':'imagenes','confianza_ocr':70})
        self.assertIn('C-31',e['afectados']);self.assertFalse(e['confirmados_con_servicio'])
    def test_codigo_roto_no_autoriza_retirar_circuitos(self):
        e=replay(lista([18,32]),lista([32]).replace('👉C-32','👉C-I8\n👉C-32'))
        self.assertIn('C-18',e['afectados']);self.assertFalse(e['restablecimientos_probables'])
    def test_ocr_sin_cierre_no_infiere_ausencias(self):
        e=replay(lista([31,32]),{'texto_nativo':'','texto_ocr':'Actualización\nC-32','medio':'imagenes','confianza_ocr':95})
        self.assertIn('C-31',e['afectados']);self.assertFalse(e['restablecimientos_probables'])
    def test_foto_de_aviso_individual_no_invalida_otros_circuitos(self):
        e=replay('Restablecido C-32',{'texto_nativo':'En fallo C-31','texto':'En fallo C-31','medio':'imagenes','error_lectura':'OCR_baja_confianza_o_sin_texto'})
        self.assertIn('C-32',e['confirmados_con_servicio']);self.assertIn('C-31',e['afectados'])

if __name__=='__main__': unittest.main()
