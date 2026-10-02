"""Contenido de data/events.json: carga, variedad y reglas que debe cumplir cada noticia (invariantes).

Estas pruebas protegen el contenido a medida que crece: si se agrega un evento mal armado (zona repetida,
variante que apunta a una pista inexistente, noticia sin opcion buena...) falla aqui y no en medio de una partida.
"""
import json
import os
import random
import sys
import unittest
from collections import Counter
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from post_truth.config import EVENTOS_POR_PARTIDA, RUTA_EVENTOS, RUTA_GRAFO_CIUDAD
from post_truth.decision_tree import load_trees
from post_truth.models.dominio import Impact
from post_truth.models.pistas import ENERGIA_POR_NOTICIA, Senal
from post_truth.pygame_app import App
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.propagacion import es_falsa

CANDIDATOS = ("Juan", "Maria", "Andres", "Lucia")
CAMPOS_IMPACTO = ("verified_information", "trust", "coexistence", "digital_wellbeing", "misinformation", "conflicts",
                  "score")


def crudos() -> list[dict]:
    return json.loads(Path(RUTA_EVENTOS).read_text(encoding="utf-8"))


def texto_del_evento(e: dict) -> str:
    partes = [e["title"], e["content"], e["autor"]["nombre"], e["fuente"]]
    partes += [h["titulo"] + " " + h["hallazgo"] for h in e["pistas"] + e["evidencias"]]
    return " ".join(partes)


class ContenidoEventosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.eventos = crudos()
        cls.arboles = load_trees(RUTA_EVENTOS)
        cls.ciudad = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)

    # --- cantidad y variedad ----------------------------------------------------------------
    def test_hay_entre_16_y_20_eventos_con_ids_unicos(self) -> None:
        self.assertTrue(16 <= len(self.eventos) <= 20, len(self.eventos))
        ids = [e["id"] for e in self.eventos]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreater(len(self.eventos), EVENTOS_POR_PARTIDA)    # sobran para sortear

    def test_hay_de_todos_los_tipos_de_noticia(self) -> None:
        tipos = Counter(e["kind"] for e in self.eventos)
        falsas = sum(es_falsa(e["truth_level"]) for e in self.eventos)
        verdaderas = sum(e["truth_level"] >= 50 and e["kind"] not in ("opinion", "campana_civica") for e in self.eventos)
        self.assertGreaterEqual(falsas, 6)
        self.assertGreaterEqual(verdaderas, 4)
        self.assertGreaterEqual(tipos["opinion"], 3)
        self.assertGreaterEqual(tipos["campana_civica"], 2)
        self.assertGreaterEqual(tipos["ataque"] + tipos["contenido_manipulado"], 3)   # ataques entre candidatos

    def test_cada_zona_tiene_al_menos_4_evidencias_de_campo(self) -> None:
        por_zona = Counter(ev["lugar"] for e in self.eventos for ev in e["evidencias"])
        self.assertEqual(set(por_zona), {z.id for z in self.ciudad.zonas()})
        for zona, n in por_zona.items():
            self.assertGreaterEqual(n, 4, zona)

    def test_los_cuatro_candidatos_aparecen_en_varios_eventos(self) -> None:
        for nombre in CANDIDATOS:
            n = sum(nombre in texto_del_evento(e) for e in self.eventos)
            self.assertGreaterEqual(n, 3, nombre)

    def test_una_partida_sortea_publicaciones_distintas_y_el_orden_cambia(self) -> None:
        app = App()
        try:
            escena = app.estados._estados["escena"]
            juegos = []
            for semilla in range(6):
                escena.rng = random.Random(semilla)
                escena.al_entrar()
                ids = [a.event.event_id for a in escena.arboles]
                self.assertEqual(len(ids), EVENTOS_POR_PARTIDA)
                self.assertEqual(len(set(ids)), len(ids))            # sin repetir ninguna en la misma partida
                juegos.append(tuple(ids))
            self.assertGreater(len(set(juegos)), 3)                  # el contenido cambia entre partidas
            escena.eventos_por_partida = None                        # None = todas (pruebas)
            escena.al_entrar()
            self.assertEqual(len(escena.arboles), len(self.eventos))
        finally:
            pygame.quit()

    # --- invariantes de cada evento ---------------------------------------------------------
    def test_pistas_y_evidencias_cumplen_las_reglas(self) -> None:
        for e in self.eventos:
            id = e["id"]
            self.assertTrue(4 <= len(e["pistas"]) <= 5, id)
            self.assertEqual(len({p["zona"] for p in e["pistas"]}), len(e["pistas"]), id)   # una pista por zona de la tarjeta
            self.assertTrue(2 <= len(e["evidencias"]) <= 3, id)
            self.assertEqual(len({ev["lugar"] for ev in e["evidencias"]}), len(e["evidencias"]), id)
            hallazgos = [h["id"] for h in e["pistas"] + e["evidencias"]]
            self.assertEqual(len(hallazgos), len(set(hallazgos)), f"{id}: ids repetidos")
            self.assertGreater(sum(p["costo"] for p in e["pistas"]), ENERGIA_POR_NOTICIA, id)   # hay que elegir
            for ev in e["evidencias"]:
                self.assertIn(ev["lugar"], self.ciudad, id)

    def test_la_senal_de_cada_hallazgo_coincide_con_la_veracidad(self) -> None:
        for a in self.arboles:
            e = a.event
            hallazgos = list(e.clues) + list(e.evidences)
            senales = {h.senal for h in hallazgos}
            if e.kind == "opinion":
                self.assertEqual(senales, {Senal.NEUTRA}, e.event_id)     # una opinion no se prueba ni se desmiente
            elif es_falsa(e.truth_level):
                self.assertNotIn(Senal.VERDADERA, senales, e.event_id)
                self.assertTrue(all(ev.senal is Senal.FALSA for ev in e.evidences), e.event_id)
            else:
                self.assertNotIn(Senal.FALSA, senales, e.event_id)
                self.assertTrue(all(ev.senal is Senal.VERDADERA for ev in e.evidences), e.event_id)

    def test_toda_decision_tiene_efecto_completo_y_acotado(self) -> None:
        for e in self.eventos:
            self.assertEqual(set(e["root_effect"]), set(CAMPOS_IMPACTO), e["id"])
            self.assertLessEqual(max(abs(v) for v in e["root_effect"].values()), 6, e["id"])
            pendientes = list(e["decisions"])
            self.assertTrue(3 <= len(pendientes) <= 4, e["id"])
            while pendientes:
                d = pendientes.pop()
                self.assertEqual(set(d["effect"]), set(CAMPOS_IMPACTO), f"{e['id']}/{d['action']}")
                self.assertLessEqual(max(abs(v) for v in d["effect"].values()), 20, f"{e['id']}/{d['action']}")
                self.assertTrue(d["description"], f"{e['id']}/{d['action']}")
                pendientes += d.get("children", [])

    def test_cada_noticia_tiene_una_opcion_buena_y_una_mala(self) -> None:
        """La decision correcta existe y suma puntos; la irresponsable resta: si no, no hay nada que aprender."""
        for a in self.arboles:
            ramas = a.root.children
            puntajes = [a.accumulated_impact(n.node_id).score for n in ramas]
            self.assertGreater(max(puntajes), 0, a.event.event_id)
            # en una noticia falsa compartir cuesta puntos; en una verdadera u opinion lo malo es no hacer nada (0)
            self.assertLess(min(puntajes), 1 if not es_falsa(a.event.truth_level) else 0, a.event.event_id)

    def test_cada_tipo_de_noticia_ofrece_las_acciones_que_le_corresponden(self) -> None:
        for a in self.arboles:
            tipos = {n.tipo for n in a.root.children}
            e = a.event
            if e.kind == "opinion":
                self.assertIn("ignorar", tipos, e.event_id)
                self.assertIn("", tipos, e.event_id)                      # responder: no propaga por el grafo
                self.assertNotIn("reportar", tipos, e.event_id)
            elif es_falsa(e.truth_level):
                self.assertTrue({"compartir", "verificar", "reportar"} <= tipos, e.event_id)
            else:
                self.assertTrue({"compartir", "verificar"} <= tipos, e.event_id)

    def test_la_respuesta_correcta_de_una_noticia_falsa_no_es_compartirla(self) -> None:
        for a in self.arboles:
            if not es_falsa(a.event.truth_level):
                continue
            por_tipo = {n.tipo: a.accumulated_impact(n.node_id) for n in a.root.children}
            self.assertLess(por_tipo["compartir"].score, 0, a.event.event_id)
            self.assertGreater(por_tipo["verificar"].score, 0, a.event.event_id)
            self.assertGreater(por_tipo["reportar"].score, 0, a.event.event_id)

    def test_el_texto_no_lleva_acentos_ni_caracteres_raros(self) -> None:
        texto = Path(RUTA_EVENTOS).read_text(encoding="utf-8")
        raros = {c for c in texto if ord(c) > 127}
        self.assertEqual(raros, set())

    def test_el_efecto_de_cada_decision_es_un_impacto_valido(self) -> None:
        for e in self.eventos:
            for d in e["decisions"]:
                Impact.from_dict(d["effect"])


if __name__ == "__main__":
    unittest.main()
