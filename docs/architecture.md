# Arquitectura

`dedsec.py` descubre módulos, aplica la selección de configuración, coordina modos iniciales entre procesos mediante un archivo de reclamaciones con bloqueo, gestiona rotación y tamaño de terminal, y escribe los fotogramas ANSI. La selección forzada usa un solo modo. La clase `Saver` recrea la escena al cambiar el tamaño y aplica las transiciones sobre una instantánea del modo anterior.

| Archivo | Responsabilidad |
| --- | --- |
| `config.py` | Valores predeterminados, plantilla y lectura de TOML del usuario. |
| `lib.py` | Lienzo `Screen`, colores, primitivas, instantáneas y renderizado diferencial. |
| `engine3d.py` | Cámara, proyección, recorte y geometría compartida. |
| `widgets.py` | Paneles, partículas, rótulos y efectos compartidos. |
| `transitions.py` | Glitch, CRT, VHS, datamosh y zoom entre escenas. |
| `cinematic.py` | Utilidades comunes para las despedidas visuales. |
| `sysdata.py` | Hilos de estadísticas, MPRIS, audio, notificaciones y meteorología. |
| `mode_*.py` | Implementaciones de las 14 escenas. `mode_logo.py` publica DEDSEC. |
| `assets/dot_hands.json` | Recurso de puntos para las manos de DOTMATRIX. |
| `assets/nudle_map.npz` | Textura y máscaras deterministas de NUDLE, precalculadas para evitar la pausa inicial. |
| `tools/build_nudle_map.py` | Regenera la textura de NUDLE al cambiar su construcción. |
| `tools/snap.py` | Simulación sin terminal interactiva y medición de modo más renderizado. |
| `tools/verify.py` | Pruebas reutilizables de escenas y cierres a tres tamaños. |
| `tools/preview.py` | Hojas PNG por fases para revisar composición y legibilidad; Pillow opcional. |
| `scripts/install.py` | Instalación e integración personal. |
| `integration/launcher/` | Lanzador para Omarchy. |
| `integration/omarchy/` | Complemento de inactividad y parches del shell y menú. |

## Contrato de una escena

Cada módulo publica `NAME` y `Mode(w, h)`. `step(screen, now)` dibuja un fotograma; `farewell(screen, now, t)` dibuja el cierre, con progreso normalizado de cero a uno durante aproximadamente 0,8 segundos. La animación depende del tiempo recibido y puede probarse con una línea temporal simulada.

`Screen` mantiene texto, fondo y dos píxeles verticales por celda. El texto tiene prioridad sobre los píxeles, y estos sobre el fondo. El renderizador compara con el fotograma anterior para reducir escrituras ANSI. La cuadrícula presupone un carácter de ancho simple por celda; `sysdata.display_text` sanea etiquetas externas antes de mostrarlas.

Las escenas construyen geometría y texturas propias según su tamaño. DOTMATRIX interpola puntos entre manos, DEDSEC y un globo durante un ciclo de 44 segundos. Las despedidas conservan una instantánea de la escena para que su textura y composición participen del cierre.

## Datos y ciclo de vida

`DATA.start()` inicia fuentes habilitadas en hilos daemon. Los fallos de fuentes opcionales no detienen el dibujo. `DATA.stop()` termina los subprocesos de captura. MPRIS se consulta por D-Bus; las estadísticas usan datos del sistema; las notificaciones se cuentan en el historial local. El audio usa `parec` cuando está disponible y NumPy para analizar muestras en memoria. La meteorología usa HTTPS y una caché temporal.

El programa restaura el modo de terminal y el cursor al salir. En una ventana gestionada de clase `org.omarchy.screensaver`, comprueba el foco de Hyprland y coordina el cierre de las ventanas del salvapantallas. La comprobación de foco falla de forma tolerante si Hyprland no está disponible.

## Recurso precalculado de NUDLE

El mapa contiene únicamente geometría y colores generados por el proyecto; no
guarda ubicaciones personales ni fuentes de datos. Su carga usa NumPy con
`allow_pickle=False`, valida dimensiones y tipos, y compara una huella SHA-256
del código de geometría/construcción. Si falta, está dañado o queda desactualizado,
se genera el mapa de forma procedural; esto conserva el funcionamiento pero
puede recuperar la pausa inicial. Los edificios se generan a partir de las
máscaras cargadas y los niveles de detalle mantienen sus píxeles originales.

Después de modificar constantes o funciones anteriores a `_WORLD` en
`mode_nudle.py`, regenera y guarda también el recurso:

```sh
/usr/bin/python3 tools/build_nudle_map.py
/usr/bin/python3 tools/verify.py --full --mode mode_nudle
```
