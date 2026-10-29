"""Game loop de Pygame + StateManager."""
import pygame

from post_truth.config import FLUJO, ANCHO, ALTO, FPS, TITULO, px
from post_truth.controllers.ayuda import Ayuda
from post_truth.controllers.escena_state import EscenaState
from post_truth.controllers.fase_state import FaseState
from post_truth.controllers.intro_state import IntroState
from post_truth.controllers.investigacion_state import InvestigacionState
from post_truth.controllers.lugar_state import LugarState
from post_truth.controllers.menu_state import MenuState
from post_truth.controllers.minijuego_state import MinijuegoState
from post_truth.controllers.mundo_state import MundoState
from post_truth.controllers.red_state import ConectarState, SalaState
from post_truth.controllers.resultado_state import ResultadoState
from post_truth.controllers.resumen_state import ResumenState
from post_truth.controllers.seleccion_state import SeleccionState
from post_truth.controllers.state_manager import StateManager
from post_truth.controllers.sustentacion import Sustentacion
from post_truth.controllers.telefono_state import TelefonoState
from post_truth.models.personaje import Personaje
from post_truth.views.componentes import Fuentes, fuente
from post_truth.views.efectos import CapaRetro
from post_truth.views.theme import GestorTemas


class App:
    """Contenedor de recursos compartidos entre estados."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(TITULO)
        self.pantalla = pygame.display.set_mode((ANCHO, ALTO))
        self.reloj = pygame.time.Clock()
        self.fuente = fuente("PixelifySans.ttf", 20)
        self.fuentes = Fuentes.crear()
        self.temas = GestorTemas()
        self.corriendo = True
        self.intro_vista = False
        self.personaje: Personaje | None = None
        self.personajes: list[Personaje] = []   # todos los jugadores, cada uno con un rol distinto
        self.flujo = FLUJO
        self.partida = None
        self.red = None                 # ConexionRed mientras se esta en la sala (multijugador)
        self.tiempo_extendido = False   # accesibilidad: dias y relojes x1.5 (X en el menu)
        self.volumen = 0.7              # de 0 a 1 (Opciones del menu)
        self.guias = True               # mensajes guia de la primera vez (Opciones del menu)
        self.guias_vistas: set[str] = set()
        self.estados = StateManager(lambda: self.temas.actual.fondo)
        self.estados.capa = CapaRetro(self.fuentes, self.temas)
        self.estados.sustentacion = Sustentacion(self)
        self.estados.ayuda = Ayuda(self)
        self.estados.registrar("menu", MenuState(self))
        self.estados.registrar("intro", IntroState(self))
        self.estados.registrar("seleccion", SeleccionState(self))
        self.estados.registrar("escena", EscenaState(self))
        self.estados.registrar("mundo", MundoState(self))
        self.estados.registrar("resumen", ResumenState(self))
        self.estados.registrar("minijuego", MinijuegoState(self))
        self.estados.registrar("resultado", ResultadoState(self))
        self.estados.registrar("telefono", TelefonoState(self))
        self.estados.registrar("investigacion", InvestigacionState(self))
        self.estados.registrar("fase", FaseState(self))
        self.estados.registrar("lugar", LugarState(self))
        self.estados.registrar("conectar", ConectarState(self))
        self.estados.registrar("sala", SalaState(self))
        self.estados.cambiar("menu")

    def run(self) -> None:
        while self.corriendo:
            dt = self.reloj.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.corriendo = False
                self.estados.handle_event(event)
            self.atender_red(dt)
            self.estados.update(dt)
            self.estados.draw(self.pantalla)
            pygame.display.flip()
        pygame.quit()

    def atender_red(self, dt: float) -> None:
        """Multijugador: la sesion espejo lee la cola de la red (sin esperar). Si se cae la conexion, a conectar."""
        s = self.partida
        if not getattr(s, "en_red", False):
            return
        s.tick(dt)
        if s.conexion.cerrada and s.fin is None:
            self.salir_de_red(f"Se perdio la conexion: {s.conexion.motivo}")

    def salir_de_red(self, aviso: str | None = None) -> None:
        if getattr(self.partida, "en_red", False):
            self.partida.conexion.cerrar()
        self.partida, self.red = None, None
        if aviso:
            self.estados.estado("conectar").aviso = (aviso, "malo")
            self.estados.cambiar("conectar")
