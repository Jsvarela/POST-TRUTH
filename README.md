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
- 1-4: decidir sobre una publicacion
- I (en el menu): ver la introduccion
- X (en el menu): tiempo extendido (dias y relojes mas largos)
- ESC: saltar la introduccion

## Estructura

- `src/post_truth/decision_tree.py`: arbol n-ario de decisiones
- `src/post_truth/structures/`: grafo social, grafo de la ciudad y propagacion
- `src/post_truth/models/`, `views/`, `controllers/`: logica, dibujo y estados del juego
- `data/`: publicaciones, grafos, mundo e introduccion en JSON
