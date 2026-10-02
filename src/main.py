"""Punto de entrada. Elige la escala de la interfaz segun la pantalla ANTES de importar el juego."""
from post_truth.escala import fijar_escala_inicial

fijar_escala_inicial()   # deja POSTTRUTH_ESCALA en el entorno; config.py la lee al importarse

from post_truth.pygame_app import App  # noqa: E402  (debe importarse despues de fijar la escala)


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
