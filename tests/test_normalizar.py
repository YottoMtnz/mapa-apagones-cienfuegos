import unittest
import _ruta  # noqa
from normalizar import expandir_ids, limpiar_lugar, lugar_desde_id, candidatos


class TestIds(unittest.TestCase):
    def test_holguin_variantes_convergen(self):
        # Todas son el mismo circuito: debe salir UN id (antes eran 3-5 entradas distintas)
        variantes = ["Cto Báguano 2", "Cto Baguanos 2", "Cto Báguanos 2", "Nipe Báguano"]
        self.assertEqual({expandir_ids("holguin", v)[0] for v in variantes[:3]}, {"Báguano 2"})

    def test_guiones_pegados(self):
        self.assertEqual(expandir_ids("holguin", "BanesBanes"), ["Banes Banes"])
        self.assertEqual(expandir_ids("holguin", "CanelaGvaca 1"), ["Canela Guardalavaca 1"])

    def test_cto_duplicado_y_numerico(self):
        self.assertEqual(expandir_ids("holguin", "Cto Cto Gibara 1"), ["Gibara 1"])
        self.assertEqual(expandir_ids("holguin", "17"), ["Cto 17"])
        self.assertEqual(expandir_ids("holguin", "Cto 17"), ["Cto 17"])

    def test_expansion_y(self):
        self.assertEqual(expandir_ids("mayabeque", "Catalina 1 y 2"), ["Catalina 1", "Catalina 2"])

    def test_5_de_moa(self):
        self.assertEqual(expandir_ids("holguin", "Cto 5 de Moa"), ["Moa 5"])

    def test_provincias_con_codigo_no_se_tocan(self):
        self.assertEqual(expandir_ids("villa-clara", "117"), ["117"])
        self.assertEqual(expandir_ids("camaguey", "Y103"), ["Y103"])


class TestLugares(unittest.TestCase):
    def test_basura(self):
        for t in ["y 51", "33 Kv: 6305", "(RF33Kv)", "seccionalizado",
                  "Nos encontramos con una afectación en estos momentos se 144 MW", ""]:
            self.assertIsNone(limpiar_lugar(t), t)

    def test_recorta(self):
        self.assertEqual(limpiar_lugar("Santiago y la línea 5380 Mella"), "Santiago")
        self.assertEqual(limpiar_lugar("seccionalizado de Santiago"), "Santiago")
        self.assertEqual(limpiar_lugar("de San Cristóbal"), "San Cristóbal")
        self.assertEqual(limpiar_lugar("de S.A.B"), "San Antonio de los Baños")

    def test_lugar_desde_id(self):
        self.assertEqual(lugar_desde_id("holguin", "Moa 4"), "Moa")
        self.assertEqual(lugar_desde_id("mayabeque", "5 de San José"), "San José")
        self.assertIsNone(lugar_desde_id("holguin", "Cto 17"))
        self.assertIsNone(lugar_desde_id("villa-clara", "117"))   # id numérico: sin pista

    def test_candidatos(self):
        self.assertEqual(candidatos("Nicaro Cabonico"), ["Nicaro Cabonico", "Nicaro", "Cabonico"])


if __name__ == "__main__":
    unittest.main()
