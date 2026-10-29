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

## Controles

- Seleccion: cada jugador (1 a 4) elige un rol distinto y su personaje; 1 agrega otro jugador y Enter inicia la partida cuando todos tienen rol
- WASD o flechas: caminar libre por la ciudad (8 direcciones)
- E: entrar al lugar donde estas (la evidencia aparece sola); adentro, 1-3 o clic: ver la noticia, jugar el minijuego o volver a la calle
- F3: superposicion de depuracion (zonas, colisiones y fronteras del grafo de la ciudad)
- F1 (en cualquier pantalla): modo sustentacion con el arbol de decisiones, el grafo social, el grafo de la ciudad y el arbol de dialogo en crudo (BFS, DFS y Dijkstra); el juego queda en pausa
- Menu: flechas y Enter o clic; O abre las opciones (tema, volumen, volumen de los pasos, silencio, tiempo extendido y mensajes guia); R multijugador; A ayuda
- F2 (en cualquier pantalla): ayuda completa, abierta en la seccion de donde estas; el juego queda en pausa
- G: mostrar la guia hacia la noticia
- Chat bajo presion (Colegio): flechas o A/D mueven a Sofi para atrapar el apoyo y esquivar los ataques; Espacio usa la calma
- Mitin (Plaza): revienta los globos de rumor con 1 dato, 2 pregunta o 3 calma segun su forma
- Rueda de prensa (Alcaldia): A/D o flechas giran el foco hacia el periodista que pregunta; responde con la prueba que pide su icono (1 pista, triangulo; 2 evidencia, cuadrado; 3 testimonio, circulo) y a una trampa (X) con Espacio, "sin pruebas". Lo que investigaste es tu municion
- De boca en boca (Barrio): WASD o flechas para correr hasta quien cree el chisme y mantener E cerca para convencerlo; con evidencia o credibilidad alta convences mas rapido, y si sueltas un argumento debil se enoja
- En la calle: los transeuntes caminan de zona en zona. Junto a uno con rumor (triangulo) manten E y siguele el paso para convencerlo; junto a un testigo de la noticia (circulo), mantenla para escucharlo. Para esquivarlos, sigue de largo
- P (en un minijuego): pausa
- T: abrir o cerrar el telefono Civitas (la red en vivo; el mundo corre al 25%). Frena el rumor: mueve el escudo (WASD, flechas o raton) para atajar las bolitas rojas y Espacio lanza el desmentido en onda; Tab cambia de pestana
- Pestana Publicar del telefono: flechas o clic para armar el post (formato segun el rol, titular, imagen, fuente y tono) y Enter para publicarlo
- H: usar la habilidad de tu rol (Periodista: verificar a distancia; Influencer: desmentido viral; Candidato: comunicado; Ciudadano: convivencia vecinal)
- Y: menu de aliados (los roles que no elegiste); 1-3 les pide ayuda
- 1-4: decidir sobre una publicacion
- I (en la noticia): ventana de investigacion. Publicacion: mueve la lupa (raton o flechas) y mantenla sobre algo raro para revelarlo. Testigos: flechas o clic para elegir, Enter para hablar, 1-4 para preguntar. Conclusion: F falsa, V verdadera, N no concluyente
- I (en el menu): ver la introduccion
- X (en el menu): tiempo extendido (dias y relojes mas largos)
- ESC: saltar la introduccion

## Inclusividad

Temas de alto contraste y daltonismo, formas que no dependen del color, tiempo extendido, pausa, avisos visuales de cada sonido, volumen y silencio, ayuda y mensajes guia. Que dificultad atiende cada una: [docs/inclusividad.md](docs/inclusividad.md).

## Fases de la campana

Cuatro dias, uno por fase (data/fases.json): Inicio de campana, Debates (abre el Auditorio), Semana final y Dia de eleccion (abre la Registraduria, de noche). Si los conflictos o la desinformacion suben, una protesta cierra una calle; si una zona queda sin camino a la Alcaldia, a sus vecinos no les llegan los desmentidos. Las zonas con mucha desinformacion entran en crisis.

## Rutas de los transeuntes

Cada transeunte elige un destino entre las zonas que puede alcanzar (BFS sobre el grafo de la ciudad) y va por el camino mas corto a pie: Dijkstra sobre una copia del grafo cuyas aristas pesan lo que se camina (centro de una zona, paso de la frontera, centro de la otra). Las fronteras cerradas no son aristas, asi que nunca las cruza; si se cierra una de su ruta, recalcula desde donde esta, y si su zona queda aislada, espera (`src/post_truth/structures/rutas.py`, `models/transeuntes.py`).

## Multijugador

1. Un equipo abre el servidor (desde `src/`):

```
python -m post_truth.red.servidor --puerto 5050
```

2. Cada jugador abre el juego (`python src/main.py`), elige Multijugador en el menu (o R) y escribe su nombre, la IP del servidor y el puerto. En la misma maquina la IP es `127.0.0.1`; en la red local, la IP del equipo del servidor.
3. En la sala de espera cada uno elige un rol distinto (1-4) y su personaje (G). El primero en entrar es el anfitrion e inicia con Enter cuando hay de 2 a 4 jugadores con rol. Los roles libres los juegan aliados.

El servidor guarda la unica `PartidaSesion` y es la autoridad: simula el dia, el rumor en vivo, las fases y el grafo de la ciudad, asi que todos ven la misma red en el telefono y las mismas fronteras en el mapa. Cada cliente tiene una copia (sesion espejo) que el servidor reemplaza unas 10 veces por segundo; las acciones se predicen en local y el servidor las valida. Los demas jugadores se ven en el mapa con su nombre, interpolados entre fotos para que no salten, y lo que hacen sale como aviso. La noticia la decide el jugador de turno; los demas pueden caminar, jugar los minijuegos (se juegan en su equipo y el servidor valida el resultado) y defender la red. El hilo de red no bloquea el juego: lee y escribe en sus propios hilos y entrega los mensajes por una cola.

Protocolo: mensajes JSON (UTF-8) sobre TCP, cada uno precedido por 4 bytes big-endian con su largo (maximo 64 KB). Todo mensaje lleva `tipo`; las acciones llevan ademas un numero `n` creciente.
- Cliente -> servidor: `unirse` (nombre o token para reconectar), `elegir_rol`, `iniciar` (solo el anfitrion), `posicion` y `escudo` (unas 10 por segundo), `ver` (abrio la noticia: corre su reloj), `evidencia`, `decidir`, `aplicar` (vio la propagacion), `continuar`, `investigar`, `concluir`, `testimonio`, `onda`, `publicar`, `habilidad`, `ayuda`, `minijuego` (su estado al terminar), `salir`.
- Servidor -> cliente: `bienvenida` (token), `sala` (con cual es el), `inicio` (la sesion completa), `estado` (foto: la sesion completa, posiciones, eventos numerados y `ack`, el ultimo `n` ya procesado de ese cliente; una foto con `ack` menor al ultimo enviado no pisa la prediccion), `corregir` (posicion rechazada: muro, salto imposible o frontera cerrada), `error` (con `motivo`), `fin` (ganador y puntos).
- Si un jugador se cae, su rol pasa a un aliado; si era su turno, tras una espera se decide Ignorar por el. Al volver con su token recupera su rol. Si el cliente pierde la conexion, vuelve a la pantalla de conectar con el aviso.

## Estructura

- `src/post_truth/decision_tree.py`: arbol n-ario de decisiones
- `src/post_truth/structures/`: grafo social, grafo de la ciudad y propagacion
- `src/post_truth/models/`, `views/`, `controllers/`: logica, dibujo y estados del juego
- `src/post_truth/red/`: protocolo, servidor, conexion del cliente (hilos y colas) y sesion espejo
- `data/`: publicaciones, grafos, mapa e introduccion en JSON
- `assets/mapa/`: el mapa por capas (mapa.png se ve; zonas.png y colisiones.png son mascaras invisibles)

## Desarrollo con asistente de IA

- Cuando el contexto del chat supere el 50%, hacer `/compact` para optimizar el uso de tokens.
