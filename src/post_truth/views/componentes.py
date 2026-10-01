"""Componentes de interfaz reutilizables: Fuentes, Boton, Panel y CajaDialogo.

Ningun componente tiene colores propios: todo sale del `Tema` activo que se pasa a
`draw` (regla de accesibilidad). Los componentes guardan estado de interaccion
(hover, texto revelado) pero nunca modifican el modelo del juego.
"""
from dataclasses import dataclass
from typing import Callable

import pygame

from post_truth.views.theme import Tema


@dataclass
class Fuentes:
    """Tamanos de fuente compartidos; se crean una sola vez (crear fuentes cada frame es caro)."""
    chica: pygame.font.Font
    normal: pygame.font.Font
    grande: pygame.font.Font
    titulo: pygame.font.Font

    @classmethod
    def crear(cls) -> "Fuentes":
        def f(tam: int, negrita: bool = False) -> pygame.font.Font:
            return pygame.font.SysFont("arial", tam, bold=negrita)
        return cls(f(16), f(22), f(30, True), f(44, True))


def ajustar_texto(texto: str, fuente: pygame.font.Font, ancho: int) -> list[str]:
    """Parte `texto` en lineas que caben en `ancho` px (word-wrap por palabras).

    Se mide con la fuente real (no por cantidad de caracteres) porque arial es
    proporcional. Respeta los saltos de linea explicitos. Una palabra mas ancha que
    la caja queda en su propia linea en vez de cortarse. Costo: O(n) medidas.
    """
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
                           color: tuple[int, int, int], rect: pygame.Rect, interlineado: int = 4) -> int:
    """Dibuja texto ajustado al ancho de `rect`; devuelve la y donde termino."""
    y = rect.y
    for linea in ajustar_texto(texto, fuente, rect.width):
        pantalla.blit(fuente.render(linea, True, color), (rect.x, y))
        y += fuente.get_linesize() + interlineado
    return y


class Boton:
    """Boton con hover y clic. El callback se dispara al SOLTAR el mouse dentro del boton
    (como en cualquier UI: permite arrepentirse arrastrando fuera) o con su tecla de atajo."""

    def __init__(self, rect: pygame.Rect, texto: str, al_hacer_clic: Callable[[], None],
                 atajo: int | None = None) -> None:
        self.rect = rect
        self.texto = texto
        self.al_hacer_clic = al_hacer_clic
        self.atajo = atajo  # constante pygame.K_*, opcional
        self.hover = False
        self.habilitado = True  # deshabilitado: se ve apagado y no responde a clics ni atajos
        self._presionado = False

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

    def draw(self, pantalla: pygame.Surface, fuente: pygame.font.Font, tema: Tema) -> None:
        if not self.habilitado:
            pygame.draw.rect(pantalla, tema.boton_off, self.rect, border_radius=10)
            pygame.draw.rect(pantalla, tema.texto_off, self.rect, width=1, border_radius=10)
            color_texto = tema.texto_off
        else:
            relleno = tema.boton_hover if self.hover else tema.boton
            borde = tema.acento if self.hover else tema.borde
            pygame.draw.rect(pantalla, relleno, self.rect, border_radius=10)
            pygame.draw.rect(pantalla, borde, self.rect, width=3 if self.hover else 2, border_radius=10)
            color_texto = tema.boton_texto
        img = fuente.render(self.texto, True, color_texto)
        maximo = self.rect.width - 16
        if img.get_width() > maximo:  # textos largos se reducen en vez de salirse del boton
            alto = max(1, img.get_height() * maximo // img.get_width())
            img = pygame.transform.smoothscale(img, (maximo, alto))
        pantalla.blit(img, img.get_rect(center=self.rect.center))


class Panel:
    """Rectangulo redondeado con titulo opcional; contenedor visual para agrupar informacion."""

    def __init__(self, rect: pygame.Rect, titulo: str = "", alfa: int = 255) -> None:
        self.rect = rect
        self.titulo = titulo
        self.alfa = alfa  # < 255 deja ver el fondo de la zona a traves del panel

    @property
    def interior(self) -> pygame.Rect:
        """Area util debajo del titulo, con margen."""
        margen_sup = 52 if self.titulo else 16
        return pygame.Rect(self.rect.x + 18, self.rect.y + margen_sup,
                           self.rect.width - 36, self.rect.height - margen_sup - 16)

    def draw(self, pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema) -> None:
        if self.alfa >= 255:
            pygame.draw.rect(pantalla, tema.panel, self.rect, border_radius=14)
        else:
            velo = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            pygame.draw.rect(velo, (*tema.panel, self.alfa), velo.get_rect(), border_radius=14)
            pantalla.blit(velo, self.rect.topleft)
        pygame.draw.rect(pantalla, tema.borde, self.rect, width=2, border_radius=14)
        if self.titulo:
            img = fuentes.grande.render(self.titulo, True, tema.acento)
            pantalla.blit(img, (self.rect.x + 18, self.rect.y + 12))


class CajaDialogo:
    """Caja de texto estilo novela visual: nombre del hablante y texto que se revela poco a poco.

    La revelacion avanza con `dt` (caracteres por segundo), nunca con sleep, asi el
    loop sigue a 60 FPS y el jugador puede saltarla con `completar()`.
    """

    def __init__(self, rect: pygame.Rect, caracteres_por_segundo: float = 80.0) -> None:
        self.rect = rect
        self.velocidad = caracteres_por_segundo
        self.texto = ""
        self.hablante = ""
        self._visibles = 0.0
        self._t = 0.0  # reloj del parpadeo del indicador "continuar"

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
        pygame.draw.rect(pantalla, tema.panel, self.rect, border_radius=14)
        pygame.draw.rect(pantalla, tema.acento, self.rect, width=3, border_radius=14)
        y = self.rect.y + 12
        if self.hablante:
            pantalla.blit(fuentes.normal.render(self.hablante, True, tema.acento), (self.rect.x + 20, y))
            y += fuentes.normal.get_linesize() + 4
        restante = int(self._visibles)
        for linea in ajustar_texto(self.texto, fuentes.normal, self.rect.width - 40):
            if restante <= 0:
                break
            pantalla.blit(fuentes.normal.render(linea[:restante], True, tema.texto), (self.rect.x + 20, y))
            restante -= len(linea) + 1  # +1: el espacio que el wrap quito al cortar la linea
            y += fuentes.normal.get_linesize() + 2
        if self.terminado and int(self._t * 2) % 2 == 0:  # triangulo parpadeante: "ya termino"
            x, yb = self.rect.right - 28, self.rect.bottom - 22
            pygame.draw.polygon(pantalla, tema.acento, [(x, yb), (x + 14, yb), (x + 7, yb + 9)])
