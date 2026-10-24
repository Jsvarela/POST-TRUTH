"""Credibilidad de un jugador (0 a 100): cuanto le cree la red. Logica pura.

Sube al verificar o desmentir con evidencia y al acertar con buena evidencia; baja al compartir falsedades,
reportar lo cierto o dejar vencer el reloj. Escala el alcance de lo que comparte y la fuerza de sus desmentidos.
"""
from __future__ import annotations

INICIAL, MINIMO, MAXIMO = 50, 0, 100
REINCIDENCIA = 2   # desde esta cantidad de falsedades compartidas, cada nueva baja el doble


def factor(credibilidad: float) -> float:
    """0.5 con credibilidad 0, 1.0 con 50, 1.5 con 100."""
    return 0.5 + credibilidad / 100


def acotar(valor: float) -> int:
    return round(max(MINIMO, min(MAXIMO, valor)))


def cambio(tipo: str, falsa: bool, respaldo: int, vencido: bool = False, falsas_compartidas: int = 0,
           costo_reporte: int = 5) -> int:
    """Cuanto cambia la credibilidad por una decision (`respaldo`: 0 nada, 1 tarjeta, 2 evidencia de campo).
    `costo_reporte`: lo que cuesta reportar sin pruebas o reportar algo cierto (menos para el Ciudadano)."""
    if vencido:
        return -3
    if not tipo:              # respuesta a una opinion: no se juega la credibilidad
        return 0
    if falsa:
        if tipo == "compartir":
            return -16 if falsas_compartidas >= REINCIDENCIA else -8
        if tipo in ("verificar", "reportar"):
            if tipo == "reportar" and respaldo == 0:
                return -costo_reporte   # reporte rechazado por infundado
            return (0, 3, 6)[min(respaldo, 2)]
        return 0
    if tipo == "reportar":
        return -costo_reporte   # reportar algo cierto
    if tipo in ("compartir", "verificar") and respaldo >= 2:
        return 3              # acerto con buena evidencia
    return 0
