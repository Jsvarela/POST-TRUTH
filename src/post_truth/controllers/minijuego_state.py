"""Pantalla que aloja cualquier minijuego de un lugar: pasa el teclado al modelo y aplica su resultado."""
import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.models import minijuego as mj
from post_truth.models.tutorial import Tutorial, tiene_tutorial
from post_truth.views import sonido
from post_truth.views.anuncio_view import Anuncio, dibujar_anuncio
from post_truth.views import hud
from post_truth.views.hud import DatosHud
from post_truth.views.minijuego_view import dibujar_minijuego, dibujar_tutorial, pantalla_a_mitin

TECLAS = {pygame.K_1: "1", pygame.K_2: "2", pygame.K_3: "3", pygame.K_4: "4", pygame.K_SPACE: "espacio",
          pygame.K_LEFT: "izq", pygame.K_a: "izq", pygame.K_RIGHT: "der", pygame.K_d: "der",
          pygame.K_UP: "arriba", pygame.K_w: "arriba", pygame.K_DOWN: "abajo", pygame.K_s: "abajo", pygame.K_e: "hablar"}


class MinijuegoState(BaseState):
    def al_entrar(self) -> None:
        s = self.app.partida
        # L6: en red, quien no tiene el turno mira el minijuego del de turno (el servidor reenvia su progreso)
        self.espectador = getattr(s, "en_red", False) and s.minijuego is None
        self.minijuego = self._vivo() if self.espectador else s.minijuego   # lo creo sesion.iniciar_minijuego
        self.resultado = None
        self.pausado = False
        self.tutorial: Tutorial | None = None
        self._t_progreso = 0.0
        if self.minijuego is None:   # no hay nada que ver (ya termino): de vuelta a la calle
            self.app.estados.cambiar("mundo", fundido=True)
            self.toast = None
            return
        if self.espectador:
            self.toast = Anuncio(f"Juega {s.nombre(self.minijuego.contexto.jugador)}", "Lo estas viendo. ESC: volver.",
                                 "info", grande=False, duracion=4.0)
            return
        vistos = getattr(self.app, "tutoriales_vistos", set())
        if tiene_tutorial(self.minijuego.id) and self.minijuego.id not in vistos:   # la primera vez: como se juega
            self.abrir_tutorial()
        self.toast = None   # sin guia aparte: la explicacion del minijuego ya esta en pantalla (y la tapaba)

    def _vivo(self):
        v = getattr(self.app.partida, "minijuego_vivo", None)
        return mj.desde_dict(v["estado"]) if v else None

    def abrir_tutorial(self) -> None:
        self.tutorial = Tutorial(self.minijuego.id, self.minijuego.contexto)

    def _raton(self, event: pygame.event.Event, juego) -> None:
        """Los minijuegos de punteria (el mitin): el raton mueve la mira y el clic dispara."""
        if not getattr(juego, "usa_raton", False):
            return
        if event.type == pygame.MOUSEMOTION and (p := pantalla_a_mitin(event.pos)) is not None:
            juego.accion(f"apuntar:{p[0]:.4f}:{p[1]:.4f}")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            juego.accion("disparo")

    def _tutorial(self, event: pygame.event.Event) -> None:
        t = self.tutorial
        if t.fase in ("practica", "listo"):
            self._raton(event, t.juego)
        if event.type == pygame.KEYUP and event.key in TECLAS:
            t.accion("-" + TECLAS[event.key])
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            t.avanzar()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            t.fase = "fin"
        elif event.type == pygame.KEYDOWN and event.key in TECLAS:
            t.accion(TECLAS[event.key])
        if t.fase == "fin":
            self.tutorial = None
            self.app.tutoriales_vistos = getattr(self.app, "tutoriales_vistos", set()) | {self.minijuego.id}

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.espectador:   # mirando: solo se puede volver
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.app.estados.cambiar("mundo", fundido=True)
            return
        if self.tutorial is not None:
            self._tutorial(event)
            return
        if self.resultado is None and not self.pausado:
            self._raton(event, self.minijuego)
        if event.type == pygame.KEYUP and event.key in TECLAS and self.resultado is None:
            self.minijuego.accion("-" + TECLAS[event.key])   # soltar: los que se mantienen (moverse, E, girar)
            return
        if event.type != pygame.KEYDOWN:
            return
        if self.resultado is not None:
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                self.app.estados.cambiar("mundo", fundido=True)
        elif event.key == pygame.K_p:
            self.pausado = not self.pausado   # accesibilidad: el reloj del minijuego se detiene
        elif event.key == pygame.K_c and tiene_tutorial(self.minijuego.id):   # volver a ver como se juega
            self.abrir_tutorial()
        elif not self.pausado and event.key in TECLAS:
            self.minijuego.accion(TECLAS[event.key])
            self._sonar()

    def update(self, dt: float) -> None:
        if self.toast is not None:
            self.toast.avanzar(dt)
            self.toast = None if self.toast.terminado else self.toast
        if self.espectador:
            vivo = self._vivo()
            if vivo is None:   # el de turno termino
                self.app.estados.cambiar("mundo", fundido=True)
            else:
                self.minijuego = vivo
            return
        if self.tutorial is not None:   # la demo y la practica no gastan el dia ni tocan la partida
            self.tutorial.update(dt)
            return
        if self.resultado is not None or self.pausado:
            return
        self.minijuego.update(dt)
        self.app.partida.transcurrir(dt)   # jugar cuesta tiempo del dia (la pausa lo detiene todo)
        self._t_progreso += dt
        if getattr(self.app.partida, "en_red", False) and self._t_progreso >= 0.2:   # que los demas lo vean
            self._t_progreso = 0.0
            self.app.partida.enviar_progreso()
        self._sonar()
        if self.minijuego.terminado:
            self.resultado = self.app.partida.terminar_minijuego()
            sonido.tocar("acierto" if self.resultado.credibilidad >= 0 else "error")

    def _sonar(self) -> None:
        """Lo que acerto o fallo el jugador desde el ultimo cuadro (cada uno tiene ademas su aviso en pantalla)."""
        for eco in self.minijuego.ecos:
            sonido.tocar(eco)
        self.minijuego.ecos.clear()

    def datos_hud(self) -> DatosHud:
        s = self.app.partida
        return hud.minimo(s, s.jugador(self.minijuego.contexto.jugador).credibilidad, "barra")

    def draw(self, pantalla: pygame.Surface) -> None:
        if self.tutorial is not None:
            dibujar_tutorial(pantalla, self.app.fuentes, self.app.temas.actual, self.tutorial)
            return
        s = self.app.partida
        dibujar_minijuego(pantalla, self.app.fuentes, self.app.temas.actual, self.minijuego, s.ciudad.as_display_rows(),
                          s.jugador(self.minijuego.contexto.jugador).credibilidad, self.resultado, self.pausado)
        if self.toast is not None:
            dibujar_anuncio(pantalla, self.app.fuentes, self.app.temas.actual, self.toast)
