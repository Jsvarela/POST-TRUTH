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
| Grafo de la ciudad | `structures/grafo_ciudad.py` | El mapa de lugares donde se investiga: a que zona ir, cuanto cuesta llegar (energia) y que evidencia hay alli |

Las tres son logica pura (sin pygame), se pueden serializar a diccionarios y se cargan desde
`data/` (`events.json`, `grafo_social.json`, `grafo_ciudad.json`). La interfaz solo las dibuja.

Los rumores se propagan SOLO en el grafo social (entre personas). El grafo de la ciudad no propaga
nada: es el mapa de lugares donde el jugador va a buscar evidencia, y viajar tiene un costo.

Antes de decidir el jugador investiga con una sola energia (5 por publicacion): revisa las pistas de
la tarjeta de Civitas y viaja por el grafo de la ciudad (Dijkstra) a los lugares donde la noticia dejo
evidencia. Luego decide, y su decision pasa por las tres estructuras (detalle en la seccion 4):

```
investigar (antes de decidir)
  tarjeta          pistas de la tarjeta de Civitas (1-2 de energia cada una)
  CIUDAD           viajar a una zona cuesta la distancia del camino mas corto (Dijkstra);
                   al llegar se revela la evidencia de la noticia que haya alli

boton de decision
  1. ARBOL         DFS hasta el nodo elegido -> impacto acumulado, escalado por el rol
  2. RESPALDO      lo hallado (nada / solo tarjeta / evidencia de campo) gradua Verificar
                   (15% / 40% / 100%) y Reportar (rechazado / limita / corta)
  3. GRAFO SOCIAL  se simula como viaja la publicacion (BFS por olas + Dijkstra) y se anima
  4. CONSECUENCIAS impacto del arbol (atenuado segun el respaldo) + impacto de la propagacion
                   -> CityState; el texto depende de las pistas y evidencias descubiertas
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

Datos reales: 18 eventos de 4 a 7 nodos y profundidad maxima 2 (cada partida juega 8, sorteados).

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

**Problema que resuelve.** El grafo social dice *como* circula una noticia entre personas; este es el
*mapa de lugares donde se investiga*. Cada zona puede guardar evidencia de una noticia (un testigo, un
documento, una grabacion) y llegar hasta ella cuesta energia: la distancia del camino mas corto.
Elegir a que zona ir es una decision real: viajar lejos a buscar evidencia o decidir con lo que ya se
sabe. Los rumores NO se propagan por aqui (antes se contagiaban por zonas; se quito porque la
propagacion tiene sentido entre personas, no entre lugares).

**Por que un grafo.** Las zonas se conectan en una red con ciclos (Barrio - Parque - Plaza forman un
triangulo) y para ir de una a otra hay varios caminos, de distinto costo: no es una jerarquia.

**Variante.**
- No dirigido: una calle se recorre en ambos sentidos (la conexion se anota en las dos zonas).
- **Ponderado**: cada conexion tiene una distancia (entero >= 1) que es su costo en energia:
  Colegio-Barrio 1, Barrio-Parque 1, Parque-Plaza 1, Colegio-Plaza 2, Plaza-Alcaldia 2, Barrio-Plaza 3.
- 5 zonas (Colegio, Barrio, Parque, Plaza, Alcaldia) y 6 conexiones. El jugador puede ir a CUALQUIER
  zona, no solo a las vecinas, y su posicion se mantiene entre publicaciones.
- Representacion: lista de adyacencia como `dict` zona -> `dict` vecino -> distancia, espacio O(V + E).
  Con 5 zonas es mas que suficiente, y consultar la distancia de una via directa es O(1).

**Insercion y eliminacion.**

| Operacion | Metodo | Costo |
|---|---|---|
| Agregar zona | `agregar_zona` | O(1) |
| Eliminar zona (y sus conexiones) | `eliminar_zona` | O(grado de la zona) |
| Agregar conexion (bidireccional, distancia entera >= 1, sin lazos ni duplicados) | `agregar_conexion` | O(1) |
| Eliminar conexion | `eliminar_conexion` | O(1) |
| Distancia de una via directa / vecinos | `distancia`, `vecinos` | O(1) / O(k) |

**Recorridos y complejidad.**

| Consulta | Metodo | Costo | Para que |
|---|---|---|---|
| Camino de menor costo y su costo | `ruta(a, b)` (**Dijkstra**) | O((V + E) log V) | Cuanto cuesta viajar a una zona y por donde se va |
| Costo a todas las zonas | `costos_desde(origen)` (Dijkstra, una corrida) | O((V + E) log V) | Saber que viajes alcanzan con la energia que queda; se muestra como rayos al pasar el mouse por un lugar (el jugador no ve numeros ni distancias) |
| Saltos / conectividad | `saltos`, `es_conexo` (**BFS**) | O(V + E) | Validar al cargar que toda zona sea alcanzable |

**Por que Dijkstra y cuando basta BFS.** El costo de un viaje es la *suma* de distancias, y el camino
con menos saltos no siempre es el mas barato. En el mapa real: de Barrio a Plaza la via directa es 1
salto pero cuesta 3, y por el Parque son 2 saltos pero cuestan 1 + 1 = 2. BFS (que minimiza saltos)
daria 3; Dijkstra da 2 y la ruta `Barrio - Parque - Plaza`. Dijkstra saca de una cola de prioridad
(`heapq`) la zona con menor costo acumulado y relaja sus vecinos; como las distancias son positivas, el
primer costo con que sale una zona ya es el minimo. Cuesta O((V + E) log V); aqui V = 5 y E = 6, asi que
es trivial. BFS (O(V + E)) bastaria si todas las distancias valieran lo mismo (el costo seria el
numero de saltos); aqui se usa solo para comprobar que el mapa sea conexo. Con distancias negativas
Dijkstra seria incorrecto: por eso se exige que sean enteros positivos.

Costos reales desde la Plaza: Parque 1, Colegio 2, Barrio 2, Alcaldia 2. El viaje mas largo
(Alcaldia - Barrio, Alcaldia - Colegio) cuesta 4: mas que los 3 de energia de una publicacion, asi
que se llega por tramos a lo largo de varias publicaciones (la posicion se conserva).

**Evidencia por zona** (`models/pistas.py`, datos en `data/events.json`). Cada noticia deja de 2 a 3
evidencias, cada una en una zona distinta: `{id, lugar, tipo (testigo, documento, grabacion), titulo,
hallazgo, senal (falsa/verdadera/neutra)}`. Al llegar a la zona (o al abrir la noticia si el jugador ya
esta ahi) la evidencia se revela como una pista mas: entra en el mismo registro que las pistas de la
tarjeta, en el veredicto y en el texto de la consecuencia, y se puede editar sin tocar codigo.

**Energia y costo.** Hay una sola energia por publicacion (3). Revisar una pista de la tarjeta cuesta 1
o 2 y viajar cuesta la distancia del camino mas corto. Por revisar hay mas que energia (la tarjeta
sola cuesta 6 o mas), asi que hay que elegir. Decidir cuesta 0: las cuatro acciones siempre estan
disponibles, aunque la energia llegue a 0.

**Como afecta la decision.** Verificar y Reportar NO exigen estar en ninguna zona: su resultado depende
del *respaldo* reunido (`Investigacion.respaldo`): 0 nada, 1 solo pistas de la tarjeta, 2 evidencia de
campo (la del mapa). Solo se atenuan los beneficios; los perjuicios de equivocarse no se abaratan.

| Respaldo | Verificar (beneficios y friccion sobre el grafo social) | Reportar |
|---|---|---|
| 0 nada | 15% | Rechazado: no pasa nada en el grafo y baja la confianza |
| 1 tarjeta | 40% | Limita al autor (sus conexiones conservan el 60% del peso; los beneficios del reporte, 30%) |
| 2 campo | 100% | Aceptado: se cortan las conexiones del autor |

Reportar cuenta solo lo que apunta a FALSA (lo que justifica un reporte); Verificar cuenta cualquier
senal que no sea neutra. Por eso reportar una noticia verdadera siempre se rechaza.

## 4. Como se combinan en una decision

Ejemplo: noticia falsa de la tarjeta "@vecina_barrio" (el colegio se cierra), jugador en la Plaza con
3 de energia.

1. Mira la tarjeta: revisa la cuenta sospechosa (1). Le quedan 2.
2. Viaja al Colegio (Dijkstra: Plaza - Colegio, costo 2). Al llegar se revela el testigo (la directora:
   no hay ninguna orden de cierre). Le quedan 0. Ya tiene respaldo de campo (2).
3. Elige Reportar: el arbol aporta sus beneficios completos, el grafo social corta las conexiones del
   autor y se anima la propagacion; el texto de la consecuencia usa la variante de la directora.
4. Si hubiera decidido sin investigar, Reportar se habria rechazado (pierde confianza) y Verificar
   habria rendido el 15%.

### 4.1 Balance (etapa 8)

Medido con `tools/balance.py` (300 partidas por politica, semillas fijas, rol Ciudadano). Se gana una
partida si termina con desinformacion < 40 e informacion verificada > 50.

| Politica | Antes: desinf. | Antes: verif. | Antes: gana | Despues: desinf. | Despues: verif. | Despues: gana |
|---|---|---|---|---|---|---|
| Ignorar siempre | 88.0 | 61.3 | 0% | 75.3 | 67.4 | 3% |
| Compartir siempre | 97.5 | 72.9 | 0% | 96.7 | 85.1 | 0% |
| Verificar siempre (a ciegas) | 29.8 | 97.0 | 94% | 44.6 | 97.0 | 43% |
| Investigar con criterio | 19.0 | 98.1 | 100% | 28.7 | 99.3 | 82% |

"Antes" son los 5 eventos, energia 5 y Verificar 50/75/100%; "despues" son 18 eventos (8 por partida),
energia 3 y los factores nuevos. Con los otros tres roles, "gana" para investigar con criterio queda entre
86% y 91%, verificar a ciegas entre 52% y 53% e ignorar entre 2% y 12% (el Periodista).

El resultado depende de la habilidad: investigar con criterio y decidir con el respaldo gana la mayoria
de las partidas pero no todas, verificar a ciegas queda a medio camino y compartir o ignorar sin mirar
pierden. Lo que se ajusto, sin cambiar la estructura: `FUERZA_VERIFICAR` (0.5/0.75/1 -> 0.15/0.4/1),
`FUERZA_REPORTAR` (0/0.6/1 -> 0/0.3/1), `FACTOR_LIMITE_REPORTE` (0.5 -> 0.6), `ENERGIA_POR_NOTICIA`
(5 -> 3) y el tope de desinformacion de una propagacion falsa (12 -> 24, `PROPAGACION_FALSA`).

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
- **Por que Dijkstra y no BFS en el grafo de la ciudad?** El viaje cuesta la suma de distancias y el
  camino con menos saltos no siempre es el mas barato (Barrio - Plaza directo: 3; por el Parque: 2).
  BFS solo basta si todas las distancias son iguales; aqui se usa para validar que el mapa sea conexo.
- **Que pasa si hubiera una distancia negativa?** Dijkstra daria resultados incorrectos (supone que
  el primer costo con que sale una zona ya es el minimo). Por eso `agregar_conexion` exige enteros >= 1.
- **Por que los rumores no se propagan por el mapa?** Un rumor viaja entre personas (grafo social); un
  lugar no "se contagia". El mapa sirve para investigar: tiene evidencia y un costo de desplazamiento.
- **Por que Verificar y Reportar no exigen estar en una zona?** Porque lo que importa es lo que el
  jugador pudo demostrar: la evidencia de campo (que obliga a viajar) da el efecto completo, la tarjeta
  da uno parcial y sin nada el reporte se rechaza.
- **Como se elimina un vertice?** Se borra su entrada (las salientes) y se hace `pop` en cada
  diccionario de los demas (las entrantes): O(V).
- **Por que Reportar elimina aristas y Verificar solo baja pesos?** Reportar actua sobre una
  cuenta (se corta del todo); Verificar frena, pero la noticia puede seguir circulando.
- **Por que investigar gasta energia y no tiempo de juego?** Porque asi investigar no delata si una
  noticia es falsa: ninguna otra cosa cambia en la ciudad al revisar o viajar.
- **Es serializable?** Si: `to_dict` / `from_dict` en el grafo social, el grafo de la ciudad, las
  noticias (con pistas y evidencias) y la investigacion, pensado para el servidor de sockets de la
  entrega final.

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
print(c.ruta("barrio", "plaza"))                # Ruta(zonas=('barrio', 'parque', 'plaza'), costo=2): Dijkstra
print(c.saltos("barrio")["plaza"])              # 1: BFS cuenta saltos (la via directa), pero cuesta 3
print(c.costos_desde("plaza"))                  # costo de viajar a cada zona desde la Plaza
```

En la ciudad imprime `Ruta(zonas=('barrio', 'parque', 'plaza'), costo=2)`, `1` y
`{'plaza': 0, 'parque': 1, 'colegio': 2, 'alcaldia': 2, 'barrio': 2}`. Con la semilla 1 el primero imprime
`(('jugador',), ('mateo', 'lina'), ('tomas', 'sofia', 'gael'), ('isabela', 'daniela'),
('esteban',), ('renata',))` y 9 personas alcanzadas.

Las pruebas unitarias (`tests/test_grafo_social.py`, `test_grafo_ciudad.py` con Dijkstra comparado
contra Floyd-Warshall, `test_propagacion.py`, `test_evidencia_modelo.py`) tambien sirven como
demostracion de cada operacion.

## 7. Como repetir las pruebas y las cifras

```bash
python -m unittest discover -s tests                 # todas las pruebas, sin ventana (SDL dummy)
python -m unittest tests.test_partida_completa       # partidas completas del jugador automatico
python tools/balance.py 300                          # tabla de balance: 300 partidas por politica (unos 10 s)
python tools/balance.py 300 --rol 1                  # con otro rol (0 Ciudadano, 1 Periodista, 2 Influencer, 3 Candidato)
```

`tests/test_partida_completa.py` juega el flujo Menu -> Seleccion -> Escena -> Fin con teclado y
mouse, los 4 roles y varias politicas de juego (azar, compartir, ignorar, viajar a la evidencia,
informado y una que agota toda la energia), dibujando en los 3 temas y comprobando invariantes en
cada fotograma, entre ellas que la energia gastada en pistas mas viajes mas la restante sea siempre
el total. `tests/test_viajes_escena.py` prueba los viajes, la evidencia y el respaldo en la escena.

## 8. Limites conocidos

- El balance (seccion 4.1) es un primer ajuste hecho con un jugador automatico, no con personas. Las perillas
  estan en constantes (`PROPAGACION_FALSA` y `PROPAGACION_VERDADERA` en `structures/grafo_social.py`,
  `FUERZA_VERIFICAR`, `FUERZA_REPORTAR` y `FACTOR_LIMITE_REPORTE` en `structures/propagacion.py`,
  `ENERGIA_POR_NOTICIA` en `models/pistas.py`). La informacion verificada final es alta con casi cualquier
  politica (67 o mas), asi que en la practica la desinformacion es lo que decide si se gana.
- Ignorar siempre gana 2-3% de las partidas (hasta 12% con el Periodista) cuando el sorteo trae pocas noticias
  falsas: esa parte depende de los efectos de cada evento, no de las perillas anteriores.
- El grafo social y el de la ciudad son datos fijos de ejemplo (14 ciudadanos, 5 zonas) y cada noticia
  tiene solo 2 o 3 evidencias. Con 3 de energia algunos lugares quedan a mas de un viaje (por ejemplo
  Alcaldia - Barrio cuesta 4).
- Aun no hay modo de sustentacion en Pygame (ver la hoja de ruta en CLAUDE.md).
