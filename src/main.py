"""Punto de entrada."""
from post_truth.escala import fijar_escala_inicial

fijar_escala_inicial()

from post_truth.pygame_app import App  # noqa: E402


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
