from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(Enum):
    CITIZEN = "Ciudadano"
    JOURNALIST = "Periodista"
    INFLUENCER = "Influencer"
    CANDIDATE = "Candidato a alcalde"


@dataclass(frozen=True)
class Impact:
    verified_information: int = 0
    trust: int = 0
    coexistence: int = 0
    digital_wellbeing: int = 0
    misinformation: int = 0
    conflicts: int = 0
    score: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, int] | None) -> "Impact":
        if not data:
            return cls()
        return cls(
            verified_information=data.get("verified_information", 0),
            trust=data.get("trust", 0),
            coexistence=data.get("coexistence", 0),
            digital_wellbeing=data.get("digital_wellbeing", 0),
            misinformation=data.get("misinformation", 0),
            conflicts=data.get("conflicts", 0),
            score=data.get("score", 0),
        )

    def scaled_for_role(self, role: Role) -> "Impact":
        if role is Role.INFLUENCER:
            factor = 1.35
        elif role is Role.JOURNALIST:
            factor = 1.2 if self.verified_information > 0 else 0.75
        elif role is Role.CANDIDATE:
            factor = 1.25 if self.trust != 0 else 1.0
        else:
            factor = 1.0
        return Impact(
            verified_information=round(self.verified_information * factor),
            trust=round(self.trust * factor),
            coexistence=round(self.coexistence * factor),
            digital_wellbeing=round(self.digital_wellbeing * factor),
            misinformation=round(self.misinformation * factor),
            conflicts=round(self.conflicts * factor),
            score=round(self.score * factor),
        )

    def __add__(self, other: "Impact") -> "Impact":
        return Impact(
            verified_information=self.verified_information + other.verified_information,
            trust=self.trust + other.trust,
            coexistence=self.coexistence + other.coexistence,
            digital_wellbeing=self.digital_wellbeing + other.digital_wellbeing,
            misinformation=self.misinformation + other.misinformation,
            conflicts=self.conflicts + other.conflicts,
            score=self.score + other.score,
        )

    def as_lines(self) -> list[str]:
        return [
            f"Informacion verificada: {self.verified_information:+}",
            f"Confianza ciudadana: {self.trust:+}",
            f"Convivencia: {self.coexistence:+}",
            f"Bienestar digital: {self.digital_wellbeing:+}",
            f"Desinformacion: {self.misinformation:+}",
            f"Conflictos: {self.conflicts:+}",
            f"Puntaje: {self.score:+}",
        ]


@dataclass(frozen=True)
class NewsEvent:
    event_id: str
    title: str
    content: str
    kind: str
    truth_level: int
