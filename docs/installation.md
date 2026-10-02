# Instalación y recuperación

Se necesita `/usr/bin/python3` con Python 3.11 o posterior y NumPy. En Omarchy,
el lanzador usa el terminal y las herramientas de sesión del sistema; consulta
el README para los requisitos de ejecución. El instalador comprueba Python y
NumPy, pero no instala paquetes ni modifica `/usr/share/omarchy`.

Desde la carpeta del repositorio:

```bash
/usr/bin/python3 scripts/install.py
/usr/bin/python3 scripts/install.py --apply
```

La primera orden muestra los cambios sin escribir. La segunda copia los módulos
Python de la raíz, `assets/` y `tools/` a `~/.local/share/wd2-screensaver`, y el
lanzador a `~/.local/bin/wd2-launch-screensaver`. Si el repositorio ya ocupa la
ruta de instalación, omite las copias sobre el mismo archivo. El ejemplo
`~/.config/wd2-screensaver/config.toml` se crea solamente si todavía no existe.

También instala el plugin `phobos.idle` y combina los ajustes de Omarchy. Activa
`phobos.idle`, desactiva `omarchy.idle`, registra la restauración del clon y
añade los tiempos de 150 segundos para el salvapantallas y 300 para el bloqueo
solamente si no estaban definidos. Conserva el resto de campos y plugins,
incluido el bloqueo existente.

El ajuste `idle.lock: false` en `~/.config/omarchy/shell.json` desactiva el
bloqueo automático del plugin y mantiene el salvapantallas. El instalador
respeta ese valor si ya existe. El bloqueo manual sigue siendo independiente:
el salvapantallas no es una pantalla de seguridad.

En el menú cambia únicamente la acción de `system.screensaver` a
`$HOME/.local/bin/wd2-launch-screensaver force`. Lee JSONC con comentarios y
comas finales; al escribir lo normaliza a JSON válido, por lo que los comentarios
y el formato del menú se pierden, pero conserva los demás campos y entradas.
Si un fichero no se puede analizar, termina antes de escribir los destinos.

Para instalar solo el programa y su lanzador, sin integrar Omarchy:

```bash
/usr/bin/python3 scripts/install.py --apply --runtime-only
```

Para probar con un directorio aislado, usa `--home /tmp/wd2-prueba` junto con
`--apply`. No cambia el HOME de la sesión ni inicia el salvapantallas.

El shell suele recargar los ajustes automáticamente. Si hace falta una recarga
explícita tras revisar los cambios:

```bash
omarchy restart shell
```

El instalador no ejecuta esta orden. Volver a instalar no duplica las entradas.
No elimina archivos antiguos que hayan desaparecido del repositorio.

## Copias de seguridad y retirada

Antes de escribir, guarda todos los destinos existentes y un manifiesto en
`~/.local/state/wd2-screensaver/backups/<fecha-UTC>/`. El manifiesto indica qué
archivos existían, su ruta relativa al HOME y sus permisos. Los originales
quedan bajo `files/` con la misma estructura. Una instalación sin cambios no
crea otra copia.

Para deshacer una ejecución concreta, revisa primero `manifest.json`. Restaura
cada archivo marcado con `existed: true` desde `files/` y aplica su permiso
`mode`; elimina únicamente los archivos marcados con `existed: false` que
introdujo esa ejecución. Usa el mismo HOME de destino de la instalación. No
borres el repositorio si coincide con la carpeta de ejecución instalada.

No hay una desinstalación automática completa: restaurar una copia antigua
también puede retirar modificaciones posteriores de esos archivos. Compara
los ajustes actuales con la copia antes de restaurar `shell.json` o el menú.
Para retirar la integración conservando cambios posteriores, desactiva
`phobos.idle`, restaura el estado anterior de `omarchy.idle` y la acción anterior
del menú según la copia, y retira los archivos del plugin y del lanzador solo
si ya no los necesitas. Recarga el shell después.
