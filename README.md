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

## Migracion a Pygame (rama migracion-pygame)

La interfaz Tkinter de la entrega 1 queda en el tag `tkinter-entrega1`. En esta
rama `python src/main.py` abre la version Pygame, que reutiliza
`decision_tree.py`, `models.py`, `game_state.py` y `data/events.json`.

```bash
pip install -r requirements.txt
python src/main.py
```

Grafo social: al elegir Compartir, Verificar o Reportar la escena muestra como viaja
la noticia por la red de Civitas (`data/grafo_social.json`), ola por ola, y despues
aplica sus consecuencias. Compartir parte del jugador (su rol amplifica), Verificar
frena la difusion de una noticia falsa (baja el peso de las conexiones) y Reportar
corta las conexiones de su autor. Los cortes duran toda la partida.

Ciudad: cada noticia ocurre en una zona (`data/grafo_ciudad.json`) y el jugador se mueve
entre zonas conectadas (clic en el minimapa o teclas Q W E R). Moverse y decidir cuestan una
ronda; Verificar y Reportar solo se pueden hacer en la zona de la noticia. Una noticia falsa
que no se atiende se convierte en rumor y se expande a las zonas vecinas cada ronda, con
una penalizacion; "Desmentir aqui" lo elimina estando en una zona infectada.

Flujo actual: Menu (ENTER) -> Seleccion de rol y personaje -> Escena de dialogo
con las publicaciones de `data/events.json`. Teclas: 1-4 para decidir, Enter para
continuar, Espacio para saltar el texto, T (en el menu) para cambiar de tema, ESC
para volver.
