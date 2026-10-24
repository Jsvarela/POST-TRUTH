"""Teclas de roles, iguales en la calle y en el telefono: H usa la habilidad; Y abre el menu de aliados y 1-3 les
pide ayuda."""
import pygame

from post_truth.models import roles
from post_truth.sesion import PartidaSesion

Aviso = tuple[str, str, str]   # (titulo, texto, tipo)


def tecla(s: PartidaSesion, menu: bool, key: int) -> tuple[bool, bool, Aviso | None]:
    """(la tecla era de roles, menu abierto despues, aviso a mostrar)."""
    if key == pygame.K_h:
        r = s.usar_habilidad(s.jugador_actual.id)
        h = roles.HABILIDADES[s.jugador_actual.rol]
        return True, menu, (h.nombre, h.descripcion if r.ok else roles.MOTIVOS.get(r.motivo, "No se pudo."),
                            "bueno" if r.ok else "malo")
    if key == pygame.K_y:
        if not s.aliados():
            return True, False, ("Aliados", "Todos los roles los juegan personas.", "info")
        return True, not menu, None
    if menu and key == pygame.K_ESCAPE:
        return True, False, None
    aliados = s.aliados()
    if menu and pygame.K_1 <= key < pygame.K_1 + len(aliados):
        rol = aliados[key - pygame.K_1]
        r = s.pedir_ayuda(rol)
        return True, False, (f"{rol.value} aliado", roles.AYUDAS[rol] if r.ok
                             else roles.MOTIVOS.get(r.motivo, "No se pudo."), "bueno" if r.ok else "malo")
    return False, menu, None


def filas_aliados(s: PartidaSesion) -> list[tuple[str, float]]:
    return [(f"{r.value} aliado: {roles.AYUDAS[r]}", s.falta(f"aliado:{r.name}")) for r in s.aliados()]


def habilidad(s: PartidaSesion) -> tuple[str, float, float]:
    """(nombre, segundos que faltan, enfriamiento total) de la habilidad del jugador de turno."""
    j = s.jugador_actual
    h = roles.HABILIDADES[j.rol]
    return h.nombre, s.falta(f"habilidad:{j.id}"), h.enfriamiento
