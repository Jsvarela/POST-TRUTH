import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.models import Role
from post_truth.models.personaje import Genero, Personaje, ROL_DESCRIPCION


class PersonajeTest(unittest.TestCase):
    def test_roundtrip_dict(self) -> None:
        p = Personaje(Role.JOURNALIST, Genero.MUJER, 1)
        self.assertEqual(Personaje.from_dict(p.to_dict()), p)

    def test_apariencia_invalida(self) -> None:
        with self.assertRaises(ValueError):
            Personaje(Role.CITIZEN, Genero.HOMBRE, 9)

    def test_todos_los_roles_tienen_descripcion(self) -> None:
        self.assertEqual(set(ROL_DESCRIPCION), set(Role))

    def test_modelo_no_importa_pygame(self) -> None:
        import post_truth.models.personaje as modulo
        self.assertNotIn("pygame", vars(modulo))


if __name__ == "__main__":
    unittest.main()
