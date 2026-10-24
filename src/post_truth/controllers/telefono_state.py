"""Telefono Civitas (T en la calle): defender la red del rumor en vivo. Mientras esta abierto el mundo corre al 25%."""
import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.sesion import FIN, FIN_DIA, HERRAMIENTAS, RITMO_TELEFONO
from post_truth.views import sonido
from post_truth.views.anuncio_view import Anuncio, dibujar_anuncio
from post_truth.views.telefono_view import (CERRAR, HERRAMIENTAS as ORDEN, PESTANAS, VistaTelefono, ciudadano_en,
                                            dibujar_telefono, rect_herramienta, rect_pestana)

TECLAS_HERRAMIENTA = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}
ALERTA = 3.0   # segundos que parpadea el aviso de "se volvio viral"
MOTIVOS = {"enfriando": "Aun se esta recargando.", "sin_rumor": "No hay un rumor corriendo ahora."}


class TelefonoState(BaseState):
    def al_entrar(self) -> None:
        s = self.app.partida
        self.pestana, self.t, self.alerta = 0, 0.0, 0.0
        self.toast: Anuncio | None = None
        self.anuncio: Anuncio | None = None
        self.seleccionado = s.en_vivo.autor if s.en_vivo is not None else self._orden()[0]
        if s.novedad == "crisis":   # la crisis abre el telefono sola, con su reloj
            s.novedad = ""
            self.anuncio = Anuncio("Crisis viral!", f"Un rumor corre por la red y se esta regando en "
                                   f"{s.zona_noticia.capitalize()}. Tienes {round(s.tiempo_restante or 0)} s.",
                                   "crisis", duracion=3.0)

    @property
    def en_pausa(self) -> bool:
        """El anuncio de la crisis detiene todo mientras se lee."""
        return self.anuncio is not None and self.anuncio.tipo == "crisis"

    def _orden(self) -> list[str]:
        """Ciudadanos de izquierda a derecha: las flechas los recorren en el orden en que se ven."""
        return [c.id for c in sorted(self.app.partida.grafo.vertices(), key=lambda c: (c.pos[0], c.pos[1]))]

    def _cerrar(self) -> None:
        self.app.estados.cambiar("mundo")

    def _avisar(self, titulo: str, texto: str, tipo: str) -> None:
        self.toast = Anuncio(titulo, texto, tipo, grande=False, duracion=2.2)

    def usar(self, i: int) -> None:
        accion = ORDEN[i]
        r = self.app.partida.usar_herramienta(accion, self.seleccionado)
        if r.ok:
            self._avisar(HERRAMIENTAS[accion], "Hecho: mira como cambia la red.", "bueno")
        else:
            self._avisar(HERRAMIENTAS[accion], MOTIVOS.get(r.motivo, "No se pudo."), "malo")

    def _mover_seleccion(self, paso: int) -> None:
        orden = self._orden()
        self.seleccionado = orden[(orden.index(self.seleccionado) + paso) % len(orden)]

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.en_pausa:
            if (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e)) \
                    or (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
                self.anuncio.cerrar()
            return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_t, pygame.K_ESCAPE):
                self._cerrar()
            elif event.key == pygame.K_TAB:
                self.pestana = (self.pestana + 1) % len(PESTANAS)
            elif self.pestana == 0 and event.key in TECLAS_HERRAMIENTA:
                self.usar(TECLAS_HERRAMIENTA[event.key])
            elif self.pestana == 0 and event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_UP, pygame.K_w):
                self._mover_seleccion(-1)
            elif self.pestana == 0 and event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN, pygame.K_s):
                self._mover_seleccion(1)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._clic(event.pos)

    def _clic(self, punto: tuple[int, int]) -> None:
        if CERRAR.collidepoint(punto):
            self._cerrar()
            return
        for i in range(len(PESTANAS)):
            if rect_pestana(i).collidepoint(punto):
                self.pestana = i
                return
        if self.pestana != 0:
            return
        for i in range(len(ORDEN)):
            if rect_herramienta(i).collidepoint(punto):
                self.usar(i)
                return
        id = ciudadano_en(self.app.partida.grafo, punto)
        if id is not None:
            self.seleccionado = id

    def update(self, dt: float) -> None:
        for nombre in ("anuncio", "toast"):
            a = getattr(self, nombre)
            if a is not None:
                a.avanzar(dt)
                if a.terminado:
                    setattr(self, nombre, None)
        self.t += dt   # el telefono sube aunque la crisis tenga todo en pausa
        if self.en_pausa:
            return
        self.alerta = max(0.0, self.alerta - dt)
        s = self.app.partida
        vencida = s.transcurrir(dt * RITMO_TELEFONO)
        if s.novedad == "viral":
            s.novedad = ""
            self.alerta = ALERTA
            sonido.alerta()
            self._avisar("Se volvio viral!", "El rumor ya llega a mucha gente.", "malo")
        if self.pestana == 1:
            s.leidas = len(s.notificaciones)
        if vencida is not None:                 # se acabo el reloj de la crisis: se ve adentro lo que paso
            self.app.estados.cambiar("escena", fundido=True)
        elif s.fase in (FIN_DIA, FIN):
            self.app.estados.cambiar("resumen", fundido=True)
        elif s.novedad == "crisis":             # una crisis nueva mientras se mira la red
            self.al_entrar()

    def vista(self) -> VistaTelefono:
        s = self.app.partida
        return VistaTelefono(s.grafo, s.en_vivo, self.pestana, self.seleccionado, s.notificaciones, s.leidas,
                             (s.tiempo_restante, s.tiempo_viral_total) if s.reloj_activo else None,
                             s.campana.factor > 1, self.alerta, self.t)

    def draw(self, pantalla: pygame.Surface) -> None:
        tema = self.app.temas.actual
        self.app.estados.estado("mundo").draw(pantalla)   # la calle detras, quieta
        dibujar_telefono(pantalla, self.app.fuentes, tema, self.vista())
        for a in (self.toast, self.anuncio):
            if a is not None:
                dibujar_anuncio(pantalla, self.app.fuentes, tema, a)
