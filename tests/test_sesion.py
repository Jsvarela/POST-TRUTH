"""PartidaSesion: turnos con 1 a 4 jugadores, operaciones y serializacion de ida y vuelta (sin pygame)."""
import json
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.config import RUTA_EVENTOS, RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL
from post_truth.decision_tree import load_trees
from post_truth.game_state import CityState
from post_truth.models import Role
from post_truth.models.personaje import Genero, Personaje
from post_truth.sesion import (CONSECUENCIA, DECIDIENDO, FIN, JUGADOR, MAX_JUGADORES, PartidaSesion)
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial

ROLES = (Role.CITIZEN, Role.JOURNALIST, Role.INFLUENCER, Role.CANDIDATE)


def nueva(n: int = 1, semilla: int = 5, eventos: int = 4) -> PartidaSesion:
    arboles = load_trees(RUTA_EVENTOS)
    rng = random.Random(semilla)
    return PartidaSesion.nueva([Personaje(ROLES[i], Genero.MUJER) for i in range(n)], rng.sample(arboles, eventos),
                               GrafoSocial.cargar(RUTA_GRAFO_SOCIAL), GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD), rng)


def ida_y_vuelta(sesion: PartidaSesion) -> PartidaSesion:
    return PartidaSesion.from_dict(json.loads(json.dumps(sesion.to_dict())))


def rama(sesion: PartidaSesion, tipo: str):
    return next(n for n in sesion.arbol.root.children if n.tipo == tipo)


def jugar_turno(sesion: PartidaSesion, tipo: str = "ignorar") -> None:
    """El jugador de turno decide `tipo` (o la primera rama si no existe) y se cierra su turno."""
    j = sesion.jugador_actual
    nodo = next((n for n in sesion.arbol.root.children if n.tipo == tipo), sesion.arbol.root.children[0])
    r = sesion.decidir(j.id, nodo)
    assert r.ok, r.motivo
    sesion.aplicar()
    assert sesion.continuar()


class CantidadTest(unittest.TestCase):
    def test_de_1_a_4_jugadores(self) -> None:
        for n in range(1, MAX_JUGADORES + 1):
            self.assertEqual(len(nueva(n).jugadores), n)

    def test_0_y_5_jugadores_se_rechazan(self) -> None:
        for n in (0, 5):
            with self.assertRaises(ValueError):
                PartidaSesion.nueva([Personaje(Role.CITIZEN, Genero.MUJER)] * n, load_trees(RUTA_EVENTOS),
                                    GrafoSocial.cargar(RUTA_GRAFO_SOCIAL), GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD),
                                    random.Random(1))

    def test_sin_publicaciones_se_rechaza(self) -> None:
        with self.assertRaises(ValueError):
            PartidaSesion.nueva([Personaje(Role.CITIZEN, Genero.MUJER)], [], GrafoSocial.cargar(RUTA_GRAFO_SOCIAL),
                                GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD), random.Random(1))

    def test_cada_jugador_tiene_su_vertice_con_su_rol_y_los_contactos_del_primero(self) -> None:
        s = nueva(4)
        self.assertEqual([j.id for j in s.jugadores], [JUGADOR, "jugador2", "jugador3", "jugador4"])
        base = {(a.destino, a.peso) for a in s.grafo.vecinos(JUGADOR)}
        entrantes = {(a.origen, a.peso) for a in s.grafo.aristas() if a.destino == JUGADOR}
        for j in s.jugadores:
            self.assertIs(s.grafo.vertice(j.id).rol, j.rol)
            self.assertEqual({(a.destino, a.peso) for a in s.grafo.vecinos(j.id)}, base)
            self.assertEqual({(a.origen, a.peso) for a in s.grafo.aristas() if a.destino == j.id}, entrantes)

    def test_con_un_jugador_el_grafo_no_cambia(self) -> None:
        s = nueva(1)
        self.assertEqual(len(s.grafo.vertices()), len(GrafoSocial.cargar(RUTA_GRAFO_SOCIAL).vertices()))


class TurnosTest(unittest.TestCase):
    def test_con_un_jugador_siempre_le_toca_al_mismo(self) -> None:
        s = nueva(1, eventos=3)
        for _ in range(3):
            self.assertEqual(s.jugador_actual.id, JUGADOR)
            jugar_turno(s)
        self.assertTrue(s.terminada)

    def test_en_cada_publicacion_deciden_todos_en_orden_y_el_que_abre_rota(self) -> None:
        for n in (2, 3, 4):
            s = nueva(n, eventos=n + 1)
            for evento in range(n + 1):
                self.assertEqual(s.indice, evento)
                esperado = [s.jugadores[(evento + k) % n].id for k in range(n)]
                vistos = []
                for _ in range(n):
                    vistos.append(s.jugador_actual.id)
                    jugar_turno(s)
                self.assertEqual(vistos, esperado, f"{n} jugadores, publicacion {evento}")
            self.assertTrue(s.terminada)

    def test_la_publicacion_solo_avanza_cuando_decidieron_todos(self) -> None:
        s = nueva(3)
        jugar_turno(s)
        jugar_turno(s)
        self.assertEqual((s.indice, s.turno), (0, 2))
        jugar_turno(s)
        self.assertEqual((s.indice, s.turno), (1, 0))

    def test_actuar_fuera_de_turno_se_rechaza_sin_cambiar_nada(self) -> None:
        s = nueva(2)
        otro = s.jugadores[1]
        antes = s.to_dict()
        pista = s.arbol.event.clues[0]
        self.assertEqual(s.investigar(otro.id, pista).motivo, "no_es_su_turno")
        self.assertEqual(s.viajar(otro.id, "colegio").motivo, "no_es_su_turno")
        r = s.decidir(otro.id, s.arbol.root.children[0])
        self.assertFalse(r.ok)
        self.assertEqual(r.motivo, "no_es_su_turno")
        self.assertIsNone(s.pendiente)
        self.assertEqual(s.to_dict(), antes)

    def test_no_se_actua_con_una_decision_pendiente_ni_en_consecuencias(self) -> None:
        s = nueva(2)
        j = s.jugador_actual
        s.decidir(j.id, rama(s, "compartir"))
        self.assertEqual(s.investigar(j.id, s.arbol.event.clues[0]).motivo, "decision_pendiente")
        self.assertEqual(s.decidir(j.id, s.arbol.root.children[0]).motivo, "decision_pendiente")
        s.aplicar()
        self.assertEqual(s.fase, CONSECUENCIA)
        self.assertEqual(s.viajar(j.id, "colegio").motivo, "fuera_de_fase")
        self.assertTrue(s.continuar())
        self.assertEqual(s.fase, DECIDIENDO)
        self.assertFalse(s.continuar())    # fuera de consecuencias no hace nada

    def test_aplicar_sin_decision_pendiente_falla(self) -> None:
        with self.assertRaises(ValueError):
            nueva(2).aplicar()

    def test_un_jugador_desconocido_es_un_error(self) -> None:
        with self.assertRaises(KeyError):
            nueva(2).viajar("fantasma", "colegio")

    def test_en_fin_ya_nadie_actua(self) -> None:
        s = nueva(2, eventos=1)
        jugar_turno(s)
        jugar_turno(s)
        self.assertEqual(s.fase, FIN)
        self.assertEqual(s.viajar(s.jugadores[0].id, "colegio").motivo, "fuera_de_fase")


class EstadoIndividualTest(unittest.TestCase):
    def test_la_zona_es_de_cada_jugador(self) -> None:
        s = nueva(2)
        a, b = s.jugadores
        self.assertTrue(s.viajar(a.id, "parque").ok)
        self.assertEqual((a.zona, b.zona), ("parque", s.mapa.zona_inicial))
        jugar_turno(s)                                        # decide a
        self.assertTrue(s.viajar(b.id, "alcaldia").ok)
        self.assertEqual((a.zona, b.zona), ("parque", "alcaldia"))

    def test_los_hallazgos_se_reinician_en_la_nueva_publicacion_y_la_zona_se_conserva(self) -> None:
        s = nueva(2)
        a, b = s.jugadores
        s.viajar(a.id, "parque")
        jugar_turno(s)
        s.viajar(b.id, "colegio")
        jugar_turno(s)
        self.assertEqual(s.indice, 1)
        for j in (a, b):
            self.assertEqual(j.investigacion.lugares_revisados(),
                             {e.lugar for e in s.arbol.event.evidences} & {j.zona})   # solo lo de donde esta parado
        self.assertEqual((a.zona, b.zona), ("parque", "colegio"))

    def test_los_hallazgos_son_individuales(self) -> None:
        s = nueva(2)
        a, b = s.jugadores
        pista = s.arbol.event.clues[0]
        r = s.investigar(a.id, pista)
        self.assertEqual((r.ok, r.estado), (True, "nueva"))
        self.assertTrue(a.investigacion.esta_descubierta(pista.id))
        self.assertFalse(b.investigacion.esta_descubierta(pista.id))
        self.assertEqual(s.investigar(a.id, pista.id).estado, "repetida")

    def test_viajar_sigue_el_camino_mas_corto_y_rechaza_destinos_invalidos(self) -> None:
        s = nueva(1)
        j = s.jugadores[0]
        r = s.viajar(j.id, "colegio")
        self.assertEqual((r.ok, r.ruta), (True, s.mapa.ruta("plaza", "colegio").zonas))
        self.assertEqual(j.zona, "colegio")
        s.llegar(j.id, s.mapa.zona_inicial)
        self.assertEqual(s.viajar(j.id, s.mapa.zona_inicial).motivo, "misma_zona")
        self.assertEqual(s.viajar(j.id, "marte").motivo, "zona_desconocida")

    def test_puntos_individuales_y_la_ciudad_suma_los_de_todos(self) -> None:
        s = nueva(3, eventos=2)
        for tipo in ("compartir", "ignorar", "verificar"):
            jugar_turno(s, tipo)
        self.assertEqual(sum(j.puntos for j in s.jugadores), s.ciudad.score)
        self.assertEqual(len({j.puntos for j in s.jugadores}), 3)     # tres decisiones distintas, tres puntajes
        self.assertTrue(any(j.puntos != 0 for j in s.jugadores))

    def test_el_rol_de_quien_decide_escala_el_impacto(self) -> None:
        s = nueva(2)
        nodo = rama(s, "ignorar")
        ciudadano = s.decidir(s.jugadores[0].id, nodo).impacto
        s.pendiente = None
        s.turno = 1                                            # ahora le toca al periodista
        periodista = s.decidir(s.jugadores[1].id, nodo).impacto
        bruto = s.arbol.accumulated_impact(nodo.node_id)
        self.assertEqual(ciudadano, bruto.scaled_for_role(Role.CITIZEN))
        self.assertEqual(periodista, bruto.scaled_for_role(Role.JOURNALIST))

    def test_compartir_parte_del_vertice_de_quien_decide_y_los_autores_no_son_jugadores(self) -> None:
        s = nueva(2)
        r = s.decidir(s.jugador_actual.id, rama(s, "compartir"))
        self.assertEqual(r.simulacion.resultado.origen, s.jugador_actual.id)
        self.assertNotIn(r.simulacion.autor, [j.id for j in s.jugadores])

    def test_decidir_no_toca_los_indicadores_hasta_aplicar(self) -> None:
        s = nueva(1)
        antes = s.ciudad.to_dict()
        r = s.decidir(s.jugador_actual.id, rama(s, "compartir"))
        self.assertEqual(s.ciudad.to_dict(), antes)
        s.aplicar()
        self.assertNotEqual(s.ciudad.to_dict(), antes)
        self.assertEqual(s.jugador_actual.puntos, r.impacto.score)

    def test_el_corte_del_grafo_persiste_para_el_siguiente_jugador(self) -> None:
        s = nueva(2)
        falsa = next(i for i, a in enumerate(s.arboles) if a.event.truth_level < 50)
        s.arboles[0], s.arboles[falsa] = s.arboles[falsa], s.arboles[0]
        s.abrir_evento()
        j = s.jugador_actual
        if not j.investigacion.lugares_revisados():                                     # busca evidencia de campo
            s.viajar(j.id, next(iter(j.investigacion.lugares_pendientes())))
        r = s.decidir(j.id, rama(s, "reportar"))
        if r.simulacion is not None and r.simulacion.aristas_cortadas:
            self.assertTrue(all(s.grafo.arista(o, d) is None for o, d in r.simulacion.aristas_cortadas))


class SerializacionTest(unittest.TestCase):
    def assertIgual(self, a: PartidaSesion, b: PartidaSesion) -> None:
        self.assertEqual(a.to_dict(), b.to_dict())

    def test_ida_y_vuelta_en_cada_momento_de_la_partida(self) -> None:
        s = nueva(3, eventos=2)
        self.assertIgual(s, ida_y_vuelta(s))                          # inicio
        j = s.jugador_actual
        s.viajar(j.id, "parque")
        s.investigar(j.id, s.arbol.event.clues[0])
        self.assertIgual(s, ida_y_vuelta(s))                          # a mitad de turno
        s.decidir(j.id, rama(s, "compartir"))
        self.assertIgual(s, ida_y_vuelta(s))                          # decision pendiente
        s.aplicar()
        self.assertIgual(s, ida_y_vuelta(s))                          # consecuencias
        s.continuar()
        self.assertIgual(s, ida_y_vuelta(s))                          # le toca al siguiente
        while not s.terminada:
            jugar_turno(s)
        self.assertIgual(s, ida_y_vuelta(s))                          # fin

    def test_el_resultado_es_json_puro(self) -> None:
        d = nueva(4).to_dict()
        self.assertEqual(json.loads(json.dumps(d)), d)

    def test_lo_restaurado_tiene_los_mismos_datos(self) -> None:
        s = nueva(2, semilla=9)
        j = s.jugador_actual
        s.viajar(j.id, "colegio")
        jugar_turno(s, "compartir")
        r = ida_y_vuelta(s)
        self.assertEqual([a.event.event_id for a in r.arboles], [a.event.event_id for a in s.arboles])
        self.assertEqual([(x.id, x.zona, x.puntos, x.investigacion.descubiertas) for x in r.jugadores],
                         [(x.id, x.zona, x.puntos, x.investigacion.descubiertas) for x in s.jugadores])
        self.assertEqual((r.indice, r.turno, r.fase), (s.indice, s.turno, s.fase))
        self.assertEqual(r.ciudad, s.ciudad)
        self.assertEqual(r.jugador_actual.id, s.jugador_actual.id)
        self.assertEqual(r.grafo.to_dict(), s.grafo.to_dict())

    def test_la_decision_pendiente_se_restaura_y_se_puede_aplicar(self) -> None:
        s = nueva(2)
        j = s.jugador_actual
        original = s.decidir(j.id, rama(s, "compartir"))
        r = ida_y_vuelta(s)
        self.assertIsNone(r.pendiente.simulacion)                       # la animacion no se guarda
        self.assertEqual((r.pendiente.nodo.node_id, r.pendiente.impacto), (original.nodo.node_id, original.impacto))
        r.aplicar()
        s.aplicar()
        self.assertIgual(s, r)

    def test_una_sesion_restaurada_juega_igual_que_la_original(self) -> None:
        for n in (1, 2, 4):
            s = nueva(n, semilla=n, eventos=3)
            jugar_turno(s, "compartir")
            copia = ida_y_vuelta(s)
            for sesion in (s, copia):
                tipos = iter(("verificar", "compartir", "reportar", "ignorar") * 6)
                while not sesion.terminada:
                    j = sesion.jugador_actual
                    sesion.viajar(j.id, "colegio")
                    jugar_turno(sesion, next(tipos))
            self.assertIgual(s, copia)

    def test_datos_invalidos_se_rechazan(self) -> None:
        d = nueva(1).to_dict()
        for cambio in ({"version": 99}, {"eventos": ["no-existe"]}):
            with self.assertRaises(ValueError):
                PartidaSesion.from_dict({**d, **cambio})

    def test_ciudad_ida_y_vuelta(self) -> None:
        c = CityState()
        c.misinformation, c.score = 80, -12
        self.assertEqual(CityState.from_dict(json.loads(json.dumps(c.to_dict()))), c)



class MundoEnLaSesionTest(unittest.TestCase):
    """Operaciones que usa el mundo caminable (etapa M2): llegar a plazas y buscar evidencia."""

    def test_la_noticia_ocurre_en_la_zona_de_su_imagen(self) -> None:
        s = nueva(1, eventos=6)
        for i in range(6):
            s.abrir_evento(i)
            self.assertEqual(s.zona_noticia, s.arbol.event.image.motivo)
            self.assertIn(s.zona_noticia, s.mapa)

    def test_llegar_actualiza_la_zona_sin_revelar(self) -> None:
        s = nueva(1)
        j = s.jugador_actual
        antes = list(j.investigacion.descubiertas)
        s.llegar(j.id, "colegio")
        self.assertEqual(j.zona, "colegio")
        self.assertEqual(j.investigacion.descubiertas, antes)
        with self.assertRaises(KeyError):
            s.llegar(j.id, "marte")

    def test_buscar_evidencia_la_revela_una_sola_vez_y_solo_donde_esta(self) -> None:
        s = nueva(1, eventos=8)
        con = next(i for i, a in enumerate(s.arboles) if any(e.lugar != "plaza" for e in a.event.evidences))
        s.abrir_evento(con)
        j = s.jugador_actual
        lugar = next(e.lugar for e in s.arbol.event.evidences if e.lugar != j.zona)   # no revelada al abrir
        otra = next(z.id for z in s.mapa.zonas() if z.id not in {e.lugar for e in s.arbol.event.evidences})
        s.llegar(j.id, otra)
        self.assertIsNone(s.buscar_evidencia(j.id))
        s.llegar(j.id, lugar)
        e = s.buscar_evidencia(j.id)
        self.assertEqual(e.lugar, lugar)
        self.assertIsNone(s.buscar_evidencia(j.id))                  # ya revelada

    def test_fuera_de_turno_no_se_busca(self) -> None:
        s = nueva(2)
        otro = s.jugadores[1]
        self.assertIsNone(s.buscar_evidencia(otro.id))


if __name__ == "__main__":
    unittest.main()
