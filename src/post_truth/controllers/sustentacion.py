"""Modo sustentacion (F1 desde cualquier pantalla): capa encima del juego, que queda en pausa debajo. Arma con los
datos de la partida (o de data/ si no hay partida) lo que la vista dibuja; los recorridos los hacen las estructuras."""
import pygame

from post_truth.config import RUTA_EVENTOS, RUTA_GRAFO_CIUDAD, RUTA_GRAFO_SOCIAL
from post_truth.decision_tree import load_trees
from post_truth.models.chat import datos as datos_chat
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.structures.grafo_social import GrafoSocial
from post_truth.views.sustentacion_view import (PESTANAS, GrafoVista, NodoVista, dibujar_sustentacion,
                                                rect_pestana)

TECLAS = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}
VALOR_DIALOGO = {"desescalar": 1, "ignorar": 0, "amplificar": -1}


class Sustentacion:
    def __init__(self, app) -> None:
        self.app = app
        self.activo = False
        self.pestana = 0

    def alternar(self) -> None:
        self.activo = not self.activo

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_F1, pygame.K_ESCAPE):
                self.activo = False
            elif event.key in TECLAS:
                self.pestana = TECLAS[event.key]
            elif event.key == pygame.K_TAB:
                self.pestana = (self.pestana + 1) % len(PESTANAS)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i in range(len(PESTANAS)):
                if rect_pestana(i).collidepoint(event.pos):
                    self.pestana = i

    def _sesion(self):
        return self.app.partida or getattr(self.app.estados.estado("escena"), "_sesion", None)

    # --- contenido de cada pestana --------------------------------------------------------------------
    def arbol_decisiones(self) -> tuple[list[NodoVista], str]:
        s = self._sesion()
        arbol = s.arbol if s is not None else load_trees(RUTA_EVENTOS)[0]
        orden_dfs = {n.node_id: i for i, n in enumerate(arbol.dfs_nodes())}
        nivel, padre = {arbol.root.node_id: 0}, {arbol.root.node_id: None}
        for n in arbol.bfs_nodes():                       # BFS por niveles
            for h in n.children:
                nivel[h.node_id], padre[h.node_id] = nivel[n.node_id] + 1, n.node_id
        nodos = [NodoVista(n.node_id, n.label, f"DFS {orden_dfs[n.node_id]} | nivel {nivel[n.node_id]}",
                           padre[n.node_id]) for n in arbol.bfs_nodes()]
        texto = (f"\"{arbol.event.title}\": arbol N-ario de {len(nodos)} nodos. DFS en preorden (O(n)) acumula el "
                 "impacto de un camino; BFS (O(n)) recorre por niveles. Insertar o eliminar un subarbol cuesta O(n) "
                 "por la busqueda del padre.")
        return nodos, texto

    def grafo_social(self) -> tuple[GrafoVista, str]:
        s = self._sesion()
        g = s.grafo if s is not None else GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)
        v = s.en_vivo if s is not None else None
        origen = v.autor if v is not None else "tomas"
        nivel = g.niveles(origen)                         # BFS: la ola en que llegaria a cada uno
        vista = GrafoVista({c.id: c.pos for c in g.vertices()},
                           {c.id: f"{c.id} (ola {nivel.get(c.id, '-')})" for c in g.vertices()},
                           [(a.origen, a.destino, f"{a.peso:.2f}", False) for a in g.aristas()], True, {origen})
        texto = (f"Lista de adyacencia dirigida y ponderada: {len(g.vertices())} ciudadanos y {len(g.aristas())} "
                 f"aristas (peso = influencia). BFS por olas desde {origen}: O(V+E); la ola de cada uno es su nivel. "
                 "En vivo, una ola por segundo; Dijkstra con costo 1/peso da el tiempo de llegada.")
        return vista, texto

    def grafo_ciudad(self) -> tuple[GrafoVista, str]:
        s = self._sesion()
        g = s.mapa if s is not None else GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)
        desde = s.jugador_actual.zona if s is not None else g.zona_inicial
        costos = g.costos_desde(desde)                    # Dijkstra con heap
        saltos = g.saltos("alcaldia") if "alcaldia" in g else {}
        cerradas = [tuple(c.split("|")) for c in getattr(s, "protestas", {})]
        aristas = [(a, b, str(d), False) for a, b, d in g.conexiones()] + [(a, b, "cerrada", True)
                                                                            for a, b in cerradas if a in g and b in g]
        vista = GrafoVista({z.id: z.pos for z in g.zonas()},
                           {z.id: f"{z.nombre} (costo {costos.get(z.id, 'inf')}, saltos {saltos.get(z.id, 'aislada')})"
                            for z in g.zonas()}, aristas, False, {desde})
        texto = (f"No dirigido y ponderado. Dijkstra desde {desde} con heap: O((V+E) log V); 'costo' es la distancia "
                 "minima. BFS desde la Alcaldia: O(V+E); 'saltos' cuenta fronteras y 'aislada' = sin camino (no le "
                 "llegan desmentidos). Las aristas punteadas las cerro una protesta.")
        return vista, texto

    def arbol_dialogo(self) -> tuple[list[NodoVista], str]:
        raiz = datos_chat()[1]
        _, mejor = raiz.mejor_camino(lambda o: VALOR_DIALOGO[o.tipo])   # DFS
        nodos = [NodoVista("r", raiz.hablante, "raiz", None, True)]

        def bajar(nodo, id: str, camino: list[int]) -> None:
            for i, o in enumerate(nodo.opciones):
                hijo = f"{id}.{i}"
                en_mejor = camino[:len(camino) + 1] + [i] == mejor[:len(camino) + 1]
                nodos.append(NodoVista(hijo, o.tipo, (o.hijo.hablante if o.hijo else "fin"), id, en_mejor))
                if o.hijo is not None:
                    bajar(o.hijo, hijo, camino + [i])
        bajar(raiz, "r", [])
        texto = (f"Chat del Colegio: arbol N-ario de {raiz.profundidad()} turnos y {raiz.contar_finales()} finales. "
                 "Jugar es bajar de la raiz a una hoja: O(h). DFS (O(n)) cuenta los finales y halla el mejor camino "
                 "(resaltado: desescalar siempre).")
        return nodos, texto

    def contenido(self):
        return (self.arbol_decisiones, self.grafo_social, self.grafo_ciudad, self.arbol_dialogo)[self.pestana]()

    def draw(self, pantalla: pygame.Surface) -> None:
        contenido, texto = self.contenido()
        dibujar_sustentacion(pantalla, self.app.fuentes, self.app.temas.actual, self.pestana, contenido, texto)

