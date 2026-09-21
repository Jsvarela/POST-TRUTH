# Entrega 1 - Arboles

## Problema que resuelve el arbol

El arbol representa las decisiones que un jugador puede tomar frente a una
publicacion de Civitas. Cada noticia parte de una raiz y cada rama modela una
accion posible: compartir, verificar, ignorar, reportar u otras consecuencias
posteriores.

Esta estructura permite que la decision no sea un boton aislado. El recorrido
del arbol calcula una trayectoria completa y modifica los indicadores de Ciudad
Nova: informacion verificada, confianza, convivencia, bienestar digital,
desinformacion, conflictos y puntaje.

## Por que se escogio esta estructura

Un arbol es adecuado porque una publicacion puede generar varias decisiones, y
cada decision puede producir nuevas consecuencias. Una lista solo guardaria
acciones en secuencia, pero no representa ramificaciones. Una matriz no expresa
con claridad la jerarquia entre publicacion, accion y consecuencia.

## Variante usada

Se usa un arbol n-ario. Cada nodo puede tener cero, uno o muchos hijos. Esta
variante encaja con el juego porque una publicacion no siempre tiene el mismo
numero de opciones y algunas decisiones pueden abrir subdecisiones.

## Insercion

La insercion ocurre de dos maneras:

- Al iniciar el juego, las publicaciones se cargan desde `data/events.json` y se
  convierten en arboles de decision.
- En la interfaz existe el boton `Insertar rama demo`, que agrega una nueva
  decision como hija del nodo seleccionado.

Codigo principal: `DecisionTree.insert_decision`.

## Eliminacion

La eliminacion permite retirar una rama completa del arbol cuando una decision
ya no debe estar disponible. No se permite eliminar la raiz porque representa la
publicacion inicial.

Codigo principal: `DecisionTree.delete_decision`.

## Recorridos

DFS:

- Recorre primero una rama completa antes de pasar a la siguiente.
- En el juego sirve para calcular trayectorias completas de consecuencias.
- Codigo principal: `DecisionTree.dfs_nodes` y `DecisionTree.path_to`.

BFS:

- Recorre el arbol por niveles.
- En el juego sirve para revisar primero todas las decisiones inmediatas y luego
  sus consecuencias secundarias.
- Codigo principal: `DecisionTree.bfs_nodes`.

## Relacion con la logica del juego

Cuando el jugador selecciona una decision, la app busca la trayectoria desde la
raiz hasta ese nodo. Luego suma los impactos de todos los nodos recorridos y
aplica el resultado al estado de Ciudad Nova. El rol del jugador modifica el
impacto para que Ciudadano, Periodista, Influencer y Candidato no tengan el
mismo peso en la simulacion.

## Archivos importantes

- `src/post_truth/decision_tree.py`: estructura de arbol n-ario.
- `src/post_truth/models.py`: impacto, roles y publicacion.
- `src/post_truth/game_state.py`: indicadores de Ciudad Nova.
- `src/post_truth/app.py`: interfaz grafica preliminar.
- `data/events.json`: eventos cargados dinamicamente.
- `tests/test_decision_tree.py`: pruebas de insercion, eliminacion, DFS y BFS.
