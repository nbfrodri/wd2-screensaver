# Diseño visual

Las escenas priorizan siluetas reconocibles, materiales diferenciados y
movimiento coherente. Las luces, partículas e interferencias acompañan al
motivo principal. Los rótulos y diagramas forman parte de la estética; no se
añaden bloques legibles de código de hacking falso.

## Identidad de los modos

| Modo | Composición y rasgos que conservar |
| --- | --- |
| DEDSEC | Calavera y logotipo dimensional, skyline y suelo de neón contenido. La calavera también aparece a 90×26. |
| WRENCH | Máscara con volumen, ojos LED expresivos y taller. Conservar su despedida establecida. |
| PROFILER | Ciudad bajo vigilancia, objetivos conectados a tarjetas opacas y retratos ficticios generados localmente. Campos con contraste y texto limitado al ancho de la tarjeta. |
| BOTNET | Globo sombreado, conexiones con oclusión, paquetes y paneles de red. |
| DRONE | Vuelo entre edificios con ventanas y franjas estructurales, carretera, persecución y túnel. El cartel se encuadra antes de la aproximación rápida; los efectos no deben ocultar las fachadas. |
| HOLOGRAM | Calavera, máscara y letras proyectadas sobre una base física. Superficies continuas, ojos contrastados e interferencia limitada a los vóxeles; sala e indicadores estables. |
| GOLDENGATE | Puente, profundidad atmosférica, niebla, reflejos y tráfico marítimo. Mantener el equilibrio entre paisaje e interfaz. |
| HACKERSPACE | Habitación con neón, pantallas, mobiliario y pequeños objetos. Alfombra de tintes apagados con tejido tenue que desaparece a distancia. |
| NUDLE | Mapa de San Francisco con edificios, puentes, búsqueda, rutas, marcadores y plegado. Su recurso precalculado evita reconstruir la textura al abrir la escena. |
| SCOUTX | Fotografías de lugares en un feed social. Piedra y vegetación diferenciadas en Coit, tranvía con cabina y raíles reconocibles, corazón central breve. |
| TEXTWALL | Grafiti con relieve sobre ladrillo, recorrido lateral y actividad callejera. Conservar el detalle de pintura y materiales. |
| TOWER | Torre con retranqueos, plantas y ciudad por capas. Los escudos son más transparentes sobre el edificio; el plano final muestra la silueta completa. |
| TRAFFIC | Cruce con coches, peatones, semáforos y fases de sabotaje y recuperación. La lectura del tráfico tiene prioridad sobre la textura del asfalto. |
| DOTMATRIX | Manos, contacto, formación de DEDSEC, globo y regreso en un ciclo de 44 segundos. Exclusivamente puntos blancos y grises sobre negro. |

Todos los modos conservan una despedida propia. Los retratos y datos ficticios
de las escenas no requieren fotografías ni consultas personales. Las fuentes
reales y sus controles se describen en el [README](../README.md#configuración-y-privacidad).

## Limitaciones visuales conocidas

La evaluación del 2 de octubre de 2026 se realizó con PNG por fases del motor.
No sustituye una comprobación de fluidez, fuente y efectos en una terminal real.

- A 90 columnas, las transformaciones de DOTMATRIX son más abstractas, el
  túnel de DRONE pierde detalle y algunas etiquetas de BOTNET y NUDLE quedan justas.
- La fragmentación de DEDSEC y los ataques de BOTNET producen fases visualmente densas.
- El ascenso de TOWER incluye primeros planos que recortan el edificio.
- Los filtros de SCOUTX alteran bastante el color de algunas fotografías.
- Las capturas de TRAFFIC muestran sus estados, pero no certifican la
  continuidad de las aceleraciones o colisiones entre fotogramas.

Consulta [validación](validation.md) para reproducir las capturas y conocer
los límites de rendimiento medidos.
