# POST-TRUTH

Videojuego educativo para Estructura de Datos II basado en el laboratorio
"Alcalde Digital". La primera entrega implementa la mecanica central con
arboles: cada publicacion genera decisiones, consecuencias y recorridos que
modifican el estado de Ciudad Nova.

## Entrega 1 - Arboles

Incluye:

- Arbol n-ario de decisiones para publicaciones de Civitas.
- Insercion dinamica de eventos desde `data/events.json`.
- Eliminacion de ramas de decision.
- Recorrido DFS para calcular trayectorias completas de consecuencias.
- Recorrido BFS para mostrar el orden de evaluacion por niveles.
- Interfaz grafica reorganizada como tablero de juego en Tkinter.
- Feed de Civitas con publicaciones, veracidad y temporizador de turno.
- Tarjetas de decision con ruta, impacto esperado y confirmacion.
- Mapa visual del arbol para sustentar la estructura sin mostrar ids tecnicos.
- Vista de Ciudad Nova con zonas, estado general y barras de indicadores.
- Bitacora de acciones, ayuda integrada y modo de alto contraste.
- Indicadores de ciudad: informacion verificada, confianza, convivencia,
  bienestar, desinformacion y conflictos.

## Ejecutar

Requisitos:

- Python 3.10 o superior.

Comando:

```bash
python src/main.py
```

## Ejecutar pruebas

```bash
python -m unittest discover -s tests
```

## Estructura

```text
data/events.json                 Eventos iniciales del juego
docs/entrega1_arboles.md         Guia de sustentacion de la entrega 1
src/main.py                      Punto de entrada
src/post_truth/app.py            Tablero visual del juego
src/post_truth/decision_tree.py  Arbol n-ario y recorridos
src/post_truth/game_state.py     Estado de Ciudad Nova
src/post_truth/models.py         Modelos del dominio
tests/test_decision_tree.py      Pruebas de arboles
```

## Lenguaje elegido

Python, porque permite una GUI en Tkinter sin dependencias externas y deja
visibles las estructuras de datos para sustentarlas con claridad. La interfaz se
organizo como tablero de simulacion para que no parezca un formulario tecnico.
En entregas posteriores se puede migrar o ampliar la interfaz a Pygame si el
equipo quiere una experiencia mas cercana a videojuego.
