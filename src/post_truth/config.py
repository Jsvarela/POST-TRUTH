"""Constantes globales de la version Pygame."""
import os
from pathlib import Path

TITULO = "Post & Truth - Alcalde Digital"
FPS = 60

DISENO_ANCHO, DISENO_ALTO = 1024, 640
ESCALA = float(os.environ.get("POSTTRUTH_ESCALA", "1.25"))


def px(n: float) -> int:
    """Convierte una medida del diseno original a pixeles reales segun ESCALA."""
    return round(n * ESCALA)


ANCHO, ALTO = px(DISENO_ANCHO), px(DISENO_ALTO)

RUTA_EVENTOS = Path(__file__).resolve().parents[2] / "data" / "events.json"
EVENTOS_POR_PARTIDA = 8
DIAS_CAMPANA = 4          # dias de la campana, uno por fase de data/fases.json (2 publicaciones + 1 crisis por dia)
RUTA_GRAFO_SOCIAL = Path(__file__).resolve().parents[2] / "data" / "grafo_social.json"
RUTA_GRAFO_CIUDAD = Path(__file__).resolve().parents[2] / "data" / "grafo_ciudad.json"
RUTA_INTRO = Path(__file__).resolve().parents[2] / "data" / "intro.json"
FLUJO = os.environ.get("POSTTRUTH_FLUJO", "mundo")
if FLUJO not in ("mundo", "escena"):
    raise ValueError(f"POSTTRUTH_FLUJO debe ser 'mundo' o 'escena', no {FLUJO!r}")
RUTA_MINIJUEGOS = Path(__file__).resolve().parents[2] / "data" / "minijuegos.json"
RUTA_MAPA = Path(__file__).resolve().parents[2] / "data" / "mapa.json"
RUTA_FASES = Path(__file__).resolve().parents[2] / "data" / "fases.json"
RUTA_POSTS = Path(__file__).resolve().parents[2] / "data" / "posts.json"
RUTA_CHAT = Path(__file__).resolve().parents[2] / "data" / "chat_colegio.json"
RUTA_MITIN = Path(__file__).resolve().parents[2] / "data" / "mitin.json"
RUTA_TESTIGOS = Path(__file__).resolve().parents[2] / "data" / "testigos.json"
RUTA_RUEDA = Path(__file__).resolve().parents[2] / "data" / "rueda_prensa.json"
RUTA_BARRIO = Path(__file__).resolve().parents[2] / "data" / "barrio.json"
RUTA_PERSUASION = Path(__file__).resolve().parents[2] / "data" / "persuasion.json"
RUTA_TRANSEUNTES = Path(__file__).resolve().parents[2] / "data" / "transeuntes.json"
