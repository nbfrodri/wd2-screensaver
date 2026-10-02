# WD2 Screensaver

Salvapantallas de terminal inspirado en DedSec y Watch Dogs 2, preparado para una instalación personal de Omarchy/Hyprland. Este repositorio privado sirve de copia de seguridad del código, los recursos y la integración necesaria; no incluye configuraciones completas del usuario ni secretos.

## Uso

Requiere Python 3.11 o posterior, NumPy y una terminal con color verdadero y caracteres de ancho simple. Desde el directorio del proyecto:

```sh
/usr/bin/python3 dedsec.py --list
/usr/bin/python3 dedsec.py
/usr/bin/python3 dedsec.py dotmatrix
```

Sin argumento, reparte los modos iniciales entre monitores y rota cada 45 segundos. Un nombre fuerza ese modo y desactiva la rotación. También se puede usar `python3 dedsec.py dotmatrix`: si ese intérprete carece de NumPy, el lanzador vuelve a `/usr/bin/python3`. El Python del sistema debe tener NumPy instalado.

La entrada de teclado o el movimiento del ratón cierran el salvapantallas después de una breve tolerancia inicial. En la integración de Omarchy, perder el foco también lo cierra. Cada modo tiene una despedida visual de aproximadamente 0,8 segundos. Las señales de terminación limpian la terminal directamente.

## Modos

Los 14 modos son `dedsec`, `wrench`, `profiler`, `botnet`, `drone`, `hologram`, `goldengate`, `hackerspace`, `nudle`, `scoutx`, `textwall`, `tower`, `traffic` y `dotmatrix`. Se descubren automáticamente en `mode_*.py`.

Las escenas combinan geometría, texturas, luces, carteles, tráfico y datos locales. DOTMATRIX anima las manos del recurso de puntos, forma DEDSEC, se transforma en un globo de puntos y vuelve a las manos en un ciclo de 44 segundos. La dirección visual evita bloques de código de hacking falso legible: los caracteres funcionan como textura. Los textos externos se limitan a caracteres imprimibles de ancho simple para conservar la cuadrícula.

## Configuración y privacidad

El primer arranque crea `~/.config/wd2-screensaver/config.toml`. Los valores predeterminados son rotación de 45 segundos, objetivo de 24 fps, efecto CRT y transiciones de un segundo. `general.modes` selecciona modos; una lista vacía incluye todos. `general.exclude` los excluye. Las fuentes se activan individualmente en `[data]` mediante `stats`, `music`, `audio`, `notifications` y `weather`.

Las notificaciones se cuentan por archivos de historial, sin leer su contenido. El audio de salida se analiza en memoria para producir un espectro y no se graba. MPRIS aporta artista y título; el texto mostrado se sanea para eliminar controles, marcas combinantes y caracteres anchos. El tiempo consulta `wttr.in` y comparte con ese servicio la ubicación o coordenadas configuradas en el widget meteorológico de Omarchy; sin ubicación configurada solicita la ubicación predeterminada del servicio. El resultado meteorológico se guarda temporalmente en el directorio de ejecución. Puede desactivarse con `weather = false`.

Las fuentes ausentes o que fallan mantienen valores predeterminados. El audio dispone además de animación de respaldo cuando no hay señal real. Las estadísticas proceden del sistema local.

## Instalación e integración

Para recuperar la copia privada con una cuenta que tenga acceso:

```sh
git clone https://github.com/nbfrodri/wd2-screensaver.git
cd wd2-screensaver
```

En Omarchy/Arch, NumPy se instala para el Python del sistema con `sudo pacman -S python-numpy`. El lanzador admite Ghostty, Alacritty, Foot y Kitty; necesita las herramientas habituales de Omarchy, Hyprland, `jq` y `socat`. Para analizar audio real hace falta `parec`; sin él se usa la animación de respaldo.

La instalación se gestiona con `scripts/install.py`. Primero muestra los cambios y después puedes aplicarlos:

```sh
/usr/bin/python3 scripts/install.py
/usr/bin/python3 scripts/install.py --apply
```

Consulta [instalación y recuperación](docs/installation.md) para las copias de seguridad, los ajustes que combina y la recarga del shell.

`integration/launcher/wd2-launch-screensaver` contiene el lanzador de terminal. `integration/omarchy/plugins/phobos.idle` contiene el complemento de inactividad adaptado. Los cambios puntuales del shell y del menú se conservan en `integration/omarchy/shell.patch.json` e `integration/omarchy/menu.patch.jsonc`. Son piezas de integración para Omarchy, no copias de toda la configuración del equipo.

La comprobación breve se ejecuta con `/usr/bin/python3 tools/verify.py`; añade `--full` para recorrer 80 segundos simulados por modo. `tools/preview.py` crea hojas PNG por fases para revisar las siluetas; requiere Pillow y se explica en el documento de validación.

Consulta [arquitectura](docs/architecture.md) y [validación](docs/validation.md) para el mapa del código y las comprobaciones registradas.

La [revisión del 2 de octubre](docs/polish-2026-10-02.md) documenta las mejoras
de los catorce modos, el fallo que ocultaba TOWER y las mediciones recientes.
Las instrucciones para asistentes están en [AGENTS.md](AGENTS.md) y
[CLAUDE.md](CLAUDE.md).

El [handoff para Claude](handoff.md) conserva la evaluación visual, las prioridades pendientes y las instrucciones para continuar este pulido.

## Guardar futuras mejoras

En esta máquina, el repositorio está en `/home/phobos/Projects/wd2-screensaver`. La ruta de ejecución `~/.local/share/wd2-screensaver` es un enlace simbólico al repositorio, de modo que el lanzador sigue usando el mismo código. Después de revisar y probar cambios, puedes guardarlos con `git add`, `git commit` y `git push`. Los archivos del lanzador y del plugin se versionan bajo `integration/`; si los modificas en sus rutas instaladas, actualiza también esas copias antes de guardar. Los cambios futuros no se suben automáticamente.

## Procedencia

`assets/dot_hands.json` deriva de un fondo de pantalla local. Las marcas DedSec y la referencia a Watch Dogs pertenecen a terceros. El complemento de inactividad procede de una copia del complemento de Omarchy adaptada para esta instalación. Esta copia privada no presupone una licencia para el arte o el código del usuario ni concede derechos sobre materiales de terceros.

La [revisión visual nocturna](docs/polish-2026-10-02-night.md) documenta la continuación sobre los cambios de Claude y la eliminación de la pausa inicial de NUDLE.
