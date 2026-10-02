"""Minimapa de la ciudad: lugares donde se investiga, con la distancia (costo en energia) de cada via.

Solo dibuja los datos que le entrega el controlador (`EstadoMapa`) y responde "que zona hay bajo este
punto" para los clics; no cambia nada del modelo. Colores del tema; ademas del color hay FORMAS:
    pin con borde           -> donde esta el jugador (se dibuja al final, siempre encima de todo)
    rombo con "?"           -> la zona guarda evidencia de la noticia actual que aun no se ha revisado
    rombo hueco con visto   -> evidencia ya revisada
    numero en cada via      -> distancia (lo que cuesta recorrerla)
    linea gruesa            -> la ruta mas corta hacia la zona elegida, con su costo total
    numero dentro de la zona -> costo de ir hasta ella desde donde estas (tachado si la energia no alcanza)
"""
from dataclasses import dataclass, field

import pygame

from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.views.componentes import Fuentes
from post_truth.views.theme import Tema

RADIO = 17
TECLAS_VIAJE = "QWERT"  # tecla de la 1.a, 2.a... zona del mapa (en el orden del archivo de data/)


@dataclass
class EstadoMapa:
    ciudad: GrafoCiudad
    actual: str                                            # zona donde esta el jugador
    costos: dict[str, int] = field(default_factory=dict)   # costo de viajar desde `actual` a cada zona (Dijkstra)
    energia: int | None = None                             # energia disponible; None = no mostrar costos de viaje
    ruta: tuple[str, ...] = ()                             # ruta resaltada (la elegida con el mouse o la ultima recorrida)
    costo_ruta: int | None = None                          # costo total de esa ruta
    pendientes: set[str] = field(default_factory=set)      # zonas con evidencia de la noticia aun sin revisar
    revisadas: set[str] = field(default_factory=set)       # zonas cuya evidencia ya se reviso
    hover: str | None = None                               # zona bajo el mouse
    teclas: bool = False                                   # mostrar la letra de atajo de cada zona


def tecla_de(ciudad: GrafoCiudad, zona: str) -> str:
    """Letra de atajo (Q W E R T) de una zona, segun su posicion en el mapa."""
    return TECLAS_VIAJE[[z.id for z in ciudad.zonas()].index(zona)]


def zona_de_tecla(ciudad: GrafoCiudad, letra: str) -> str | None:
    i = TECLAS_VIAJE.find(letra.upper())
    zonas = ciudad.zonas()
    return zonas[i].id if 0 <= i < len(zonas) else None


def _posiciones(estado: EstadoMapa, rect: pygame.Rect) -> dict[str, tuple[int, int]]:
    # Margen inferior grande: debajo de cada zona van su nombre y su costo de viaje, y al pie la leyenda
    area = pygame.Rect(rect.x + RADIO + 22, rect.y + RADIO + 30, rect.width - 2 * (RADIO + 22),
                       rect.height - (RADIO + 30) - (RADIO + 52))
    return {z.id: (round(area.x + z.pos[0] * area.width), round(area.y + z.pos[1] * area.height))
            for z in estado.ciudad.zonas()}


def zona_en(estado: EstadoMapa, rect: pygame.Rect, punto: tuple[int, int]) -> str | None:
    """Id de la zona dibujada bajo `punto`, o None."""
    for id, (x, y) in _posiciones(estado, rect).items():
        if (punto[0] - x) ** 2 + (punto[1] - y) ** 2 <= (RADIO + 6) ** 2:
            return id
    return None


# --- formas ---------------------------------------------------------------------------------------
def _rombo(pantalla: pygame.Surface, color: tuple[int, int, int], centro: tuple[int, int], r: int,
           relleno: bool) -> None:
    x, y = centro
    puntos = [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]
    pygame.draw.polygon(pantalla, color, puntos, 0 if relleno else 3)


def _pin(pantalla: pygame.Surface, tema: Tema, base: tuple[int, int]) -> None:
    """Marcador de posicion tipo chincheta: gota con la punta en `base`. Doble contorno (oscuro y claro)
    para que se vea sobre cualquier fondo y en alto contraste."""
    x, y = base
    cabeza = (x, y - 19)
    for radio, color in ((11, tema.texto), (9, tema.acento)):
        pygame.draw.circle(pantalla, color, cabeza, radio)
    pygame.draw.polygon(pantalla, tema.texto, [(x - 8, y - 15), (x + 8, y - 15), (x, y + 1)])
    pygame.draw.polygon(pantalla, tema.acento, [(x - 6, y - 14), (x + 6, y - 14), (x, y - 3)])
    pygame.draw.circle(pantalla, tema.fondo, cabeza, 4)


def _etiqueta_distancia(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, centro: tuple[float, float],
                        distancia: int, resaltada: bool) -> None:
    c = (round(centro[0]), round(centro[1]))
    pygame.draw.circle(pantalla, tema.acento if resaltada else tema.panel, c, 9)
    pygame.draw.circle(pantalla, tema.acento if resaltada else tema.borde, c, 9, 2)
    n = fuentes.chica.render(str(distancia), True, tema.fondo if resaltada else tema.texto)
    pantalla.blit(n, n.get_rect(center=c))


def dibujar_mapa(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, rect: pygame.Rect,
                 estado: EstadoMapa) -> None:
    pygame.draw.rect(pantalla, tema.fondo, rect, border_radius=12)
    pygame.draw.rect(pantalla, tema.borde, rect, width=2, border_radius=12)
    pantalla.blit(fuentes.chica.render("Mapa de Ciudad Nova", True, tema.acento), (rect.x + 10, rect.y + 6))
    pos = _posiciones(estado, rect)
    tramos_ruta = {frozenset(par) for par in zip(estado.ruta, estado.ruta[1:])}

    # 1) vias: la ruta elegida va gruesa y en color de acento; todas llevan su distancia
    for a, b, d in estado.ciudad.conexiones():
        en_ruta = frozenset((a, b)) in tramos_ruta
        pygame.draw.line(pantalla, tema.acento if en_ruta else tema.borde, pos[a], pos[b], 6 if en_ruta else 2)
    for a, b, d in estado.ciudad.conexiones():
        medio = ((pos[a][0] + pos[b][0]) / 2, (pos[a][1] + pos[b][1]) / 2)
        _etiqueta_distancia(pantalla, fuentes, tema, medio, d, frozenset((a, b)) in tramos_ruta)

    # 2) zonas, con nombre, costo de viaje y marca de evidencia
    for zona in estado.ciudad.zonas():
        x, y = pos[zona.id]
        es_actual = zona.id == estado.actual
        en_ruta = zona.id in estado.ruta
        pygame.draw.circle(pantalla, tema.acento if en_ruta and not es_actual else tema.panel, (x, y), RADIO)
        grosor = 4 if (es_actual or estado.hover == zona.id) else 2
        pygame.draw.circle(pantalla, tema.acento if (es_actual or estado.hover == zona.id or en_ruta) else tema.borde,
                           (x, y), RADIO, grosor)
        nombre = fuentes.chica.render(zona.nombre, True, tema.texto)
        pantalla.blit(nombre, nombre.get_rect(midtop=(x, y + RADIO + 4)))
        if estado.energia is not None and not es_actual and zona.id in estado.costos:
            costo = estado.costos[zona.id]
            alcanza = costo <= estado.energia
            color_cifra = tema.fondo if en_ruta else (tema.texto if alcanza else tema.borde)  # sobre relleno de acento, oscuro
            cifra = fuentes.normal.render(str(costo), True, color_cifra)
            pantalla.blit(cifra, cifra.get_rect(center=(x, y)))
            if not alcanza:   # tachado: este viaje no alcanza con la energia que queda
                pygame.draw.line(pantalla, tema.borde, (x - 11, y + 11), (x + 11, y - 11), 3)
        if estado.teclas and not es_actual:
            tecla = fuentes.chica.render(tecla_de(estado.ciudad, zona.id), True, tema.texto)
            pantalla.blit(tecla, tecla.get_rect(center=(x - RADIO - 8, y - RADIO + 2)))
        # Evidencia: rombo pendiente (relleno, con "?") o revisada (hueco, con visto). Forma propia, no solo color.
        if zona.id in estado.pendientes:
            _rombo(pantalla, tema.detalle, (x + RADIO + 6, y - 2), 10, True)
            signo = fuentes.chica.render("?", True, tema.fondo)
            pantalla.blit(signo, signo.get_rect(center=(x + RADIO + 6, y - 2)))
        elif zona.id in estado.revisadas:
            _rombo(pantalla, tema.bueno, (x + RADIO + 6, y - 2), 10, False)
            pygame.draw.lines(pantalla, tema.bueno, False,
                              [(x + RADIO + 1, y - 2), (x + RADIO + 5, y + 2), (x + RADIO + 12, y - 6)], 2)

    # 3) costo total de la ruta elegida, arriba a la derecha (junto al titulo, sin tapar zonas)
    if estado.ruta and estado.costo_ruta is not None and len(estado.ruta) >= 2:
        total = fuentes.chica.render(f"Ruta: {estado.costo_ruta}", True, tema.fondo)
        marco = total.get_rect(topright=(rect.right - 10, rect.y + 6)).inflate(12, 4)
        pygame.draw.rect(pantalla, tema.acento, marco, border_radius=6)
        pantalla.blit(total, total.get_rect(center=marco.center))

    # 4) leyenda al pie
    y = rect.bottom - 42
    _pin(pantalla, tema, (rect.x + 18, y + 13))
    pantalla.blit(fuentes.chica.render("Tu posicion", True, tema.texto), (rect.x + 32, y + 3))
    _rombo(pantalla, tema.detalle, (rect.x + 130, y + 9), 7, True)
    pantalla.blit(fuentes.chica.render("Evidencia", True, tema.texto), (rect.x + 142, y + 3))
    pantalla.blit(fuentes.chica.render("En via: distancia   En zona: viaje", True, tema.borde), (rect.x + 10, y + 22))

    # 5) el jugador, AL FINAL: el marcador queda sobre cualquier otra cosa y siempre se ve
    if estado.actual in pos:
        x, y = pos[estado.actual]
        _pin(pantalla, tema, (x, y - RADIO + 2))
