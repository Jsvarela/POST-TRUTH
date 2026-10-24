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

- WASD o flechas: caminar por la ciudad
- E: entrar a un lugar / buscar evidencia
- G: mostrar la guia hacia la noticia
- 1-3: elegir que hacer en un lugar con varias opciones (noticia, evidencia o minijuego)
- P (en un minijuego): pausa
- T: abrir o cerrar el telefono Civitas (la red en vivo; el mundo corre al 25%). Dentro: 1-4 herramientas, flechas o clic para elegir ciudadano, Tab o clic para cambiar de pestana
- Pestana Publicar del telefono: flechas o clic para armar el post (formato segun el rol, titular, imagen, fuente y tono) y Enter para publicarlo
- 1-4: decidir sobre una publicacion
- I (en la noticia): ventana de investigacion. Publicacion: mueve la lupa (raton o flechas) y mantenla sobre algo raro para revelarlo. Testigos: flechas o clic para elegir, Enter para hablar, 1-4 para preguntar. Conclusion: F falsa, V verdadera, N no concluyente
- I (en el menu): ver la introduccion
- X (en el menu): tiempo extendido (dias y relojes mas largos)
- ESC: saltar la introduccion

## Estructura

- `src/post_truth/decision_tree.py`: arbol n-ario de decisiones
- `src/post_truth/structures/`: grafo social, grafo de la ciudad y propagacion
- `src/post_truth/models/`, `views/`, `controllers/`: logica, dibujo y estados del juego
- `data/`: publicaciones, grafos, mundo e introduccion en JSON

## Desarrollo con asistente de IA

- Cuando el contexto del chat supere el 50%, hacer `/compact` para optimizar el uso de tokens.
