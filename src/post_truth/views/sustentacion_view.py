"""Modo sustentacion (F1): las estructuras de datos en crudo, fuera de la vista normal del jugador.
Arbol de decisiones (orden DFS y nivel BFS), grafo social (pesos y olas BFS), grafo de la ciudad (distancias,
Dijkstra, BFS de aislamiento) y arbol de dialogo del chat (mejor camino por DFS)."""
import math
from dataclasses import dataclass, field

import pygame

from post_truth.config import ALTO, ANCHO, px
from post_truth.views.componentes import Fuentes, ajustar_texto, panel, recortar
from post_truth.views.theme import TOKENS, Tema, esp

PESTANAS = ("Arbol de decisiones", "Grafo social", "Grafo de la ciudad", "Arbol de dialogo")
AREA = pygame.Rect(px(24), px(96), ANCHO - px(48), ALTO - px(200))


@dataclass
class NodoVista:
    """Un nodo ya dispuesto para dibujar: texto, marcas y a quien cuelga."""
    id: str
    texto: str
    marca: str = ""            # p. ej. "DFS 3 | nivel 1"
    padre: str | None = None
    resaltado: bool = False


@dataclass
class GrafoVista:
    nodos: dict[str, tuple[float, float]]                 # id -> posicion normalizada 0..1
    etiquetas: dict[str, str]
    aristas: list[tuple[str, str, str, bool]]             # (a, b, texto, cerrada)
    dirigido: bool = False
    resaltados: set[str] = field(default_factory=set)


def rect_pestana(i: int) -> pygame.Rect:
    ancho = (ANCHO - px(48)) // len(PESTANAS)
    return pygame.Rect(px(24) + i * ancho, px(48), ancho - esp(1), px(38))


def dibujar_sustentacion(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, pestana: int, contenido,
                         explicacion: str) -> None:
    pantalla.fill(tema.fondo)
    pantalla.blit(fuentes.grande.render("Modo sustentacion", True, tema.acento), (px(24), px(8)))
    ayuda = fuentes.chica.render("1-4 o Tab: estructura   |   F1 o ESC: volver al juego", True, tema.texto_off)
    pantalla.blit(ayuda, ayuda.get_rect(topright=(ANCHO - px(24), px(18))))
    for i, nombre in enumerate(PESTANAS):
        r = rect_pestana(i)
        activa = i == pestana
        pygame.draw.rect(pantalla, tema.boton if activa else tema.panel, r)
        pygame.draw.rect(pantalla, tema.acento if activa else tema.borde, r, px(2))
        img = fuentes.chica.render(f"{i + 1}. {nombre}", True, tema.boton_texto if activa else tema.texto)
        pantalla.blit(img, img.get_rect(center=r.center))
    panel(pantalla, tema, AREA, 255)
    interior = AREA.inflate(-px(60), -px(60))
    if isinstance(contenido, GrafoVista):
        _grafo(pantalla, fuentes, tema, interior, contenido)
    else:
        _arbol(pantalla, fuentes, tema, interior, contenido)
    caja = pygame.Rect(px(24), AREA.bottom + esp(2), ANCHO - px(48), ALTO - AREA.bottom - esp(4))
    y = caja.y
    for linea in ajustar_texto(explicacion, fuentes.chica, caja.w)[:4]:
        pantalla.blit(fuentes.chica.render(linea, True, tema.texto), (caja.x, y))
        y += fuentes.chica.get_linesize()


def disponer_arbol(nodos: list[NodoVista]) -> dict[str, tuple[float, float]]:
    """Hojas repartidas a lo ancho en orden DFS; cada padre en el centro de sus hijos; y = profundidad."""
    hijos: dict[str | None, list[str]] = {}
    for n in nodos:
        hijos.setdefault(n.padre, []).append(n.id)
    pos: dict[str, tuple[float, float]] = {}
    hojas = [0]
    profundidad = {}

    def colocar(id: str, d: int) -> float:
        profundidad[id] = d
        if not hijos.get(id):
            x = hojas[0]
            hojas[0] += 1
        else:
            xs = [colocar(h, d + 1) for h in hijos[id]]
            x = (xs[0] + xs[-1]) / 2
        pos[id] = (x, d)
        return x
    for raiz in hijos.get(None, []):
        colocar(raiz, 0)
    ancho, alto = max(1, hojas[0] - 1), max(1, max(profundidad.values(), default=0))
    return {id: (x / ancho if hojas[0] > 1 else 0.5, d / alto) for id, (x, d) in pos.items()}


def _arbol(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, area: pygame.Rect, nodos: list[NodoVista]) -> None:
    pos = disponer_arbol(nodos)
    por_nivel: dict[float, int] = {}
    for _, y in pos.values():
        por_nivel[y] = por_nivel.get(y, 0) + 1
    ancho_nivel = {y: min(px(170), area.w // n) for y, n in por_nivel.items()}   # cada nivel reparte su ancho
    alto = fuentes.chica.get_linesize() * 2 + esp(1)
    util = area.inflate(-max(ancho_nivel.values()), -alto)   # los nodos de la orilla no se salen
    p = {id: (util.x + round(x * util.w), util.y + round(y * util.h)) for id, (x, y) in pos.items()}
    por_id = {n.id: n for n in nodos}
    for n in nodos:
        if n.padre is not None:
            color = tema.acento if n.resaltado and por_id[n.padre].resaltado else tema.borde
            pygame.draw.line(pantalla, color, p[n.padre], p[n.id], px(3 if n.resaltado else 2))
    for n in nodos:
        caja = pygame.Rect(0, 0, ancho_nivel[pos[n.id][1]] - px(2), alto)
        caja.center = p[n.id]
        pygame.draw.rect(pantalla, tema.boton if n.resaltado else tema.panel, caja)
        pygame.draw.rect(pantalla, tema.acento if n.resaltado else tema.borde, caja, px(2))
        for i, (texto, color) in enumerate(((n.texto[:22], tema.texto), (n.marca, tema.acento))):
            img = fuentes.chica.render(recortar(texto, fuentes.chica, caja.w - px(4)), True, color)   # cabe en su columna
            pantalla.blit(img, img.get_rect(midtop=(caja.centerx, caja.y + px(2) + i * fuentes.chica.get_linesize())))


def _grafo(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, area: pygame.Rect, g: GrafoVista) -> None:
    p = {id: (area.x + round(x * area.w), area.y + round(y * area.h)) for id, (x, y) in g.nodos.items()}
    for a, b, texto, cerrada in g.aristas:
        if a not in p or b not in p:
            continue
        ini, fin = p[a], p[b]
        if cerrada:   # arista eliminada: punteada
            largo = max(1, math.dist(ini, fin))
            for k in range(0, int(largo), px(14)):
                f0, f1 = k / largo, min(1.0, (k + px(7)) / largo)
                pygame.draw.line(pantalla, tema.malo, (ini[0] + (fin[0] - ini[0]) * f0, ini[1] + (fin[1] - ini[1]) * f0),
                                 (ini[0] + (fin[0] - ini[0]) * f1, ini[1] + (fin[1] - ini[1]) * f1), px(2))
        else:
            pygame.draw.line(pantalla, tema.borde, ini, fin, px(2))
        if g.dirigido and not cerrada:   # punta de flecha cerca del destino
            ang = math.atan2(fin[1] - ini[1], fin[0] - ini[0])
            punta = (fin[0] - math.cos(ang) * px(16), fin[1] - math.sin(ang) * px(16))
            pygame.draw.polygon(pantalla, tema.borde, [punta, (punta[0] - math.cos(ang - 0.4) * px(9),
                                punta[1] - math.sin(ang - 0.4) * px(9)), (punta[0] - math.cos(ang + 0.4) * px(9),
                                punta[1] - math.sin(ang + 0.4) * px(9))])
        if texto:
            medio = ((ini[0] * 2 + fin[0]) / 3, (ini[1] * 2 + fin[1]) / 3) if g.dirigido else (
                (ini[0] + fin[0]) / 2, (ini[1] + fin[1]) / 2)
            img = fuentes.chica.render(texto, True, tema.texto_off)
            fondo = img.get_rect(center=(round(medio[0]), round(medio[1]))).inflate(px(4), px(2))
            pygame.draw.rect(pantalla, tema.panel, fondo)
            pantalla.blit(img, fondo.move(px(2), px(1)))
    for id, centro in p.items():
        resaltado = id in g.resaltados
        pygame.draw.circle(pantalla, tema.acento if resaltado else tema.boton, centro, px(14))
        pygame.draw.circle(pantalla, tema.texto, centro, px(14), px(2))
        img = fuentes.chica.render(g.etiquetas.get(id, id), True, tema.texto)
        pantalla.blit(img, img.get_rect(midtop=(centro[0], centro[1] + px(16))))
