"""Eleccion de la escala de la interfaz segun el tamano de la pantalla."""
import os

ESCALA_MAXIMA = 1.25
ESCALA_MINIMA = 1.0
ALTO_DISENO = 640
MARGEN_VERTICAL = 110


def escala_para_pantalla(alto_pantalla: int) -> float:
    """Escala con la que la ventana cabe en una pantalla de `alto_pantalla` px."""
    if alto_pantalla <= 0:
        return ESCALA_MAXIMA
    cabe = (alto_pantalla - MARGEN_VERTICAL) / ALTO_DISENO
    return round(max(ESCALA_MINIMA, min(ESCALA_MAXIMA, cabe)) * 20) / 20


def fijar_escala_inicial() -> float:
    """Deja POSTTRUTH_ESCALA en el entorno y devuelve la escala efectiva."""
    if "POSTTRUTH_ESCALA" in os.environ:
        return float(os.environ["POSTTRUTH_ESCALA"])
    escala = escala_para_pantalla(_alto_del_escritorio())
    os.environ["POSTTRUTH_ESCALA"] = str(escala)
    return escala


def _alto_del_escritorio() -> int:
    """Alto en pixeles del escritorio, o 0 si no se puede saber."""
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
    except Exception:
        return 0
