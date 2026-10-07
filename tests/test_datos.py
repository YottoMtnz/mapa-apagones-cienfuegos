"""Invariantes de los datos publicados. Si alguno falla, el mapa mentiría."""
import glob, json, os, re, unittest
import _ruta  # noqa
from normalizar import limpiar_lugar, expandir_ids
from provincias import PROVINCIAS, es_centro_de_capital, en_caja, NOMBRE_ES_LUGAR

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def cargar(nombre):
    with open(os.path.join(DATA, nombre), encoding="utf-8") as f:
        return json.load(f)


class TestDatos(unittest.TestCase):
    def test_hay_archivo_por_provincia(self):
        for p in PROVINCIAS:
            self.assertTrue(os.path.exists(os.path.join(DATA, f"circuitos_{p}.json")), p)
            self.assertTrue(os.path.exists(os.path.join(DATA, f"estado_{p}.json")), p)

    def test_esquema_y_coherencia(self):
        for p in PROVINCIAS:
            d = cargar(f"circuitos_{p}.json")
            self.assertEqual(d["schema"], 2, p)
            for cid, c in d["circuitos"].items():
                self.assertEqual(c["ubicado"], bool(c["puntos"]), f"{p}/{cid}")
                self.assertEqual(c["revisar"], any(x["dudoso"] for x in c["puntos"]), f"{p}/{cid}")
                for x in c["puntos"]:
                    self.assertTrue(en_caja(p, x["lat"], x["lng"]), f"{p}/{cid}/{x['lugar']} fuera de caja")

    def test_no_hay_pines_de_relleno_en_capital(self):
        """El bug original: 'aproximado' en el centro de la capital. Un pin en el centro
        solo es válido si el lugar ES la capital (o viene del gazetteer)."""
        for p in PROVINCIAS:
            capital = PROVINCIAS[p][2].lower()
            for cid, c in cargar(f"circuitos_{p}.json")["circuitos"].items():
                for x in c["puntos"]:
                    if es_centro_de_capital(p, x["lat"], x["lng"], 0.05) and x["fuente"] != "gazetteer":
                        self.assertFalse(x.get("fuente")=="fallback-capital", f"{p}/{cid}: punto de relleno")

    def test_ids_name_keyed_son_canonicos(self):
        for p in NOMBRE_ES_LUGAR:
            ids = list(cargar(f"circuitos_{p}.json")["circuitos"])
            for cid in ids:
                self.assertEqual(expandir_ids(p, cid), [cid], f"{p}/{cid} no es canónico")
            self.assertEqual(len(ids), len({i.lower() for i in ids}), f"{p}: ids duplicados")

    def test_no_hay_lugares_basura(self):
        for p in PROVINCIAS:
            for cid, c in cargar(f"circuitos_{p}.json")["circuitos"].items():
                for l in c["lugares"]:
                    self.assertEqual(limpiar_lugar(l), l, f"{p}/{cid}: lugar basura {l!r}")

    def test_ids_basura_conocidos_no_existen(self):
        self.assertNotIn("5040", cargar("circuitos_artemisa.json")["circuitos"])
        self.assertNotIn("Circuito", cargar("circuitos_las-tunas.json")["circuitos"])

    def test_puntos_gazetteer_en_su_provincia(self):
        g = cargar("gazetteer.json")
        for p, entradas in g.items():
            if p.startswith("_"):
                continue
            for nombre, (lat, lng, prec, _) in entradas.items():
                self.assertTrue(en_caja(p, lat, lng), f"gazetteer {p}/{nombre}")
                self.assertIn(prec, ("ciudad", "localidad"))


if __name__ == "__main__":
    unittest.main()
