"""Vista: personajes originales dibujados con formas de Pygame (sin imagenes externas).

El modelo `Personaje` solo guarda ids; aqui se traducen a formas y colores del tema
activo. Para reemplazar esto por PNG de assets/ basta cambiar esta funcion: el modelo
no se entera. El rol se distingue por color de ropa Y por accesorio, de modo que no
dependa solo del color (daltonismo).
"""
import math

import pygame

from post_truth.models import Role
from post_truth.models.personaje import Genero, Personaje
from post_truth.views.theme import Tema

# Todo se dibuja en una caja de diseno de 100x160 unidades y se escala al rect pedido,
# asi el mismo personaje sirve en la escena (grande) y en la seleccion (vista previa).
ANCHO_U, ALTO_U = 100, 160
_ROLES = list(Role)  # orden fijo que usa Tema.rol


def dibujar_personaje(pantalla: pygame.Surface, personaje: Personaje, tema: Tema,
                      rect: pygame.Rect, animo: int = 0) -> None:
    """Dibuja `personaje` dentro de `rect`, apoyado en su borde inferior.

    `animo` (-1 triste, 0 neutro, 1 contento) cambia solo la boca: es la reaccion
    visible a la consecuencia de la decision.
    """
    s = min(rect.width / ANCHO_U, rect.height / ALTO_U)
    ox = rect.centerx - ANCHO_U * s / 2
    oy = rect.bottom - ALTO_U * s

    def p(x: float, y: float) -> tuple[float, float]:
        return ox + x * s, oy + y * s

    def r(x: float, y: float, w: float, h: float) -> pygame.Rect:
        return pygame.Rect(round(ox + x * s), round(oy + y * s), round(w * s), round(h * s))

    piel = tema.piel[personaje.apariencia]
    pelo = tema.cabello[personaje.apariencia]
    ropa = tema.rol[_ROLES.index(personaje.rol)]
    mujer = personaje.genero is Genero.MUJER

    # Sombra en el suelo
    pygame.draw.ellipse(pantalla, tema.panel, r(10, 150, 80, 10))

    # Pelo largo detras de la cabeza y los hombros (solo mujer)
    if mujer:
        pygame.draw.rect(pantalla, pelo, r(25, 28, 50, 62), border_radius=round(20 * s))

    # Torso: hombros mas anchos en hombre
    torso = r(20, 82, 60, 78) if not mujer else r(25, 82, 50, 78)
    pygame.draw.rect(pantalla, ropa, torso, border_radius=round(14 * s))
    pygame.draw.rect(pantalla, tema.borde, torso, width=max(1, round(s)), border_radius=round(14 * s))

    # Cuello y cabeza
    pygame.draw.rect(pantalla, piel, r(44, 66, 12, 20))
    cx, cy = p(50, 48)
    pygame.draw.circle(pantalla, piel, (round(cx), round(cy)), round(22 * s))

    # Pelo corto sobre la frente (ambos generos); el rol puede taparlo con gorra
    pygame.draw.ellipse(pantalla, pelo, r(28, 24, 44, 24))

    # Cara: ojos y boca segun el animo
    for ex in (42, 58):
        ex_, ey_ = p(ex, 52)
        pygame.draw.circle(pantalla, tema.fondo, (round(ex_), round(ey_)), max(2, round(2.6 * s)))
    boca = r(42, 60, 16, 10)
    if animo > 0:      # sonrisa: arco inferior
        pygame.draw.arc(pantalla, tema.fondo, boca, math.pi, 2 * math.pi, max(2, round(2 * s)))
    elif animo < 0:    # ceno: arco superior, mas abajo
        pygame.draw.arc(pantalla, tema.fondo, r(42, 64, 16, 10), 0, math.pi, max(2, round(2 * s)))
    else:
        pygame.draw.line(pantalla, tema.fondo, p(44, 64), p(56, 64), max(2, round(2 * s)))

    _accesorio(pantalla, personaje.rol, tema, p, r, s)


def _accesorio(pantalla: pygame.Surface, rol: Role, tema: Tema, p, r, s: float) -> None:
    """Accesorio distintivo del rol (silueta reconocible aunque se pierda el color)."""
    ancho = max(2, round(2 * s))
    if rol is Role.CITIZEN:
        # Gorra con visera
        pygame.draw.rect(pantalla, tema.acento, r(27, 22, 46, 13), border_radius=round(6 * s))
        pygame.draw.rect(pantalla, tema.acento, r(48, 31, 34, 6), border_radius=round(3 * s))
    elif rol is Role.JOURNALIST:
        # Lentes + credencial colgante + libreta en la mano
        for ex in (42, 58):
            cx, cy = p(ex, 52)
            pygame.draw.circle(pantalla, tema.texto, (round(cx), round(cy)), round(7 * s), ancho)
        pygame.draw.line(pantalla, tema.texto, p(48, 52), p(52, 52), ancho)
        pygame.draw.line(pantalla, tema.texto, p(44, 84), p(50, 108), ancho)
        pygame.draw.line(pantalla, tema.texto, p(56, 84), p(50, 108), ancho)
        pygame.draw.rect(pantalla, tema.texto, r(42, 108, 16, 20), border_radius=round(3 * s))
        pygame.draw.rect(pantalla, tema.panel, r(70, 112, 20, 28), border_radius=round(3 * s))
        pygame.draw.rect(pantalla, tema.texto, r(70, 112, 20, 28), width=ancho, border_radius=round(3 * s))
        pygame.draw.line(pantalla, tema.texto, p(74, 122), p(86, 122), max(1, round(s)))
        pygame.draw.line(pantalla, tema.texto, p(74, 128), p(86, 128), max(1, round(s)))
    elif rol is Role.INFLUENCER:
        # Auriculares + celular
        pygame.draw.arc(pantalla, tema.texto, r(26, 24, 48, 48), 0, math.pi, max(3, round(3 * s)))
        for ex in (27, 73):
            pygame.draw.rect(pantalla, tema.texto, r(ex - 5, 46, 10, 16), border_radius=round(4 * s))
        pygame.draw.rect(pantalla, tema.texto, r(70, 108, 14, 26), border_radius=round(3 * s))
        pygame.draw.rect(pantalla, tema.fondo, r(72, 111, 10, 18), border_radius=round(2 * s))
    else:
        # Candidato: corbata + banda cruzada + insignia
        pygame.draw.polygon(pantalla, tema.acento,
                            [p(50, 84), p(44, 92), p(50, 128), p(56, 92)])
        pygame.draw.polygon(pantalla, tema.texto,
                            [p(24, 88), p(38, 84), p(78, 148), p(64, 152)])
        cx, cy = p(36, 98)
        pygame.draw.circle(pantalla, tema.acento, (round(cx), round(cy)), round(5 * s))
