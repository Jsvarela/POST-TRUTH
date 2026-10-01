# Entrega 2 - Grafos

Guia de sustentacion. Cubre las tres estructuras del juego y como se combinan en una sola
decision del jugador. Todas las cifras de este documento salen de pruebas y simulaciones del
repositorio (se indica como repetirlas al final).

Notacion: V = numero de vertices, E = numero de aristas, k = grado de un vertice, n = nodos
de un arbol, h = altura del arbol.

## 0. Vision general

| Estructura | Archivo | Pregunta del juego que responde |
|---|---|---|
| Arbol n-ario de decisiones | `decision_tree.py` | Que consecuencias tiene cada decision sobre una publicacion |
| Grafo social | `structures/grafo_social.py` | Quien recibe una publicacion cuando se comparte, cuantos y que tan rapido |
| Grafo de la ciudad | `structures/grafo_ciudad.py` y `structures/rumores_ciudad.py` | Donde ocurre cada noticia, a donde puede ir el jugador y por donde se expande un rumor |

Las tres son logica pura (sin pygame), se pueden serializar a diccionarios y se cargan desde
`data/` (`events.json`, `grafo_social.json`, `grafo_ciudad.json`). La interfaz solo las dibuja.

Una decision del jugador pasa por las tres, en este orden (detalle en la seccion 4):

```
boton de decision
  1. ARBOL         DFS hasta el nodo elegido -> impacto acumulado, escalado por el rol
  2. CIUDAD        zona de la noticia: Verificar/Reportar solo si el jugador esta en ella;
                   el rumor de la noticia se elimina (Verificar/Reportar) o se extiende (Compartir)
  3. GRAFO SOCIAL  se simula como viaja la publicacion (BFS por olas + Dijkstra) y se anima
  4. RONDA         los rumores sin atender se expanden un anillo por el mapa y penalizan
  5. CONSECUENCIAS impacto del arbol + impacto de la propagacion + penalizacion del rumor
                   -> CityState (indicadores de Ciudad Nova)
```

## 1. Arbol de decisiones (entrega 1, integrado)

**Problema que resuelve.** Una publicacion no tiene una sola salida: cada accion (compartir,
verificar, ignorar, reportar) abre consecuencias distintas y algunas abren subdecisiones
("Pedir disculpas" despues de compartir un rumor). Hace falta una estructura que exprese
ramificacion y que permita acumular el efecto de una cadena de decisiones.

**Por que un arbol.** Una lista no representa ramas y una matriz no expresa la jerarquia
publicacion -> accion -> consecuencia.

**Variante.** Arbol n-ario: un nodo puede tener cualquier numero de hijos (3 o 4 acciones segun
el evento). Cada nodo guarda su `Impact` y el campo `tipo` (compartir, verificar, reportar,
ignorar) que conecta la rama con la mecanica sin depender del texto del boton.

**Insercion y eliminacion.**

| Operacion | Metodo | Costo |
|---|---|---|
| Agregar hijo | `DecisionNode.add_child` | O(1) |
| Insertar decision bajo un padre | `DecisionTree.insert_decision` (busca padre y verifica que el id no exista) | O(n) |
| Eliminar una rama completa | `DecisionTree.delete_decision` (no permite borrar la raiz) | O(n) la busqueda; el subarbol se descarta de una vez |

**Recorridos.**

| Recorrido | Metodo | Para que | Costo |
|---|---|---|---|
| DFS | `dfs_nodes`, `path_to` | Acumular el impacto de la cadena raiz -> decision (`accumulated_impact`) | O(n) tiempo, O(h) pila |
| BFS | `bfs_nodes` | Ver las decisiones inmediatas antes que las secundarias | O(n) tiempo, O(ancho) cola |

DFS es el natural para "suma a lo largo de un camino"; BFS para "nivel por nivel".

**Como afecta la decision.** `EscenaState._decidir` llama a `accumulated_impact(nodo)`: suma el
efecto de la publicacion (`root_effect`) y el de la decision, y lo escala por rol
(`Impact.scaled_for_role`: el Influencer amplifica 1.35, el Periodista premia verificar, el
Candidato pesa mas sobre la confianza). Es la reaccion inmediata.

Datos reales: 5 eventos de 4 a 7 nodos y profundidad maxima 3.

## 2. Grafo social

**Problema que resuelve.** Compartir no es un numero: la publicacion viaja por una red de
personas con roles y relaciones de distinta fuerza. El juego necesita decir quien la recibe en
cada ola, cuantos, que tan rapido, y si lo que viaja es verdadero o falso.

**Por que un grafo.** Las relaciones no son jerarquicas ni de uno a uno: una persona tiene
varios contactos y varios contactos pueden converger en la misma persona (ciclos). Un arbol no
lo expresa.

**Variante.**
- Dirigido: la arista `u -> v` significa "lo que publica `u` le llega a `v`" (v es su amigo,
  confia en u o lo sigue). Que A llegue a B no implica que B llegue a A.
- Ponderado: el peso en (0, 1] es la probabilidad base de que la publicacion pase por esa
  arista y, a la vez, su velocidad (mas peso, mas rapido).
- Vertices: ciudadanos con rol (Ciudadano, Periodista, Influencer, Candidato). Aristas con tipo
  (amistad, confianza, seguimiento).
- Representacion: lista de adyacencia como `dict` de origen -> `dict` de destino -> `Arista`,
  espacio O(V + E). Es dispersa (grado medio de salida 2.64 con V = 14, E = 37), asi que una
  matriz gastaria O(V^2) sin necesidad, y el diccionario interno permite consultar o borrar una
  arista en O(1) en vez de O(k).

**Insercion y eliminacion.**

| Operacion | Metodo | Costo |
|---|---|---|
| Agregar vertice | `agregar_vertice` | O(1) |
| Eliminar vertice (y todas sus aristas, entrantes y salientes) | `eliminar_vertice` | O(V): un `pop` O(1) en el diccionario de cada vertice |
| Agregar arista (valida vertices, peso en [0.02, 1], sin lazos ni duplicados) | `agregar_arista` | O(1) |
| Eliminar arista | `eliminar_arista` | O(1) |
| Vecinos (aristas salientes) | `vecinos` | O(k) |
| Bajar el peso de las salientes de un vertice | `debilitar_salientes` | O(k) |
| Cortar todas las salientes de un vertice | `cortar_salientes` | O(k) |

**Recorridos y complejidad.** `propagar(origen, es_falsa)` usa dos algoritmos con funciones
distintas:

1. **BFS por olas, O(V + E).** La cola es la ola actual; sus vecinos nuevos forman la
   siguiente. Se eligio BFS porque la pregunta es "quien la recibe en cada ola" y el nivel de
   BFS es exactamente la ola. Cada arista se evalua una sola vez, con probabilidad
   `min(1, peso * factor del rol del emisor)`:
   - Influencer: factor 1.35 (amplifica).
   - Periodista: no retransmite una noticia falsa (la verifica; queda marcado con una X en la
     animacion) y difunde con factor 1.2 una verdadera.
2. **Dijkstra con `heapq`, O(E log V).** Se usa solo para "que tan rapido". BFS cuenta saltos y
   trata igual una arista de peso 0.9 y una de 0.2; con costo `1 / peso`, el camino de menor
   costo es el mas rapido. Corre sobre las aristas que si se activaron y da el tiempo minimo
   de llegada de cada persona (horas simuladas), de donde salen el tiempo hasta la mitad y el
   tiempo total. Una prueba lo demuestra: un camino de 2 saltos fuertes (costo 2.2) le gana a
   un atajo directo debil (costo 10), aunque BFS ubica ambos en la ola 1.

DFS no se usa: sirve para alcanzabilidad, pero no entrega niveles (olas) ni tiempos.

El resultado es un dato inmutable (`ResultadoPropagacion`) con las olas, el arbol BFS
(`padres`), los periodistas que frenaron la noticia y los tiempos. Se simula con un generador
con semilla: el resultado varia entre partidas (azar) pero es reproducible en las pruebas.

**Como afecta la decision** (`structures/propagacion.py`, `simular_decision`).

| Decision | Que le pasa al grafo social |
|---|---|
| Compartir | La publicacion parte del jugador; su rol amplifica (Influencer) |
| Verificar (noticia falsa) | Baja el peso de las salientes del autor (x0.35) y de sus contactos (x0.6): se ve en el grosor de las aristas; el cambio dura toda la partida |
| Verificar (noticia verdadera) | No frena nada: se difunde normal desde su autor |
| Reportar | Se **eliminan** las aristas salientes del autor: su cuenta deja de difundir |
| Ignorar | No se simula |

Consecuencia segun veracidad (`ResultadoPropagacion.impacto`, con topes): una falsa sube
desinformacion y conflictos y baja confianza; una verdadera sube informacion verificada y
confianza.

Alcance medio de compartir una falsa (13 posibles receptores, 300 simulaciones):
Ciudadano 7.2, Periodista 7.2, Candidato 7.9, Influencer 9.3. Verificar la deja en 1.0 y
Reportar en 0.0. Una verdadera compartida por un Ciudadano llega a 9.0 personas en 3.7 olas
(mitad en 3.8 h, total en 7.0 h).

## 3. Grafo de la ciudad

**Problema que resuelve.** El grafo social dice *como* circula una noticia en linea; este dice
*donde* ocurre y por donde se contagia en persona. Da una funcion real a la geografia: a donde
puede ir el jugador, que zonas quedan expuestas a un rumor y cuanto tarda en llegar a cada una.

**Por que un grafo.** Las zonas se conectan en una red con ciclos (Barrio - Parque - Plaza forman
un triangulo): no es una jerarquia.

**Variante.**
- No dirigido: una calle se recorre en ambos sentidos (la conexion se anota en la lista de las
  dos zonas).
- Sin pesos: todas las conexiones cuestan un movimiento (una ronda).
- 5 zonas (Colegio, Barrio, Parque, Plaza, Alcaldia) y 6 conexiones. Plaza es el centro: llega
  a todas en un salto; Alcaldia solo se conecta con Plaza.
- Representacion: lista de adyacencia `dict` zona -> `list` de vecinos, O(V + E). Con grado
  maximo 4, buscar en la lista es practicamente O(1) y se conserva el orden de insercion, lo que
  hace los recorridos deterministas (y asigna las letras Q, W, E, R del teclado a los vecinos).

**Insercion y eliminacion.**

| Operacion | Metodo | Costo |
|---|---|---|
| Agregar zona | `agregar_zona` | O(1) |
| Eliminar zona (y sus conexiones) | `eliminar_zona` | O(suma de grados de sus vecinos), a lo sumo O(E) |
| Agregar conexion (bidireccional, sin lazos ni duplicados) | `agregar_conexion` | O(k) |
| Eliminar conexion | `eliminar_conexion` | O(k) |
| Vecinos | `vecinos` | O(k) |

**Recorridos y complejidad.** Todos son BFS, O(V + E), porque las aristas no tienen peso y el
camino con menos saltos es el mas corto (Dijkstra no aportaria nada sin pesos):

| Consulta | Metodo | Para que |
|---|---|---|
| Camino mas corto | `camino(a, b)` (BFS guardando el padre de cada zona) | Ruta del jugador hacia la zona de una noticia |
| Distancias | `distancias(origen, limite)` | Base de las otras consultas |
| Zonas expuestas | `expuestas(origen, alcance)` (BFS agrupado por anillos) | El anillo k son las zonas que un rumor toca en la ronda k |

Ejemplo real: `camino("colegio", "alcaldia")` = Colegio - Plaza - Alcaldia, y
`expuestas("colegio", 3)` = [(Plaza, Barrio), (Parque, Alcaldia)]: un rumor nacido en el Colegio
llega a la Alcaldia en 2 rondas.

**Rumores** (`structures/rumores_ciudad.py`). Una noticia falsa es un rumor desde que aparece.
Cada ronda, el rumor ocupa todas las vecinas de las zonas que ya ocupa: es avanzar un nivel de
BFS desde el origen, asi que tras k rondas ocupa exactamente lo que predice `expuestas(origen, k)`
(una prueba lo comprueba). Una ronda cuesta O(suma de grados de las zonas ocupadas), nunca mas
que O(V + E). Cada zona infectada penaliza por ronda (desinformacion y conflictos, con tope).
El rumor solo se muestra cuando ya empezo a correr, porque si se viera desde el principio el
mapa delataria cuales noticias son falsas y no habria nada que investigar.

**Como afecta la decision.**

| Accion | Efecto en la ciudad |
|---|---|
| Moverse a una zona vecina (clic en el mapa o Q W E R) | Cuesta una ronda: los rumores avanzan |
| Verificar o Reportar | Solo se pueden hacer **en la zona de la noticia**; eliminan el rumor |
| Compartir una falsa | Extiende el rumor un anillo de inmediato |
| Ignorar | El rumor sigue activo y crece |
| Desmentir aqui | En una zona infectada, elimina ese rumor, cuesta una ronda y da un premio (confianza e informacion verificada) |

Esto obliga a decidir si vale la pena viajar: mientras el jugador se desplaza, los rumores
avanzan.

## 4. Como se combinan en una decision

Ejemplo: noticia falsa "Rumor sobre el colegio" (zona Colegio), jugador en la Plaza.

1. Verificar y Reportar aparecen apagados ("ir a Colegio"). Compartir e Ignorar si se pueden.
2. Si el jugador va al Colegio (1 ronda), el rumor aparece en el mapa y ya ocupa Plaza y Barrio.
3. Alli elige Verificar: el arbol aporta +informacion verificada, +confianza; el rumor se
   elimina; el grafo social frena a los contactos del autor y se anima la propagacion limitada;
   al terminar se aplican los indicadores.
4. Si en cambio elige Compartir desde la Plaza: el arbol penaliza, el rumor crece un anillo y
   el grafo social lleva la publicacion a unas 7 personas; la desinformacion y los conflictos
   suben y el rumor sigue ampliandose en las rondas siguientes.

Resultados de 40 partidas por estilo de juego (jugador automatico, roles y semillas
repetidos), promedio al final:

| Estilo | Puntaje | Desinformacion | Conflictos | Info verificada |
|---|---|---|---|---|
| Azar | -17.0 | 98.5 | 80.0 | 74.0 |
| Siempre compartir | -35.4 | 100.0 | 92.2 | 69.5 |
| Siempre ignorar | -17.5 | 100.0 | 67.7 | 62.5 |
| Investigar (viajar a la zona y verificar) | +74.5 | 22.1 | 13.6 | 100.0 |

Es decir, el resultado depende de la habilidad (decidir bien y moverse con criterio), no solo
del azar de la propagacion.

## 5. Preguntas tipicas de sustentacion

- **Por que lista de adyacencia y no matriz?** Los grafos son dispersos (grado medio 2.64 en el
  social, maximo 4 en el de la ciudad). Lista: O(V + E) espacio; matriz: O(V^2).
- **Por que `dict` de `dict` en el grafo social?** Es una lista de adyacencia cuyas entradas se
  buscan por clave: consultar o borrar una arista pasa de O(k) a O(1).
- **Por que el grafo social es dirigido y el de la ciudad no?** La influencia en redes es
  asimetrica (alguien te sigue y tu no a el); una calle se recorre en los dos sentidos.
- **Por que BFS para las olas?** El nivel de BFS es la ola. DFS recorreria una rama hasta el
  fondo y no entrega niveles.
- **Por que Dijkstra solo para el tiempo?** Porque es lo unico que depende de los pesos; para
  quien recibe y en que ola, BFS basta y es mas barato.
- **Que pasa si un peso fuera 0?** El costo 1/peso seria infinito: por eso el peso minimo es
  0.02 y "sin relacion" se modela eliminando la arista.
- **Por que BFS y no Dijkstra en el grafo de la ciudad?** Las conexiones no tienen peso: el
  camino con menos saltos ya es el mas corto.
- **Como se elimina un vertice?** Se borra su entrada (las salientes) y se hace `pop` en cada
  diccionario de los demas (las entrantes): O(V).
- **Por que Reportar elimina aristas y Verificar solo baja pesos?** Reportar actua sobre una
  cuenta (se corta del todo); Verificar frena, pero la noticia puede seguir circulando.
- **Por que el rumor no se ve de inmediato?** Para no revelar cual noticia es falsa sin que el
  jugador investigue.
- **Es serializable?** Si: `to_dict` / `from_dict` en el grafo social, el grafo de la ciudad y
  los rumores, pensado para el servidor de sockets de la entrega final.

## 6. Modo de sustentacion

El modo de sustentacion que existe es el panel de la version Tkinter (`src/post_truth/app.py`,
tag `tkinter-entrega1`): muestra DFS, BFS, insercion y eliminacion **del arbol**. Esa version esta
obsoleta y no cubre los grafos. Para demostrar los grafos en vivo se pueden usar estos
fragmentos desde la raiz del repositorio:

```python
import sys; sys.path.insert(0, "src")
import random
from post_truth.config import RUTA_GRAFO_SOCIAL, RUTA_GRAFO_CIUDAD
from post_truth.models import Role
from post_truth.structures.grafo_social import Ciudadano, GrafoSocial, TipoRelacion
from post_truth.structures.grafo_ciudad import GrafoCiudad

# Insertar un vertice y aristas, propagar y eliminar
g = GrafoSocial.cargar(RUTA_GRAFO_SOCIAL)
g.agregar_vertice(Ciudadano("lina", "Lina Vega", Role.INFLUENCER))
g.agregar_arista("jugador", "lina", 0.9, TipoRelacion.SEGUIMIENTO)
g.agregar_arista("lina", "gael", 0.8, TipoRelacion.SEGUIMIENTO)
r = g.propagar("jugador", True, random.Random(1))
print(r.olas)                                   # quien recibe en cada ola (BFS)
print(r.alcanzados, round(r.tiempo_total, 1))   # cuantos y que tan rapido (Dijkstra)
print(r.impacto())                              # consecuencias de una noticia falsa
g.eliminar_vertice("lina")                      # sus aristas desaparecen

# Ciudad
c = GrafoCiudad.cargar(RUTA_GRAFO_CIUDAD)
print(c.camino("colegio", "alcaldia"))          # ['colegio', 'plaza', 'alcaldia']
print(c.expuestas("colegio", 3))                # [('plaza', 'barrio'), ('parque', 'alcaldia')]
```

Con la semilla 1 el primero imprime
`(('jugador',), ('mateo', 'lina'), ('tomas', 'sofia', 'gael'), ('isabela', 'daniela'),
('esteban',), ('renata',))` y 9 personas alcanzadas.

Las pruebas unitarias (`tests/test_grafo_social.py`, `test_grafo_ciudad.py`,
`test_rumores_ciudad.py`, `test_propagacion.py`) tambien sirven como demostracion de cada
operacion.

## 7. Como repetir las pruebas y las cifras

```bash
python -m unittest discover -s tests                 # todas las pruebas, sin ventana (SDL dummy)
python -m unittest tests.test_partida_completa       # partidas completas del jugador automatico
```

`tests/test_partida_completa.py` juega el flujo Menu -> Seleccion -> Escena -> Fin con teclado y
mouse, los 4 roles y varias politicas de juego, dibujando en los 3 temas y comprobando
invariantes en cada fotograma.

## 8. Limites conocidos

- Con solo 5 publicaciones, jugar al azar o ignorar satura la desinformacion en 100 (ver la
  tabla de la seccion 4). Los topes y penalizaciones estan en constantes
  (`ResultadoPropagacion.impacto`, `rumores_ciudad.py`) para ajustarlos al balance final.
- El grafo social y el de la ciudad son datos fijos de ejemplo (14 ciudadanos, 5 zonas).
- Aun no hay modo de sustentacion en Pygame (ver la hoja de ruta en CLAUDE.md).
