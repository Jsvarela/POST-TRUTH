from __future__ import annotations

from dataclasses import dataclass

from post_truth.models import Impact


@dataclass
class CityState:
    verified_information: int = 55
    trust: int = 55
    coexistence: int = 60
    digital_wellbeing: int = 58
    misinformation: int = 35
    conflicts: int = 22
    score: int = 0

    def apply(self, impact: Impact) -> None:
        self.verified_information = self._bounded(
            self.verified_information + impact.verified_information
        )
        self.trust = self._bounded(self.trust + impact.trust)
        self.coexistence = self._bounded(self.coexistence + impact.coexistence)
        self.digital_wellbeing = self._bounded(
            self.digital_wellbeing + impact.digital_wellbeing
        )
        self.misinformation = self._bounded(self.misinformation + impact.misinformation)
        self.conflicts = self._bounded(self.conflicts + impact.conflicts)
        self.score += impact.score

    def reset(self) -> None:
        self.verified_information = 55
        self.trust = 55
        self.coexistence = 60
        self.digital_wellbeing = 58
        self.misinformation = 35
        self.conflicts = 22
        self.score = 0

    def as_display_rows(self) -> list[tuple[str, int]]:
        return [
            ("Informacion verificada", self.verified_information),
            ("Confianza ciudadana", self.trust),
            ("Convivencia", self.coexistence),
            ("Bienestar digital", self.digital_wellbeing),
            ("Desinformacion", self.misinformation),
            ("Conflictos", self.conflicts),
            ("Puntaje jugador", self.score),
        ]

    @staticmethod
    def _bounded(value: int) -> int:
        return max(0, min(100, value))
