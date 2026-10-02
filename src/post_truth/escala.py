"""Eleccion de la escala de la interfaz segun el tamano de la pantalla (sin depender de config).

La interfaz se diseno en 1024 x 640 y `config.ESCALA` la agranda de forma uniforme. En una pantalla grande
conviene la escala maxima (1.25: ventana de 1280 x 800); en una pantalla baja (portatiles de 768 px de alto)
la ventana no cabria, asi que se reduce. `src/main.py` la calcula una vez al arrancar y la deja en la
variable de entorno POSTTRUTH_ESCALA ANTES de importar el resto del juego.
"""
import os

ESCALA_MAXIMA = 1.25   # lo que se ve en pantallas grandes
ESCALA_MINIMA = 1.0    # el tamano original del diseno
ALTO_DISENO = 640
MARGEN_VERTICAL = 110  # alto reservado para la barra de titulo y la barra de tareas


def escala_para_pantalla(alto_pantalla: int) -> float:
    """Escala (entre 1.0 y 1.25, en pasos de 0.05) con la que la ventana cabe en una pantalla de `alto_pantalla` px.
    Si no se conoce el alto (0 o negativo) devuelve la escala maxima."""
    if alto_pantalla <= 0:
        return ESCALA_MAXIMA
    cabe = (alto_pantalla - MARGEN_VERTICAL) / ALTO_DISENO
    return round(max(ESCALA_MINIMA, min(ESCALA_MAXIMA, cabe)) * 20) / 20


def fijar_escala_inicial() -> float:
    """Deja POSTTRUTH_ESCALA en el entorno (si el usuario no la fijo ya) y devuelve la escala efectiva."""
    if "POSTTRUTH_ESCALA" in os.environ:
        return float(os.environ["POSTTRUTH_ESCALA"])
    escala = escala_para_pantalla(_alto_del_escritorio())
    os.environ["POSTTRUTH_ESCALA"] = str(escala)
    return escala


def _alto_del_escritorio() -> int:
    """Alto en pixeles del escritorio, o 0 si no se puede saber.

    Si el video de pygame ya esta iniciado se lee tal cual (iniciarlo y cerrarlo de nuevo borraria la cola de
    eventos y los temporizadores de quien ya lo esta usando). Si no, se inicia solo el tiempo de la lectura."""
    try:
        import pygame
    except ImportError:
        return 0
    try:
        if pygame.display.get_init():
            return pygame.display.Info().current_h
        pygame.display.init()
        try:
            return pygame.display.Info().current_h
        finally:
            pygame.display.quit()
    except Exception:  # sin pantalla: se usa la escala por defecto
        return 0
