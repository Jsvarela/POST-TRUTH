"""Mide el balance del juego con cientos de partidas simuladas, sin ventana.

Cada partida recorre la escena real (EscenaState: viajes por el mapa, pistas, evidencia, energia, decision,
propagacion por el grafo social y consecuencias) pero sin dibujar ni esperar animaciones, por lo que cientos
de partidas tardan segundos. El azar sale de una semilla por partida: la misma semilla da el mismo resultado.

Politicas:
  ignorar    siempre Ignorar.
  compartir  siempre Compartir.
  verificar  siempre Verificar, a ciegas (sin revisar pistas ni viajar).
  investigar con criterio: revisa 2 pistas de la tarjeta y, si no apuntan a verdadera, va a la evidencia de campo
             mas barata; comparte lo que sale verdadero, reporta lo que tiene pruebas de falsedad, verifica
             si hay respaldo parcial y, si todo es incierto, ignora.

Se "gana" una partida si termina con desinformacion < 40 e informacion verificada > 50.

Uso:  python tools/balance.py [partidas_por_politica=300] [--rol N] [--json]
"""
import os
import random
import statistics
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.controllers.escena_state import CONSECUENCIA, DECIDIENDO, FIN, PROPAGACION  # noqa: E402

POLITICAS = ("ignorar", "compartir", "verificar", "investigar")
UMBRAL_DESINFORMACION = 40   # se gana con desinformacion final por debajo de esto...
UMBRAL_VERIFICADA = 50       # ...y con informacion verificada final por encima de esto
SEMILLA_BASE = 20261


def _boton_de(escena, tipo: str):
    ramas = escena.arbol.root.children[:4]
    for boton, nodo in zip(escena.botones, ramas):
        if nodo.tipo == tipo:
            return nodo
    return None


def _viajar_a_evidencia(escena) -> None:
    """Va a la zona con evidencia pendiente mas barata que alcance la energia."""
    costos = escena.mapa.costos_desde(escena.zona)
    inv = escena.investigacion
    posibles = [z for z in inv.lugares_pendientes() if 0 < costos[z] <= inv.energia]
    if posibles:
        escena._viajar(min(posibles, key=lambda z: (costos[z], z)))


def _revisar_pistas(escena, maximo: int) -> None:
    inv = escena.investigacion
    hechas = 0
    for pista in sorted(inv.pistas, key=lambda p: p.costo):
        if hechas >= maximo:
            break
        if inv.energia >= pista.costo and not inv.esta_descubierta(pista.id):
            escena._investigar(pista)
            hechas += 1


def _elegir(escena, politica: str):
    ramas = {n.tipo: n for n in escena.arbol.root.children[:4] if n.tipo}
    if politica in ("ignorar", "compartir", "verificar"):
        return ramas.get(politica, escena.arbol.root.children[0])
    inv = escena.investigacion
    if inv.veredicto() == "verdadera" and "compartir" in ramas:
        return ramas["compartir"]
    if "reportar" in ramas and inv.respaldo("reportar") >= 1:
        return ramas["reportar"]
    for tipo in ("verificar", "ignorar"):
        if tipo in ramas:
            return ramas[tipo]
    return escena.arbol.root.children[0]


def jugar(app, politica: str, semilla: int, rol: int = 0):
    """Una partida completa; devuelve la ciudad final."""
    from post_truth.models.personaje import Genero, Personaje, Role
    escena = app.estados._estados["escena"]
    escena.rng = random.Random(semilla)
    app.personaje = Personaje(list(Role)[rol], Genero.MUJER)
    escena.al_entrar()
    while escena.fase != FIN:
        assert escena.fase == DECIDIENDO
        if politica == "investigar":
            _revisar_pistas(escena, 2)
            if escena.investigacion.veredicto() != "verdadera":
                _viajar_a_evidencia(escena)
        escena._decidir(_elegir(escena, politica))
        if escena.fase == PROPAGACION:                  # la animacion no cambia el resultado: se salta
            escena.animacion.saltar()
            escena._terminar_propagacion()
        assert escena.fase == CONSECUENCIA
        escena._continuar()
    return escena.ciudad


def medir(partidas: int = 300, rol: int = 0) -> dict[str, dict[str, float]]:
    import pygame
    from post_truth.pygame_app import App
    app = App()
    resultados: dict[str, dict[str, float]] = {}
    try:
        for politica in POLITICAS:
            finales = [jugar(app, politica, SEMILLA_BASE + i, rol) for i in range(partidas)]
            desinfo = [c.misinformation for c in finales]
            verif = [c.verified_information for c in finales]
            puntaje = [c.score for c in finales]
            ganadas = sum(c.misinformation < UMBRAL_DESINFORMACION and c.verified_information > UMBRAL_VERIFICADA
                          for c in finales)
            resultados[politica] = {
                "desinformacion": statistics.mean(desinfo), "desinfo_sd": statistics.pstdev(desinfo),
                "verificada": statistics.mean(verif), "verificada_sd": statistics.pstdev(verif),
                "puntaje": statistics.mean(puntaje), "gana_pct": 100 * ganadas / partidas,
            }
    finally:
        pygame.quit()
    return resultados


def tabla(resultados: dict[str, dict[str, float]], partidas: int) -> str:
    lineas = [f"{partidas} partidas por politica (semillas {SEMILLA_BASE}..{SEMILLA_BASE + partidas - 1}); "
              f"gana = desinformacion < {UMBRAL_DESINFORMACION} y verificada > {UMBRAL_VERIFICADA}",
              "| Politica | Desinformacion final | Informacion verificada final | Puntaje | Gana |",
              "|---|---|---|---|---|"]
    for politica, r in resultados.items():
        lineas.append(f"| {politica} | {r['desinformacion']:.1f} (sd {r['desinfo_sd']:.1f}) | "
                      f"{r['verificada']:.1f} (sd {r['verificada_sd']:.1f}) | {r['puntaje']:+.1f} | {r['gana_pct']:.0f}% |")
    return "\n".join(lineas)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 300
    rol = int(sys.argv[sys.argv.index("--rol") + 1]) if "--rol" in sys.argv else 0
    if "--rol" in sys.argv:
        args = [a for a in args if a != str(rol)] or args
        n = int(args[0]) if args else 300
    print(tabla(medir(n, rol), n))
