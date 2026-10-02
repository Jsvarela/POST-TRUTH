"""Constantes globales de la version Pygame. Sin dependencias de pygame para poder usarse en el Modelo."""
import os
from pathlib import Path

TITULO = "Post & Truth - Alcalde Digital"
FPS = 60

# La interfaz se diseno en 1024 x 640 y se escala de forma UNIFORME con ESCALA: ventana, fuentes, botones,
# paneles y mapa crecen juntos y el diseno no cambia. ESCALA = 1.0 es el tamano original. Se puede ajustar con
# la variable de entorno POSTTRUTH_ESCALA (src/main.py la elige solo segun el alto de la pantalla).
DISENO_ANCHO, DISENO_ALTO = 1024, 640
ESCALA = float(os.environ.get("POSTTRUTH_ESCALA", "1.25"))


def px(n: float) -> int:
    """Convierte una medida del diseno original (1024 x 640) a pixeles reales segun ESCALA."""
    return round(n * ESCALA)


ANCHO, ALTO = px(DISENO_ANCHO), px(DISENO_ALTO)

# data/events.json en la raiz del repo (src/post_truth/config.py -> subir 2 niveles)
RUTA_EVENTOS = Path(__file__).resolve().parents[2] / "data" / "events.json"
# Publicaciones que se juegan en una partida: se sortean entre todas las de events.json (variedad entre partidas)
EVENTOS_POR_PARTIDA = 8
RUTA_GRAFO_SOCIAL = Path(__file__).resolve().parents[2] / "data" / "grafo_social.json"
RUTA_GRAFO_CIUDAD = Path(__file__).resolve().parents[2] / "data" / "grafo_ciudad.json"
RUTA_INTRO = Path(__file__).resolve().parents[2] / "data" / "intro.json"
