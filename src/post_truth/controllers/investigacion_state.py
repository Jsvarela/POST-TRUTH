"""Ventana de investigacion (I desde la noticia): lupa sobre la publicacion, interrogatorio de testigos y conclusion.
El reloj de la publicacion sigue corriendo mientras se investiga."""
import pygame

from post_truth.config import px
from post_truth.models import roles
from post_truth.controllers.base_state import BaseState
from post_truth.sesion import FIN_DIA, PartidaSesion
from post_truth.structures.arbol_dialogo import NodoDialogo
from post_truth.views.anuncio_view import Anuncio, dibujar_anuncio
from post_truth.views.investigacion_view import (PESTANAS, RADIO_LUPA, RECT_TARJETA, VEREDICTOS, VistaInvestigacion,
                                                 dibujar_investigacion, rect_opcion, rect_pestana, rect_testigo,
                                                 rect_veredicto, zonas_con_senal)

VELOCIDAD_LUPA = px(420)
FLECHAS = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}
TECLAS_VEREDICTO = {pygame.K_f: "falsa", pygame.K_v: "verdadera", pygame.K_n: "no_concluyente"}


class InvestigacionState(BaseState):
    def al_entrar(self) -> None:
        self.pestana, self.t = 0, 0.0
        self.lupa = RECT_TARJETA.center
        self.bajo_lupa, self.mantenido = None, 0.0
        self.presionadas: set[int] = set()
        self.elegido = 0
        self.raiz: NodoDialogo | None = None
        self.camino: list[int] = []
        self.charla: list[tuple[str, str]] = []
        self.toast: Anuncio | None = None

    @property
    def sesion(self) -> PartidaSesion:
        return self.app.estados.estado("escena").sesion

    @property
    def jugador(self) -> str:
        return self.sesion.jugador_actual.id

    def _volver(self) -> None:
        self.app.estados.cambiar("escena", fundido=True)

    # --- lupa ------------------------------------------------------------------------------------
    def _mover_lupa(self, pos: tuple[int, int]) -> None:
        self.lupa = (max(RECT_TARJETA.left, min(RECT_TARJETA.right, round(pos[0]))),
                     max(RECT_TARJETA.top, min(RECT_TARJETA.bottom, round(pos[1]))))

    def _actualizar_lupa(self, dt: float) -> None:
        """Mantener la lupa sobre una senal sin descubrir la revela; moverse a otra zona reinicia la cuenta."""
        inv = self.sesion.jugador_actual.investigacion
        evento = self.sesion.arbol.event
        zona = next((z for z, r in zonas_con_senal(evento).items() if r.collidepoint(self.lupa)), None)
        pista = inv.pista_en(zona) if zona is not None else None
        if pista is None or inv.esta_descubierta(pista.id):
            self.bajo_lupa, self.mantenido = None, 0.0
            return
        if zona is not self.bajo_lupa:
            self.bajo_lupa, self.mantenido = zona, 0.0
        self.mantenido += dt
        if self.mantenido >= roles.mantener_lupa(self.sesion.jugador_actual.rol):
            self.sesion.investigar(self.jugador, pista)
            tipo = {"falsa": "malo", "verdadera": "bueno"}.get(pista.senal.value, "info")
            self.toast = Anuncio(pista.titulo, pista.hallazgo, tipo, grande=False, duracion=3.5)
            self.bajo_lupa, self.mantenido = None, 0.0

    # --- testigos ----------------------------------------------------------------------------------
    def _hablar(self) -> None:
        testigos = self.sesion.testigos()
        if not testigos:
            return
        t = testigos[self.elegido % len(testigos)]
        if not self.sesion.puede_hablar(t):
            self.toast = Anuncio(t.nombre, f"Esta en {t.lugar.capitalize()}: ve alla primero.", "info", grande=False)
            return
        self.raiz, self.camino = self.sesion.interrogatorio(t), []
        self.charla = [(t.nombre, self.raiz.texto)]

    def _preguntar(self, i: int) -> None:
        nodo = self.raiz.seguir(self.camino) if self.raiz is not None else None
        if nodo is None or i >= len(nodo.opciones):
            return
        opcion = nodo.opciones[i]
        self.charla.append(("Tu", opcion.texto))
        self.camino.append(i)
        if opcion.tipo == "version":
            t = self.sesion.testigos()[self.elegido % len(self.sesion.testigos())]
            self.sesion.anotar_testimonio(self.jugador, t)
        if opcion.hijo is not None:
            self.charla.append((nodo.hablante, opcion.hijo.texto))
        else:
            self.raiz = None

    @property
    def conclusion(self) -> str:
        return self.sesion.jugador_actual.investigacion.como_concluyo

    def _concluir(self, veredicto: str) -> None:
        r = self.sesion.concluir(self.jugador, veredicto)
        if r.ok:
            tipo = "malo" if r.como == "error" else "bueno" if r.como in ("buena", "a_ciegas") else "info"
            self.toast = Anuncio(f"Credibilidad {r.credibilidad:+}", f"Puntos {r.puntos:+}", tipo, grande=False)

    # --- eventos -------------------------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_i):
                self._volver()
            elif event.key == pygame.K_TAB:
                self.pestana = (self.pestana + 1) % len(PESTANAS)
            elif event.key in TECLAS_VEREDICTO and not self.conclusion:
                self._concluir(TECLAS_VEREDICTO[event.key])
            elif self.pestana == 0 and event.key in FLECHAS:
                self.presionadas.add(event.key)
            elif self.pestana == 1:
                self._tecla_testigos(event.key)
        elif event.type == pygame.KEYUP:
            self.presionadas.discard(event.key)
        elif event.type == pygame.MOUSEMOTION and self.pestana == 0:
            self._mover_lupa(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._clic(event.pos)

    def _tecla_testigos(self, key: int) -> None:
        n = len(self.sesion.testigos())
        if key in (pygame.K_UP, pygame.K_DOWN) and self.raiz is None:
            self.elegido = (self.elegido + (1 if key == pygame.K_DOWN else -1)) % max(1, n)
        elif key == pygame.K_RETURN and self.raiz is None:
            self._hablar()
        elif pygame.K_1 <= key <= pygame.K_4:
            self._preguntar(key - pygame.K_1)

    def _clic(self, punto: tuple[int, int]) -> None:
        for i in range(len(PESTANAS)):
            if rect_pestana(i).collidepoint(punto):
                self.pestana = i
                return
        if not self.conclusion:
            for i, (veredicto, _) in enumerate(VEREDICTOS):
                if rect_veredicto(i).collidepoint(punto):
                    self._concluir(veredicto)
                    return
        if self.pestana != 1:
            return
        for i in range(len(self.sesion.testigos())):
            if rect_testigo(i).collidepoint(punto):
                self.elegido = i
                self.raiz = None
                self._hablar()
                return
        nodo = self.raiz.seguir(self.camino) if self.raiz is not None else None
        if nodo is not None:
            for i in range(len(nodo.opciones)):
                if rect_opcion(4 - len(nodo.opciones) + i).collidepoint(punto):
                    self._preguntar(i)
                    return

    def update(self, dt: float) -> None:
        self.t += dt
        if self.toast is not None:
            self.toast.avanzar(dt)
            if self.toast.terminado:
                self.toast = None
        s = self.sesion
        vencida = s.transcurrir(dt)   # investigar cuesta tiempo: el reloj viral y el dia siguen
        if vencida is not None or s.novedad == "crisis" or s.fase == FIN_DIA:
            self._volver()           # la escena muestra lo que paso o manda a la calle
            return
        dx = sum(FLECHAS[k][0] for k in self.presionadas)
        dy = sum(FLECHAS[k][1] for k in self.presionadas)
        if dx or dy:
            self._mover_lupa((self.lupa[0] + dx * VELOCIDAD_LUPA * dt, self.lupa[1] + dy * VELOCIDAD_LUPA * dt))
        if self.pestana == 0:
            self._actualizar_lupa(dt)

    def vista(self) -> VistaInvestigacion:
        s = self.sesion
        nodo = self.raiz.seguir(self.camino) if self.raiz is not None else None
        return VistaInvestigacion(
            s.arbol.event, s.jugador_actual.investigacion, self.pestana, self.lupa, self.mantenido / roles.mantener_lupa(s.jugador_actual.rol),
            [(t, s.puede_hablar(t)) for t in s.testigos()], self.elegido, self.charla,
            [o.texto for o in nodo.opciones] if nodo is not None else [],
            self.conclusion,
            (s.tiempo_restante, s.tiempo_viral_total) if s.reloj_activo else None, self.t,
            round(RADIO_LUPA * roles.lupa(s.jugador_actual.rol)))

    def draw(self, pantalla: pygame.Surface) -> None:
        tema = self.app.temas.actual
        dibujar_investigacion(pantalla, self.app.fuentes, tema, self.vista())
        if self.toast is not None:
            dibujar_anuncio(pantalla, self.app.fuentes, tema, self.toast)
