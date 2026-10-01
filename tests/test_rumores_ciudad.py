import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.config import RUTA_GRAFO_CIUDAD
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.rumores_ciudad import (RumoresCiudad, TOPE_CONFLICTOS, TOPE_DESINFORMACION)


def ciudad() -> GrafoCiudad:
    return GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)


class RumoresTest(unittest.TestCase):
    def test_nace_en_su_zona_y_no_se_ve_hasta_que_corre(self) -> None:
        r = RumoresCiudad(ciudad())
        r.nacer("n1", "colegio")
        self.assertEqual(r.rumor("n1").zonas, ["colegio"])
        self.assertEqual(r.zonas_infectadas(), set())    # aun no delata que la noticia es falsa
        r.avanzar_ronda()
        self.assertIn("colegio", r.zonas_infectadas())

    def test_se_expande_un_anillo_por_ronda(self) -> None:
        r = RumoresCiudad(ciudad())
        r.nacer("n1", "colegio")
        r.avanzar_ronda()
        self.assertEqual(set(r.rumor("n1").zonas), {"colegio", "plaza", "barrio"})
        r.avanzar_ronda()
        self.assertEqual(set(r.rumor("n1").zonas), {"colegio", "plaza", "barrio", "parque", "alcaldia"})
        self.assertEqual(r.avanzar_ronda(), [])           # ya ocupa todo: nada nuevo

    def test_coincide_con_lo_que_predice_expuestas(self) -> None:
        g = ciudad()
        for origen in ("colegio", "alcaldia", "parque"):
            r = RumoresCiudad(g)
            r.nacer("n", origen)
            for k in (1, 2):
                r.avanzar_ronda()
                esperado = {origen} | {z for anillo in g.expuestas(origen, k) for z in anillo}
                self.assertEqual(set(r.rumor("n").zonas), esperado, (origen, k))

    def test_nacer_con_radio_usa_los_anillos(self) -> None:
        r = RumoresCiudad(ciudad())
        r.nacer("n1", "alcaldia", radio=1)
        self.assertEqual(set(r.rumor("n1").zonas), {"alcaldia", "plaza"})

    def test_ampliar_expande_de_inmediato(self) -> None:
        r = RumoresCiudad(ciudad())
        r.nacer("n1", "alcaldia")
        self.assertEqual(r.ampliar("n1"), ["plaza"])
        self.assertEqual(r.ampliar("zzz"), [])

    def test_resolver_elimina_el_rumor(self) -> None:
        r = RumoresCiudad(ciudad())
        r.nacer("n1", "colegio")
        r.avanzar_ronda()
        self.assertTrue(r.resolver("n1"))
        self.assertFalse(r.resolver("n1"))
        self.assertEqual(r.zonas_infectadas(), set())
        self.assertEqual(r.avanzar_ronda(), [])

    def test_rumor_en_zona_y_exclusion(self) -> None:
        r = RumoresCiudad(ciudad())
        r.nacer("n1", "colegio")
        r.avanzar_ronda()
        self.assertEqual(r.rumor_en("plaza").id, "n1")
        self.assertIsNone(r.rumor_en("plaza", excluir="n1"))
        self.assertIsNone(r.rumor_en("alcaldia"))         # todavia no llego

    def test_zonas_en_riesgo(self) -> None:
        r = RumoresCiudad(ciudad())
        r.nacer("n1", "alcaldia")
        r.avanzar_ronda()                                  # ocupa alcaldia y plaza
        self.assertEqual(r.zonas_en_riesgo(), {"colegio", "barrio", "parque"})

    def test_penalizacion_crece_con_las_zonas_y_tiene_tope(self) -> None:
        r = RumoresCiudad(ciudad())
        self.assertEqual(r.penalizacion().misinformation, 0)
        r.nacer("n1", "colegio")
        r.avanzar_ronda()                                  # 3 zonas
        p = r.penalizacion()
        self.assertEqual((p.misinformation, p.conflicts), (3, 1))
        for i in range(2, 6):
            r.nacer(f"n{i}", "plaza")
        for _ in range(3):
            r.avanzar_ronda()
        p = r.penalizacion()
        self.assertEqual(p.misinformation, TOPE_DESINFORMACION)
        self.assertEqual(p.conflicts, TOPE_CONFLICTOS)

    def test_roundtrip_dict(self) -> None:
        g = ciudad()
        r = RumoresCiudad(g)
        r.nacer("n1", "colegio")
        r.avanzar_ronda()
        copia = RumoresCiudad.from_dict(g, json.loads(json.dumps(r.to_dict())))
        self.assertEqual(copia.to_dict(), r.to_dict())


if __name__ == "__main__":
    unittest.main()
