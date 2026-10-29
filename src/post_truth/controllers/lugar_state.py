"""Interior de un lugar (E en la calle entra siempre aqui). Al entrar se encuentra sola la evidencia del lugar;
adentro se elige: ver la noticia (si es aqui), jugar el minijuego del lugar o volver a la calle. El dia sigue."""
import pygame

from post_truth.controllers.base_state import BaseState
from post_truth.models import minijuego as mj
from post_truth.sesion import FIN, FIN_DIA
from post_truth.views.componentes import Boton
from post_truth.views.hud import DatosHud
from post_truth.views.lugar_view import dibujar_lugar, rect_boton

TECLAS = (pygame.K_1, pygame.K_2, pygame.K_3)


class LugarState(BaseState):
    def al_entrar(self) -> None:
        s = self.app.partida
        self.t = 0.0
        self.zona = s.jugador_actual.zona
        evidencia = s.buscar_evidencia(s.jugador_actual.id)
        self.tarjetas: list[tuple[str, str, str]] = []
        if evidencia is not None:
            self.tarjetas.append(("Encontraste evidencia", f"{evidencia.titulo}: {evidencia.hallazgo}", "bueno"))
        if self.zona == s.zona_noticia:
            self.tarjetas.append(("La noticia es aqui", s.arbol.event.title, "crisis" if s.reloj_activo else "info"))
        if not self.tarjetas:
            self.tarjetas.append(("Nada nuevo por aqui", "Aqui no hay nada de la noticia de hoy.", "info"))
        acciones = []
        if self.zona == s.zona_noticia and getattr(s, "en_red", False) and not s.es_mi_turno:
            self.tarjetas.insert(0, (f"Turno de {s.nombre(s.de_turno.id)}",
                                     "Solo quien tiene el turno decide la noticia; tu puedes jugar o defender la red.",
                                     "info"))
        elif self.zona == s.zona_noticia:
            acciones.append(("Ver la noticia", self._noticia))
        juego = s.minijuego_en(self.zona)
        if juego is not None:
            acciones.append((f"Jugar {mj.REGISTRO[juego].nombre}", self._minijuego))
        acciones.append(("Volver a la calle", self._volver))
        self.botones = [Boton(rect_boton(i), f"{i + 1}. {texto}", accion, atajo=TECLAS[i])
                        for i, (texto, accion) in enumerate(acciones)]

    @property
    def opciones(self) -> list[str]:
        return [b.texto.split(". ", 1)[1] for b in self.botones]

    def _noticia(self) -> None:
        self.app.estados.cambiar("escena", fundido=True)

    def _minijuego(self) -> None:
        if self.app.partida.iniciar_minijuego(self.zona) is not None:
            self.app.estados.cambiar("minijuego", fundido=True)

    def _volver(self) -> None:
        self.app.estados.cambiar("mundo", fundido=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._volver()
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e):
            self.botones[0].al_hacer_clic()
            return
        for b in self.botones:
            if b.handle_event(event):
                break

    def update(self, dt: float) -> None:
        self.t += dt
        s = self.app.partida
        vencida = s.transcurrir(dt)   # adentro el dia sigue corriendo
        if vencida is not None:
            self.app.estados.cambiar("escena", fundido=True)
        elif s.novedad == "crisis":   # la calle la anuncia y abre el telefono
            self.app.estados.cambiar("mundo", fundido=True)
        elif s.fase in (FIN_DIA, FIN):
            self.app.estados.cambiar("resumen", fundido=True)

    def datos_hud(self) -> DatosHud:
        s = self.app.partida
        return DatosHud(s.ciudad.as_display_rows(), s.jugador_actual.credibilidad, origen=id(s.ciudad))

    def draw(self, pantalla: pygame.Surface) -> None:
        nombre = self.app.partida.mapa.zona(self.zona).nombre if self.zona in self.app.partida.mapa else self.zona
        dibujar_lugar(pantalla, self.app.fuentes, self.app.temas.actual, self.zona, nombre, self.tarjetas,
                      self.botones, self.t)
