"""Componentes de interfaz reutilizables (todos con colores del tema y medidas de los tokens): Fuentes, Boton,
Panel, Tarjeta, BarraAnimada, Modal y CajaDialogo. El aviso flotante es `anuncio_view.Anuncio` y el texto
flotante de impacto vive en `efectos.py`."""
import math
from dataclasses import dataclass
from typing import Callable

import pygame

from post_truth.config import RUTA_FUENTES, px
from post_truth.views.theme import NEGRO, TOKENS, Tema, esp, mezclar


@dataclass
class Fuentes:
    """Tamanos de fuente compartidos."""
    chica: pygame.font.Font
    normal: pygame.font.Font
    grande: pygame.font.Font
    titulo: pygame.font.Font
    enorme: pygame.font.Font = None   # cuenta regresiva y titulos de portada

    @classmethod
    def crear(cls) -> "Fuentes":
        return cls(**{nombre: fuente(archivo, tam) for nombre, tam, archivo in TOKENS.fuentes})


def fuente(archivo: str, tam: int) -> pygame.font.Font:
    """La fuente pixel de assets/fuentes; si falta o no se puede leer, Arial del sistema (el juego sigue)."""
    try:
        return pygame.font.Font(str(RUTA_FUENTES / archivo), px(tam))
    except (FileNotFoundError, OSError, pygame.error):
        return pygame.font.SysFont("arial", px(tam), bold=tam >= 30)


def ajustar_texto(texto: str, fuente: pygame.font.Font, ancho: int) -> list[str]:
    """Parte `texto` en lineas que caben en `ancho` px."""
    lineas: list[str] = []
    for parrafo in texto.split("\n"):
        actual = ""
        for palabra in parrafo.split():
            prueba = f"{actual} {palabra}".strip()
            if actual and fuente.size(prueba)[0] > ancho:
                lineas.append(actual)
                actual = palabra
            else:
                actual = prueba
        lineas.append(actual)
    return lineas


def dibujar_texto_ajustado(pantalla: pygame.Surface, fuente: pygame.font.Font, texto: str,
                           color: tuple[int, int, int], rect: pygame.Rect, interlineado: int | None = None) -> int:
    """Dibuja texto ajustado al ancho de `rect`."""
    y = rect.y
    interlineado = px(4) if interlineado is None else interlineado
    for linea in ajustar_texto(texto, fuente, rect.width):
        pantalla.blit(fuente.render(linea, True, color), (rect.x, y))
        y += fuente.get_linesize() + interlineado
    return y


class Boton:
    """Boton con estados normal, encima (hover o foco de teclado), presionado y deshabilitado."""

    def __init__(self, rect: pygame.Rect, texto: str, al_hacer_clic: Callable[[], None],
                 atajo: int | None = None) -> None:
        self.rect = rect
        self.texto = texto
        self.al_hacer_clic = al_hacer_clic
        self.atajo = atajo
        self.hover = False
        self.habilitado = True
        self.foco = False          # elegido con el teclado (se ve igual que el hover)
        self._presionado = False

    @property
    def presionado(self) -> bool:
        return self._presionado and self.hover

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Devuelve True si el evento disparo el boton."""
        if not self.habilitado:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._presionado = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            disparar = self._presionado and self.rect.collidepoint(event.pos)
            self._presionado = False
            if disparar:
                self.al_hacer_clic()
                return True
        elif event.type == pygame.KEYDOWN and self.atajo is not None and event.key == self.atajo:
            self.al_hacer_clic()
            return True
        return False

    LABIO = 4   # alto (de diseno) del borde oscuro de abajo: la tecla "sobresale"

    def draw(self, pantalla: pygame.Surface, fuente: pygame.font.Font, tema: Tema) -> None:
        """Tecla pixel: cara con luz arriba y labio oscuro abajo; presionada se hunde y el labio desaparece."""
        p, labio = px(2), px(self.LABIO)
        encima = self.habilitado and (self.hover or self.foco)
        hundido = self.habilitado and self.presionado
        oscuro = mezclar(tema.fondo, NEGRO, 0.6)
        if not self.habilitado:
            cara_color, contorno, color_texto = tema.boton_off, tema.texto_off, tema.texto_off
        else:
            cara_color = mezclar(tema.boton_hover, tema.fondo, 0.25) if hundido else (
                tema.boton_hover if encima else tema.boton)
            contorno, color_texto = (tema.acento if encima else oscuro), tema.boton_texto
        r = self.rect.move(0, labio) if hundido else self.rect
        alto = self.rect.h - labio if hundido else self.rect.h
        _cortado(pantalla, contorno, pygame.Rect(r.x, r.y, r.w, alto), p)
        cara = pygame.Rect(r.x + p, r.y + p, r.w - 2 * p, alto - 2 * p - (0 if hundido else labio))
        if not hundido:   # el labio: el costado de la tecla que se ve debajo de la cara
            pygame.draw.rect(pantalla, mezclar(cara_color, NEGRO, 0.45), (cara.x, cara.bottom, cara.w, labio))
        pygame.draw.rect(pantalla, cara_color, cara)
        pygame.draw.rect(pantalla, mezclar(cara_color, tema.texto, 0.3), (cara.x, cara.y, cara.w, p))   # luz
        flecha = 3 * p + px(6)
        img = fuente.render(recortar(self.texto, fuente, cara.w - 2 * flecha), True, color_texto)
        destino = img.get_rect(center=cara.center)
        pantalla.blit(img, destino)
        if encima:   # flechita pixel a la izquierda del texto (tres columnas: 5, 3 y 1 pixeles)
            x = destino.x - flecha
            for k, filas in enumerate((5, 3, 1)):   # alturas en pixeles: no es un color
                pygame.draw.rect(pantalla, tema.acento, (x + k * p, cara.centery - filas * p // 2, p, filas * p))


def recortar(texto: str, fuente: pygame.font.Font, ancho: int) -> str:
    """El texto entero si cabe en `ancho`; si no, cortado con "..." (no se escala: la letra pixel se veria borrosa)."""
    if fuente.size(texto)[0] <= ancho:
        return texto
    while texto and fuente.size(texto + "...")[0] > ancho:
        texto = texto[:-1]
    return texto.rstrip() + "..."


class Panel:
    """Rectangulo redondeado con titulo opcional."""

    def __init__(self, rect: pygame.Rect, titulo: str = "", alfa: int = 255) -> None:
        self.rect = rect
        self.titulo = titulo
        self.alfa = alfa

    @property
    def interior(self) -> pygame.Rect:
        """Area util debajo del titulo, con margen."""
        margen_sup = px(52) if self.titulo else px(16)
        return pygame.Rect(self.rect.x + px(18), self.rect.y + margen_sup,
                           self.rect.width - px(36), self.rect.height - margen_sup - px(16))

    def draw(self, pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema) -> None:
        panel(pantalla, tema, self.rect, self.alfa)
        if self.titulo:
            img = fuentes.grande.render(self.titulo, True, tema.acento)
            pantalla.blit(img, (self.rect.x + px(18), self.rect.y + px(12)))


def _cortado(sup: pygame.Surface, color, r: pygame.Rect, p: int) -> None:
    """Rectangulo con las cuatro esquinas recortadas un pixel (de tamano `p`)."""
    pygame.draw.rect(sup, color, (r.x + p, r.y, r.w - 2 * p, r.h))
    pygame.draw.rect(sup, color, (r.x, r.y + p, r.w, r.h - 2 * p))


def marco_pixel(pantalla: pygame.Surface, tema: Tema, rect: pygame.Rect, relleno=None, alfa: int = 255,
                borde=None, sombra: bool = True) -> None:
    """Marco pixel art: esquinas recortadas, contorno oscuro (o `borde`), luz arriba e izquierda, sombra abajo y
    derecha, y una sombra dura desplazada (sin difuminar). El pixel mide px(2)."""
    p = px(2)
    relleno = relleno or tema.panel
    oscuro = mezclar(tema.fondo, NEGRO, 0.6)
    capa = pygame.Surface((rect.w + 2 * p, rect.h + 2 * p), pygame.SRCALPHA)
    if sombra:
        _cortado(capa, (*oscuro, TOKENS.alfa_sombra), pygame.Rect(2 * p, 2 * p, rect.w, rect.h), p)
    _cortado(capa, (*(borde or oscuro), 255), pygame.Rect(0, 0, rect.w, rect.h), p)
    pygame.draw.rect(capa, (*relleno, alfa), (p, p, rect.w - 2 * p, rect.h - 2 * p))
    luz, sombra_cara = (*mezclar(relleno, tema.texto, 0.22), alfa), (*mezclar(relleno, NEGRO, 0.35), alfa)
    pygame.draw.rect(capa, luz, (p, p, rect.w - 2 * p, p))                    # arriba
    pygame.draw.rect(capa, luz, (p, p, p, rect.h - 2 * p))                    # izquierda
    pygame.draw.rect(capa, sombra_cara, (2 * p, rect.h - 2 * p, rect.w - 3 * p, p))   # abajo
    pygame.draw.rect(capa, sombra_cara, (rect.w - 2 * p, 2 * p, p, rect.h - 3 * p))   # derecha
    pantalla.blit(capa, rect.topleft)


def panel(pantalla: pygame.Surface, tema: Tema, rect: pygame.Rect, alfa: int = 255, borde=None) -> None:
    """El fondo de todo lo que flota (marco pixel, con transparencia sobre el mapa)."""
    marco_pixel(pantalla, tema, rect, tema.panel, alfa, borde)


class Tarjeta:
    """Panel con icono, titulo y cuerpo: un hallazgo, una notificacion, un cambio de la ciudad."""

    def __init__(self, rect: pygame.Rect, titulo: str, texto: str = "", tipo: str = "info") -> None:
        self.rect, self.titulo, self.texto, self.tipo = rect, titulo, texto, tipo

    def draw(self, pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema) -> None:
        from post_truth.views.anuncio_view import _icono
        panel(pantalla, tema, self.rect, TOKENS.alfa_panel)
        r = min(px(16), self.rect.h // 3)
        _icono(pantalla, tema, self.tipo, (self.rect.x + esp(3) + r, self.rect.y + esp(3) + r), r, 0)
        x = self.rect.x + esp(4) + 2 * r + esp(2)
        pantalla.blit(fuentes.normal.render(self.titulo, True, tema.texto), (x, self.rect.y + esp(2)))
        y = self.rect.y + esp(2) + fuentes.normal.get_linesize()
        for linea in ajustar_texto(self.texto, fuentes.chica, self.rect.right - x - esp(3)):
            if y + fuentes.chica.get_linesize() > self.rect.bottom - esp(1):
                break
            pantalla.blit(fuentes.chica.render(linea, True, tema.texto_off), (x, y))
            y += fuentes.chica.get_linesize()


class BarraAnimada:
    """Barra 0-100 que se llena interpolando hacia su valor con dt (amortiguacion exponencial): el mismo
    resultado a 30 y a 60 FPS, y nunca bloquea el bucle."""
    RAPIDEZ = 6.0

    def __init__(self, valor: float = 0.0) -> None:
        self.objetivo = self.actual = float(valor)

    def fijar(self, valor: float) -> None:
        self.objetivo = float(valor)

    def update(self, dt: float) -> None:
        self.actual += (self.objetivo - self.actual) * (1 - math.exp(-self.RAPIDEZ * max(0.0, dt)))

    def draw(self, pantalla: pygame.Surface, tema: Tema, rect: pygame.Rect, color) -> None:
        radio = rect.h // 2
        pygame.draw.rect(pantalla, tema.fondo, rect, border_radius=radio)
        lleno = round(rect.w * max(0.0, min(100.0, self.actual)) / 100)
        if lleno:
            pygame.draw.rect(pantalla, color, (rect.x, rect.y, lleno, rect.h), border_radius=radio)
        if abs(self.objetivo - self.actual) > 0.5:   # mientras se mueve, una marca en el valor al que va
            x = rect.x + round(rect.w * max(0.0, min(100.0, self.objetivo)) / 100)
            pygame.draw.line(pantalla, tema.texto, (x, rect.y - px(2)), (x, rect.bottom + px(1)), px(2))


class Modal:
    """Ventana al frente sobre un velo: titulo, texto y botones (1-9 o clic; Enter = el primero).
    `cuenta` = (restante, total) dibuja una cuenta regresiva grande en un anillo que se vacia."""

    def __init__(self, titulo: str, texto: str = "", botones: tuple[str, ...] = ("Aceptar",), tipo: str = "info",
                 ancho: int = 620) -> None:
        self.titulo, self.texto, self.botones, self.tipo = titulo, texto, botones, tipo
        self.ancho = ancho
        self.t = 0.0
        self.elegido: int | None = None
        self.cuenta: tuple[float, float] | None = None
        self._rects: list[pygame.Rect] = []

    def update(self, dt: float) -> None:
        self.t += dt

    def handle_event(self, event: pygame.event.Event) -> int | None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.elegido = 0
            elif len(self.botones) > 1 and pygame.K_1 <= event.key < pygame.K_1 + len(self.botones):   # con uno: Enter
                self.elegido = event.key - pygame.K_1
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.elegido = next((i for i, r in enumerate(self._rects) if r.collidepoint(event.pos)), None)
        return self.elegido

    def draw(self, pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema) -> None:
        from post_truth.views.anuncio_view import _color, _icono, _rebote
        entrada = min(1.0, self.t / TOKENS.dur_media)
        velo = pygame.Surface(pantalla.get_size(), pygame.SRCALPHA)
        velo.fill((*tema.fondo, round(TOKENS.alfa_velo * entrada)))
        pantalla.blit(velo, (0, 0))
        w = px(self.ancho)
        lineas = ajustar_texto(self.texto, fuentes.normal, w - px(150))
        alto = px(150) + len(lineas) * fuentes.normal.get_linesize() + (px(150) if self.cuenta else 0)
        caja = pygame.Rect(0, 0, w, alto)
        caja.center = (pantalla.get_width() // 2, pantalla.get_height() // 2 - round(px(30) * (1 - _rebote(entrada))))
        color = _color(tema, self.tipo)
        panel(pantalla, tema, caja, 255, borde=color)
        _icono(pantalla, tema, self.tipo, (caja.x + px(56), caja.y + px(60)), px(32), self.t)
        x = caja.x + px(110)
        pantalla.blit(fuentes.titulo.render(self.titulo, True, color), (x, caja.y + esp(4)))
        y = caja.y + esp(4) + fuentes.titulo.get_linesize()
        for linea in lineas:
            pantalla.blit(fuentes.normal.render(linea, True, tema.texto), (x, y))
            y += fuentes.normal.get_linesize()
        if self.cuenta is not None:
            restante, total = self.cuenta
            centro, radio = (caja.centerx, y + px(70)), px(60)
            pygame.draw.circle(pantalla, tema.fondo, centro, radio)
            arco = pygame.Rect(0, 0, 2 * radio, 2 * radio)
            arco.center = centro
            fraccion = max(0.0, min(1.0, restante / total)) if total else 0.0
            if fraccion > 0:
                pygame.draw.arc(pantalla, tema.malo if fraccion < 0.35 else color, arco, math.pi / 2,
                                math.pi / 2 + 2 * math.pi * fraccion, px(10))
            num = fuentes.enorme.render(str(math.ceil(restante)), True, tema.texto)
            pantalla.blit(num, num.get_rect(center=centro))
            y += px(150)
        ancho_boton = (w - px(40) - esp(2) * (len(self.botones) - 1)) // len(self.botones)
        self._rects = []
        for i, texto in enumerate(self.botones):
            r = pygame.Rect(caja.x + px(20) + i * (ancho_boton + esp(2)), caja.bottom - px(64), ancho_boton, px(46))
            b = Boton(r, f"{i + 1}. {texto}" if len(self.botones) > 1 else f"{texto} (Enter)", lambda: None)
            b.foco = i == 0
            b.draw(pantalla, fuentes.normal, tema)
            self._rects.append(r)


class CajaDialogo:
    """Caja de texto estilo novela visual."""

    def __init__(self, rect: pygame.Rect, caracteres_por_segundo: float = 80.0) -> None:
        self.rect = rect
        self.velocidad = caracteres_por_segundo
        self.texto = ""
        self.hablante = ""
        self._visibles = 0.0
        self._t = 0.0

    def set_texto(self, texto: str, hablante: str = "") -> None:
        self.texto = texto
        self.hablante = hablante
        self._visibles = 0.0

    @property
    def terminado(self) -> bool:
        return self._visibles >= len(self.texto)

    def completar(self) -> None:
        self._visibles = float(len(self.texto))

    def update(self, dt: float) -> None:
        self._t += dt
        if not self.terminado:
            self._visibles = min(float(len(self.texto)), self._visibles + self.velocidad * dt)

    def draw(self, pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema) -> None:
        marco_pixel(pantalla, tema, self.rect, borde=tema.acento)
        y = self.rect.y + px(12)
        if self.hablante:
            pantalla.blit(fuentes.normal.render(self.hablante, True, tema.acento), (self.rect.x + px(20), y))
            y += fuentes.normal.get_linesize() + px(4)
        restante = int(self._visibles)
        for linea in ajustar_texto(self.texto, fuentes.normal, self.rect.width - px(40)):
            if restante <= 0:
                break
            pantalla.blit(fuentes.normal.render(linea[:restante], True, tema.texto), (self.rect.x + px(20), y))
            restante -= len(linea) + 1
            y += fuentes.normal.get_linesize() + px(2)
        if self.terminado and int(self._t * 2) % 2 == 0:
            x, yb = self.rect.right - px(28), self.rect.bottom - px(22)
            pygame.draw.polygon(pantalla, tema.acento, [(x, yb), (x + px(14), yb), (x + px(7), yb + px(9))])
