"""Tabla de puntajes local (para ferias): los mejores puntajes con sus iniciales, en un JSON fuera del repositorio.
Si el archivo no se puede leer o escribir, el juego sigue sin tabla."""
from __future__ import annotations

import json
import os
from pathlib import Path

MAXIMO = 10   # cuantos se guardan


def ruta() -> Path:
    return Path(os.environ.get("POSTTRUTH_PUNTAJES") or Path.home() / ".post_truth_puntajes.json")


def cargar() -> list[dict]:
    """[{nombre, puntos, medalla}] de mayor a menor; vacia si no hay archivo o esta dañado."""
    try:
        datos = json.loads(ruta().read_text(encoding="utf-8"))
        return sorted(({"nombre": str(d["nombre"])[:3], "puntos": int(d["puntos"]), "medalla": str(d.get("medalla", ""))}
                       for d in datos), key=lambda d: -d["puntos"])[:MAXIMO]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def agregar(nombre: str, puntos: int, medalla: str) -> list[dict]:
    """Anota el puntaje y devuelve la tabla nueva (los empates conservan el orden de llegada)."""
    tabla = sorted(cargar() + [{"nombre": nombre.upper()[:3], "puntos": int(puntos), "medalla": medalla}],
                   key=lambda d: -d["puntos"])[:MAXIMO]
    try:
        ruta().write_text(json.dumps(tabla), encoding="utf-8")
    except OSError:
        pass   # disco de solo lectura: la tabla vale por esta vez
    return tabla
