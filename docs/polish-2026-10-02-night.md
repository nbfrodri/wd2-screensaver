# Revisión visual nocturna del 2 de octubre de 2026

Esta pasada continúa las reescrituras de Claude y conserva sus arreglos de cursor
e inactividad. Las imágenes se revisaron por fases y sobre la cuadrícula real
del renderizador, mediante PNG aproximados; no se hizo una nueva prueba visual
en Ghostty ni se modificó la configuración del escritorio.

## Cambios sobre el trabajo de Claude

| Modo | Resultado |
| --- | --- |
| DRONE | Conservados vuelo más alto, calles anchas, tráfico y fachadas con LOD. Más profundidad de ciudad, módulos de ventana constantes por fachada, sin cambios de subdivisión LOD dentro de una misma pared, con luz más contenida, lluvia y reflejos excluidos del túnel, salida abierta hacia la ciudad y persecución visible dentro. |
| DOTMATRIX | Manos mejor encuadradas y puntos blancos con volumen; letras de mayor peso y contraste, fondo más discreto. Flujo menos disperso, globo con pausa legible y regreso completo a las manos sin salto prematuro. Ciclo de 44 segundos, siempre blanco/gris sobre negro. |
| TOWER | Conservados nueva torre con retranqueos, ciudad por capas y escudos. Plantas técnicas oscuras y parapetos aclaran la arquitectura; plano final más amplio para mostrar corona, antena y calavera sin recorte superior. |
| NUDLE | Conservado el mapa nuevo con puentes, edificios, rutas y plegado. Eliminada la construcción pesada del mapa al abrir el modo mediante un recurso precalculado de idénticos píxeles. |
| BOTNET | Revisada y conservada la reescritura de Claude: globo ortográfico, arcos y paquetes dibujados en píxeles, oclusión, luces y paneles. |

## Pausa inicial de NUDLE

Antes, el primer `Mode(175,45)` construía todos los niveles del mapa: **1,291 s**
en la muestra local. Con `assets/nudle_map.npz` tomó **0,094 s**. El primer
fotograma medido fue 41 ms antes y 56 ms después, bajo cargas distintas: la
mejora demostrada corresponde a la construcción inicial, no a todos los FPS.

El recurso ocupa unos 549 KiB. Se compararon todos los niveles RGB y máscaras
con la generación original: son idénticos. La huella del constructor evita usar
un mapa obsoleto; se valida formato y se carga sin pickle. Faltas, daños o
incompatibilidades recurren a la generación original. Se probaron esos caminos.
No contiene datos del usuario ni resultados de fuentes en vivo.

Consulta [arquitectura](architecture.md#recurso-precalculado-de-nudle) para
regenerarlo. Hay todavía trabajo puntual al capturar un nuevo plano para el
plegado; eliminar la pausa de arranque no garantiza que todos los cambios de
escena carezcan de picos.

## Validación y rendimiento

- Los 14 modos aparecen sin errores de importación.
- Prueba completa de 80 segundos simulados, caracteres de cada fotograma y
  nueve progresos de cierre: 42 combinaciones de modo/tamaño superadas.
- DRONE y DOTMATRIX volvieron a superar las pruebas completas después de la
  segunda revisión visual. TOWER y NUDLE también superaron sus pruebas propias.
- Revisadas capturas por fases de DRONE y DOTMATRIX a los tres tamaños; TOWER,
  NUDLE y BOTNET se revisaron en hojas de 175×45, incluidos finales y transiciones.

Mediciones seriales con `tools/snap.py`, 240 fotogramas de preparación y 48 de
medición, sin otros procesos de revisión/renderizado. Se midieron los 14 modos
a 175×45 y los cuatro focos de esta pasada también a 90×26 y 240×60. Valores en
ms por fotograma; raya significa que ese tamaño no se midió en esta pasada.
[Datos CSV](performance-2026-10-02-night.csv).

| Modo | 90×26 | 175×45 | 240×60 |
| --- | ---: | ---: | ---: |
| BOTNET | — | 22.9 | — |
| DOTMATRIX | 9.6 | 16.8 | 24.9 |
| DRONE | 18.5 | 32.5 | 54.8 |
| GOLDENGATE | — | 27.1 | — |
| HACKERSPACE | — | 37.4 | — |
| HOLOGRAM | — | 41.1 | — |
| DEDSEC | — | 20.5 | — |
| NUDLE | 5.1 | 11.8 | 19.0 |
| PROFILER | — | 23.2 | — |
| SCOUTX | — | 14.1 | — |
| TEXTWALL | — | 23.0 | — |
| TOWER | 16.5 | 34.6 | 49.1 |
| TRAFFIC | — | 11.2 | — |
| WRENCH | — | 25.5 | — |

Las mediciones incluyen dibujo y renderizado ANSI, pero no toda la latencia del
terminal. Son muestras de una fase y no máximos del ciclo completo; cambian con
la hora, escena y carga. DRONE, TOWER y otros modos superan el objetivo orientativo
de 25 ms a 175×45. Todos los valores de esta muestra quedan debajo de 41,7 ms en ese
tamaño, con escaso margen en HOLOGRAM. DRONE 54,8 ms y TOWER 49,1 ms a 240×60 superan
el presupuesto de 24 FPS; no se garantiza esa tasa en pantallas grandes.

Las capturas ayudan a evaluar materiales y composición; no comprueban foco,
fuente de terminal, datos en vivo ni comportamiento de suspensión. Se conserva
la despedida de cada modo y las reglas de privacidad: notificaciones solo
contadas, audio en memoria y ningún volcado de código falso legible.

## Puntos que aún conviene evaluar

- DRONE: los vuelos próximos y el túnel siguen limitados por la resolución de
  medio bloque del terminal. Conviene comprobar cambios de iluminación y
  persecución en movimiento real, además de capturas aisladas.
- DOTMATRIX: el morph intermedio es abstracto; la densidad y el tamaño del punto
  dependen de la fuente y del tamaño de terminal. Las figuras formadas tienen
  ahora más contraste, pero esto debe verse también en el monitor real.
- TOWER: el ascenso conserva planos próximos que recortan parte del edificio;
  el plano de revelación final muestra la silueta completa. Los escudos producen
  fases densas de luz y fragmentos.
- NUDLE: la carga fría de un recurso ausente vuelve a ser procedural. Si se
  cambian constantes o el constructor del mapa, hay que regenerar el NPZ.
