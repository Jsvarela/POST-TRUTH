"""Evidencia por zona, viaje con energia, respaldo y su efecto sobre Verificar y Reportar (modelo puro)."""
import copy
import json
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.config import RUTA_EVENTOS, RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL
from post_truth.decision_tree import DecisionTree, load_trees
from post_truth.models import Impact, NewsEvent
from post_truth.models.pistas import (ENERGIA_POR_NOTICIA, Evidencia, Investigacion, Pista, Senal, TipoEvidencia,
                                      ZonaTarjeta, texto_consecuencia, validar_evidencias)
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.structures.propagacion import (FUERZA_REPORTAR, FUERZA_VERIFICAR, REPORTAR, REPORTE_INFUNDADO, VERIFICAR,
                                               fuerza_reportar, fuerza_verificar, mensaje_respaldo, reporte_rechazado,
                                               simular_decision)


def pista(id: str, zona: ZonaTarjeta, senal: Senal = Senal.FALSA, costo: int = 1) -> Pista:
    return Pista(id, zona, id.title(), f"hallazgo de {id}", senal, costo)


def evidencia(id: str, lugar: str, senal: Senal = Senal.FALSA, tipo: TipoEvidencia = TipoEvidencia.TESTIGO) -> Evidencia:
    return Evidencia(id, lugar, tipo, id.title(), f"hallazgo de {id}", senal)


def investigacion(**kw) -> Investigacion:
    return Investigacion(
        (pista("cuenta", ZonaTarjeta.AUTOR), pista("hora", ZonaTarjeta.FECHA, Senal.NEUTRA),
         pista("foto", ZonaTarjeta.IMAGEN, Senal.VERDADERA)),
        evidencias=(evidencia("testigo", "colegio"), evidencia("acta", "alcaldia", Senal.VERDADERA, TipoEvidencia.DOCUMENTO),
                    evidencia("ruido", "parque", Senal.NEUTRA, TipoEvidencia.GRABACION)), **kw)


class EvidenciaTest(unittest.TestCase):
    def test_roundtrip_dict(self) -> None:
        e = evidencia("testigo", "colegio")
        self.assertEqual(Evidencia.from_dict(json.loads(json.dumps(e.to_dict()))), e)

    def test_no_tiene_costo_propio_porque_se_paga_el_viaje(self) -> None:
        self.assertEqual(evidencia("t", "colegio").costo, 0)

    def test_datos_invalidos(self) -> None:
        with self.assertRaises(ValueError):
            Evidencia("", "colegio", TipoEvidencia.TESTIGO, "t", "h", Senal.FALSA)
        with self.assertRaises(ValueError):
            Evidencia("x", "", TipoEvidencia.TESTIGO, "t", "h", Senal.FALSA)
        with self.assertRaises(ValueError):
            Evidencia("x", "colegio", TipoEvidencia.TESTIGO, " ", "h", Senal.FALSA)
        with self.assertRaises(ValueError):
            Evidencia.from_dict({"id": "x", "lugar": "colegio", "tipo": "rumor", "titulo": "t", "hallazgo": "h", "senal": "falsa"})

    def test_ids_y_lugares_unicos(self) -> None:
        self.assertEqual(len(validar_evidencias([evidencia("a", "colegio"), evidencia("b", "parque")])), 2)
        with self.assertRaises(ValueError):
            validar_evidencias([evidencia("a", "colegio"), evidencia("a", "parque")])
        with self.assertRaises(ValueError):
            validar_evidencias([evidencia("a", "colegio"), evidencia("b", "colegio")])

    def test_una_pista_y_una_evidencia_no_pueden_compartir_id(self) -> None:
        with self.assertRaises(ValueError):
            Investigacion((pista("x", ZonaTarjeta.AUTOR),), evidencias=(evidencia("x", "colegio"),))


class InvestigacionConMapaTest(unittest.TestCase):
    def test_arranca_con_la_energia_completa_y_sin_hallazgos(self) -> None:
        inv = investigacion()
        self.assertEqual((inv.energia, inv.viaje_gastado), (ENERGIA_POR_NOTICIA, 0))
        self.assertEqual(inv.lugares_pendientes(), {"colegio", "alcaldia", "parque"})
        self.assertEqual(inv.lugares_revisados(), set())

    def test_revelar_evidencia_al_llegar_no_cuesta_y_es_idempotente(self) -> None:
        inv = investigacion()
        e = inv.revelar_evidencia("colegio")
        self.assertEqual(e.id, "testigo")
        self.assertEqual(inv.energia, ENERGIA_POR_NOTICIA)             # el viaje se paga aparte
        self.assertIsNone(inv.revelar_evidencia("colegio"))            # ya revelada
        self.assertEqual(inv.descubiertas, ["testigo"])
        self.assertEqual(inv.lugares_pendientes(), {"alcaldia", "parque"})
        self.assertEqual(inv.lugares_revisados(), {"colegio"})

    def test_una_zona_sin_evidencia_no_revela_nada(self) -> None:
        inv = investigacion()
        self.assertIsNone(inv.revelar_evidencia("plaza"))
        self.assertEqual(inv.descubiertas, [])

    def test_la_evidencia_entra_al_mismo_registro_que_las_pistas(self) -> None:
        inv = investigacion(energia_max=9)
        inv.investigar("cuenta")
        inv.revelar_evidencia("colegio")
        self.assertEqual([h.id for h in inv.pistas_descubiertas()], ["cuenta", "testigo"])
        self.assertTrue(inv.esta_descubierta("testigo"))
        self.assertEqual(inv.hallazgo("testigo").lugar, "colegio")

    def test_viajar_gasta_energia_y_no_cobra_si_no_alcanza(self) -> None:
        inv = investigacion()
        self.assertTrue(inv.viajar(2))
        self.assertEqual((inv.energia, inv.viaje_gastado), (ENERGIA_POR_NOTICIA - 2, 2))
        self.assertFalse(inv.viajar(ENERGIA_POR_NOTICIA))              # no alcanza
        self.assertEqual((inv.energia, inv.viaje_gastado), (ENERGIA_POR_NOTICIA - 2, 2))
        self.assertTrue(inv.viajar(0))                                  # quedarse no cuesta
        with self.assertRaises(ValueError):
            inv.viajar(-1)

    def test_la_energia_es_una_sola_para_la_tarjeta_y_los_viajes(self) -> None:
        inv = investigacion(energia_max=4)
        inv.viajar(3)
        self.assertEqual(inv.investigar("foto").estado, "nueva")        # cuesta 1: queda 0
        self.assertEqual(inv.energia, 0)
        self.assertEqual(inv.investigar("cuenta").estado, "sin_energia")
        gastado = sum(inv.pista(id).costo for id in inv.descubiertas if id in {"cuenta", "hora", "foto"})
        self.assertEqual(gastado + inv.viaje_gastado + inv.energia, inv.energia_max)

    def test_el_veredicto_cuenta_pistas_y_evidencias(self) -> None:
        inv = investigacion(energia_max=9)
        self.assertEqual(inv.veredicto(), "incierta")
        inv.revelar_evidencia("colegio")                                # falsa
        self.assertEqual(inv.veredicto(), "falsa")
        inv.revelar_evidencia("alcaldia")                               # verdadera: empate
        self.assertEqual(inv.veredicto(), "incierta")
        inv.investigar("cuenta")                                        # falsa
        self.assertEqual(inv.veredicto(), "falsa")

    def test_serializacion_del_progreso_con_viajes(self) -> None:
        inv = investigacion()
        inv.viajar(2)
        inv.revelar_evidencia("colegio")
        inv.investigar("cuenta")
        copia = Investigacion.from_dict(json.loads(json.dumps(inv.to_dict())), inv.pistas, inv.evidencias)
        self.assertEqual(copia, inv)
        self.assertEqual(copia.viaje_gastado, 2)


class RespaldoTest(unittest.TestCase):
    def test_nada_tarjeta_o_campo(self) -> None:
        inv = investigacion(energia_max=9)
        self.assertEqual((inv.respaldo("verificar"), inv.respaldo("reportar")), (0, 0))
        inv.investigar("cuenta")                                        # pista de la tarjeta que apunta a falsa
        self.assertEqual((inv.respaldo("verificar"), inv.respaldo("reportar")), (1, 1))
        inv.revelar_evidencia("colegio")                                # evidencia de campo que apunta a falsa
        self.assertEqual((inv.respaldo("verificar"), inv.respaldo("reportar")), (2, 2))

    def test_lo_neutro_no_respalda_nada(self) -> None:
        inv = investigacion(energia_max=9)
        inv.investigar("hora")
        inv.revelar_evidencia("parque")
        self.assertEqual((inv.respaldo("verificar"), inv.respaldo("reportar")), (0, 0))

    def test_reportar_solo_cuenta_lo_que_apunta_a_falsa_pero_verificar_cuenta_cualquier_senal(self) -> None:
        inv = investigacion(energia_max=9)
        inv.revelar_evidencia("alcaldia")                               # evidencia que apunta a VERDADERA
        self.assertEqual(inv.respaldo("verificar"), 2)                  # verificar se apoya en ella
        self.assertEqual(inv.respaldo("reportar"), 0)                   # pero no justifica reportar
        inv.investigar("foto")                                          # pista verdadera: tampoco
        self.assertEqual(inv.respaldo("reportar"), 0)

    def test_la_evidencia_de_campo_pesa_mas_que_cualquier_cantidad_de_pistas_de_tarjeta(self) -> None:
        inv = investigacion(energia_max=9)
        inv.investigar("cuenta")
        inv.investigar("foto")
        self.assertEqual(inv.respaldo("verificar"), 1)
        inv.revelar_evidencia("colegio")
        self.assertEqual(inv.respaldo("verificar"), 2)


class FuerzaYEfectoTest(unittest.TestCase):
    def test_tablas_de_fuerza(self) -> None:
        self.assertEqual([fuerza_verificar(n) for n in (0, 1, 2)], [0.5, 0.75, 1.0])
        self.assertEqual([fuerza_reportar(n) for n in (0, 1, 2)], [0.0, 0.6, 1.0])
        self.assertEqual((fuerza_verificar(-3), fuerza_verificar(9)), (0.5, 1.0))   # se acota a 0..2
        self.assertEqual((FUERZA_VERIFICAR[2], FUERZA_REPORTAR[0]), (1.0, 0.0))
        self.assertTrue(reporte_rechazado(0))
        self.assertFalse(reporte_rechazado(1))

    def test_mensajes_para_el_jugador(self) -> None:
        self.assertEqual(len({mensaje_respaldo(VERIFICAR, n) for n in (0, 1, 2)}), 3)
        self.assertEqual(len({mensaje_respaldo(REPORTAR, n) for n in (0, 1, 2)}), 3)
        self.assertEqual(mensaje_respaldo("compartir", 2), "")
        self.assertIn("rechazado", mensaje_respaldo(REPORTAR, 0))

    def test_atenuar_beneficios_solo_toca_lo_bueno(self) -> None:
        impacto = Impact(verified_information=12, trust=-7, misinformation=-8, conflicts=5, score=10)
        a = impacto.atenuar_beneficios(0.5)
        self.assertEqual(a.verified_information, 6)       # beneficio: baja a la mitad
        self.assertEqual(a.misinformation, -4)            # reducir desinformacion tambien es beneficio
        self.assertEqual(a.score, 5)
        self.assertEqual(a.trust, -7)                     # perjuicio: intacto
        self.assertEqual(a.conflicts, 5)                  # subir conflictos es perjuicio: intacto
        self.assertEqual(impacto.atenuar_beneficios(1.0), impacto)
        self.assertEqual(impacto.atenuar_beneficios(0.0).verified_information, 0)

    def _social(self) -> GrafoSocial:
        return GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)

    def test_reportar_sin_pruebas_es_rechazado_y_no_toca_el_grafo(self) -> None:
        g = self._social()
        antes = g.to_dict()
        self.assertIsNone(simular_decision(g, REPORTAR, True, "jugador", "tomas", random.Random(1), respaldo=0))
        self.assertEqual(g.to_dict(), antes)

    def test_reportar_con_respaldo_parcial_limita_y_con_respaldo_total_corta(self) -> None:
        g = self._social()
        n = len(g.vecinos("tomas"))
        sim = simular_decision(g, REPORTAR, True, "jugador", "tomas", random.Random(1), respaldo=1)
        self.assertEqual(len(g.vecinos("tomas")), n)                    # sigue conectado...
        self.assertEqual(sim.aristas_cortadas, ())
        self.assertEqual(len(sim.aristas_debilitadas), n)               # ...pero con la mitad del peso
        g2 = self._social()
        sim2 = simular_decision(g2, REPORTAR, True, "jugador", "tomas", random.Random(1), respaldo=2)
        self.assertEqual(g2.vecinos("tomas"), [])
        self.assertEqual(len(sim2.aristas_cortadas), n)

    def test_verificar_frena_mas_con_mas_respaldo(self) -> None:
        pesos = {}
        for nivel in (0, 1, 2):
            g = self._social()
            antes = g.arista("tomas", "isabela").peso
            simular_decision(g, VERIFICAR, True, "jugador", "tomas", random.Random(1), respaldo=nivel)
            pesos[nivel] = g.arista("tomas", "isabela").peso / antes
        self.assertGreater(pesos[0], pesos[1])
        self.assertGreater(pesos[1], pesos[2])
        self.assertAlmostEqual(pesos[2], 0.35)                           # respaldo total: el freno de siempre
        self.assertLess(pesos[0], 1.0)                                   # incluso sin pruebas frena algo

    def test_el_alcance_baja_al_subir_el_respaldo_en_promedio(self) -> None:
        def alcance(nivel: int) -> float:
            total = 0
            for semilla in range(150):
                g = self._social()
                sim = simular_decision(g, VERIFICAR, True, "jugador", "tomas", random.Random(semilla), respaldo=nivel)
                total += sim.resultado.alcanzados
            return total / 150
        self.assertGreater(alcance(0), alcance(1))
        self.assertGreater(alcance(1), alcance(2))

    def test_el_reporte_infundado_cuesta_confianza(self) -> None:
        self.assertLess(REPORTE_INFUNDADO.trust, 0)


class EventosConEvidenciaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.arboles = load_trees(RUTA_EVENTOS)
        self.ciudad = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)

    def test_cada_noticia_tiene_de_dos_a_tres_evidencias_en_zonas_distintas_y_existentes(self) -> None:
        for a in self.arboles:
            ev = a.event.evidences
            self.assertTrue(2 <= len(ev) <= 3, a.event.event_id)
            self.assertEqual(len({e.lugar for e in ev}), len(ev))
            for e in ev:
                self.assertIn(e.lugar, self.ciudad, f"{a.event.event_id}: {e.lugar}")
                self.assertTrue(e.titulo and e.hallazgo)

    def test_las_evidencias_apuntan_a_la_veracidad_real_de_la_noticia(self) -> None:
        for a in self.arboles:
            esperada = Senal.FALSA if a.event.truth_level < 50 else Senal.VERDADERA
            for e in a.event.evidences:
                self.assertIs(e.senal, esperada, f"{a.event.event_id}/{e.id}")

    def test_hay_evidencia_a_distintas_distancias_de_la_plaza(self) -> None:
        costos = self.ciudad.costos_desde(self.ciudad.zona_inicial)
        distancias = {costos[e.lugar] for a in self.arboles for e in a.event.evidences}
        self.assertTrue({0, 1, 2} <= distancias, distancias)

    def test_investigar_todo_no_alcanza_la_energia(self) -> None:
        """Pistas de la tarjeta + viajar a todo lo que hay en el mapa cuesta mas de lo que se tiene."""
        for a in self.arboles:
            tarjeta = sum(p.costo for p in a.event.clues)
            viajes = sum(self.ciudad.ruta(self.ciudad.zona_inicial, e.lugar).costo for e in a.event.evidences)
            self.assertGreater(tarjeta + viajes, ENERGIA_POR_NOTICIA, a.event.event_id)

    def test_una_conclusion_cabe_en_la_energia_con_las_pistas_baratas_o_con_un_viaje(self) -> None:
        """Siempre hay una forma de llegar a respaldo 2 gastando como maximo la energia."""
        for a in self.arboles:
            costos = self.ciudad.costos_desde(self.ciudad.zona_inicial)
            mas_barata = min(costos[e.lugar] for e in a.event.evidences)
            self.assertLessEqual(mas_barata, ENERGIA_POR_NOTICIA, a.event.event_id)

    def test_las_variantes_de_evidencia_cambian_el_texto(self) -> None:
        a = self.arboles[0]                                              # colegio-cerrado
        verificar = next(n for n in a.root.children if n.tipo == "verificar")
        inv = Investigacion(a.event.clues, evidencias=a.event.evidences)
        sin = verificar.consecuencia(inv.pistas_descubiertas())
        inv.revelar_evidencia("colegio")
        con = verificar.consecuencia(inv.pistas_descubiertas())
        self.assertNotEqual(sin, con)
        self.assertIn("directora", con)

    def test_una_variante_con_una_evidencia_inexistente_es_invalida(self) -> None:
        crudo = copy.deepcopy(json.loads(Path(RUTA_EVENTOS).read_text(encoding="utf-8"))[0])
        crudo["decisions"][0]["variantes"] = [{"si": ["testigo-fantasma"], "texto": "x"}]
        with self.assertRaises(ValueError):
            DecisionTree.from_event_dict(crudo)

    def test_dos_evidencias_en_la_misma_zona_son_invalidas(self) -> None:
        crudo = copy.deepcopy(json.loads(Path(RUTA_EVENTOS).read_text(encoding="utf-8"))[0])
        crudo["evidencias"][1]["lugar"] = crudo["evidencias"][0]["lugar"]
        with self.assertRaises(ValueError):
            DecisionTree.from_event_dict(crudo)

    def test_roundtrip_de_la_noticia_con_evidencias(self) -> None:
        for crudo in json.loads(Path(RUTA_EVENTOS).read_text(encoding="utf-8")):
            evento = NewsEvent.from_dict(crudo)
            self.assertEqual(NewsEvent.from_dict(json.loads(json.dumps(evento.to_dict()))), evento)
            self.assertEqual(evento.to_dict()["evidencias"], crudo["evidencias"])

    def test_el_texto_incluye_la_evidencia_revisada_si_no_hay_variante(self) -> None:
        inv = Investigacion((), evidencias=(evidencia("t", "colegio"),))
        inv.revelar_evidencia("colegio")
        self.assertIn("Habias revisado: t.", texto_consecuencia("base.", (), inv.pistas_descubiertas()))


if __name__ == "__main__":
    unittest.main()
