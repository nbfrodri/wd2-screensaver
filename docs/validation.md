# Validación

## Estado comprobado

Última ejecución funcional y medición: **2 de octubre de 2026**, después del
pulido visual de siete escenas. Esta actualización documental no vuelve a
medir el programa.

- Descubrimiento de los 14 modos sin omisiones ni avisos de importación.
- `tools/verify.py --full`: 42 combinaciones superadas en 90×26, 175×45 y
  240×60, con 80 segundos simulados y nueve progresos de despedida.
- Revisión de PNG por fases de los 14 modos. HOLOGRAM se revisó de nuevo en
  los tres tamaños, DRONE/TOWER/SCOUTX en 240×60 y PROFILER en 90×26;
  también se inspeccionaron las hojas grandes de DEDSEC, PROFILER y HACKERSPACE.

Las comprobaciones son sin interfaz: no certifican la fuente de Ghostty, la
fluidez real, el foco, las fuentes de datos en vivo ni la suspensión. La
[evaluación visual](visuals.md) recoge el diseño y las limitaciones actuales.

## Comprobaciones reutilizables

Desde la raíz del repositorio, con el Python del sistema:

```sh
/usr/bin/python3 dedsec.py --list
/usr/bin/python3 tools/verify.py
/usr/bin/python3 tools/verify.py --full
/usr/bin/python3 tools/verify.py --full --mode mode_dotmatrix
```

La prueba breve dibuja 24 fotogramas por combinación de modo y tamaño.
`--full` usa 101 pasos separados por 0,8 segundos, hasta 80 segundos simulados.
Ambas prueban nueve progresos de despedida y verifican que cada celda contiene
un carácter imprimible de ancho simple. `--seed` permite cambiar la semilla
procedural; por defecto es 24. No se inician fuentes en vivo ni acciones del
escritorio.

Tras cambiar el motor compartido o la integración, comprueba todos los modos.
Para un cambio local, comprueba el modo afectado en los tres tamaños, sus fases
tardías y el cierre. Revisa imágenes además de errores de ejecución.

## Revisión visual por fases

`tools/preview.py` necesita Pillow, indicado en `requirements-dev.txt`, y una
fuente local compatible. Genera hojas PNG sin abrir ventanas:

```sh
/usr/bin/python3 tools/preview.py --mode mode_dotmatrix --times 0 2.6 6 12 26 31 --output /tmp/dotmatrix.png
/usr/bin/python3 tools/preview.py --mode mode_hologram --width 175 --height 45 --times 3 15 30 45 60 --output /tmp/hologram.png
```

Usa `--mode all` para incluir todas las escenas y `--font` para elegir otra
fuente. La imagen aproxima la cuadrícula del terminal y dibuja los puntos
braille explícitamente. No reproduce todos los efectos del terminal real.
Algunos rótulos usan la hora real mientras la escena usa tiempo simulado;
esto puede producir contadores de inactividad negativos en las previsualizaciones.

## Medir rendimiento

```sh
/usr/bin/python3 tools/snap.py mode_drone 175 45 240
/usr/bin/python3 tools/snap.py mode_tower 240 60 240
/usr/bin/python3 tools/snap.py mode_dotmatrix 90 26 240 --show
```

Los argumentos son módulo, columnas, filas y fotogramas de preparación.
La simulación avanza a 24 fps; después mide 48 fotogramas de dibujo y
renderizado ANSI. `--show` imprime el último fotograma como texto.
Mide en serie, sin otros procesos de previsualización o perfilado.

## Rendimiento medido

Se ejecutó `tools/snap.py` en serie, sin otras tareas de renderizado o pruebas:
240 fotogramas de preparación y 48 de medición por muestra. Son tiempos de
dibujo y generación ANSI; no incluyen toda la latencia del terminal ni son
máximos de todas las fases. La hora y la aleatoriedad pueden cambiar la escena.
Estas mediciones no son una comparación controlada antes/después.

[CSV completo](performance-2026-10-02-review.csv). Valores en ms por fotograma;
raya significa que ese tamaño no se midió en esta pasada.

| Modo | 90×26 | 175×45 | 240×60 |
| --- | ---: | ---: | ---: |
| BOTNET | — | 23.9 | — |
| DOTMATRIX | — | 15.6 | — |
| DRONE | 20.1 | 34.0 | 48.7 |
| GOLDENGATE | — | 29.8 | — |
| HACKERSPACE | 17.2 | 36.3 | 63.9 |
| HOLOGRAM | 18.7 | 40.0 | 42.7 |
| DEDSEC | 5.9 | 17.1 | 29.1 |
| NUDLE | — | 10.6 | — |
| PROFILER | 10.1 | 22.1 | 33.9 |
| SCOUTX | 4.5 | 13.4 | 22.4 |
| TEXTWALL | — | 19.6 | — |
| TOWER | 14.9 | 32.9 | 50.9 |
| TRAFFIC | — | 10.9 | — |
| WRENCH | — | 23.0 | — |

A 175×45 todas las muestras quedan por debajo de 41,7 ms, el presupuesto de
24 FPS, aunque HOLOGRAM (40,0 ms) tiene poco margen. DRONE, GOLDENGATE,
HACKERSPACE, HOLOGRAM y TOWER superan el objetivo orientativo de 25 ms.
A 240×60, DRONE (48,7 ms), HACKERSPACE (63,9 ms), HOLOGRAM (42,7 ms) y
TOWER (50,9 ms) exceden el presupuesto de 24 FPS. Estos límites siguen pendientes de optimización.
