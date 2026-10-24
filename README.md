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
- Menu: flechas y Enter o clic; O abre las opciones (tema, volumen y tiempo extendido)
- G: mostrar la guia hacia la noticia
- Chat bajo presion (Colegio): flechas o A/D mueven a Sofi para atrapar el apoyo y esquivar los ataques; Espacio usa la calma
- Mitin (Plaza): revienta los globos de rumor con 1 dato, 2 pregunta o 3 calma segun su forma
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

## Fases de la campana

Cuatro dias, uno por fase (data/fases.json): Inicio de campana, Debates (abre el Auditorio), Semana final y Dia de eleccion (abre la Registraduria, de noche). Si los conflictos o la desinformacion suben, una protesta cierra una calle; si una zona queda sin camino a la Alcaldia, a sus vecinos no les llegan los desmentidos. Las zonas con mucha desinformacion entran en crisis.

## Estructura

- `src/post_truth/decision_tree.py`: arbol n-ario de decisiones
- `src/post_truth/structures/`: grafo social, grafo de la ciudad y propagacion
- `src/post_truth/models/`, `views/`, `controllers/`: logica, dibujo y estados del juego
- `data/`: publicaciones, grafos, mapa e introduccion en JSON
- `assets/mapa/`: el mapa por capas (mapa.png se ve; zonas.png y colisiones.png son mascaras invisibles)

## Desarrollo con asistente de IA

- Cuando el contexto del chat supere el 50%, hacer `/compact` para optimizar el uso de tokens.
