# Inclusividad en Post & Truth

Este documento explica que dificultad atiende cada caracteristica de accesibilidad del juego, como se activa y donde
esta en el codigo. Todo se configura en **Opciones** del menu principal (tecla O) y la ayuda del juego (F2 o
**Ayuda** en el menu) lo resume en la seccion "Accesibilidad".

## Resumen

| Caracteristica | Dificultad que atiende | Como se usa | Donde esta |
|---|---|---|---|
| Tema de alto contraste | Baja vision, pantallas con brillo o reflejos | Opciones > Tema (o T en el menu) | `views/theme.py` (`TEMAS["alto_contraste"]`) |
| Tema para daltonismo | Daltonismo rojo-verde (protanopia, deuteranopia) y tritanopia parcial | Opciones > Tema | `views/theme.py` (`TEMAS["daltonismo"]`) |
| Formas ademas de colores | Cualquier tipo de daltonismo, impresion en blanco y negro, pantallas con mal color | Siempre activo | Vistas del telefono, minijuegos, mundo; leyenda en la ayuda |
| Tiempo extendido | Procesamiento mas lento, dificultades motrices, primera vez con el teclado | Opciones > Tiempo extendido (o X en el menu) | `sesion.FACTOR_TIEMPO_EXTENDIDO`, `ContextoMinijuego.ritmo` |
| Pausa en los minijuegos | Necesidad de pausas, interrupciones, fatiga | P dentro de un minijuego | `controllers/minijuego_state.py` |
| Aviso visual de cada sonido | Sordera, hipoacusia, jugar sin audio o en silencio | Siempre activo | `views/sonido.py` y la tabla de abajo |
| Volumen, volumen de pasos y silencio | Sensibilidad al ruido, hiperacusia, entornos donde no se puede hacer ruido | Opciones > Volumen / Volumen de los pasos / Silencio | `views/sonido.py` (`VOLUMEN`, `PASOS`, `SILENCIO`) |
| Ayuda completa (F2) | Dudas sobre reglas o controles en cualquier momento; memoria de trabajo | F2 en cualquier pantalla (pausa el juego) o Ayuda en el menu | `controllers/ayuda.py`, `data/ayuda.json` |
| Mensajes guia de la primera vez | Carga cognitiva, jugadores nuevos | Opciones > Mensajes guia (Si/No) | `models/guia.py` |
| Teclado completo y raton | Distintas formas de controlar: solo teclado, raton para los menus y el telefono | Siempre activo | Controladores |
| Juego sin texto obligatorio bajo presion | Lectura lenta | Los relojes se alargan con tiempo extendido; las instrucciones quedan a la vista en cada minijuego | `views/minijuego_view.py` |

## Alto contraste

Fondo negro, texto blanco y colores puros y saturados (amarillo para lo bueno, magenta para lo malo, cian para el
acento). Los bordes de los paneles y botones son blancos para que se vean los limites. El velo de la tarde y la
noche sobre el mapa es mas suave en este tema para no oscurecer el contraste (`views/mundo_view.py`).

## Daltonismo

La paleta sale de la propuesta de Okabe e Ito, pensada para que se distinga con los tipos comunes de daltonismo:
azul cielo (86, 180, 233) para lo bueno, naranja (230, 159, 0) para lo malo y purpura rojizo (204, 121, 167) para
el acento, en lugar del par rojo y verde que esas personas confunden. El fondo es el mismo morado oscuro del tema
normal y todos los textos y senales cumplen el contraste WCAG (4.5:1 el texto, 3:1 los elementos de interfaz); hay
una prueba que lo mide en los tres temas.

Ademas, **ningun dato depende solo del color**: todo lo que importa tiene una forma propia. La seccion "Leyenda de
formas" de la ayuda las dibuja todas:

- Telefono (personas de la red): circulo vacio no sabe, circulo lleno lo cree, triangulo lo comparte, cuadrado es
  inmune.
- Chat del Colegio: circulo es apoyo, triangulo es ataque.
- Mitin de la Plaza: cuadrado dato, circulo pregunta, triangulo calma (y el numero de la tecla dentro del globo).
- Rueda de prensa: triangulo pista, cuadrado evidencia, circulo testimonio, X trampa.
- De boca en boca: cuadrado vacio no sabe, triangulo lo cree, circulo convencido, X enojado.
- En la calle (sobre la cabeza): triangulo lleva un rumor, circulo es testigo, cuadrado esta enojado.
- Mitin (la multitud): circulo animada, cuadrado molesta.
- Mapa: las zonas en obras, en crisis o aisladas llevan franjas, no solo un tinte; una calle cerrada es una valla.
- HUD: cada indicador tiene su icono y su numero, no solo la barra de color.

## Tiempo extendido

Multiplica por 1.5 la duracion del dia, el reloj de las publicaciones virales y los tiempos de los minijuegos:

- Chat: los mensajes caen mas lento.
- Mitin: los globos suben mas lento.
- Rueda de prensa: los anillos de cada pregunta duran mas y nunca preguntan dos periodistas a la vez.
- De boca en boca: el chisme salta y vuelve a entrar mas lento.
- Telefono: el escudo es mas grande y el rumor avanza al mismo ritmo relativo.

Atiende a quien procesa la informacion mas despacio, a quien tiene dificultades motrices o a quien juega por primera
vez con teclado. No cambia lo que se aprende, solo el ritmo.

## Pausa y controles sin ritmo

P pausa cualquier minijuego (en el modo individual tambien se detiene el reloj del dia). Las ventanas de ayuda (F2)
y de sustentacion (F1) pausan el juego entero mientras estan abiertas. Ninguna mecanica exige pulsar al compas: el
mitin y la rueda piden reaccionar a lo que aparece, y el tiempo extendido les da margen.

## Sonido y sus avisos visuales

Los sonidos son tonos generados por codigo, sin archivos. Si el equipo no tiene audio, o falla, el juego sigue en
silencio sin errores. Cada sonido tiene un equivalente visual, asi que nadie pierde informacion por no oirlo:

| Sonido | Cuando suena | Aviso visual equivalente |
|---|---|---|
| Pasos | Al caminar por la ciudad | La animacion de caminar del personaje |
| Alerta viral | Un rumor se vuelve viral | Aviso "Se volvio viral!" arriba y el icono del telefono que late |
| Cambio de fase | Empieza una fase electoral | La pantalla de la fase nueva con lo que cambio en la ciudad |
| Acierto | Buena decision, minijuego bien jugado, persuadir a alguien, atajar un rumor con el escudo | Reaccion de los presentes, el destello del escudo, los contadores del minijuego y el aviso del resultado |
| Error | Mala decision, fallo en un minijuego, alguien que se enoja | Reaccion de los presentes, los contadores del minijuego y el aviso del resultado |

El volumen general, el de los pasos (el sonido que mas se repite) y el silencio total se cambian en Opciones.

## Ayuda y mensajes guia

- **Ayuda (F2)**: se abre encima de cualquier pantalla, en la seccion que corresponde a donde se esta (en el
  telefono abre "Defensa de la red", en un minijuego abre "Minijuegos"). Explica el objetivo, las reglas, todos los
  controles, el mapa y las fases, el telefono, crear posts, los minijuegos, los encuentros, los roles, la
  credibilidad, los indicadores, como ganar, el multijugador y la accesibilidad. Los numeros (dias, segundos del
  reloj, recargas) salen de las constantes del juego, asi que no se desactualizan.
- **Mensajes guia**: una pista corta la primera vez que pasa algo (empezar el dia, entrar a un lugar, el primer
  transeunte, la primera vez en el telefono, cada minijuego, una protesta, la credibilidad baja). Cada una sale una
  sola vez y se pueden apagar.

Atienden la carga cognitiva de un juego con varias mecanicas y ayudan a quien juega por primera vez.

## Lo que no cubre

- Lector de pantalla: Pygame dibuja todo como imagen y no expone el texto al sistema.
- Cambiar las teclas: los controles son fijos (estan todos en la ayuda).
- Subtitulos de voz: el juego no tiene voces; todo el dialogo ya es texto.
