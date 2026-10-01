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

- Stack: Python 3.x + Pygame. Repo: github.com/Jsvarela/POST-TRUTH (rama main).
- Se migra el prototipo de Tkinter a Pygame manteniendo MVC. El esqueleto base ya existe (ver seccion 4). Todo codigo nuevo va sobre el game loop de Pygame.
- Entregas (cada una vale 10%):
  - Entrega 1, semana 8 (14-18 sep 2026): arboles. Ya paso.
  - Entrega 2, semana 12 (19-23 oct 2026): grafos, operaciones sobre grafos, integracion con arboles y con la mecanica, visualizacion grafica. PRIORIDAD ACTUAL.
  - Entrega final, semana 16 (16-20 nov 2026): todo integrado y estable.
  - VI Feria Gamer: 26 nov 2026.
- El repositorio debe mostrar commits de cada integrante: commits pequenos, frecuentes y con mensajes claros.

## 3. Estructuras de datos (nucleo del proyecto)

Cada estructura debe resolver un problema real del juego, no estar solo para cumplir el requisito. Todos los integrantes deben poder defender: que problema resuelve, por que esa estructura, que variante, como se inserta/elimina y como se recorre.

### 3.1 Arbol de decisiones (N-ario) - `structures/arbol_decision.py`
- Modela noticias/eventos y la ramificacion de consecuencias segun la accion elegida (Compartir, Verificar, Ignorar, Reportar). Ejemplo del laboratorio: PUBLICACION -> que hacer -> Verificar -> es verdadera? -> Si: Compartir / No: Reportar.
- Insercion dinamica de ramas; eliminacion de subarboles.
- Recorridos: DFS para acumular el impacto de una cadena de decisiones; BFS para explorar eventos por nivel.
- Nodo base: `Noticia` con `hijos: dict[Accion, Noticia]` (ya implementado en `models/noticia.py`).

### 3.2 Grafo social - `structures/grafo_social.py`
- Lista de adyacencia dirigida y ponderada. Vertices: ciudadanos con rol (Ciudadano, Periodista, Influencer, Candidato). Aristas: amistad, confianza o seguimiento; el peso es la probabilidad/velocidad de propagacion.
- Funcion en el juego: simular como se propaga una publicacion al compartirla. Debe determinar: quien la recibe, cuantas personas, que tan rapido, si es verdadera o falsa y que consecuencias genera.
- Algoritmos: BFS por olas (nivel = ola de propagacion), DFS, Dijkstra para rutas/velocidad. Elegir segun la necesidad y explicar por que.

### 3.3 Grafo de la ciudad - `structures/grafo_ciudad.py`
- Vertices: zonas (Colegio, Barrio, Parque, Plaza, Alcaldia). Aristas: conexiones fisicas. Debe tener un uso real en la mecanica (por ejemplo, donde se concentra un rumor o por donde se mueve el jugador).

## 4. Arquitectura (MVC + patron State)

```
POST-TRUTH/
├── src/main.py                      # entrada: lanza la App de Pygame
├── src/post_truth/
│   ├── pygame_app.py                # game loop (clase App), 60 FPS, dt en segundos
│   ├── config.py                    # constantes sin dependencias de pygame
│   ├── models.py                    # Impact, NewsEvent, Role (entrega 1, se reutiliza)
│   ├── game_state.py                # CityState: indicadores (ya incluye conflictos)
│   ├── decision_tree.py             # DecisionTree N-ario, DFS/BFS (entrega 1, se reutiliza)
│   ├── structures/                  # grafo_social.py, grafo_ciudad.py (entrega 2)
│   ├── views/                       # theme.py, menu_view.py, game_view.py
│   ├── controllers/                 # base_state, state_manager, menu_state, game_state
│   └── app.py                       # version Tkinter (tag tkinter-entrega1), a retirar
├── data/events.json                 # eventos y ramas de decision
└── tests/
```

Modelos nuevos previstos en `models/`: `Rol`, `Personaje` (rol, genero, id de apariencia, habilidad), `Pista` (incluye llamada filtrada), `Escena` (noticia, pistas, opciones).

Reglas de dependencia: `models` y `structures` no importan nada de `views` ni `controllers`. Las vistas leen datos, nunca los modifican. Los controladores conectan eventos con el modelo.

Estados previstos: `MenuState`, `GameState`, `CivitasFeedState`, `HelpState`, y mas adelante `ResultadoState` (eleccion del alcalde).

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

Hecho:
- Esqueleto Pygame: `main.py`, StateManager, estados Menu y Juego, temas de accesibilidad.
- Modelo base: `Noticia`, `Impacto`, `Accion`, `EstadoCiudad`.

Siguiente (orden sugerido; la entrega 2 evalua grafos pero la profesora pide ante todo que se vea como juego, asi que el aspecto de juego avanza en paralelo):
1. Componentes UI reutilizables (`views/componentes.py`): Boton, Panel, Temporizador, caja de dialogo.
2. Seleccion de rol y personaje (`seleccion_state.py`) con personajes dibujados por codigo, hombre y mujer por rol.
3. Escena de dialogo (`escena_state.py`): personaje a un costado, texto y opciones abajo, HUD de indicadores compacto.
4. Noticia como tarjeta de Civitas con pistas clicables y llamadas filtradas.
5. `structures/arbol_decision.py`: arbol N-ario (insercion, eliminacion, DFS/BFS) que alimenta las escenas en lugar de la noticia fija de `GameState`.
6. `structures/grafo_social.py`: lista de adyacencia ponderada; propagacion por olas con BFS; Dijkstra para velocidad. Vista que anima la propagacion.
7. `structures/grafo_ciudad.py` y su uso en la mecanica.
8. Agregar indicador `conflictos`, puntuacion, eventos aleatorios y HelpState.

Despues (entrega final): roles con habilidades, eleccion del alcalde, sonidos/animaciones/logros, servidor y clientes con sockets.

## 8. Comandos utiles

```
pip install pygame
python main.py
SDL_VIDEODRIVER=dummy python -c "from main import App; App()"   # prueba sin ventana (Linux/macOS)
```