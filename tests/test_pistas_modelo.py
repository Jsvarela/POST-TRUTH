import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from post_truth.models.intro import AspectoRetrato
from post_truth.models.pistas import (ENERGIA_POR_NOTICIA, Investigacion, Pista, Senal, VarianteTexto, ZonaTarjeta,
                                      elegir_variante, texto_consecuencia, validar_pistas)
from post_truth.models.publicacion import Autor, Avatar, Imagen


def pista(id: str, zona: ZonaTarjeta, senal: Senal = Senal.FALSA, costo: int = 1) -> Pista:
    return Pista(id, zona, id.replace("-", " ").title(), f"hallazgo de {id}", senal, costo)


def pistas_demo() -> tuple[Pista, ...]:
    return (pista("cuenta", ZonaTarjeta.AUTOR), pista("fecha", ZonaTarjeta.FECHA, Senal.NEUTRA),
            pista("imagen", ZonaTarjeta.IMAGEN, costo=2), pista("fuente", ZonaTarjeta.FUENTE, Senal.VERDADERA))


class PistaTest(unittest.TestCase):
    def test_roundtrip_dict(self) -> None:
        p = pista("imagen", ZonaTarjeta.IMAGEN, costo=2)
        self.assertEqual(Pista.from_dict(json.loads(json.dumps(p.to_dict()))), p)

    def test_datos_invalidos(self) -> None:
        for kwargs in ({"costo": 0}, {"costo": 4}, {"titulo": " "}, {"hallazgo": ""}, {"id": ""}):
            base = {"id": "x", "zona": ZonaTarjeta.TEXTO, "titulo": "t", "hallazgo": "h", "senal": Senal.FALSA, "costo": 1}
            base.update(kwargs)
            with self.assertRaises(ValueError, msg=str(kwargs)):
                Pista(**base)
        with self.assertRaises(ValueError):
            Pista.from_dict({"id": "x", "zona": "inventada", "titulo": "t", "hallazgo": "h", "senal": "falsa"})

    def test_ids_y_zonas_unicos(self) -> None:
        self.assertEqual(len(validar_pistas(pistas_demo())), 4)
        with self.assertRaises(ValueError):
            validar_pistas([pista("a", ZonaTarjeta.AUTOR), pista("a", ZonaTarjeta.FECHA)])
        with self.assertRaises(ValueError):
            validar_pistas([pista("a", ZonaTarjeta.AUTOR), pista("b", ZonaTarjeta.AUTOR)])

    def test_modelo_no_importa_pygame(self) -> None:
        import post_truth.models.pistas as a
        import post_truth.models.publicacion as b
        for modulo in (a, b):
            self.assertNotIn("pygame", vars(modulo))


class PublicacionTest(unittest.TestCase):
    def test_avatares_validos_y_roundtrip(self) -> None:
        aspecto = AspectoRetrato(0, 1, "corto", "barba", 2)
        for avatar in (Avatar("retrato", 0, aspecto), Avatar("anonimo", 2), Avatar("institucional", 3)):
            self.assertEqual(Avatar.from_dict(json.loads(json.dumps(avatar.to_dict()))), avatar)
        autor = Autor("@alguien", Avatar("retrato", 1, aspecto))
        self.assertEqual(Autor.from_dict(json.loads(json.dumps(autor.to_dict()))), autor)

    def test_avatar_invalido(self) -> None:
        with self.assertRaises(ValueError):
            Avatar("retrato", 0)                        # un retrato necesita aspecto
        with self.assertRaises(ValueError):
            Avatar("dibujito", 0)
        with self.assertRaises(ValueError):
            Avatar("anonimo", 9)
        with self.assertRaises(ValueError):
            Autor(" ", Avatar("anonimo"))

    def test_imagen(self) -> None:
        self.assertEqual(Imagen.from_dict(Imagen("parque", "pie").to_dict()), Imagen("parque", "pie"))
        with self.assertRaises(ValueError):
            Imagen("luna")


class InvestigacionTest(unittest.TestCase):
    def test_empieza_con_la_energia_completa_y_sin_pistas(self) -> None:
        inv = Investigacion(pistas_demo(), energia_max=3)
        self.assertEqual((inv.energia, inv.energia_max), (3, 3))
        self.assertEqual(inv.pistas_descubiertas(), [])
        self.assertEqual(inv.veredicto(), "incierta")

    def test_investigar_gasta_energia_y_revela(self) -> None:
        inv = Investigacion(pistas_demo(), energia_max=3)
        r = inv.investigar("imagen")
        self.assertEqual((r.estado, inv.energia), ("nueva", 1))
        self.assertTrue(inv.esta_descubierta("imagen"))
        self.assertEqual(inv.pistas_descubiertas()[0].id, "imagen")

    def test_releer_una_pista_es_gratis(self) -> None:
        inv = Investigacion(pistas_demo(), energia_max=3)
        inv.investigar("cuenta")
        r = inv.investigar("cuenta")
        self.assertEqual((r.estado, inv.energia), ("repetida", 2))
        self.assertEqual(inv.descubiertas, ["cuenta"])

    def test_sin_energia_no_cobra_ni_revela(self) -> None:
        inv = Investigacion(pistas_demo(), energia_max=3)
        inv.investigar("imagen")           # cuesta 2: quedan 1
        inv.investigar("cuenta")           # cuesta 1: quedan 0
        r = inv.investigar("fecha")
        self.assertEqual((r.estado, inv.energia), ("sin_energia", 0))
        self.assertFalse(inv.esta_descubierta("fecha"))

    def test_una_pista_cara_no_cabe_si_la_energia_no_alcanza_aunque_quede_algo(self) -> None:
        inv = Investigacion(pistas_demo(), energia_max=3)
        inv.investigar("cuenta")
        inv.investigar("fecha")            # quedan 1
        r = inv.investigar("imagen")       # cuesta 2
        self.assertEqual((r.estado, inv.energia), ("sin_energia", 1))

    def test_pista_inexistente(self) -> None:
        with self.assertRaises(KeyError):
            Investigacion(pistas_demo(), energia_max=3).investigar("fantasma")

    def test_hay_que_elegir_no_alcanza_para_todo(self) -> None:
        pistas = pistas_demo()
        self.assertGreater(sum(p.costo for p in pistas), 3)

    def test_veredicto_segun_las_senales(self) -> None:
        inv = Investigacion(pistas_demo(), energia_max=9)
        inv.investigar("fecha")                      # neutra
        self.assertEqual(inv.veredicto(), "incierta")
        inv.investigar("cuenta")                     # falsa
        self.assertEqual(inv.veredicto(), "falsa")
        inv.investigar("fuente")                     # verdadera: empate
        self.assertEqual(inv.veredicto(), "incierta")
        inv.investigar("imagen")                     # falsa
        self.assertEqual(inv.veredicto(), "falsa")

    def test_pista_en_una_zona(self) -> None:
        inv = Investigacion(pistas_demo(), energia_max=3)
        self.assertEqual(inv.pista_en(ZonaTarjeta.IMAGEN).id, "imagen")
        self.assertIsNone(inv.pista_en(ZonaTarjeta.TEXTO))

    def test_serializacion_del_progreso(self) -> None:
        inv = Investigacion(pistas_demo(), energia_max=3)
        inv.investigar("imagen")
        inv.investigar("cuenta")
        copia = Investigacion.from_dict(json.loads(json.dumps(inv.to_dict())), pistas_demo())
        self.assertEqual(copia, inv)
        self.assertEqual(copia.energia, 0)

    def test_progreso_con_pistas_desconocidas_es_invalido(self) -> None:
        with self.assertRaises(ValueError):
            Investigacion.from_dict({"energia_max": 3, "energia": 3, "descubiertas": ["fantasma"]}, pistas_demo())


class TextoConsecuenciaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.p = {p.id: p for p in pistas_demo()}
        self.variantes = (
            VarianteTexto(frozenset({"cuenta"}), "solo cuenta"),
            VarianteTexto(frozenset({"cuenta", "imagen"}), "cuenta e imagen"),
            VarianteTexto(frozenset({"fuente"}), "solo fuente"),
            VarianteTexto(frozenset({"fecha"}), "solo fecha (primera)"),
            VarianteTexto(frozenset({"imagen"}), "solo imagen"),
        )

    def _texto(self, *ids: str) -> str:
        return texto_consecuencia("base.", self.variantes, [self.p[i] for i in ids])

    def test_sin_pistas_se_usa_el_texto_base(self) -> None:
        self.assertEqual(self._texto(), "base.")

    def test_gana_la_variante_mas_especifica(self) -> None:
        self.assertEqual(self._texto("cuenta", "imagen"), "cuenta e imagen")
        self.assertEqual(self._texto("imagen", "cuenta"), "cuenta e imagen")   # el orden de revision no importa

    def test_una_variante_necesita_todas_sus_pistas(self) -> None:
        self.assertEqual(self._texto("cuenta"), "solo cuenta")
        self.assertEqual(self._texto("imagen"), "solo imagen")

    def test_sin_variante_aplicable_agrega_las_pistas_revisadas(self) -> None:
        sin_variantes = texto_consecuencia("base.", (), [self.p["cuenta"], self.p["fecha"]])
        self.assertEqual(sin_variantes, "base. Habias revisado: cuenta, fecha.")

    def test_empate_gana_la_primera_escrita(self) -> None:
        v = elegir_variante((VarianteTexto(frozenset({"a"}), "uno"), VarianteTexto(frozenset({"b"}), "dos")), ["a", "b"])
        self.assertEqual(v.texto, "uno")

    def test_las_pistas_cambian_el_texto(self) -> None:
        self.assertNotEqual(self._texto(), self._texto("cuenta"))
        self.assertNotEqual(self._texto("cuenta"), self._texto("cuenta", "imagen"))

    def test_variante_invalida(self) -> None:
        with self.assertRaises(ValueError):
            VarianteTexto(frozenset(), "texto")
        with self.assertRaises(ValueError):
            VarianteTexto(frozenset({"a"}), " ")

    def test_roundtrip_variante(self) -> None:
        v = VarianteTexto(frozenset({"b", "a"}), "t")
        self.assertEqual(VarianteTexto.from_dict(json.loads(json.dumps(v.to_dict()))), v)


if __name__ == "__main__":
    unittest.main()
