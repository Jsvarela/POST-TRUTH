"""Minimapa de la ciudad: los lugares donde se investiga, dibujado para un jugador (no para un programador).

Se ve limpio: calles simples, cada lugar con su icono y su nombre, el pin de donde estas y un rombo en
los lugares donde queda algo por descubrir. NO se muestran distancias, numeros ni letras de atajo: el
costo de un viaje se explica en lenguaje normal, con rayos de energia, en el cuadro que aparece al pasar
el mouse sobre un lugar (junto con la tecla de atajo, si se pide). La distancia y la ruta mas corta
(Dijkstra, structures/grafo_ciudad.py) son calculo interno; aqui solo se dibuja su resultado.

Solo dibuja los datos que le entrega el controlador (`EstadoMapa`) y responde "que zona hay bajo este
punto" para los clics; no cambia nada del modelo. Colores del tema; ademas del color hay FORMAS:
    pin con borde         -> donde esta el jugador (se dibuja al final, siempre encima de todo)
    rombo con "?"         -> en ese lugar queda algo por descubrir de la noticia actual
    rombo hueco con visto -> ya revisado
    linea gruesa de acento -> el camino hacia el lugar que se esta mirando
    lugar apagado         -> la energia no alcanza para ir hasta alli
"""
from dataclasses import dataclass, field

import pygame

from post_truth.config import px
from post_truth.structures.grafo_ciudad import GrafoCiudad
from post_truth.views.componentes import Fuentes
from post_truth.views.iconos import rayo
from post_truth.views.theme import Tema

RADIO = px(22)          # radio de cada lugar en el minimapa de la escena
ANCHO_BASE = px(290)    # ancho del minimapa de la escena: si el mapa se dibuja mas grande (introduccion), los lugares crecen con el
TECLAS_VIAJE = "QWERT"  # tecla de la 1.a, 2.a... zona del mapa (en el orden del archivo de data/)


@dataclass
class EstadoMapa:
    ciudad: GrafoCiudad
    actual: str                                            # zona donde esta el jugador
    costos: dict[str, int] = field(default_factory=dict)   # costo de viajar desde `actual` a cada zona (Dijkstra)
    energia: int | None = None                             # energia disponible; None = no hablar de viajes
    ruta: tuple[str, ...] = ()                             # camino resaltado (el del lugar bajo el mouse o el ultimo recorrido)
    costo_ruta: int | None = None                          # costo total de ese camino
    pendientes: set[str] = field(default_factory=set)      # lugares con algo por descubrir de la noticia actual
    revisadas: set[str] = field(default_factory=set)       # lugares ya revisados
    hover: str | None = None                               # lugar bajo el mouse
    teclas: bool = False                                   # mencionar la tecla de atajo en la franja de ayuda
    mostrar_ayuda: bool = True                             # franja de ayuda al pie (la introduccion la oculta)


def tecla_de(ciudad: GrafoCiudad, zona: str) -> str:
    """Letra de atajo (Q W E R T) de una zona, segun su posicion en el mapa."""
    return TECLAS_VIAJE[[z.id for z in ciudad.zonas()].index(zona)]


def zona_de_tecla(ciudad: GrafoCiudad, letra: str) -> str | None:
    i = TECLAS_VIAJE.find(letra.upper())
    zonas = ciudad.zonas()
    return zonas[i].id if 0 <= i < len(zonas) else None


ALTO_FRANJA = px(78)  # franja de ayuda al pie del mapa
ALTO_NOMBRE = px(50)  # lo que ocupa el nombre bajo un lugar (radio del lugar + nombre)


def _posiciones(estado: EstadoMapa, rect: pygame.Rect) -> dict[str, tuple[int, int]]:
    # Margenes: arriba cabe el titulo y el pin sobre un lugar de la fila superior; abajo, el nombre y la franja de ayuda
    franja = ALTO_FRANJA if estado.mostrar_ayuda else px(10)
    area = pygame.Rect(rect.x + px(44), rect.y + px(66), rect.width - 2 * px(44),
                       rect.height - px(66) - franja - ALTO_NOMBRE - px(8))
    return {z.id: (round(area.x + z.pos[0] * area.width), round(area.y + z.pos[1] * area.height))
            for z in estado.ciudad.zonas()}


def _radio(rect: pygame.Rect) -> int:
    """Radio de los lugares: RADIO en el minimapa de la escena y hasta 1.5 veces mas en mapas grandes."""
    return round(RADIO * max(1.0, min(1.5, rect.width / ANCHO_BASE)))


def zona_en(estado: EstadoMapa, rect: pygame.Rect, punto: tuple[int, int]) -> str | None:
    """Id de la zona dibujada bajo `punto`, o None."""
    for id, (x, y) in _posiciones(estado, rect).items():
        if (punto[0] - x) ** 2 + (punto[1] - y) ** 2 <= (_radio(rect) + px(8)) ** 2:
            return id
    return None


# --- pictogramas de cada lugar ---------------------------------------------------------------------
def _icono_zona(pantalla: pygame.Surface, tema: Tema, zona_id: str, centro: tuple[int, int], r: int,
                inicial: str, fuente: pygame.font.Font) -> None:
    """Dibujo sencillo del lugar dentro de su circulo (radio `r`), solo con colores del tema."""
    cx, cy = centro
    u = r / 10  # unidad: 1/10 del radio

    def rect(x: float, y: float, w: float, h: float) -> pygame.Rect:
        return pygame.Rect(round(cx + x * u), round(cy + y * u), round(w * u), round(h * u))

    def poli(*puntos: tuple[float, float]) -> list[tuple[int, int]]:
        return [(round(cx + x * u), round(cy + y * u)) for x, y in puntos]

    if zona_id == "colegio":            # edificio con bandera
        pygame.draw.rect(pantalla, tema.texto, rect(-6, -2, 12, 8))
        pygame.draw.rect(pantalla, tema.panel, rect(-1.2, 2, 2.4, 4))
        for x in (-4.5, 2):
            pygame.draw.rect(pantalla, tema.panel, rect(x, -0.5, 2.5, 2.2))
        pygame.draw.line(pantalla, tema.texto, poli((0, -2))[0], poli((0, -7))[0], max(2, round(u * 0.5)))
        pygame.draw.polygon(pantalla, tema.acento, poli((0, -7), (4.5, -5.5), (0, -4)))
    elif zona_id == "barrio":           # dos casas
        for x, ancho, alto in ((-7, 7, 6), (1, 6, 4.5)):
            pygame.draw.rect(pantalla, tema.texto, rect(x, 6 - alto, ancho, alto))
            pygame.draw.polygon(pantalla, tema.acento, poli((x - 0.8, 6 - alto), (x + ancho + 0.8, 6 - alto),
                                                            (x + ancho / 2, 6 - alto - 3.2)))
            pygame.draw.rect(pantalla, tema.panel, rect(x + ancho / 2 - 0.9, 6 - 2.4, 1.8, 2.4))
    elif zona_id == "parque":           # arbol
        pygame.draw.rect(pantalla, tema.texto, rect(-0.9, 1, 1.8, 5.5))
        for dx, dy, rad in ((0, -3, 4.2), (-3, -0.5, 3), (3, -0.5, 3)):
            pygame.draw.circle(pantalla, tema.verde, (round(cx + dx * u), round(cy + dy * u)), round(rad * u))
    elif zona_id == "plaza":            # fuente
        pygame.draw.ellipse(pantalla, tema.texto, rect(-7, 2, 14, 5))
        pygame.draw.ellipse(pantalla, tema.acento, rect(-5.2, 3, 10.4, 2.6))
        pygame.draw.line(pantalla, tema.texto, poli((0, 3.5))[0], poli((0, -3))[0], max(2, round(u * 0.6)))
        for dx in (-3.5, 0, 3.5):
            pygame.draw.line(pantalla, tema.acento, poli((0, -3))[0], poli((dx, 2.5))[0], max(2, round(u * 0.5)))
    elif zona_id == "alcaldia":         # edificio con columnas y frontis
        pygame.draw.polygon(pantalla, tema.texto, poli((-7, -2), (7, -2), (0, -6.8)))
        for x in (-5.2, -1.6, 2.2):
            pygame.draw.rect(pantalla, tema.texto, rect(x, -1, 2.6, 6))
        pygame.draw.rect(pantalla, tema.texto, rect(-7, 5, 14, 1.8))
    else:                               # lugar desconocido: su inicial
        img = fuente.render(inicial[:1].upper(), True, tema.texto)
        pantalla.blit(img, img.get_rect(center=centro))


def _pin(pantalla: pygame.Surface, tema: Tema, punta: tuple[int, int]) -> None:
    """Marcador de posicion tipo chincheta, con la punta en `punta`. Doble contorno (claro y de acento)
    para que se vea sobre cualquier fondo y en alto contraste."""
    x, y = punta
    cabeza = (x, y - px(22))
    for radio, color in ((px(13), tema.texto), (px(10), tema.acento)):
        pygame.draw.circle(pantalla, color, cabeza, radio)
    pygame.draw.polygon(pantalla, tema.texto, [(x - px(9), y - px(17)), (x + px(9), y - px(17)), (x, y + px(1))])
    pygame.draw.polygon(pantalla, tema.acento, [(x - px(7), y - px(16)), (x + px(7), y - px(16)), (x, y - px(3))])
    pygame.draw.circle(pantalla, tema.fondo, cabeza, px(4))


def _rombo(pantalla: pygame.Surface, color: tuple[int, int, int], centro: tuple[int, int], r: int, relleno: bool) -> None:
    x, y = centro
    pygame.draw.polygon(pantalla, color, [(x, y - r), (x + r, y), (x, y + r), (x - r, y)], 0 if relleno else px(3))


# --- franja de ayuda al pie del mapa ----------------------------------------------------------------
def _tecla(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, letra: str, derecha: int, y: int) -> None:
    """Teclita con la letra de atajo, alineada a la derecha."""
    img = fuentes.chica.render(letra, True, tema.fondo)
    caja = img.get_rect(midright=(derecha, y)).inflate(px(14), px(6))
    pygame.draw.rect(pantalla, tema.texto, caja, border_radius=px(6))
    pantalla.blit(img, img.get_rect(center=caja.center))


def _franja_de_ayuda(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, rect: pygame.Rect,
                     estado: EstadoMapa) -> None:
    """Zona fija bajo el mapa (no tapa nada). Sin mouse sobre un lugar: que significan el pin y el rombo.
    Con el mouse sobre un lugar: a donde se va, cuanto cuesta (con rayos, no con cifras sueltas) y si queda
    algo por descubrir."""
    franja = pygame.Rect(rect.x + px(10), rect.bottom - ALTO_FRANJA - px(8), rect.width - px(20), ALTO_FRANJA)
    pygame.draw.rect(pantalla, tema.panel, franja, border_radius=px(10))
    f = fuentes.chica
    paso = f.get_linesize() + px(2)
    x0, y = franja.x + px(14), franja.y + px(6)
    zona = estado.ciudad.zona(estado.hover) if estado.hover in estado.ciudad else None
    if zona is None:                                   # leyenda de los dos simbolos
        _pin(pantalla, tema, (x0 + px(8), y + px(24)))
        pantalla.blit(f.render("Tu posicion", True, tema.texto), (x0 + px(26), y + px(1)))
        _rombo(pantalla, tema.detalle, (x0 + px(8), y + paso + px(14)), px(9), True)
        pantalla.blit(f.render("Hay algo por descubrir", True, tema.texto), (x0 + px(26), y + paso + px(3)))
        return
    if zona.id == estado.actual:
        pantalla.blit(f.render(f"Estas en {zona.nombre}", True, tema.acento), (x0, y))
    else:
        pantalla.blit(f.render(f"Ir a {zona.nombre}", True, tema.acento), (x0, y))
        if estado.teclas:
            _tecla(pantalla, fuentes, tema, tecla_de(estado.ciudad, zona.id), franja.right - px(14), y + f.get_linesize() // 2)
        costo = estado.costos.get(zona.id)
        if estado.energia is not None and costo is not None:
            y += paso
            if costo <= estado.energia:
                pantalla.blit(f.render("Cuesta", True, tema.texto), (x0, y))
                xr = x0 + f.size("Cuesta")[0] + px(16)
                for k in range(costo):
                    rayo(pantalla, tema.acento, (xr + k * px(18), y + f.get_linesize() // 2), px(9))
            else:
                pantalla.blit(f.render("No te alcanza la energia", True, tema.malo), (x0, y))
    y += paso
    if zona.id in estado.pendientes:
        _rombo(pantalla, tema.detalle, (x0 + px(8), y + f.get_linesize() // 2), px(8), True)
        pantalla.blit(f.render("Hay algo por descubrir", True, tema.texto), (x0 + px(24), y))
    elif zona.id in estado.revisadas:
        _rombo(pantalla, tema.bueno, (x0 + px(8), y + f.get_linesize() // 2), px(8), False)
        pantalla.blit(f.render("Ya lo revisaste", True, tema.texto), (x0 + px(24), y))


# --- mapa completo -----------------------------------------------------------------------------------
def dibujar_mapa(pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema, rect: pygame.Rect,
                 estado: EstadoMapa) -> None:
    pygame.draw.rect(pantalla, tema.fondo, rect, border_radius=px(12))
    pygame.draw.rect(pantalla, tema.borde, rect, width=px(2), border_radius=px(12))
    radio = _radio(rect)
    pos = _posiciones(estado, rect)
    tramos_ruta = {frozenset(par) for par in zip(estado.ruta, estado.ruta[1:])}

    # 1) calles: lineas simples y gruesas; la que lleva al lugar que se mira va resaltada
    for a, b, _distancia in estado.ciudad.conexiones():   # la distancia es calculo interno: no se dibuja
        en_ruta = frozenset((a, b)) in tramos_ruta
        pygame.draw.line(pantalla, tema.acento if en_ruta else tema.borde, pos[a], pos[b], px(11 if en_ruta else 7))
        for punto in (pos[a], pos[b]):                    # extremos redondeados
            pygame.draw.circle(pantalla, tema.acento if en_ruta else tema.borde, punto, px(5.5 if en_ruta else 3.5))

    # 2) lugares: circulo con su icono, nombre debajo y marca si queda algo por descubrir
    for zona in estado.ciudad.zonas():
        x, y = pos[zona.id]
        es_actual = zona.id == estado.actual
        mirado = estado.hover == zona.id
        inalcanzable = (estado.energia is not None and not es_actual
                        and estado.costos.get(zona.id, 0) > estado.energia)
        pygame.draw.circle(pantalla, tema.panel, (x, y), radio)
        _icono_zona(pantalla, tema, zona.id, (x, y), radio - px(3), zona.nombre, fuentes.normal)
        if inalcanzable:                                  # apagado: no alcanza la energia
            velo = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
            pygame.draw.circle(velo, (*tema.fondo, 150), (radio, radio), radio)
            pantalla.blit(velo, (x - radio, y - radio))
        destacado = es_actual or mirado or zona.id in estado.ruta
        pygame.draw.circle(pantalla, tema.acento if destacado else tema.borde, (x, y), radio,
                           px(4) if (es_actual or mirado) else px(2))
        nombre = fuentes.chica.render(zona.nombre, True, tema.acento if es_actual else (tema.borde if inalcanzable else tema.texto))
        pantalla.blit(nombre, nombre.get_rect(midtop=(x, y + radio + px(5))))
        if zona.id in estado.pendientes:                  # algo por descubrir: rombo relleno con "?"
            c = (x + radio - px(2), y - radio + px(4))
            _rombo(pantalla, tema.detalle, c, px(12), True)
            signo = fuentes.chica.render("?", True, tema.fondo)
            pantalla.blit(signo, signo.get_rect(center=c))
        elif zona.id in estado.revisadas:                 # ya revisado: rombo hueco con visto
            c = (x + radio - px(2), y - radio + px(4))
            _rombo(pantalla, tema.bueno, c, px(12), False)
            pygame.draw.lines(pantalla, tema.bueno, False,
                              [(c[0] - px(5), c[1]), (c[0] - px(1), c[1] + px(4)), (c[0] + px(6), c[1] - px(5))], px(3))

    # 3) franja de ayuda al pie: leyenda, o lo que cuesta ir al lugar que se esta mirando
    if estado.mostrar_ayuda:
        _franja_de_ayuda(pantalla, fuentes, tema, rect, estado)

    # 4) el jugador, AL FINAL: el pin queda sobre cualquier otra cosa y siempre se ve
    if estado.actual in pos:
        x, y = pos[estado.actual]
        _pin(pantalla, tema, (x, y - radio + px(3)))
