import json, os, tempfile, unittest
from datetime import datetime, timedelta, timezone
import _ruta  # noqa
import actualizar as A

AHORA = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
LISTA = "Circuitos afectados por déficit de generación\n🔥342 Bahía Honda\n"


class TestEstado(unittest.TestCase):
    def test_reporte_reciente_es_ok(self):
        e = A.analizar_mensajes("artemisa", [(LISTA, AHORA - timedelta(hours=1))], AHORA)
        self.assertEqual(e["estado_datos"], "ok")
        self.assertIn("342", e["afectados"])

    def test_reporte_viejo_no_se_muestra_como_actual(self):
        e = A.analizar_mensajes("artemisa", [(LISTA, AHORA - timedelta(hours=30))], AHORA)
        self.assertEqual(e["afectados"], {})
        self.assertTrue(e["reporte_vencido"])
        self.assertNotEqual(e["estado_datos"], "ok")       # => el mapa NO pinta verde

    def test_sin_afectaciones_cierra_lista_anterior(self):
        msgs = [("Sin afectaciones en la provincia", AHORA - timedelta(hours=1)),
                (LISTA, AHORA - timedelta(hours=3))]
        e = A.analizar_mensajes("artemisa", msgs, AHORA)
        self.assertEqual(e["afectados"], {})
        self.assertTrue(e["sin_afectaciones"])
        self.assertEqual(e["estado_datos"], "ok")

    def test_provincia_sin_fuente(self):
        e = A.analizar_mensajes("matanzas", [("lo que sea", AHORA)], AHORA)
        self.assertEqual(e["estado_datos"], "sin_fuente")
        self.assertFalse(e["fuente_afectados"])

    def test_error_conserva_estado_previo(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "data"))
            viejo_base = A.BASE
            A.BASE = d
            try:
                previo = A.analizar_mensajes("artemisa", [(LISTA, AHORA - timedelta(hours=1))], AHORA)
                A.guardar("artemisa", previo, AHORA)
                A.registrar_error("artemisa", AHORA, "TimeoutError")
                r = json.load(open(os.path.join(d, "data", "estado_artemisa.json")))
                self.assertIn("342", r["afectados"])         # NO se vació
                self.assertEqual(r["estado_datos"], "error")
            finally:
                A.BASE = viejo_base

    def test_sin_cambios_no_reescribe(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "data"))
            viejo_base = A.BASE
            A.BASE = d
            try:
                e = A.analizar_mensajes("artemisa", [(LISTA, AHORA - timedelta(hours=1))], AHORA)
                self.assertTrue(A.guardar("artemisa", dict(e), AHORA))
                self.assertFalse(A.guardar("artemisa", dict(e), AHORA + timedelta(minutes=5)))
                self.assertTrue(A.guardar("artemisa", dict(e), AHORA + timedelta(minutes=90)))  # heartbeat
            finally:
                A.BASE = viejo_base


    def test_lista_averias_vieja_no_reagrega_resueltos(self):
        # Dos "continúan en avería": la vieja NO debe re-agregar C-82 (resuelto)
        msgs = [
            ("Continúan en avería:\nC-81 Federal\nC-83 Cartagena", AHORA - timedelta(minutes=10)),
            ("Continúan en avería:\nC-81 Federal\nC-82 Balboa\nC-83 Cartagena", AHORA - timedelta(minutes=60)),
        ]
        e = A.analizar_mensajes("cienfuegos", msgs, AHORA)
        self.assertEqual(set(e["afectados"]), {"C-81", "C-83"})

    def test_listas_independientes_cercanas_no_se_fusionan(self):
        # La cercanía temporal no demuestra que sean fragmentos de una misma lista.
        msgs = [
            ("Continúan en avería:\nC-81 Federal", AHORA - timedelta(minutes=10)),
            ("Continúan en avería:\nC-83 Cartagena", AHORA - timedelta(minutes=11)),
        ]
        e = A.analizar_mensajes("cienfuegos", msgs, AHORA)
        self.assertEqual(set(e["afectados"]), {"C-81"})

    def test_actualizacion_reciente_reemplaza_aunque_sea_cercana(self):
        msgs = [
            ("Actualización\nC-80 Aguada", AHORA - timedelta(minutes=10)),
            ("Actualización\nC-81 Federal", AHORA - timedelta(minutes=11)),
        ]
        e = A.analizar_mensajes("cienfuegos", msgs, AHORA)
        self.assertEqual(set(e["afectados"]), {"C-80"})

    def test_actualizacion_vieja_separada_se_ignora(self):
        msgs = [
            ("Actualización\nC-80 Aguada", AHORA - timedelta(minutes=10)),
            ("Actualización\nC-82 Balboa", AHORA - timedelta(hours=3)),
        ]
        e = A.analizar_mensajes("cienfuegos", msgs, AHORA)
        self.assertEqual(set(e["afectados"]), {"C-80"})

    def test_averia_activa_protege_de_actualizacion(self):
        # C-82 sale de la lista de déficit pero sigue en avería => se queda
        msgs = [
            ("Actualización\nC-80 Aguada", AHORA - timedelta(minutes=10)),
            ("Continúan en avería:\nC-82 Balboa", AHORA - timedelta(minutes=20)),
        ]
        e = A.analizar_mensajes("cienfuegos", msgs, AHORA)
        self.assertEqual(set(e["afectados"]), {"C-80", "C-82"})

    def test_deficit_activo_protege_de_lista_averias(self):
        # C-82 sale de la lista de averías pero sigue en déficit => se queda
        msgs = [
            ("Continúan en avería:\nC-81 Federal", AHORA - timedelta(minutes=10)),
            ("Actualización\nC-80 Aguada\nC-82 Balboa", AHORA - timedelta(minutes=20)),
        ]
        e = A.analizar_mensajes("cienfuegos", msgs, AHORA)
        self.assertEqual(set(e["afectados"]), {"C-80", "C-81", "C-82"})


if __name__ == "__main__":
    unittest.main()
