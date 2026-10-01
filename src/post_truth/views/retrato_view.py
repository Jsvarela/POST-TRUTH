"""Vista: retratos de busto de los candidatos, dibujados con formas de Pygame (sin imagenes).

El modelo `AspectoRetrato` solo trae ids (tono de piel y de cabello, peinado, accesorio, color de
campana); aqui se traducen a formas y colores del tema activo. Cada candidato se reconoce por su
silueta (peinado y accesorio) y no solo por el color, para que el alto contraste y el daltonismo
no los vuelvan indistinguibles. El marco usa el color de campana del candidato.
"""
import math

import pygame

from post_truth.models.intro import AspectoRetrato
from post_truth.views.theme import Tema

# Caja de diseno de 100 x 120 unidades, escalada al rectangulo pedido.
ANCHO_U, ALTO_U = 100, 120


def dibujar_retrato(pantalla: pygame.Surface, aspecto: AspectoRetrato, tema: Tema,
                    rect: pygame.Rect) -> None:
    s = min(rect.width / ANCHO_U, rect.height / ALTO_U)
    ox = rect.centerx - ANCHO_U * s / 2
    oy = rect.bottom - ALTO_U * s

    def p(x: float, y: float) -> tuple[int, int]:
        return round(ox + x * s), round(oy + y * s)

    def r(x: float, y: float, w: float, h: float) -> pygame.Rect:
        return pygame.Rect(round(ox + x * s), round(oy + y * s), round(w * s), round(h * s))

    marco = r(0, 0, ANCHO_U, ALTO_U)
    piel = tema.piel[aspecto.piel]
    pelo = tema.cabello[aspecto.cabello]
    campana = tema.rol[aspecto.color]
    ancho_linea = max(2, round(2 * s))
    radio = round(10 * s)

    pygame.draw.rect(pantalla, campana, marco, border_radius=radio)
    clip_previo = pantalla.get_clip()
    pantalla.set_clip(marco)  # los hombros se cortan en el marco, como una foto

    # Pelo que va DETRAS de la cabeza
    if aspecto.peinado == "largo":
        pygame.draw.rect(pantalla, pelo, r(25, 28, 50, 64), border_radius=round(18 * s))
    elif aspecto.peinado == "recogido":
        pygame.draw.circle(pantalla, pelo, p(50, 17), round(10 * s))   # mono

    # Hombros (saco), cuello y cabeza
    pygame.draw.ellipse(pantalla, tema.edificio, r(8, 88, 84, 64))
    pygame.draw.ellipse(pantalla, tema.borde, r(8, 88, 84, 64), ancho_linea)
    pygame.draw.rect(pantalla, piel, r(43, 68, 14, 24))
    pygame.draw.circle(pantalla, piel, p(50, 48), round(21 * s))

    # Pelo que va ENCIMA de la frente
    if aspecto.peinado == "rizado":
        for cx, cy, rad in ((34, 32, 9), (44, 25, 10), (56, 25, 10), (66, 32, 9), (30, 44, 7), (70, 44, 7)):
            pygame.draw.circle(pantalla, pelo, p(cx, cy), round(rad * s))
    else:
        pygame.draw.ellipse(pantalla, pelo, r(28, 24, 44, 24))
        if aspecto.peinado == "corto":
            pygame.draw.rect(pantalla, pelo, r(28, 34, 5, 10))
            pygame.draw.rect(pantalla, pelo, r(67, 34, 5, 10))

    # Barba (antes de la boca para que no la tape)
    if aspecto.accesorio == "barba":
        pygame.draw.polygon(pantalla, pelo, [p(32, 54), p(68, 54), p(64, 72), p(50, 78), p(36, 72)])

    # Cara
    for ex in (42, 58):
        pygame.draw.circle(pantalla, tema.fondo, p(ex, 50), max(2, round(2.4 * s)))
    pygame.draw.arc(pantalla, tema.fondo, r(43, 55, 14, 9), math.pi, 2 * math.pi, ancho_linea)

    # Accesorio distintivo
    if aspecto.accesorio == "corbata":
        pygame.draw.polygon(pantalla, tema.texto, [p(40, 90), p(50, 98), p(60, 90), p(50, 86)])   # cuello de camisa
        pygame.draw.polygon(pantalla, tema.acento, [p(50, 94), p(45, 102), p(50, 118), p(55, 102)])
    elif aspecto.accesorio == "aretes":
        for ax in (28.5, 71.5):
            pygame.draw.circle(pantalla, tema.detalle, p(ax, 58), round(3.2 * s))
    elif aspecto.accesorio == "lentes":
        for ex in (42, 58):
            pygame.draw.circle(pantalla, tema.texto, p(ex, 50), round(7.5 * s), ancho_linea)
        pygame.draw.line(pantalla, tema.texto, p(49, 50), p(51, 50), ancho_linea)
    elif aspecto.accesorio == "bufanda":
        pygame.draw.rect(pantalla, tema.acento, r(32, 82, 36, 11), border_radius=round(5 * s))
        pygame.draw.rect(pantalla, tema.acento, r(56, 88, 10, 26), border_radius=round(4 * s))

    pantalla.set_clip(clip_previo)
    pygame.draw.rect(pantalla, tema.borde, marco, width=max(2, round(3 * s)), border_radius=radio)
