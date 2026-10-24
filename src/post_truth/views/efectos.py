"""Retroalimentacion global: el HUD compacto con barras que se llenan interpolando y los textos flotantes de impacto
("+8 Confianza") que suben y se desvanecen cuando cambia un indicador. Lo dibuja el StateManager encima de la
pantalla activa si esta lo pide con `datos_hud()`. Todo con dt: nunca bloquea el bucle."""
from dataclasses import dataclass

import pygame

from post_truth.config import px
from post_truth.views import hud
from post_truth.views.componentes import BarraAnimada, Fuentes
from post_truth.views.theme import Tema

ETIQUETA = dict((i[0], i[1]) for i in hud.INDICADORES) | {hud.CREDIBILIDAD: "Credibilidad"}
MALOS = {i[0] for i in hud.INDICADORES if i[2]}


@dataclass
class TextoFlotante:
    texto: str
    pos: tuple[int, int]
    bueno: bool
    t: float = 0.0
    duracion: float = 1.4
    subida: int = 46

    def update(self, dt: float) -> None:
        self.t += dt

    @property
    def terminado(self) -> bool:
        return self.t >= self.duracion

    @property
    def alfa(self) -> int:
        """Aparece rapido y se desvanece en la segunda mitad."""
        f = self.t / self.duracion
        return round(255 * min(1.0, f / 0.15, max(0.0, (1 - f) / 0.5)))

    @property
    def posicion(self) -> tuple[int, int]:
        f = min(1.0, self.t / self.duracion)
        return self.pos[0], round(self.pos[1] - px(self.subida) * (1 - (1 - f) ** 2))

    def draw(self, pantalla: pygame.Surface, fuentes: Fuentes, tema: Tema) -> None:
        color = tema.bueno if self.bueno else tema.malo
        img = fuentes.normal.render(self.texto, True, color)
        sombra = fuentes.normal.render(self.texto, True, tema.fondo)
        capa = pygame.Surface((img.get_width() + px(2), img.get_height() + px(2)), pygame.SRCALPHA)
        capa.blit(sombra, (px(2), px(2)))
        capa.blit(img, (0, 0))
        capa.set_alpha(self.alfa)
        pantalla.blit(capa, capa.get_rect(midleft=self.posicion))


class CapaRetro:
    def __init__(self, fuentes: Fuentes, temas) -> None:
        self.fuentes, self.temas = fuentes, temas
        self.barras: dict[str, BarraAnimada] = {}
        self.flotantes: list[TextoFlotante] = []
        self._valores: dict[str, int] = {}
        self._origen = None

    def update(self, dt: float, estado) -> None:
        d = estado.datos_hud() if estado is not None else None
        if d is not None:
            valores = hud._valores(d)
            nuevo = d.origen != self._origen
            pos = hud.posiciones(d.modo)
            for nombre, v in valores.items():
                if nombre not in self.barras or nuevo:
                    self.barras[nombre] = BarraAnimada(v)
                elif v != self._valores.get(nombre) and nombre in pos:
                    delta = v - self._valores[nombre]
                    x, y = pos[nombre]
                    y += px(16) * sum(f.texto.endswith(ETIQUETA[nombre]) for f in self.flotantes)   # no se tapan
                    self.flotantes.append(TextoFlotante(f"{delta:+} {ETIQUETA[nombre]}", (x, y),
                                                        (delta > 0) != (nombre in MALOS)))
                self.barras[nombre].fijar(v)
            self._valores, self._origen = valores, d.origen
        for b in self.barras.values():
            b.update(dt)
        for f in self.flotantes:
            f.update(dt)
        self.flotantes = [f for f in self.flotantes if not f.terminado]

    def draw(self, pantalla: pygame.Surface, estado) -> None:
        tema = self.temas.actual
        d = estado.datos_hud() if estado is not None else None
        if d is not None:
            hud.dibujar(pantalla, self.fuentes, tema, d, self.barras)
        for f in self.flotantes[-8:]:   # a lo sumo 8 a la vez, para que se lean
            f.draw(pantalla, self.fuentes, tema)

