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
                      rect: pygame.Rect, animo: int = 0, sombra: bool = True) -> None:
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

    if sombra:  # sombra en el suelo (en el mundo caminable la pone dibujar_personaje_mundo, bajo las piernas)
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
    elif animo < 0:    # ceno: arco superior (n invertida), fino para que no parezca bigote
        pygame.draw.arc(pantalla, tema.fondo, r(44, 63, 12, 8), 0, math.pi, max(2, round(1.5 * s)))
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


# --- personaje del mundo caminable: 4 direcciones, quieto y caminando --------------------------------------
# Caja de 100x160 como la del retrato, pero con piernas: el cuerpo de arriba (dibujar_personaje, de frente) se
# encoge a ALTO_CUERPO y las piernas ocupan el resto hasta los pies (y = 160).
ALTO_CUERPO = 134
_S_CUERPO = ALTO_CUERPO / ALTO_U                  # escala del cuerpo dentro de la caja
_OX_CUERPO = (ANCHO_U - ANCHO_U * _S_CUERPO) / 2   # el cuerpo encogido queda centrado
PASO = (1, 0, -1, 0)    # caminar: piernas abiertas (1, -1) y cruzandose (0); 4 cuadros = un ciclo de dos pasos
REBOTE_CAMINAR = 3      # unidades que sube el cuerpo al cruzar las piernas
REBOTE_IDLE = (0, 1.5)  # respiracion


def dibujar_personaje_mundo(pantalla: pygame.Surface, personaje: Personaje, tema: Tema, pies: tuple[int, int],
                            alto: int, nombre: str, cuadro: int) -> None:
    """Dibuja la animacion `nombre` (idle_abajo, caminar_derecha...) en su `cuadro`, de `alto` pixeles y apoyada
    en `pies`. Son los mismos nombres y cuadros que tendra una hoja de sprites PNG (models/animacion.py).

    La izquierda es el espejo de la derecha: se dibuja en una superficie aparte y se voltea."""
    estado, direccion = nombre.split("_", 1)
    paso = PASO[cuadro % len(PASO)] if estado == "caminar" else 0
    rebote = (REBOTE_CAMINAR * (1 - abs(paso)) if estado == "caminar"
              else REBOTE_IDLE[cuadro % len(REBOTE_IDLE)])
    s = alto / ALTO_U
    ancho = max(1, round(ANCHO_U * s))
    lienzo = pygame.Surface((ancho, alto), pygame.SRCALPHA)

    def p(x: float, y: float) -> tuple[float, float]:
        return x * s, y * s

    def r(x: float, y: float, w: float, h: float) -> pygame.Rect:
        return pygame.Rect(round(x * s), round(y * s), max(1, round(w * s)), max(1, round(h * s)))

    lado = direccion in ("izquierda", "derecha")
    _piernas(lienzo, tema, r, p, s, paso, lado)
    if direccion == "abajo":
        cuerpo = pygame.Rect(round(_OX_CUERPO * s), round(-rebote * s), round(ANCHO_U * _S_CUERPO * s),
                             round(ALTO_CUERPO * s))
        _brazos_frente(lienzo, personaje, tema, r, s, paso, rebote)
        dibujar_personaje(lienzo, personaje, tema, cuerpo, sombra=False)
    else:
        _cuerpo_atras_o_lado(lienzo, personaje, tema, s, rebote, lado, paso)
    if direccion == "izquierda":
        lienzo = pygame.transform.flip(lienzo, True, False)

    # Sombra bajo los pies (semitransparente): se achica un poco cuando el cuerpo sube
    sombra = pygame.Surface((ancho, max(2, round(12 * s))), pygame.SRCALPHA)
    pygame.draw.ellipse(sombra, (*tema.borde, 110), sombra.get_rect().inflate(-round((30 + rebote * 3) * s), 0))
    pantalla.blit(sombra, sombra.get_rect(center=(pies[0], pies[1] - round(2 * s))))
    pantalla.blit(lienzo, lienzo.get_rect(midbottom=pies))


def _piernas(lienzo: pygame.Surface, tema: Tema, r, p, s: float, paso: int, lado: bool) -> None:
    grosor = max(2, round(11 * s))
    if lado:   # de perfil las piernas van adelante y atras; la de atras, mas oscura
        for signo, color in ((-1, tema.panel), (1, tema.borde)):
            x_pie = 50 + signo * paso * 12
            pygame.draw.line(lienzo, color, p(50, 128), p(x_pie, 154), grosor)
            pygame.draw.ellipse(lienzo, tema.fondo, r(x_pie - 4, 151, 14, 8))
        return
    for x, signo in ((40, 1), (60, -1)):   # de frente o de espaldas: la pierna que avanza se acorta (se levanta)
        alza = max(0, signo * paso) * 5
        pygame.draw.rect(lienzo, tema.borde, r(x - 6, 126, 12, 30 - alza), border_radius=max(1, round(3 * s)))
        pygame.draw.ellipse(lienzo, tema.fondo, r(x - 8, 150 - alza, 16, 8))


def _brazos_frente(lienzo: pygame.Surface, personaje: Personaje, tema: Tema, r, s: float, paso: int,
                   rebote: float) -> None:
    ropa = tema.rol[_ROLES.index(personaje.rol)]
    for x, signo in ((14, 1), (77, -1)):    # se balancean en contrafase con las piernas
        y = 90 - rebote + signo * paso * 3
        pygame.draw.rect(lienzo, ropa, r(x, y, 9, 32), border_radius=max(1, round(4 * s)))
        pygame.draw.circle(lienzo, tema.piel[personaje.apariencia], r(x, y + 32, 9, 9).center, max(1, round(4.5 * s)))


def _cuerpo_atras_o_lado(lienzo: pygame.Surface, personaje: Personaje, tema: Tema, s: float, rebote: float,
                         lado: bool, paso: int) -> None:
    """De espaldas (sin cara) o de perfil mirando a la derecha, con la misma ropa, piel, pelo y rol que de frente."""
    k = s * _S_CUERPO
    ox, oy = _OX_CUERPO * s, -rebote * s

    def p(x: float, y: float) -> tuple[float, float]:
        return ox + x * k, oy + y * k

    def r(x: float, y: float, w: float, h: float) -> pygame.Rect:
        return pygame.Rect(round(ox + x * k), round(oy + y * k), max(1, round(w * k)), max(1, round(h * k)))

    piel = tema.piel[personaje.apariencia]
    pelo = tema.cabello[personaje.apariencia]
    ropa = tema.rol[_ROLES.index(personaje.rol)]
    mujer = personaje.genero is Genero.MUJER
    rol = personaje.rol
    fino = max(1, round(k))
    trazo = max(2, round(2 * k))

    if lado:
        if mujer:   # el pelo largo cae por la espalda (a la izquierda del perfil)
            pygame.draw.rect(lienzo, pelo, r(28, 30, 26, 62), border_radius=round(12 * k))
        pygame.draw.line(lienzo, ropa, p(50, 94), p(50 - paso * 14, 128), max(2, round(9 * k)))   # brazo de atras
        torso = r(32, 82, 38, 78)
        pygame.draw.rect(lienzo, ropa, torso, border_radius=round(12 * k))
        pygame.draw.rect(lienzo, tema.borde, torso, width=fino, border_radius=round(12 * k))
        pygame.draw.rect(lienzo, piel, r(46, 66, 12, 20))
        cx, cy = p(52, 48)
        pygame.draw.circle(lienzo, piel, (round(cx), round(cy)), round(22 * k))
        pygame.draw.ellipse(lienzo, pelo, r(28, 22, 40, 30))                     # nuca y coronilla
        pygame.draw.polygon(lienzo, piel, [p(72, 48), p(79, 56), p(71, 58)])      # nariz
        ex, ey = p(64, 50)
        pygame.draw.circle(lienzo, tema.fondo, (round(ex), round(ey)), max(2, round(2.6 * k)))
        pygame.draw.line(lienzo, tema.fondo, p(62, 64), p(69, 64), trazo)
        for color, g in ((tema.borde, 12), (ropa, 8)):   # brazo de adelante, con contorno para verlo sobre el torso
            pygame.draw.line(lienzo, color, p(54, 94), p(54 + paso * 14, 128), max(2, round(g * k)))
        pygame.draw.circle(lienzo, piel, p(54 + paso * 14, 130), max(1, round(5 * k)))
        if rol is Role.CITIZEN:
            pygame.draw.rect(lienzo, tema.acento, r(30, 20, 42, 13), border_radius=round(6 * k))
            pygame.draw.rect(lienzo, tema.acento, r(62, 29, 22, 6), border_radius=round(3 * k))   # visera adelante
        elif rol is Role.JOURNALIST:
            pygame.draw.circle(lienzo, tema.texto, (round(ex), round(ey)), round(7 * k), trazo)
            pygame.draw.line(lienzo, tema.texto, p(57, 50), p(40, 46), trazo)                      # patilla
        elif rol is Role.INFLUENCER:
            pygame.draw.arc(lienzo, tema.texto, r(28, 24, 48, 48), math.pi / 3, math.pi, max(3, round(3 * k)))
            pygame.draw.rect(lienzo, tema.texto, r(40, 42, 12, 18), border_radius=round(4 * k))    # auricular
        else:
            pygame.draw.polygon(lienzo, tema.acento, [p(68, 84), p(64, 92), p(66, 118), p(70, 92)])  # corbata
        return

    # De espaldas: torso, cabeza cubierta por el pelo y lo que asoma del accesorio
    for x, signo in ((14, -1), (77, 1)):
        pygame.draw.rect(lienzo, ropa, r(x, 92 + signo * paso * 3, 9, 34), border_radius=round(4 * k))
    torso = r(20, 82, 60, 78) if not mujer else r(25, 82, 50, 78)
    pygame.draw.rect(lienzo, ropa, torso, border_radius=round(14 * k))
    pygame.draw.rect(lienzo, tema.borde, torso, width=fino, border_radius=round(14 * k))
    pygame.draw.rect(lienzo, piel, r(44, 66, 12, 20))
    cx, cy = p(50, 48)
    pygame.draw.circle(lienzo, pelo, (round(cx), round(cy)), round(22 * k))
    if mujer:
        pygame.draw.rect(lienzo, pelo, r(27, 40, 46, 52), border_radius=round(18 * k))
    if rol is Role.CITIZEN:
        pygame.draw.rect(lienzo, tema.acento, r(27, 22, 46, 13), border_radius=round(6 * k))
    elif rol is Role.INFLUENCER:
        pygame.draw.arc(lienzo, tema.texto, r(26, 24, 48, 48), 0, math.pi, max(3, round(3 * k)))
    elif rol is Role.JOURNALIST:
        pygame.draw.line(lienzo, tema.texto, p(38, 84), p(62, 84), trazo)          # cordon de la credencial
    else:
        pygame.draw.polygon(lienzo, tema.texto, [p(76, 88), p(62, 84), p(22, 148), p(36, 152)])   # banda
