"""Vista de las cinematicas (L3): el mapa real con los actores, franjas negras, dialogo con retrato, cartel y
fundido. Solo lee el interprete (models/cinematica.py)."""
import pygame

from post_truth.config import px
from post_truth.mapa_abierto import MapaAbierto
from post_truth.models import Role
from post_truth.models.cinematica import Interprete
from post_truth.models.personaje import Genero, Personaje
from post_truth.views.arte_mundo import ARTE_PIXEL
from post_truth.views.componentes import CajaDialogo, Fuentes, marco_pixel, panel
from post_truth.views.mundo_view import EstadoMundo, dibujar_mundo
from post_truth.views.theme import NEGRO, TOKENS, Tema, esp

FRANJA = px(64)
RETRATO = px(136)


def personaje(a: dict) -> Personaje:
    return Personaje(Role[a["rol"]], Genero[a["genero"]], a["variante"])


def dibujar_cinematica(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, mundo: MapaAbierto, i: Interprete,
                       decorado=None) -> None:
    dx, dy = i.desplazamiento
    actores = tuple((a["nombre"], personaje(a), tuple(a["pos"]), a["anim"].nombre, a["anim"].cuadro, "")
                    for a in i.actores.values())
    dibujar_mundo(pantalla, fuentes, tema, mundo, EstadoMundo(
        centro_camara=(i.camara[0] + dx, i.camara[1] + dy), transeuntes=actores, noche=i.noche, t=i.t,
        decorado=decorado, jugador_visible=False))
    ancho, alto = pantalla.get_size()
    pygame.draw.rect(pantalla, NEGRO, (0, 0, ancho, FRANJA))
    pygame.draw.rect(pantalla, NEGRO, (0, alto - FRANJA, ancho, FRANJA))
    if i.cartel is not None:
        _cartel(pantalla, fuentes, tema, *i.cartel)
    if i.dialogo is not None:
        _dialogo(pantalla, fuentes, tema, i)
    if i.negro > 0:
        velo = pygame.Surface((ancho, alto))
        velo.fill(NEGRO)
        velo.set_alpha(round(255 * i.negro))
        pantalla.blit(velo, (0, 0))


def _cartel(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, texto: str, sub: str) -> None:
    img = fuentes.titulo.render(texto, True, tema.texto)
    ancho = max(img.get_width(), fuentes.normal.size(sub)[0] if sub else 0)
    caja = pygame.Rect(0, 0, ancho, img.get_height()).inflate(
        esp(5) * 2, esp(4) * 2 + (fuentes.normal.get_linesize() if sub else 0))
    caja.center = (pantalla.get_width() // 2, pantalla.get_height() // 2)
    panel(pantalla, tema, caja, TOKENS.alfa_panel, borde=tema.acento)
    pantalla.blit(img, img.get_rect(midtop=(caja.centerx, caja.y + esp(4))))
    if sub:
        s = fuentes.normal.render(sub, True, tema.acento)
        pantalla.blit(s, s.get_rect(midbottom=(caja.centerx, caja.bottom - esp(3))))


def _dialogo(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, i: Interprete) -> None:
    d = i.dialogo
    ancho, alto = pantalla.get_size()
    abajo = alto - FRANJA - esp(2)
    retrato = d["retrato"] or ""
    actor = i.actores.get(retrato)
    x = esp(4)
    cuadro = pygame.Rect(x, abajo - RETRATO, RETRATO, RETRATO)
    if actor is not None:   # retrato: el mismo sprite del actor, en grande
        marco_pixel(pantalla, tema, cuadro, borde=tema.acento)
        ARTE_PIXEL.personaje(pantalla, tema, (cuadro.centerx, cuadro.bottom - px(10)), RETRATO - px(24),
                             personaje(actor), "idle_abajo", 0)
        x = cuadro.right + esp(2)
    caja = CajaDialogo(pygame.Rect(x, abajo - RETRATO, ancho - x - esp(4), RETRATO))
    caja.set_texto(d["texto"], d["quien"])
    caja._visibles, caja._t = d["visibles"], i.t
    caja.draw(pantalla, fuentes, tema)
