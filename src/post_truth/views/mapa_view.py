"""Minimapa de la ciudad: zonas como nodos, conexiones como lineas, zona actual resaltada.

Solo dibuja los datos que le entrega el controlador (`EstadoMapa`) y responde "que zona hay
bajo este punto" para los clics; no cambia nada del modelo. Colores del tema; ademas del
color hay formas: aro grueso para la zona actual, "!" para la zona de la noticia, X para
una zona con rumor y letra de atajo en las zonas a las que se puede ir.
"""
from dataclasses import dataclass, field

import pygame

from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.views.componentes import Fuentes
from post_truth.views.theme import Tema

RADIO = 17
TECLAS_MOVER = "QWER"  # atajos de teclado para ir a la 1.a, 2.a, 3.a o 4.a zona vecina


@dataclass
class EstadoMapa:
    ciudad: GrafoCiudad
    actual: str                                      # zona donde esta el jugador
    zona_noticia: str = ""                           # zona de la publicacion que se decide ahora
    infectadas: set[str] = field(default_factory=set)  # zonas con un rumor visible
    en_riesgo: set[str] = field(default_factory=set)   # a donde llegaria un rumor la proxima ronda
    alcanzables: list[str] = field(default_factory=list)  # vecinas a las que se puede ir ahora


def _posiciones(estado: EstadoMapa, rect: pygame.Rect) -> dict[str, tuple[int, int]]:
    area = rect.inflate(-2 * (RADIO + 22), -2 * (RADIO + 26))
    return {z.id: (round(area.x + z.pos[0] * area.width), round(area.y + z.pos[1] * area.height))
            for z in estado.ciudad.zonas()}


def zona_en(estado: EstadoMapa, rect: pygame.Rect, punto: tuple[int, int]) -> str | None:
    """Id de la zona dibujada bajo `punto`, o None."""
    for id, (x, y) in _posiciones(estado, rect).items():
        if (punto[0] - x) ** 2 + (punto[1] - y) ** 2 <= (RADIO + 4) ** 2:
            return id
    return None


def dibujar_mapa(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, rect: pygame.Rect,
                 estado: EstadoMapa) -> None:
    pygame.draw.rect(pantalla, tema.fondo, rect, border_radius=12)
    pygame.draw.rect(pantalla, tema.borde, rect, width=2, border_radius=12)
    pantalla.blit(fuentes.chica.render("Mapa de Ciudad Nova", True, tema.acento), (rect.x + 10, rect.y + 6))
    pos = _posiciones(estado, rect)

    # Conexiones: las que sigue una ola de rumor se pintan con el color de peligro
    for a, b in estado.ciudad.conexiones():
        contagio = a in estado.infectadas and b in estado.infectadas
        pygame.draw.line(pantalla, tema.malo if contagio else tema.borde, pos[a], pos[b], 4 if contagio else 2)

    for zona in estado.ciudad.zonas():
        x, y = pos[zona.id]
        es_actual = zona.id == estado.actual
        infectada = zona.id in estado.infectadas
        if zona.id in estado.alcanzables:  # aro punteado: se puede ir con clic o con su letra
            _aro_punteado(pantalla, tema.texto, (x, y), RADIO + 7)
        if zona.id in estado.en_riesgo and not infectada:
            pygame.draw.circle(pantalla, tema.malo, (x, y), RADIO + 3, 2)   # el rumor llega pronto
        relleno = tema.malo if infectada else (tema.acento if es_actual else tema.panel)
        pygame.draw.circle(pantalla, relleno, (x, y), RADIO)
        pygame.draw.circle(pantalla, tema.acento if es_actual else tema.borde, (x, y), RADIO, 4 if es_actual else 2)
        if infectada:  # X ademas del color
            pygame.draw.line(pantalla, tema.fondo, (x - 6, y - 6), (x + 6, y + 6), 3)
            pygame.draw.line(pantalla, tema.fondo, (x - 6, y + 6), (x + 6, y - 6), 3)
        elif es_actual:  # el jugador
            pygame.draw.circle(pantalla, tema.fondo, (x, y), 5)
        if zona.id == estado.zona_noticia:  # marca "!" sobre la zona de la noticia
            pygame.draw.circle(pantalla, tema.detalle, (x + RADIO - 2, y - RADIO + 2), 9)
            signo = fuentes.chica.render("!", True, tema.fondo)
            pantalla.blit(signo, signo.get_rect(center=(x + RADIO - 2, y - RADIO + 2)))
        if zona.id in estado.alcanzables:
            tecla = fuentes.chica.render(TECLAS_MOVER[estado.alcanzables.index(zona.id)], True, tema.texto)
            pantalla.blit(tecla, tecla.get_rect(center=(x - RADIO - 8, y - RADIO)))
        nombre = fuentes.chica.render(zona.nombre, True, tema.texto)
        pantalla.blit(nombre, nombre.get_rect(midtop=(x, y + RADIO + 5)))


def _aro_punteado(pantalla: pygame.Surface, color: tuple[int, int, int], centro: tuple[int, int],
                  radio: int) -> None:
    import math
    for i in range(0, 360, 30):
        a, b = math.radians(i), math.radians(i + 15)
        pygame.draw.line(pantalla, color, (centro[0] + radio * math.cos(a), centro[1] + radio * math.sin(a)),
                         (centro[0] + radio * math.cos(b), centro[1] + radio * math.sin(b)), 2)
