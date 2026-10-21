"""Modelo: Personaje del jugador."""
from dataclasses import dataclass
from enum import Enum

from post_truth.models.dominio import Role


class Genero(Enum):
    HOMBRE = "Hombre"
    MUJER = "Mujer"


ROL_DESCRIPCION: dict[Role, str] = {
    Role.CITIZEN: "Interactua con responsabilidad. Sus decisiones son estables.",
    Role.JOURNALIST: "Investiga y detecta falsas. Verificar rinde mas; ignorar rinde menos.",
    Role.INFLUENCER: "Mayor alcance: amplifica todo lo que hace, para bien o para mal.",
    Role.CANDIDATE: "Construye confianza y enfrenta rumores. Pesa mas sobre la confianza.",
}

APARIENCIAS = 2


@dataclass(frozen=True)
class Personaje:
    rol: Role
    genero: Genero
    apariencia: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.apariencia < APARIENCIAS:
            raise ValueError(f"apariencia fuera de rango: {self.apariencia}")

    @property
    def descripcion_rol(self) -> str:
        return ROL_DESCRIPCION[self.rol]

    def to_dict(self) -> dict[str, str | int]:
        return {"rol": self.rol.name, "genero": self.genero.name, "apariencia": self.apariencia}

    @classmethod
    def from_dict(cls, datos: dict[str, str | int]) -> "Personaje":
        return cls(Role[str(datos["rol"])], Genero[str(datos["genero"])], int(datos.get("apariencia", 0)))
