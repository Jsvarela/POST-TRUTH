"""Sonidos hechos con codigo (tonos generados, sin archivos). Cada sonido tiene un aviso visual equivalente
(docs/inclusividad.md), asi que si no hay audio, o el jugador lo apaga, no se pierde informacion: no suena y el
juego sigue igual. Ninguna funcion de aqui lanza errores."""
import math
import os
from array import array

import pygame

VOLUMEN = [0.7]      # general; lo cambia el menu de opciones (listas: se comparten sin reimportar)
PASOS = [0.4]        # los pasos aparte: es el sonido que mas se repite
SILENCIO = [False]

# nombre -> (frecuencias en orden, segundos por tono, volumen relativo)
SONIDOS = {
    "pasos": ((180,), 0.04, 0.5),
    "alerta": ((880, 660), 0.12, 1.0),       # algo se volvio viral: dos tonos que bajan
    "fase": ((440, 554, 659), 0.12, 0.9),    # tres notas que suben (Hz, no es un color)
    "acierto": ((660, 880), 0.08, 0.8),
    "error": ((196,), 0.18, 0.8),
}

_cache: dict[str, pygame.mixer.Sound] = {}
_sin_audio = [False]   # el mixer fallo una vez: no se vuelve a intentar en cada cuadro
ultimo: list[str] = []   # lo que se pidio tocar (las pruebas lo leen; sirve igual sin audio)


def _tonos(frecuencias: tuple[int, ...], duracion: float) -> pygame.mixer.Sound:
    freq, _, canales = pygame.mixer.get_init()
    muestras = array("h")
    n = int(freq * duracion)
    for f in frecuencias:
        for i in range(n):
            volumen = 0.3 * min(1.0, (n - i) / (0.3 * n))   # se apaga al final de cada tono (sin chasquido)
            muestras.extend([int(32767 * volumen * math.sin(2 * math.pi * f * i / freq))] * canales)
    return pygame.mixer.Sound(buffer=muestras.tobytes())


def volumen(nombre: str) -> float:
    """0..1 con el que sonaria `nombre` (0: no suena)."""
    if SILENCIO[0] or nombre not in SONIDOS:
        return 0.0
    return VOLUMEN[0] * SONIDOS[nombre][2] * (PASOS[0] if nombre == "pasos" else 1.0)


def tocar(nombre: str) -> None:
    ultimo[:] = (ultimo + [nombre])[-20:]
    v = volumen(nombre)
    if v <= 0 or _sin_audio[0] or os.environ.get("SDL_VIDEODRIVER") == "dummy":   # sin ventana (pruebas): mudo
        return
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        if nombre not in _cache:
            frecuencias, duracion, _ = SONIDOS[nombre]
            _cache[nombre] = _tonos(frecuencias, duracion)
        _cache[nombre].set_volume(v)
        _cache[nombre].play()
    except (pygame.error, OSError, ValueError, TypeError):   # sin tarjeta de sonido o mixer roto: mudo y sigue
        _sin_audio[0] = True


def alerta() -> None:
    tocar("alerta")
