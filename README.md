# POST-TRUTH

Videojuego educativo para Estructura de Datos II basado en el laboratorio
"Alcalde Digital" (Universidad del Norte). Ciudad Nova esta en elecciones y el
jugador decide que hacer con cada publicacion de la red Civitas: Compartir,
Verificar, Ignorar o Reportar. Las decisiones y sus consecuencias, no las
preguntas, ensenan a verificar antes de compartir y a no amplificar rumores.

## Estado del proyecto

| Entrega | Contenido | Estado |
|---|---|---|
| 1 - Arboles | Arbol n-ario de decisiones, insercion, eliminacion, DFS y BFS | Hecha (version Tkinter en el tag `tkinter-entrega1`) |
| 2 - Grafos | Grafo social, grafo de la ciudad, operaciones, integracion con el arbol y la mecanica, visualizacion | Hecha, en Pygame |
| Final | Todo integrado y estable (ver la hoja de ruta de `CLAUDE.md`) | En curso |

El juego se migro de Tkinter a Pygame. El codigo Tkinter (`src/post_truth/app.py`) esta
obsoleto: se conserva solo como referencia.

## Estructuras de datos

| Estructura | Donde | Para que |
|---|---|---|
| Arbol n-ario de decisiones | `decision_tree.py`, `data/events.json` | Ramas de cada publicacion y sus consecuencias (DFS acumula el impacto, BFS recorre por niveles) |
| Grafo social (dirigido, ponderado) | `structures/grafo_social.py`, `data/grafo_social.json` | Como se propaga una publicacion al compartirla: BFS por olas y Dijkstra para el tiempo |
| Grafo de la ciudad (no dirigido) | `structures/grafo_ciudad.py`, `structures/rumores_ciudad.py`, `data/grafo_ciudad.json` | Zonas, movimiento del jugador y expansion de rumores: BFS |

La justificacion completa (problema, estructura, variante, insercion y eliminacion,
recorridos y complejidad, efecto de la decision) esta en
[`docs/entrega2_grafos.md`](docs/entrega2_grafos.md); la del arbol, en
[`docs/entrega1_arboles.md`](docs/entrega1_arboles.md).

## Como se juega

Flujo: Menu -> Seleccion de rol y personaje -> Escena -> Fin.

- Se elige un rol (Ciudadano, Periodista, Influencer, Candidato) y un personaje.
- Cada publicacion ocurre en una zona de la ciudad. Se decide con los botones (teclas 1-4).
- **Compartir, Verificar o Reportar** muestran como viaja la noticia por la red social,
  ola por ola, y despues sus consecuencias. Compartir parte del jugador (el Influencer
  amplifica), Verificar frena la difusion de una noticia falsa y Reportar corta las
  conexiones de su autor.
- **Verificar y Reportar solo se pueden hacer en la zona de la noticia.** El jugador se
  mueve por el minimapa (clic en una zona vecina o teclas Q W E R). Moverse y decidir cuestan
  una ronda: una noticia falsa sin atender es un rumor que se expande a las zonas vecinas y
  penaliza. "Desmentir aqui" lo elimina estando en una zona infectada.
- Otras teclas: Enter para continuar, Espacio para saltar el texto, T en el menu para cambiar
  de tema (normal, alto contraste, daltonismo), ESC para volver.

## Ejecutar

Requisitos: Python 3.10 o superior y Pygame.

```bash
pip install -r requirements.txt
python src/main.py
```

## Ejecutar pruebas

```bash
python -m unittest discover -s tests
```

Las pruebas corren sin ventana (SDL en modo `dummy`). Incluyen pruebas unitarias de cada
estructura, de las vistas y de la integracion, y `tests/test_partida_completa.py`, donde un
jugador automatico juega partidas completas con teclado y mouse.

## Estructura

```text
src/main.py                              Punto de entrada (Pygame)
src/post_truth/pygame_app.py             Game loop (60 FPS, dt en segundos) y recursos compartidos
src/post_truth/config.py                 Constantes y rutas de los datos
src/post_truth/models/                   Logica pura: dominio (Impact, NewsEvent, Role) y personaje
src/post_truth/game_state.py             CityState: indicadores de Ciudad Nova
src/post_truth/decision_tree.py          Arbol n-ario, DFS y BFS
src/post_truth/structures/               grafo_social, propagacion, grafo_ciudad, rumores_ciudad
src/post_truth/controllers/              Estados: menu, seleccion, escena (patron State)
src/post_truth/views/                    Tema, componentes, personajes, escena, grafo, mapa, fondos por zona
src/post_truth/app.py                    Version Tkinter de la entrega 1 (obsoleta)
data/                                    events.json, grafo_social.json, grafo_ciudad.json
docs/                                    Guias de sustentacion de las entregas 1 y 2
tests/                                   Pruebas unitarias, de integracion y de partida completa
```

Reglas de arquitectura: `models` y `structures` son logica pura (sin pygame) y serializable;
las vistas solo dibujan; los controladores conectan eventos con el modelo. Todos los colores
salen de `views/theme.py` (alto contraste y daltonismo).

## Lenguaje elegido

Python. En la entrega 1 se uso Tkinter por no tener dependencias externas; para la entrega 2
se migro a Pygame, que da una experiencia de juego (escenas, animaciones, personajes dibujados
con formas) manteniendo la logica de las estructuras de datos separada de la interfaz.
