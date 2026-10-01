"""Constantes globales de la version Pygame. Sin dependencias de pygame para poder usarse en el Modelo."""
from pathlib import Path

TITULO = "Post & Truth - Alcalde Digital"
ANCHO, ALTO = 1024, 640
FPS = 60

# data/events.json en la raiz del repo (src/post_truth/config.py -> subir 2 niveles)
RUTA_EVENTOS = Path(__file__).resolve().parents[2] / "data" / "events.json"
