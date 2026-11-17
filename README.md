# POST-TRUTH

Videojuego educativo para Estructura de Datos II (laboratorio "Alcalde Digital", Universidad del Norte).
Ciudad Nova esta en elecciones y el jugador decide que hacer con cada publicacion de la red Civitas:
Compartir, Verificar, Ignorar o Reportar.

## Requisitos

- Python 3.10 o superior
- Pygame

```
pip install -r requirements.txt
```

## Ejecutar

```
python src/main.py
```

## Como se juega

La campaña dura cuatro dias y cada dia es un capitulo con pasos en orden, uno a la vez: una escena de apertura, ir al lugar de la noticia, investigarla y decidir, defender la red mientras el rumor corre (el telefono se abre solo), jugar el minijuego del lugar y una escena de cierre. Una cuenta anonima, @VerdadNova, riega un rumor cada dia; al final se revela quien es, se elige al alcalde y el final de la historia depende de como quedo la ciudad (informada, dividida o engañada).

## Controles

- Menu: flechas y Enter o clic; R multijugador; A ayuda; O opciones (tema, volumen, volumen de los pasos, silencio, tiempo extendido, mensajes guia y avance manual de las escenas); I muestra la introduccion completa (al dar Jugar sale una corta); X tiempo extendido
- Seleccion: cada jugador (1 a 4) elige un rol distinto y su personaje; 1 agrega otro jugador y Enter inicia cuando todos tienen rol
- Escenas: Enter avanza el dialogo, ESC salta la escena
- WASD o flechas: caminar libre por la ciudad (8 direcciones). Arriba se ve el dia, el objetivo y la credibilidad; una flecha apunta al lugar
- E: entrar al lugar donde estas (la evidencia aparece sola); adentro, 1-3 o clic: ver la noticia, jugar el minijuego o volver a la calle. Junto a un personaje del dia (circulo sobre la cabeza), mantener E para escucharlo
- G: dibuja el camino mas corto hasta el objetivo
- P o ESC (en la calle): menu de pausa con los indicadores y el minimapa (seguir, ayuda o salir al menu; salir pide confirmacion). P en un minijuego: pausa
- En la noticia: 1-4 decidir; I abre la investigacion. Publicacion: mueve la lupa (raton o flechas) y mantenla sobre algo raro para revelarlo. Testigos: flechas o clic para elegir, Enter para hablar, 1-4 para preguntar. Conclusion: F falsa, V verdadera, N no concluyente
- Telefono Civitas (se abre solo despues de decidir): mueve el escudo (WASD, flechas o raton) para atajar las bolitas rojas y Espacio lanza el desmentido en onda; Tab cambia de pestaña. El dia que la historia lo pide aparece Publicar: flechas o clic para armar el post y Enter para publicarlo
- H: habilidad de tu rol (Periodista: verificar a distancia; Influencer: desmentido viral; Candidato: comunicado; Ciudadano: convivencia vecinal). Y: menu de aliados, 1-3 les pide ayuda. Solo en el paso donde sirven; un aviso lo dice
- Chat bajo presion (Colegio): flechas o A/D mueven a Sofi para atrapar el apoyo y esquivar los ataques; Espacio usa la calma
- Mitin (Plaza y Registraduria): apunta con el raton o WASD, elige la municion por la forma del globo (1 dato, cuadrado; 2 pregunta, circulo; 3 calma, triangulo) y dispara con clic o Espacio; el disparo tarda en llegar
- Rueda de prensa (Alcaldia y Auditorio): A/D o flechas giran el foco hacia quien pregunta; responde con la prueba que pide (1 pista, 2 evidencia, 3 testimonio; Espacio a una trampa X) cuando el marcador esta en la zona verde. Lo que investigaste es tu municion; dura 90 segundos como mucho
- De boca en boca (Barrio): WASD o flechas para correr hasta quien cree el chisme y mantener E cerca para convencerlo
- La primera vez, la rueda y el mitin empiezan con "Como se juega" (demostracion y practica); C lo repite, ESC lo salta
- F1: modo sustentacion con el arbol de decisiones, el grafo social, el grafo de la ciudad y el arbol de dialogo en crudo (BFS, DFS y Dijkstra). F2: ayuda completa, en la seccion de donde estas. Los dos pausan el juego. F3: depuracion del mapa (zonas, colisiones y fronteras)

## Para ferias y demostraciones

- Partida corta: en Opciones (O), "Partida corta" deja la campaña en dos dias (unos 5 minutos) con su eleccion y su final.
- Pantalla de espera: si nadie toca el menu durante 40 segundos, el juego muestra solo la introduccion; cualquier tecla vuelve al menu.
- Tabla de puntajes: al final cada partida da un puntaje de 0 a 100 con medalla; se escriben tres iniciales y Enter lo guarda. La tabla queda en el equipo, en `.post_truth_puntajes.json` de la carpeta del usuario (borrar ese archivo la reinicia).

## Inclusividad

Temas de alto contraste y daltonismo, formas que no dependen del color, tiempo extendido, pausa, avisos visuales de cada sonido, volumen y silencio, ayuda y mensajes guia. Que dificultad atiende cada una: [docs/inclusividad.md](docs/inclusividad.md).

## Fases de la campaña

Cuatro dias, uno por fase (data/fases.json): Inicio de campaña, Debates (abre el Auditorio), Semana final y Dia de eleccion (abre la Registraduria, de noche). Si los conflictos o la desinformacion suben, una protesta cierra una calle; si una zona queda sin camino a la Alcaldia, a sus vecinos no les llegan los desmentidos. Las zonas con mucha desinformacion entran en crisis.

## Rutas de los transeuntes

Cada transeunte elige un destino entre las zonas que puede alcanzar (BFS sobre el grafo de la ciudad) y va por el camino mas corto a pie: Dijkstra sobre una copia del grafo cuyas aristas pesan lo que se camina (centro de una zona, paso de la frontera, centro de la otra). Las fronteras cerradas no son aristas, asi que nunca las cruza; si se cierra una de su ruta, recalcula desde donde esta, y si su zona queda aislada, espera (`src/post_truth/structures/rutas.py`, `models/transeuntes.py`).

## Multijugador

1. Un equipo abre el servidor (desde `src/`):

```
python -m post_truth.red.servidor --puerto 5050
```

2. Cada jugador abre el juego (`python src/main.py`), elige Multijugador en el menu (o R) y escribe su nombre, la IP del servidor y el puerto. En la misma maquina la IP es `127.0.0.1`; en la red local, la IP del equipo del servidor.
3. En la sala de espera cada uno elige un rol distinto (1-4) y su personaje (G). El primero en entrar es el anfitrion e inicia con Enter cuando hay de 2 a 4 jugadores con rol. Los roles libres los juegan aliados.

El servidor guarda la unica `PartidaSesion` y es la autoridad: simula el dia, el rumor en vivo, las fases y el grafo de la ciudad, asi que todos ven la misma red en el telefono y las mismas fronteras en el mapa. Cada cliente tiene una copia (sesion espejo) que el servidor reemplaza unas 10 veces por segundo; las acciones se predicen en local y el servidor las valida. Los demas jugadores se ven en el mapa con su nombre, interpolados entre fotos para que no salten, y lo que hacen sale como aviso. El hilo de red no bloquea el juego: lee y escribe en sus propios hilos y entrega los mensajes por una cola.

El servidor es dueño del director del dia (los pasos del capitulo) y avisa cada cambio de paso a todos:
- Escenas: la apertura, el cierre de cada dia y la revelacion con el final se ven en todos a la vez. Cada jugador puede saltarlas en su equipo; el dia sigue cuando todos los conectados terminaron o tras 90 segundos. El final lo calcula el servidor, asi que todos ven el mismo.
- Turnos: cada dia tiene un jugador de turno, rotando por orden de llegada a la sala. El decide la noticia (una decision por dia) y juega el minijuego del dia; los demas lo ven en vivo. En la consecuencia todos defienden la red juntos. Los roles sin jugador siguen siendo aliados.
- En red los minijuegos son mas grandes y dificiles: la rueda tiene 3 preguntas mas por cada jugador extra y una zona mas angosta, el mitin dura mas y sus globos salen mas seguido, y todos van algo mas rapido. El tiempo extendido es de cada equipo: alarga los minijuegos de quien lo activo; el dia y el reloj de defensa son del servidor y valen igual para todos.

Protocolo: mensajes JSON (UTF-8) sobre TCP, cada uno precedido por 4 bytes big-endian con su largo (maximo 64 KB). Todo mensaje lleva `tipo`; las acciones llevan ademas un numero `n` creciente.
- Cliente -> servidor: `unirse` (nombre o token para reconectar), `elegir_rol`, `iniciar` (solo el anfitrion), `posicion` y `escudo` (unas 10 por segundo), `ver` (abrio la noticia: corre su reloj), `evidencia`, `decidir` (solo el de turno), `aplicar` (vio la propagacion), `continuar`, `investigar`, `concluir`, `testimonio`, `onda`, `publicar`, `habilidad`, `ayuda`, `minijuego` (solo el de turno: `progreso` con su estado unas 5 veces por segundo mientras juega, y `terminar` con su estado al final), `cinematica_fin` (termino o salto la escena), `salir`.
- Servidor -> cliente: `bienvenida` (token), `sala` (con cual es el), `inicio` (la sesion completa), `estado` (foto: la sesion completa con el director, posiciones, eventos numerados y `ack`, el ultimo `n` ya procesado de ese cliente; una foto con `ack` menor al ultimo enviado no pisa la prediccion; ademas `minijuego_vivo` con el minijuego del de turno, `cine` con la escena en curso y `cine_listos` con cuantos ya la terminaron), `paso` (dia, paso del director y jugador de turno), `cinematica` (ids de la escena que todos ven ahora y su espera maxima), `corregir` (posicion rechazada: muro, salto imposible o frontera cerrada), `error` (con `motivo`), `fin` (ganador y puntos).
- Si un jugador se cae, su rol pasa a un aliado y el dia no se detiene: si era su turno, tras una espera de 10 segundos el servidor lo da por llegado al lugar del dia, decide Ignorar por el en la noticia o cuenta su minijuego como perdido. Las escenas solo esperan a los conectados. Al volver con su token recupera su rol. Si el cliente pierde la conexion, vuelve a la pantalla de conectar con el aviso.

## Arte y creditos

- Mapa, edificios, personajes y decorado: pixel art original del proyecto, dibujado en codigo. El mapa (`assets/mapa/`) se genero con una herramienta de desarrollo que no hace falta para jugar y no esta en el repositorio; parte de `data/mapa.json`, `zonas.png` y `colisiones.png`, asi que respeta exactamente donde se camina. Los personajes y el decorado se construyen al vuelo en `src/post_truth/views/pixel_sprites.py` con los colores del tema activo.
- Musica: tres pistas de "15 Melodic RPG Chiptunes" de Aureolus_Omicron (OpenGameArt, https://opengameart.org/content/15-melodic-rpg-chiptunes), licencia CC0, en `assets/musica/`: `menu.ogg` (title screen), `calle.ogg` (town) y `tension.ogg` (battle 1). Los efectos de sonido son tonos generados por codigo.
- Fuentes: Pixelify Sans y Jersey 10 (Google Fonts), bajo la SIL Open Font License 1.1; las licencias estan en `assets/fuentes/`.

## Estructura

- `src/post_truth/decision_tree.py`: arbol n-ario de decisiones
- `src/post_truth/structures/`: grafo social y su propagacion (por olas y en vivo), grafo de la ciudad y rutas, arbol de dialogo y arbol de finales
- `src/post_truth/sesion.py`: la partida (estado y reglas, sin pygame y serializable); `models/director.py` ordena los pasos de cada dia y `models/cinematica.py` interpreta las escenas
- `src/post_truth/models/`, `views/`, `controllers/`: logica, dibujo y estados del juego
- `src/post_truth/red/`: protocolo, servidor, conexion del cliente (hilos y colas) y sesion espejo
- `data/`: publicaciones, grafos, mapa, fases, historia de la campaña, escenas, minijuegos y ayuda en JSON
- `assets/mapa/`: el mapa por capas (mapa.png se ve; zonas.png y colisiones.png son mascaras invisibles)

## Desarrollo con asistente de IA

- Cuando el contexto del chat supere el 50%, hacer `/compact` para optimizar el uso de tokens.
