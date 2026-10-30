"""Controlador del menu principal: botones con teclado o raton, opciones (tema, volumen, tiempo extendido) y los
atajos de siempre (Enter jugar, R multijugador, A ayuda, I intro, M mundo, T tema, X tiempo extendido, ESC salir)."""
import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.views import sonido
from post_truth.views.componentes import Boton
from post_truth.views.menu_view import dibujar_menu, rect_boton, rect_opcion

NOMBRES_TEMA = {"normal": "Normal", "alto_contraste": "Alto contraste", "daltonismo": "Daltonismo"}


class MenuState(BaseState):
    def __init__(self, app) -> None:
        super().__init__(app)
        acciones = [("Jugar", self._jugar), ("Multijugador", self._multijugador), ("Ayuda", self._ayuda),
                    ("Introduccion", self._intro), ("Opciones", self._opciones), ("Salir", self._salir)]
        self.botones = [Boton(rect_boton(i), texto, accion) for i, (texto, accion) in enumerate(acciones)]
        self.al_entrar()

    def al_entrar(self) -> None:
        self.t, self.foco, self.en_opciones, self.fila = 0.0, 0, False, 0

    # --- acciones ------------------------------------------------------------------------------------
    def _jugar(self) -> None:
        if self.app.intro_vista:
            self.app.estados.cambiar("seleccion")
        else:   # la primera vez, la apertura de la campana (L4)
            self.app.estados.estado("cinematica").reproducir("campana", "seleccion", self._intro_vista)

    def _intro_vista(self) -> None:
        self.app.intro_vista = True

    def _ayuda(self) -> None:
        self.app.estados.ayuda.abrir("objetivo")

    def _multijugador(self) -> None:
        self.app.estados.cambiar("conectar")

    def _intro(self) -> None:
        self.app.estados.estado("cinematica").reproducir("campana", "menu", self._intro_vista)

    def _opciones(self) -> None:
        self.en_opciones, self.fila = True, 0

    def _salir(self) -> None:
        self.app.corriendo = False

    def opciones(self) -> list[tuple[str, str]]:
        app = self.app
        return [("Tema", NOMBRES_TEMA.get(app.temas.nombre, app.temas.nombre)),
                ("Volumen", f"{round(app.volumen * 100)}%"),
                ("Tiempo extendido", "Si" if app.tiempo_extendido else "No"),
                ("Volumen de los pasos", f"{round(sonido.PASOS[0] * 100)}%"),
                ("Silencio", "Si" if sonido.SILENCIO[0] else "No"),
                ("Mensajes guia", "Si" if app.guias else "No"),
                ("Avance manual", "Si" if app.avance_manual else "No"),
                ("Cerrar", "")]

    def _cambiar_opcion(self, paso: int) -> None:
        app = self.app
        if self.fila == 0:
            if paso > 0:
                app.temas.siguiente()
            else:
                app.temas.anterior()
        elif self.fila == 1:
            app.volumen = max(0.0, min(1.0, round(app.volumen + 0.1 * paso, 1)))
            sonido.VOLUMEN[0] = app.volumen
        elif self.fila == 2:
            app.tiempo_extendido = not app.tiempo_extendido
        elif self.fila == 3:
            sonido.PASOS[0] = max(0.0, min(1.0, round(sonido.PASOS[0] + 0.1 * paso, 1)))
        elif self.fila == 4:
            sonido.SILENCIO[0] = not sonido.SILENCIO[0]
        elif self.fila == 5:
            app.guias = not app.guias
        elif self.fila == 6:
            app.avance_manual = not app.avance_manual
        if self.fila in (1, 3):   # se escucha como queda
            sonido.tocar("acierto" if self.fila == 1 else "pasos")

    # --- eventos -------------------------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.en_opciones:
            self._evento_opciones(event)
            return
        if event.type == pygame.KEYDOWN:
            atajos = {pygame.K_i: self._intro, pygame.K_m: self._mundo, pygame.K_o: self._opciones,
                      pygame.K_r: self._multijugador, pygame.K_a: self._ayuda, pygame.K_ESCAPE: self._salir}
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.botones[self.foco].al_hacer_clic()
            elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                paso = 1 if event.key in (pygame.K_DOWN, pygame.K_s) else -1
                self.foco = (self.foco + paso) % len(self.botones)
            elif event.key == pygame.K_t:
                self.app.temas.siguiente()
            elif event.key == pygame.K_x:
                self.app.tiempo_extendido = not self.app.tiempo_extendido
            elif event.key == pygame.K_c:   # cinematica de prueba (L3)
                self.app.estados.estado("cinematica").reproducir("prueba", "menu")
            elif event.key in atajos:
                atajos[event.key]()
            return
        for i, b in enumerate(self.botones):
            if event.type == pygame.MOUSEMOTION and b.rect.collidepoint(event.pos):
                self.foco = i
            if b.handle_event(event):
                break

    def _mundo(self) -> None:
        self.app.partida = None
        self.app.estados.cambiar("mundo")

    def _evento_opciones(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            ultima = len(self.opciones()) - 1
            if event.key == pygame.K_ESCAPE or (event.key in (pygame.K_RETURN, pygame.K_SPACE) and self.fila == ultima):
                self.en_opciones = False
            elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                paso = 1 if event.key in (pygame.K_DOWN, pygame.K_s) else -1
                self.fila = (self.fila + paso) % (ultima + 1)
            elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_SPACE):
                self._cambiar_opcion(-1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            ultima = len(self.opciones()) - 1
            for i in range(ultima + 1):
                if rect_opcion(i).collidepoint(event.pos):
                    self.fila = i
                    if i == ultima:
                        self.en_opciones = False
                    else:
                        self._cambiar_opcion(1)

    def update(self, dt: float) -> None:
        self.t += dt
        for i, b in enumerate(self.botones):
            b.foco = i == self.foco

    def draw(self, pantalla: pygame.Surface) -> None:
        dibujar_menu(pantalla, self.app.fuentes, self.app.temas.actual, self.botones, self.t,
                     self.opciones() if self.en_opciones else None, self.fila)
