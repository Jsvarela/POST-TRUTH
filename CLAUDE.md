# CLAUDE.md - Post & Truth (Alcalde Digital)

Videojuego educativo en Python + Pygame para el laboratorio "Alcalde Digital" de Estructura de Datos II (Universidad del Norte). Este archivo es el contexto permanente del proyecto: leelo completo antes de escribir codigo.

## 1. Resumen del juego

- Ciudad Nova esta en elecciones. Los ciudadanos usan la red ficticia Civitas para publicar, compartir, verificar y reportar informacion.
- Circulan publicaciones verdaderas, opiniones y noticias falsas. El jugador decide por cada publicacion: Compartir, Verificar, Ignorar o Reportar.
- Objetivo: terminar el proceso electoral con la ciudad lo mas sana posible (informacion verificada, convivencia, confianza, bienestar, participacion responsable) y evitar el aumento de desinformacion, conflictos y rumores.
- El juego NO usa preguntas explicitas de conocimiento: el aprendizaje sale de las decisiones y sus consecuencias.
- Mensaje educativo a fomentar: verificar antes de compartir, reportar contenido danino, no amplificar rumores.

## 1.1 Direccion de juego (vision actual - PRIORIDAD DE DISENO)

Retroalimentacion de la profesora sobre el prototipo en Tkinter: "se ve como un laboratorio", ella espera un JUEGO. Por eso la experiencia pasa de paneles de indicadores a una novela visual de toma de decisiones, inspirada en el estilo de juegos narrativos de decisiones sobre noticias (referencia de genero, no copiar arte, nombres ni personajes de ningun juego existente; todo el arte y los personajes son originales).

Pilares:
1. Seleccion de personaje: el jugador elige primero su ROL (Ciudadano, Periodista, Influencer, Candidato) y luego un personaje masculino o femenino de ese rol. Cada rol tiene su apariencia y su habilidad propia.
2. Escena de dialogo: el personaje del jugador se muestra a un costado de la pantalla; el texto narrativo y las opciones de decision van abajo en una caja de dialogo. Los indicadores de la ciudad se muestran de forma compacta (HUD), no como protagonista.
3. Noticias interactivas, no solo texto:
   - Tarjeta tipo post de Civitas: autor, avatar, texto, imagen, likes y comentarios. El jugador interactua con la tarjeta para decidir (Compartir, Verificar, Ignorar, Reportar).
   - Pistas para investigar: partes clicables de la noticia (fuente, fecha, imagen, cuenta que publica) que revelan senales de falsedad antes de decidir. Investigar cuesta tiempo (temporizador), lo que obliga a elegir.
   - Llamadas filtradas: audios o llamadas telefonicas "filtradas" que el jugador puede escuchar o leer (en pantalla, con subtitulos) y que sirven de evidencia para demostrar que una noticia es falsa (o verdadera). Son un tipo de pista que se desbloquea con ciertas acciones, por ejemplo Verificar o el rol Periodista.
   - Propagacion visible: al compartir, se ve en pantalla como la publicacion viaja por el grafo social (nodos y olas), mostrando quien la recibe y que tan rapido.
   - Temporizador en noticias virales.
4. Las consecuencias deben verse y sentirse: reacciones del personaje, mensajes de ciudadanos, cambios visuales en la ciudad y retroalimentacion despues de cada decision.

Arte: los personajes se dibujan con codigo (formas de Pygame) en `views/personaje_view.py`, con variantes por rol y genero (colores, accesorios, peinado) leidas del tema activo. Dejar la carga de imagenes PNG desde `assets/` como reemplazo futuro sin cambiar el modelo (el modelo solo guarda ids de apariencia, nunca superficies de Pygame).

Como encajan las estructuras: el arbol de decisiones define las ramas de cada escena y sus consecuencias (las pistas y llamadas filtradas pueden ser nodos del arbol); el grafo social define la propagacion que se visualiza; el grafo de la ciudad define las zonas/escenarios.

## 2. Estado actual y fechas

- Stack: Python 3.x + Pygame. Repo: github.com/Jsvarela/POST-TRUTH. Rama de trabajo: `migracion-pygame` (todo se actualiza en esa unica rama; `main` y `jose-redesign` no se tocan).
- El prototipo de Tkinter (tag `tkinter-entrega1`, `src/post_truth/app.py`) esta obsoleto; todo codigo nuevo va sobre el game loop de Pygame manteniendo MVC.
- Entregas (cada una vale 10%):
  - Entrega 1, semana 8 (14-18 sep 2026): arboles. Ya paso.
  - Entrega 2, semana 12 (19-23 oct 2026): grafos, operaciones sobre grafos, integracion con arboles y con la mecanica, visualizacion grafica. CERRADA: ver `docs/entrega2_grafos.md`.
  - Entrega final, semana 16 (16-20 nov 2026): todo integrado y estable. PRIORIDAD ACTUAL (ver hoja de ruta, seccion 7).
  - VI Feria Gamer: 26 nov 2026.
- El repositorio debe mostrar commits de cada integrante: commits pequenos, frecuentes y con mensajes claros.

## 3. Estructuras de datos (nucleo del proyecto)

Cada estructura debe resolver un problema real del juego, no estar solo para cumplir el requisito. Todos los integrantes deben poder defender: que problema resuelve, por que esa estructura, que variante, como se inserta/elimina y como se recorre.

### 3.1 Arbol de decisiones (N-ario) - `decision_tree.py` (HECHO)
- Modela noticias/eventos y la ramificacion de consecuencias segun la accion elegida (Compartir, Verificar, Ignorar, Reportar). Ejemplo del laboratorio: PUBLICACION -> que hacer -> Verificar -> es verdadera? -> Si: Compartir / No: Reportar.
- Insercion dinamica de ramas; eliminacion de subarboles.
- Recorridos: DFS para acumular el impacto de una cadena de decisiones; BFS para explorar eventos por nivel.
- Implementado en `decision_tree.py` (`DecisionTree`, `DecisionNode` con `Impact` y `tipo`), cargado desde `data/events.json`. Se quedo ahi en vez de moverlo a `structures/` para no romper imports ni pruebas.

### 3.2 Grafo social - `structures/grafo_social.py` (HECHO)
- Lista de adyacencia dirigida y ponderada. Vertices: ciudadanos con rol (Ciudadano, Periodista, Influencer, Candidato). Aristas: amistad, confianza o seguimiento; el peso es la probabilidad/velocidad de propagacion.
- Funcion en el juego: simular como se propaga una publicacion al compartirla. Debe determinar: quien la recibe, cuantas personas, que tan rapido, si es verdadera o falsa y que consecuencias genera.
- Algoritmos: BFS por olas (nivel = ola de propagacion), DFS, Dijkstra para rutas/velocidad. Elegir segun la necesidad y explicar por que.
- Implementado: BFS por olas O(V+E) para quien recibe y cuantos; Dijkstra (costo 1/peso) O(E log V) solo para el tiempo de llegada; DFS no se usa. Reglas de cada decision en `structures/propagacion.py`.

### 3.3 Grafo de la ciudad - `structures/grafo_ciudad.py` (HECHO)
- Vertices: zonas (Colegio, Barrio, Parque, Plaza, Alcaldia). Aristas: conexiones fisicas con distancia. Funcion en el juego: es el MAPA DE LUGARES DONDE SE INVESTIGA. Cada noticia deja evidencia (testigo, documento, grabacion) en zonas del mapa; llegar cuesta energia (la distancia del camino mas corto) y al llegar se revela como una pista mas. Los rumores NO se propagan por zonas: eso ocurre solo en el grafo social, entre personas.
- Implementado: no dirigido y PONDERADO (distancia entera >= 1 en `data/grafo_ciudad.json`). **Dijkstra** (`ruta`, `costos_desde`, heapq, O((V+E) log V)) da el costo del viaje: el camino de menos saltos no siempre es el mas barato (Barrio-Plaza directo cuesta 3, por el Parque 2); BFS (O(V+E)) solo basta si todas las distancias son iguales y aqui se usa para validar que el mapa sea conexo. El jugador va a CUALQUIER zona (clic o Q W E R T), su posicion persiste entre publicaciones y comparte con la tarjeta una sola energia por publicacion (5). La evidencia vive en `data/events.json` (`evidencias`). Verificar y Reportar no exigen estar en una zona: rinden segun el respaldo reunido (0 nada, 1 tarjeta, 2 campo): Verificar 50/75/100%, Reportar rechazado/limita/corta.

## 4. Arquitectura (MVC + patron State)

```
POST-TRUTH/
├── src/main.py                      # entrada: lanza la App de Pygame
├── src/post_truth/
│   ├── pygame_app.py                # game loop (clase App), 60 FPS, dt en segundos
│   ├── config.py                    # constantes sin dependencias de pygame
│   ├── models/                      # logica pura: dominio.py (Impact, NewsEvent, Role), personaje.py (Personaje, Genero), intro.py (Intro, Lamina, Candidato), publicacion.py (Autor, Avatar, Imagen), pistas.py (Pista, Investigacion, VarianteTexto)
│   ├── game_state.py                # CityState: indicadores (ya incluye conflictos)
│   ├── decision_tree.py             # DecisionTree N-ario, DFS/BFS (entrega 1, se reutiliza)
│   ├── structures/                  # grafo_social.py (GrafoSocial), propagacion.py (reglas de Compartir/Verificar/Reportar), grafo_ciudad.py (mapa ponderado, Dijkstra)
│   ├── views/                       # theme, componentes (Boton, Panel, CajaDialogo), personaje_view, seleccion_view, escena_view, grafo_view (animacion de propagacion), mapa_view (minimapa), zona_view (fondos), retrato_view (candidatos), intro_view (laminas con fundido), tarjeta_civitas_view (post con pistas clicables), menu_view
│   ├── controllers/                 # base_state, state_manager, menu_state, intro_state, seleccion_state, escena_state (game_state: prototipo previo)
│   └── app.py                       # version Tkinter (tag tkinter-entrega1), a retirar
├── data/events.json                 # eventos, tarjeta de Civitas (autor, fuente, fecha, imagen, pistas) y ramas de decision (con "tipo" y variantes de texto)
├── data/grafo_social.json           # 14 ciudadanos y 37 relaciones del grafo social de ejemplo
├── data/grafo_ciudad.json           # 5 zonas (Colegio, Barrio, Parque, Plaza, Alcaldia) y sus conexiones
├── data/intro.json                  # textos de la introduccion, zonas, 4 candidatos y publicaciones del feed
├── docs/                            # entrega1_arboles.md, entrega2_grafos.md (guias de sustentacion)
└── tests/                           # unitarias, integracion y test_partida_completa.py (bot que juega partidas)
```

Modelos en `models/`: `Role` (ya existia) y `Personaje` (rol, genero, id de apariencia) estan hechos. Pendientes: habilidad por rol, `Pista` (incluye llamada filtrada) y `Escena` (noticia, pistas, opciones).

Reglas de dependencia: `models` y `structures` no importan nada de `views` ni `controllers`. Las vistas leen datos, nunca los modifican. Los controladores conectan eventos con el modelo.

Estados: hechos `MenuState`, `IntroState`, `SeleccionState` y `EscenaState` (`GameState` es el prototipo previo, ya fuera del flujo). Previstos: `HelpState` y `ResultadoState` (eleccion del alcalde); `CivitasFeedState` se integra en la escena si hace falta.

## 5. Requisitos del laboratorio que el codigo debe cubrir

- Jugadores y roles: 2 a 4 jugadores; roles con habilidades distintas. Ciudadano (interactua con responsabilidad), Periodista (investiga y detecta falsas), Influencer (mayor alcance al compartir), Candidato (construye confianza y enfrenta rumores).
- Indicadores de Ciudad Nova (todos entre 0 y 100): Informacion verificada, Confianza, Convivencia, Bienestar digital, Desinformacion y Conflictos. `CityState` (game_state.py) ya incluye `conflictos`.
- Propagacion de publicaciones por el grafo social (seccion 3.2).
- Aleatoriedad: eventos como noticia falsa, publicacion viral, rumor sobre un candidato, discusion entre ciudadanos, noticia verdadera, campana de convivencia, reporte de contenido. El resultado debe variar entre partidas, pero tambien debe haber componentes que dependan de la habilidad del jugador, no solo del azar.
- Habilidad: decisiones con tiempo limitado (ejemplo: "Informacion viral, tiempo restante 10 s" con botones Verificar/Compartir/Reportar/Ignorar). Usar `dt` o `pygame.time.get_ticks()`.
- Puntuacion: individual por jugador mas resultado general de la ciudad. Acciones responsables dan reputacion, confianza, puntos, logros; las irresponsables restan reputacion y confianza y suben conflictos y desinformacion. Siempre dar retroalimentacion visible de las consecuencias.
- Eleccion del alcalde al final, calculada a partir del comportamiento durante la partida (confianza, reputacion, participacion, pocos conflictos, informacion verificada).
- Multijugador local con arquitectura cliente-servidor, preferiblemente sockets. El servidor mantiene y sincroniza estado de la partida, jugadores, publicaciones, relaciones, eventos, puntuaciones, turnos e informacion compartida. Por eso la logica de `models/` y `structures/` debe ser serializable (diccionarios/JSON) y no depender de la interfaz.
- Interfaz grafica minima: ciudad, personaje del jugador, publicaciones, opciones, estado de la partida, puntuacion, indicadores y resultados de acciones. Nada de solo consola.
- Inclusividad: al menos un componente (ya hay temas de alto contraste y daltonismo en `views/theme.py`); documentar que dificultad atiende.
- Ayuda: seccion AYUDA con objetivo, reglas, funcion de botones, funcion de cada personaje, como ganar y significado de indicadores; ademas mensajes guia durante la partida.
- Elementos motivadores: sonidos, animaciones, logros, mensajes, cambios visuales, efectos al ganar/perder. Deben aportar a la experiencia, no ser decoracion.

## 6. Reglas de trabajo para Claude

1. POO y modularidad: una clase por archivo cuando sea razonable, nombres claros en espanol consistentes con el codigo existente, type hints.
2. Pygame: usar `pygame.event.get()` y `clock.tick(60)`. Nunca `time.sleep()` ni bucles bloqueantes; temporizadores con `dt` o `get_ticks()`. Renderizado de texto e imagenes limpio y escalable.
3. Estructuras de datos: al implementar o modificar arboles/grafos, explicar brevemente el razonamiento algoritmico (que recorrido, por que, complejidad) en comentarios y en la respuesta. Esto sirve para la sustentacion.
4. Accesibilidad: todo color sale de `views/theme.py`; no usar colores fijos en las vistas. Mantener soporte de alto contraste y daltonismo.
5. Mantener el modelo desacoplado de la interfaz y serializable (pensando en el servidor de sockets).
6. Comentarios utiles en el codigo (el porque, no solo el que).
7. Cambios pequenos y enfocados: una tarea por vez, rama `feature/<tema>`, commits pequenos con mensaje claro. No reescribir archivos completos si basta un cambio puntual.
8. Probar lo que se escribe (por ejemplo, ejecutar con `SDL_VIDEODRIVER=dummy` para verificar sin ventana) y avisar que se probo y que no.
9. Si algo del laboratorio es ambiguo, preguntar antes de asumir. Si una decision afecta la sustentacion (por que arbol/grafo, que variante), explicarla.

## 7. Hoja de ruta

Hecho (entregas 1 y 2):
- Esqueleto Pygame: game loop, StateManager (con `al_entrar`), temas de accesibilidad (normal, alto contraste, daltonismo).
- Modelo: `Impact`, `NewsEvent`, `Role`, `Personaje`, `CityState` (con conflictos) y `DecisionTree`.
- Componentes UI (`views/componentes.py`), seleccion de rol y personaje (4 roles x hombre/mujer dibujados con formas) y escena de dialogo alimentada por el `DecisionTree`.
- Grafo social: propagacion BFS por olas + Dijkstra, vista animada, integrada con Compartir/Verificar/Reportar.
- Grafo de la ciudad (rediseno de la etapa 3): mapa ponderado de lugares donde se investiga. Viajar a cualquier zona cuesta la distancia del camino mas corto (Dijkstra) en la misma energia que la tarjeta; cada zona guarda evidencia de la noticia; minimapa con distancias en las vias, ruta con su costo, pin de posicion y rombo de evidencia pendiente; fondos por zona. Se eliminaron los rumores por zonas, las rondas y "Desmentir aqui".
- Introduccion (etapa 5): 6 laminas con fundidos y texto letra por letra (`IntroState`, `intro_view`, `retrato_view`, `models/intro.py`, `data/intro.json`). Flujo Menu -> Intro -> Seleccion -> Escena: sale sola la primera vez de la sesion, con I desde el menu se repite y con ESC se salta. Los cuatro candidatos (Juan, Maria, Andres, Lucia) conectan con las noticias y el grafo social; la futura eleccion del alcalde los usara.
- Noticias interactivas (etapa 6): cada publicacion es una tarjeta de Civitas (`views/tarjeta_civitas_view.py`) con zonas clicables que esconden pistas (`models/pistas.py`, `models/publicacion.py`, `events.json`). Investigar gasta energia (5 por publicacion, compartida con los viajes del mapa; hay mas por revisar que energia; hay pistas neutras); lo descubierto (pistas y evidencia de campo) cambia el texto de consecuencia (variantes en `events.json`) y gradua Verificar y Reportar (respaldo 0/1/2). La tarjeta no muestra el titulo del evento para no delatar noticias falsas.
- Pruebas: unitarias, de integracion y partidas completas con un bot (`tests/test_partida_completa.py`). Documentacion de sustentacion en `docs/`.

Siguiente (entrega final, en este orden sugerido; el aspecto de juego sigue siendo prioridad):
1. Roles con habilidades propias de verdad (hoy el rol solo escala el impacto y la propagacion): p. ej. el Periodista investiga pistas con descuento de energia y detecta falsas.
2. Llamadas filtradas (audios o llamadas con subtitulos, como un tipo de pista que se desbloquea con ciertas acciones o con el rol Periodista) y temporizador en noticias virales (`dt`). La tarjeta de Civitas con pistas clicables ya esta hecha (etapa 6).
3. Eventos aleatorios (noticia falsa, publicacion viral, rumor sobre un candidato, discusion, campana de convivencia, reporte) y mas contenido: eventos, zonas y ciudadanos. Balancear: compartir o ignorar siempre sigue dejando la desinformacion cerca de 100, mientras que investigar con criterio la deja en 12-16 (ver `docs/entrega2_grafos.md`, secciones 4 y 8); ajustar `FUERZA_VERIFICAR` / `FUERZA_REPORTAR` y los topes de propagacion.
4. Puntuacion individual por jugador, logros y eleccion del alcalde (`ResultadoState`) calculada con confianza, reputacion, participacion, pocos conflictos e informacion verificada.
5. `HelpState` (AYUDA: objetivo, reglas, botones, personajes, como ganar, indicadores), mensajes guia durante la partida y documentar la inclusividad (alto contraste y daltonismo).
6. Sonidos, animaciones y efectos al ganar/perder que aporten a la experiencia.
7. Multijugador local cliente-servidor con sockets: el servidor mantiene el estado; el modelo ya es serializable (`to_dict`/`from_dict`).
8. Modo de sustentacion en Pygame (arbol y grafos): hoy solo existe el panel Tkinter del arbol; los grafos se demuestran con los fragmentos de `docs/entrega2_grafos.md`.
9. Retirar el codigo Tkinter (`app.py`) y el prototipo `GameState` cuando ya no hagan falta.

## 8. Comandos utiles

```
pip install -r requirements.txt
python src/main.py
python -m unittest discover -s tests              # todas las pruebas, sin ventana
SDL_VIDEODRIVER=dummy python -m unittest tests.test_partida_completa   # Linux/macOS (en Windows las pruebas ya fijan el driver dummy)
```
