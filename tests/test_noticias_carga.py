"""Carga de data/events.json con la tarjeta de Civitas, las pistas y las variantes de consecuencia."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.config import RUTA_EVENTOS, RUTA_GRAFO_CIUDAD
from post_truth.decision_tree import DecisionTree, load_trees
from post_truth.models import NewsEvent
from post_truth.models.pistas import ENERGIA_POR_NOTICIA, Investigacion, Senal, ZonaTarjeta
from post_truth.models.publicacion import MOTIVOS_IMAGEN
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.propagacion import es_falsa


def datos() -> list[dict]:
    return json.loads(Path(RUTA_EVENTOS).read_text(encoding="utf-8"))


class NoticiasCargaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.arboles = load_trees(RUTA_EVENTOS)

    def test_las_cinco_noticias_traen_tarjeta_completa(self) -> None:
        self.assertEqual(len(self.arboles), 5)
        for a in self.arboles:
            e = a.event
            self.assertIsNotNone(e.author, e.event_id)
            self.assertTrue(e.source and e.date, e.event_id)
            self.assertIsNotNone(e.image, e.event_id)
            self.assertGreater(e.likes, 0)
            self.assertGreaterEqual(e.comments, 0)

    def test_de_cuatro_a_cinco_pistas_con_zonas_e_ids_unicos_y_costos_validos(self) -> None:
        for a in self.arboles:
            pistas = a.event.clues
            self.assertTrue(4 <= len(pistas) <= 5, a.event.event_id)
            self.assertEqual(len({p.id for p in pistas}), len(pistas))
            self.assertEqual(len({p.zona for p in pistas}), len(pistas))
            for p in pistas:
                self.assertIn(p.costo, (1, 2))
                self.assertTrue(p.titulo and p.hallazgo)

    def test_hay_que_elegir_el_costo_total_supera_la_energia(self) -> None:
        for a in self.arboles:
            self.assertGreater(sum(p.costo for p in a.event.clues), ENERGIA_POR_NOTICIA, a.event.event_id)

    def test_las_pistas_son_coherentes_con_la_veracidad(self) -> None:
        for a in self.arboles:
            senales = [p.senal for p in a.event.clues]
            if es_falsa(a.event.truth_level):
                self.assertIn(Senal.FALSA, senales, a.event.event_id)
                self.assertNotIn(Senal.VERDADERA, senales, a.event.event_id)
            else:
                self.assertIn(Senal.VERDADERA, senales, a.event.event_id)
                self.assertNotIn(Senal.FALSA, senales, a.event.event_id)
            self.assertIn(Senal.NEUTRA, senales, f"{a.event.event_id}: falta una pista enganosa")

    def test_con_la_energia_se_puede_llegar_a_una_conclusion_pero_no_a_todo(self) -> None:
        """Con 3 de energia hay una combinacion de pistas baratas que ya apunta a la veracidad."""
        for a in self.arboles:
            inv = Investigacion(a.event.clues)
            for p in sorted(a.event.clues, key=lambda p: p.costo):
                inv.investigar(p.id)
            self.assertIn(inv.veredicto(), ("falsa", "verdadera"), a.event.event_id)
            self.assertLess(len(inv.descubiertas), len(a.event.clues))

    def test_las_imagenes_usan_una_zona_conocida_y_el_motivo_coincide_con_la_ciudad(self) -> None:
        ciudad = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)
        self.assertEqual(set(MOTIVOS_IMAGEN), {z.id for z in ciudad.zonas()})
        for a in self.arboles:
            self.assertIn(a.event.image.motivo, MOTIVOS_IMAGEN)

    def test_las_variantes_nombran_pistas_de_su_noticia(self) -> None:
        for a in self.arboles:
            ids = {p.id for p in a.event.clues} | {e.id for e in a.event.evidences}
            n = 0
            for nodo in a.dfs_nodes():
                for v in nodo.variantes:
                    self.assertTrue(v.si <= ids, f"{nodo.node_id}: {sorted(v.si - ids)}")
                    n += 1
            self.assertGreaterEqual(n, 3, a.event.event_id)

    def test_cada_noticia_tiene_variantes_en_su_decision_de_compartir(self) -> None:
        for a in self.arboles:
            compartir = next(n for n in a.root.children if n.tipo == "compartir")
            self.assertTrue(compartir.variantes, a.event.event_id)

    def test_las_pistas_cambian_la_consecuencia(self) -> None:
        a = self.arboles[0]                                                 # colegio-cerrado
        compartir = next(n for n in a.root.children if n.tipo == "compartir")
        inv = Investigacion(a.event.clues, energia_max=9)
        sin_pistas = compartir.consecuencia(inv.pistas_descubiertas())
        self.assertEqual(sin_pistas, compartir.description)                 # sin investigar: texto base
        inv.investigar("imagen-reutilizada")
        con_imagen = compartir.consecuencia(inv.pistas_descubiertas())
        inv.investigar("cuenta-sospechosa")
        inv.investigar("sin-fuente")
        con_varias = compartir.consecuencia(inv.pistas_descubiertas())
        self.assertEqual(len({sin_pistas, con_imagen, con_varias}), 3)
        self.assertIn("2021", con_imagen)

    def test_una_pista_neutra_no_cambia_a_una_variante_pero_si_se_registra(self) -> None:
        a = self.arboles[0]
        compartir = next(n for n in a.root.children if n.tipo == "compartir")
        inv = Investigacion(a.event.clues)
        inv.investigar("hora-normal")
        self.assertEqual(compartir.consecuencia(inv.pistas_descubiertas()),
                         f"{compartir.description} Habias revisado: hora normal.")

    def test_roundtrip_de_la_noticia(self) -> None:
        for crudo in datos():
            evento = NewsEvent.from_dict(crudo)
            self.assertEqual(NewsEvent.from_dict(json.loads(json.dumps(evento.to_dict()))), evento)

    def test_el_json_serializado_conserva_los_campos_de_la_tarjeta(self) -> None:
        crudo = datos()[0]
        d = NewsEvent.from_dict(crudo).to_dict()
        for campo in ("autor", "fuente", "fecha", "imagen", "likes", "comentarios", "pistas", "evidencias"):
            self.assertEqual(d[campo], crudo[campo], campo)

    def test_un_evento_sin_los_campos_nuevos_sigue_cargando(self) -> None:
        """Compatibilidad: los campos de la tarjeta y las pistas son opcionales."""
        viejo = {"id": "x", "title": "t", "content": "c", "kind": "rumor", "truth_level": 20,
                 "decisions": [{"action": "Compartir", "tipo": "compartir", "description": "d"}]}
        arbol = DecisionTree.from_event_dict(viejo)
        self.assertEqual(arbol.event.clues, ())
        self.assertIsNone(arbol.event.author)
        self.assertEqual(arbol.root.children[0].consecuencia([]), "d")

    def test_variante_con_pista_inexistente_es_invalida(self) -> None:
        crudo = copy.deepcopy(datos()[0])
        crudo["decisions"][0]["variantes"] = [{"si": ["fantasma"], "texto": "x"}]
        with self.assertRaises(ValueError):
            DecisionTree.from_event_dict(crudo)

    def test_dos_pistas_en_la_misma_zona_son_invalidas(self) -> None:
        crudo = copy.deepcopy(datos()[0])
        crudo["pistas"][1]["zona"] = crudo["pistas"][0]["zona"]
        with self.assertRaises(ValueError):
            DecisionTree.from_event_dict(crudo)

    def test_todas_las_zonas_de_la_tarjeta_se_pueden_usar(self) -> None:
        usadas = {p.zona for a in self.arboles for p in a.event.clues}
        self.assertEqual(usadas, set(ZonaTarjeta))                          # el diseno usa las 6 zonas


if __name__ == "__main__":
    unittest.main()
