import unittest
import _ruta  # noqa
from parsers import (parse_villa_clara, parse_artemisa, parse_las_tunas, parse_santiago_de_cuba,
                     parse_holguin, parse_cienfuegos, parse_mayabeque, extraer_info_extra, detectar_tipo)


class TestParsers(unittest.TestCase):
    def test_villa_clara_ctos_multiples(self):
        r = parse_villa_clara("Municipio Santa Clara:\n👉Ctos 117 y 51 Camacho\n👉Cto 81 26 de Julio\n👉Ctos 14, 15 Maleza")
        self.assertEqual(r["117"], ["Camacho"])
        self.assertEqual(r["51"], ["Camacho"])           # antes: lugar 'y 51'
        self.assertEqual(r["81"], ["26 de Julio"])       # antes: 'de Julio'
        self.assertEqual(r["15"], ["Maleza"])

    def test_artemisa_ignora_mw_y_horas(self):
        txt = ("Circuitos afectados por déficit de generación\n🔥3220 de S.A.B\n👉342 Provicional de Bahía Honda\n"
               "Nos encontramos con una afectación en estos momentos se 144 MW\n🧠1570 de Artemisa\n"
               "Reporte de las 10:30 horas")
        r = parse_artemisa(txt)
        self.assertEqual(sorted(r), ["1570", "3220", "342"])     # sin 5040, 144, 10, 30
        self.assertEqual(r["3220"], ["San Antonio de los Baños"])

    def test_las_tunas_exige_digito(self):
        r = parse_las_tunas("circuito: TK10 El Cornito\nCircuito: Circuito 33 Kv: 6305")
        self.assertEqual(list(r), ["TK10"])

    def test_santiago_dos_circuitos_en_una_linea(self):
        r = parse_santiago_de_cuba("el circuito 8 de Santiago y la línea 5380 Mella.\nel circuito 24 de Santiago se encuentra disparado")
        self.assertEqual(r, {"8": ["Santiago"], "5380": ["Mella"], "24": ["Santiago"]})

    def test_holguin_ids_canonicos(self):
        r = parse_holguin("📌Cto Uñas 1- 48:39 Horas(Avería)\n📌BanesBanes- 10:00 Horas\nCto 17 y Cto Aeropuerto 1.")
        self.assertEqual(sorted(r), ["Aeropuerto 1", "Banes Banes", "Cto 17", "Uñas 1"])

    def test_tiempos_usan_misma_clave_que_ids(self):
        e = extraer_info_extra("📌Cto Báguanos 2- 48:39 Horas(Avería)", "holguin")
        self.assertEqual(e["tiempos"], {"baguano 2": "48:39"})
        self.assertEqual(e["causas"], {"baguano 2": "avería"})

    def test_cienfuegos_conserva_guion_interno(self):
        r = parse_cienfuegos("⚡C-31 Caonao-Pueblo, Palmira\n")
        self.assertEqual(r["C-31"], ["Caonao-Pueblo", "Palmira"])

    def test_mayabeque_filtra_ruido(self):
        txt = "Se afecta el servicio en:\n* Nazareno\n* Güines 1 y 2\nDisculpen las molestias, se trabaja para restablecer\n"
        self.assertEqual(sorted(parse_mayabeque(txt)), ["Güines 1", "Güines 2", "Nazareno"])

    def test_detectar_tipo_heredado(self):
        # Documenta el comportamiento ACTUAL (heurística no verificada con mensajes reales)
        self.assertEqual(detectar_tipo("Serán afectados los circuitos..."), "programado")
        self.assertEqual(detectar_tipo("Circuitos sin servicio por déficit"), "actual")


if __name__ == "__main__":
    unittest.main()
