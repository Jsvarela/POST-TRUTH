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
| Grafo de la ciudad (no dirigido, ponderado) | `structures/grafo_ciudad.py`, `data/grafo_ciudad.json` | Mapa de lugares donde se investiga: viajar cuesta energia (la distancia del camino mas corto, con Dijkstra) y cada zona guarda evidencia de la noticia |

La justificacion completa (problema, estructura, variante, insercion y eliminacion,
recorridos y complejidad, efecto de la decision) esta en
[`docs/entrega2_grafos.md`](docs/entrega2_grafos.md); la del arbol, en
[`docs/entrega1_arboles.md`](docs/entrega1_arboles.md).

## Como se juega

Flujo: Menu -> Introduccion -> Seleccion de rol y personaje -> Escena -> Fin.

- La **introduccion** (6 laminas: Ciudad Nova, las zonas, Civitas y los primeros rumores, los cuatro
  candidatos y el cierre) se muestra sola la primera vez de la sesion y se puede ver de nuevo con la
  tecla I en el menu. Clic o cualquier tecla avanzan (el primer clic completa el texto que se escribe
  letra por letra) y ESC la salta. Sus textos, candidatos y zonas estan en `data/intro.json`.

- Se elige un rol (Ciudadano, Periodista, Influencer, Candidato) y un personaje.
- Cada publicacion es una **tarjeta de Civitas** (autor con avatar, fuente, fecha, texto, imagen, likes y
  comentarios). Se decide con los botones (teclas 1-4).
- **Investigar:** las partes de la tarjeta (autor, fuente, fecha, imagen, texto, reacciones) son zonas
  clicables (o teclas A S D F G) que esconden pistas: una cuenta sospechosa, una fecha antigua, una imagen
  reutilizada... Revisar una pista revela su hallazgo y gasta energia (5 por publicacion; hay mas por revisar
  que energia, asi que hay que elegir; algunas pistas son neutras y no prueban nada).
- **Viajar por el mapa:** la noticia tambien deja **evidencia en lugares de la ciudad** (un testigo, un
  documento, una grabacion). Se puede ir a cualquier zona con un clic en el minimapa (o Q W E R T); el viaje
  cuesta la distancia del camino mas corto (Dijkstra) en la misma energia, y al llegar se revela la
  evidencia. En el minimapa cada via muestra su distancia, la ruta elegida se resalta con su costo, el pin
  marca donde estas y un rombo marca las zonas con evidencia pendiente.
- **Compartir, Verificar o Reportar** muestran como viaja la noticia por la red social,
  ola por ola, y despues sus consecuencias. Compartir parte del jugador (el Influencer
  amplifica), Verificar frena la difusion de una noticia falsa y Reportar corta las
  conexiones de su autor.
- **Verificar y Reportar no exigen estar en ningun lugar:** su resultado depende del respaldo reunido
  (nada, solo la tarjeta o evidencia de campo). Verificar rinde 50%, 75% o 100%; Reportar sin pruebas se
  rechaza y baja la confianza, con pruebas de la tarjeta limita al autor y con evidencia de campo corta
  sus conexiones. Los rumores se propagan solo por el grafo social (entre personas), no por el mapa.
  Lo investigado tambien cambia el texto de la consecuencia.
- Otras teclas: Enter para continuar, Espacio para saltar el texto, I en el menu para ver la introduccion, T en el menu para cambiar
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
src/post_truth/models/                   Logica pura: dominio (Impact, NewsEvent, Role), personaje, intro, publicacion y pistas
src/post_truth/game_state.py             CityState: indicadores de Ciudad Nova
src/post_truth/decision_tree.py          Arbol n-ario, DFS y BFS
src/post_truth/structures/               grafo_social, propagacion, grafo_ciudad
src/post_truth/controllers/              Estados: menu, intro, seleccion, escena (patron State)
src/post_truth/views/                    Tema, componentes, personajes, retratos, intro, escena, tarjeta de Civitas, grafo, mapa, fondos por zona
src/post_truth/app.py                    Version Tkinter de la entrega 1 (obsoleta)
data/                                    events.json, grafo_social.json, grafo_ciudad.json, intro.json
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
