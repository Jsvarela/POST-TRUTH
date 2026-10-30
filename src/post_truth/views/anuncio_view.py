"""Anuncios animados: uno GRANDE en el centro (crisis, nuevo dia, se acabo el tiempo) y TOASTS que bajan desde
arriba (evidencia, credibilidad...). Cada tipo tiene icono propio (forma, no solo color) y colores del tema."""
import math
from dataclasses import dataclass

import pygame

from post_truth.config import px
from post_truth.views.componentes import Fuentes, ajustar_texto, marco_pixel
from post_truth.views.hud import MINIMO
from post_truth.views.theme import Tema

ENTRADA, SALIDA = 0.35, 0.4   # segundos de la animacion de entrada y de salida


@dataclass
class Anuncio:
    titulo: str
    texto: str = ""
    tipo: str = "info"        # crisis | dia | bueno | malo | info
    grande: bool = True       # grande: al centro y pausa el mundo; si no, toast arriba
    duracion: float = 2.6
    t: float = 0.0

    def avanzar(self, dt: float) -> None:
        self.t += dt

    def cerrar(self) -> None:
        """Enter o Espacio: pasa directo a la salida."""
        self.t = max(self.t, self.duracion - SALIDA)

    @property
    def terminado(self) -> bool:
        return self.t >= self.duracion


def _color(tema: Tema, tipo: str) -> tuple[int, int, int]:
    return {"crisis": tema.malo, "malo": tema.malo, "bueno": tema.bueno, "dia": tema.detalle}.get(tipo, tema.acento)


def _rebote(x: float) -> float:
    """Sale un poco de mas y vuelve (ease-out-back): da la sensacion de que el anuncio 'golpea'."""
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def _icono(sup: pygame.Surface, tema: Tema, tipo: str, centro: tuple[int, int], r: int, t: float) -> None:
    x, y = centro
    color = _color(tema, tipo)
    if tipo in ("crisis", "malo"):      # triangulo de alerta con "!"
        pygame.draw.polygon(sup, color, [(x, y - r), (x + r, y + r * 0.8), (x - r, y + r * 0.8)])
        pygame.draw.line(sup, tema.fondo, (x, y - r * 0.35), (x, y + r * 0.25), max(2, r // 5))
        pygame.draw.circle(sup, tema.fondo, (x, round(y + r * 0.52)), max(2, r // 7))
    elif tipo == "dia":                  # sol con rayos que giran
        for k in range(8):
            a = t * 1.5 + k * math.pi / 4
            pygame.draw.line(sup, color, (x + math.cos(a) * r * 0.75, y + math.sin(a) * r * 0.75),
                             (x + math.cos(a) * r * 1.1, y + math.sin(a) * r * 1.1), max(2, r // 8))
        pygame.draw.circle(sup, color, centro, round(r * 0.55))
    elif tipo == "bueno":                # circulo con visto
        pygame.draw.circle(sup, color, centro, r)
        pygame.draw.lines(sup, tema.fondo, False, [(x - r * 0.45, y), (x - r * 0.1, y + r * 0.35), (x + r * 0.5, y - r * 0.35)],
                          max(3, r // 5))
    else:                                # circulo con "i"
        pygame.draw.circle(sup, color, centro, r)
        pygame.draw.line(sup, tema.fondo, (x, y - r * 0.05), (x, y + r * 0.5), max(2, r // 5))
        pygame.draw.circle(sup, tema.fondo, (x, round(y - r * 0.4)), max(2, r // 7))


def dibujar_anuncio(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, a: Anuncio) -> None:
    ancho_p, alto_p = pantalla.get_size()
    entrada = min(1.0, a.t / ENTRADA)
    salida = max(0.0, (a.t - (a.duracion - SALIDA)) / SALIDA)
    alfa = round(255 * min(entrada, 1 - salida))
    if alfa <= 0:
        return
    color = _color(tema, a.tipo)
    w, h = (px(660), px(210)) if a.grande else (px(560), px(74))
    panel = pygame.Surface((w + px(4), h + px(4)), pygame.SRCALPHA)   # + la sombra dura del marco
    marco_pixel(panel, tema, pygame.Rect(0, 0, w, h), alfa=245, borde=color)
    latido = 0.5 + 0.5 * math.sin(a.t * 8) if a.tipo == "crisis" else 1.0
    pygame.draw.rect(panel, color, pygame.Rect(0, 0, w, h).inflate(-px(4), -px(4)), px(1) + round(px(2) * latido))
    r = px(40) if a.grande else px(20)
    _icono(panel, tema, a.tipo, (px(24) + r, h // 2), r, a.t)
    x = px(40) + 2 * r
    fuente_titulo = fuentes.titulo if a.grande else fuentes.normal
    titulo = fuente_titulo.render(a.titulo, True, color if a.grande else tema.texto)
    if a.grande:
        panel.blit(titulo, (x, px(30)))
        y = px(30) + titulo.get_height() + px(8)
        for linea in ajustar_texto(a.texto, fuentes.normal, w - x - px(24))[:3]:
            panel.blit(fuentes.normal.render(linea, True, tema.texto), (x, y))
            y += fuentes.normal.get_linesize()
    else:
        panel.blit(titulo, (x, px(10)))
        if a.texto:
            linea = ajustar_texto(a.texto, fuentes.chica, w - x - px(16))[0]
            panel.blit(fuentes.chica.render(linea, True, tema.texto), (x, px(12) + titulo.get_height()))
    if a.grande:
        velo = pygame.Surface((ancho_p, alto_p), pygame.SRCALPHA)   # oscurece el fondo para que el aviso mande
        velo.fill((*tema.fondo, round(120 * alfa / 255)))
        pantalla.blit(velo, (0, 0))
        escala = max(0.05, _rebote(entrada)) * (1 - 0.15 * salida)
        panel = pygame.transform.scale(panel, (max(1, round(w * escala)), max(1, round(h * escala))))   # sin suavizar: pixel
        dx = round(math.sin(a.t * 60) * px(8) * max(0.0, 1 - a.t / 0.5)) if a.tipo == "crisis" else 0   # sacudida
        rect = panel.get_rect(center=(ancho_p // 2 + dx, alto_p // 2 - round(px(30) * salida)))
    else:
        centro = max(ancho_p // 2, MINIMO.right + px(12) + w // 2)   # al lado del HUD de la calle, sin taparlo
        rect = panel.get_rect(midtop=(centro, px(64) - round(px(60) * (1 - _rebote(entrada))) - round(px(40) * salida)))
    panel.set_alpha(alfa)
    pantalla.blit(panel, rect)
