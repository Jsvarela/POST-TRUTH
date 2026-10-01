import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.config import RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL, RUTA_INTRO
from post_truth.models.intro import Intro, MAX_LAMINAS, MIN_LAMINAS
from post_truth.structures.grafo_ciudad import GrafoCiudad


def datos() -> dict:
    return json.loads(Path(RUTA_INTRO).read_text(encoding="utf-8"))


class IntroModeloTest(unittest.TestCase):
    def test_carga_el_archivo_de_data(self) -> None:
        intro = Intro.cargar(RUTA_INTRO)
        self.assertTrue(MIN_LAMINAS <= len(intro.laminas) <= MAX_LAMINAS)
        self.assertEqual(len(intro.candidatos), 4)
        self.assertEqual(intro.laminas[-1].tipo, "cierre")        # el cierre pasa a la seleccion
        self.assertEqual(intro.laminas[0].tipo, "ciudad")

    def test_roundtrip_dict(self) -> None:
        intro = Intro.cargar(RUTA_INTRO)
        self.assertEqual(Intro.from_dict(json.loads(json.dumps(intro.to_dict()))), intro)

    def test_las_zonas_coinciden_con_las_del_grafo_de_la_ciudad(self) -> None:
        intro = Intro.cargar(RUTA_INTRO)
        ciudad = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)
        self.assertEqual({z.id for z in intro.zonas}, {z.id for z in ciudad.zonas()})
        for z in intro.zonas:
            self.assertTrue(z.descripcion.strip())

    def test_cada_lamina_tiene_subtitulo_y_los_candidatos_que_nombra_existen(self) -> None:
        intro = Intro.cargar(RUTA_INTRO)
        for lamina in intro.laminas:
            self.assertTrue(lamina.texto.strip(), lamina.id)
            for id in lamina.candidatos:
                intro.candidato(id)
        mostrados = [id for l in intro.laminas for id in l.candidatos]
        self.assertEqual(sorted(mostrados), sorted(c.id for c in intro.candidatos))  # los 4, una vez cada uno

    def test_los_candidatos_tienen_nombre_lema_propuesta_y_aspecto_distinto(self) -> None:
        intro = Intro.cargar(RUTA_INTRO)
        for c in intro.candidatos:
            self.assertTrue(c.nombre and c.lema and c.propuesta)
        self.assertEqual(len({c.aspecto for c in intro.candidatos}), 4)
        self.assertEqual(len({c.nombre for c in intro.candidatos}), 4)

    def test_los_candidatos_son_coherentes_con_el_resto_del_juego(self) -> None:
        """Las noticias hablan de "Juan" y "Maria" y el grafo social tiene a Andres Quintero."""
        intro = Intro.cargar(RUTA_INTRO)
        primeros = {c.nombre.split()[0] for c in intro.candidatos}
        self.assertTrue({"Juan", "Maria"} <= primeros)
        social = json.loads(Path(RUTA_GRAFO_SOCIAL).read_text(encoding="utf-8"))
        candidatos_sociales = {c["nombre"] for c in social["ciudadanos"] if c["rol"] == "CANDIDATE"}
        self.assertTrue(candidatos_sociales & {c.nombre for c in intro.candidatos})

    def test_publicaciones_tienen_rumores_y_verdades(self) -> None:
        intro = Intro.cargar(RUTA_INTRO)
        self.assertEqual({p.tipo for p in intro.publicaciones}, {"rumor", "verdad"})

    def test_pocas_o_demasiadas_laminas_son_invalidas(self) -> None:
        d = datos()
        d["laminas"] = d["laminas"][:4]
        with self.assertRaises(ValueError):
            Intro.from_dict(d)
        d = datos()
        d["laminas"] = d["laminas"] + [copy.deepcopy(d["laminas"][0]) for _ in range(2)]
        for i, l in enumerate(d["laminas"]):
            l["id"] = f"l{i}"
        with self.assertRaises(ValueError):
            Intro.from_dict(d)

    def test_lamina_sin_texto_o_con_tipo_desconocido_es_invalida(self) -> None:
        d = datos()
        d["laminas"][0]["texto"] = "  "
        with self.assertRaises(ValueError):
            Intro.from_dict(d)
        d = datos()
        d["laminas"][0]["tipo"] = "dibujo"
        with self.assertRaises(ValueError):
            Intro.from_dict(d)

    def test_candidato_inexistente_o_ids_repetidos_son_invalidos(self) -> None:
        d = datos()
        d["laminas"][3]["candidatos"] = ["fantasma"]
        with self.assertRaises(ValueError):
            Intro.from_dict(d)
        d = datos()
        d["candidatos"][1]["id"] = d["candidatos"][0]["id"]
        with self.assertRaises(ValueError):
            Intro.from_dict(d)

    def test_aspecto_fuera_de_rango_es_invalido(self) -> None:
        d = datos()
        d["candidatos"][0]["aspecto"]["peinado"] = "mohicano"
        with self.assertRaises(ValueError):
            Intro.from_dict(d)
        d = datos()
        d["candidatos"][0]["aspecto"]["color"] = 9
        with self.assertRaises(ValueError):
            Intro.from_dict(d)

    def test_modelo_no_importa_pygame(self) -> None:
        import post_truth.models.intro as modulo
        self.assertNotIn("pygame", vars(modulo))


if __name__ == "__main__":
    unittest.main()
