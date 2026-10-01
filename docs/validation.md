# Validación

Este documento registra la validación anterior comunicada para esta versión. Durante la preparación de esta copia y su documentación no se hizo una nueva comprobación visual en vivo: ya había un salvapantallas en ejecución y se evitó interferir con él.

Al preparar el repositorio se ejecutó además `tools/verify.py`: sus 42 combinaciones de modo y tamaño, con comprobaciones de cierre, pasaron. El instalador se probó en un HOME temporal: vista previa sin escrituras, conservación de ajustes ajenos y configuración existente, lectura de JSONC, copias de seguridad y segunda instalación sin cambios.

La última pasada registrada cubrió los 14 modos en tres tamaños de terminal: 42 comprobaciones en total, todas superadas. También se registró una simulación temporal de 80 segundos y comprobaciones de las despedidas, todas superadas. Las comprobaciones manuales mediante PTY cubrieron DOTMATRIX, TRAFFIC y WRENCH, junto con el cierre por pérdida de foco. Esto documenta el resultado comunicado; no sustituye una prueba visual nueva después de cambiar el entorno o el código.

## Comprobaciones reutilizables

```sh
/usr/bin/python3 tools/verify.py
/usr/bin/python3 tools/verify.py --full
/usr/bin/python3 tools/verify.py --mode mode_dotmatrix
```

La pasada breve dibuja 24 fotogramas por modo en 90 × 26, 175 × 45 y 240 × 60. Después prueba nueve progresiones de despedida. `--full` sustituye esos fotogramas por 101 pasos separados por 0,8 segundos, cubriendo una línea temporal simulada de 80 segundos. `--mode` limita la comprobación al módulo indicado y puede combinarse con `--full`.

La herramienta verifica que las celdas finales y las despedidas contienen un único carácter imprimible de ancho simple, además de ejecutar el dibujo y renderizado. No inicia fuentes en vivo ni acciones del escritorio. Estas comprobaciones detectan errores de ejecución y de cuadrícula; la apariencia, los cambios continuos entre muestras y la integración requieren revisión visual y una prueba interactiva.

## Repetir una captura sin interfaz

Usa el Python del sistema, que dispone de NumPy:

```sh
/usr/bin/python3 tools/snap.py mode_dotmatrix 175 45 1920 --show
/usr/bin/python3 tools/snap.py mode_traffic 240 60 240
/usr/bin/python3 tools/snap.py mode_wrench 175 45 240
```

El argumento es el nombre del módulo (`mode_logo` para DEDSEC), seguido de columnas, filas y número de fotogramas. La herramienta avanza tiempo simulado a 24 fps, mide 48 fotogramas adicionales y comunica milisegundos por fotograma para dibujo más renderizado. `--show` imprime el último fotograma como texto. No inicia las fuentes de datos reales ni verifica el foco, la restauración de terminal o la integración de escritorio.

## Revisión visual por fases

La herramienta opcional `tools/preview.py` necesita Pillow (incluido en
`requirements-dev.txt`) y una fuente local compatible. Crea PNG sin abrir
ventanas ni iniciar fuentes de datos:

```sh
/usr/bin/python3 tools/preview.py --mode mode_dotmatrix --times 0 2.6 6 12 26 31 --output /tmp/dotmatrix.png
/usr/bin/python3 tools/preview.py --mode mode_traffic --width 175 --height 45 --times 0 7 12 --output /tmp/traffic.png
```

Su raster es una aproximación de la cuadrícula del terminal, con puntos braille
dibujados explícitamente. No verifica la fuente real de Ghostty, CRT, foco ni
restauración del terminal. `--font` permite elegir otra fuente instalada.

La pasada de pulido posterior comprobó líneas temporales completas y cierres de
DOTMATRIX, TRAFFIC, DRONE, TOWER y PROFILER a los tres tamaños. El ajuste final
de los fragmentos orbitales de DOTMATRIX pasó comprobaciones de sus límites de
fase y cierre. No se hizo una nueva prueba en vivo del escritorio.

## Rendimiento registrado

TEXTWALL y WRENCH son las escenas más costosas de las medidas comunicadas: aproximadamente 56 y 57 ms por fotograma a 240 × 60, respectivamente. A un tamaño habitual de 175 columnas se registraron aproximadamente 27 y 32 ms. Son mediciones de referencia de esta máquina, no garantías de rendimiento.

El objetivo de 24 fps deja unos 41,7 ms por fotograma. Las dos escenas grandes pueden superar ese presupuesto; el bucle no espera cuando el trabajo ya ha consumido el intervalo, por lo que la tasa real baja. La escritura efectiva de la terminal y las fuentes en vivo pueden añadir trabajo que la captura sin interfaz no representa.
