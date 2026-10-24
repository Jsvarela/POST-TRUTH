"""Sonidos hechos con codigo (sin archivos). Cada sonido tiene un aviso visual equivalente: si no hay audio, no
suena y el juego sigue igual."""
import math
import os
from array import array

import pygame

_cache: dict[str, pygame.mixer.Sound] = {}


def _tonos(frecuencias: tuple[int, ...], duracion: float) -> pygame.mixer.Sound:
    freq, _, canales = pygame.mixer.get_init()
    muestras = array("h")
    n = int(freq * duracion)
    for f in frecuencias:
        for i in range(n):
            volumen = 0.3 * min(1.0, (n - i) / (0.3 * n))   # se apaga al final de cada tono (sin chasquido)
            muestras.extend([int(32767 * volumen * math.sin(2 * math.pi * f * i / freq))] * canales)
    return pygame.mixer.Sound(buffer=muestras.tobytes())


def alerta() -> None:
    """Dos tonos que bajan: algo se volvio viral."""
    if os.environ.get("SDL_VIDEODRIVER") == "dummy":   # sin ventana (pruebas): sin sonido
        return
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        if "alerta" not in _cache:
            _cache["alerta"] = _tonos((880, 660), 0.12)
        _cache["alerta"].play()
    except pygame.error:
        pass
