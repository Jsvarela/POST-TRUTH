"""Estado de animacion de un personaje del mundo caminable. Logica pura (sin pygame) y serializable.

Los NOMBRES de animacion son el contrato con el arte: la vista de formas los dibuja y una hoja de sprites PNG
(etapa M9) tendra una fila por nombre, en el orden de ANIMACIONES, y una columna por cuadro (CUADROS[estado]).
El cuadro depende solo del tiempo acumulado, asi que la animacion se ve igual a 30 y a 60 FPS.
"""
from __future__ import annotations

from dataclasses import dataclass

ESTADOS = ("idle", "caminar")
DIRECCIONES = ("abajo", "arriba", "izquierda", "derecha")
ANIMACIONES = tuple(f"{e}_{d}" for e in ESTADOS for d in DIRECCIONES)   # idle_abajo ... caminar_derecha
CUADROS = {"idle": 2, "caminar": 4}       # cuadros por animacion (columnas de la hoja de sprites)
FPS_ANIM = {"idle": 2, "caminar": 8}      # cuadros por segundo de cada estado
UMBRAL_MOVIDO = 1e-6                       # pixeles: por debajo se considera que no se movio (contra una pared)


@dataclass
class AnimacionPersonaje:
    direccion: str = "abajo"
    estado: str = "idle"
    t: float = 0.0          # segundos desde que empezo el estado actual

    def __post_init__(self) -> None:
        if self.direccion not in DIRECCIONES or self.estado not in ESTADOS:
            raise ValueError(f"Animacion invalida: {self.estado}_{self.direccion}")

    @property
    def nombre(self) -> str:
        return f"{self.estado}_{self.direccion}"

    @property
    def cuadro(self) -> int:
        return int(self.t * FPS_ANIM[self.estado]) % CUADROS[self.estado]

    def actualizar(self, dir_x: float, dir_y: float, movido: float, dt: float) -> None:
        """La DIRECCION sale de las teclas (gira aunque roce una pared); el ESTADO, de cuanto se movio de verdad."""
        if dir_x or dir_y:
            self.direccion = _direccion(dir_x, dir_y, self.direccion)
        estado = "caminar" if movido > UMBRAL_MOVIDO else "idle"
        if estado != self.estado:
            self.estado, self.t = estado, 0.0   # cada estado empieza en su primer cuadro
        self.t += dt

    def to_dict(self) -> dict:
        return {"direccion": self.direccion, "estado": self.estado, "t": self.t}

    @classmethod
    def from_dict(cls, d: dict) -> "AnimacionPersonaje":
        return cls(d["direccion"], d["estado"], float(d.get("t", 0.0)))


def _direccion(dx: float, dy: float, actual: str) -> str:
    """Manda el eje con mas componente. En diagonal exacta se conserva la actual si es una de las dos; si no,
    gana la horizontal."""
    horizontal = "derecha" if dx > 0 else "izquierda"
    vertical = "abajo" if dy > 0 else "arriba"
    if abs(dx) > abs(dy):
        return horizontal
    if abs(dy) > abs(dx):
        return vertical
    return actual if actual in (horizontal, vertical) else horizontal
