#!/usr/bin/env python3
"""Install user-owned runtime and Omarchy integration; dry-run unless --apply."""
import argparse
import datetime
import json
from pathlib import Path
import re
import subprocess
import sys


def read_jsonc(text):
    """Remove JSONC comments and trailing commas without touching strings."""
    tokens = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/')
    clean = tokens.sub(lambda m: m[0] if m[0].startswith('"') else ' ', text)
    # Strings must remain opaque during trailing-comma removal too.
    tokens = re.compile(r'"(?:\\.|[^"\\])*"|,(\s*[}\]])')
    clean = tokens.sub(lambda m: m[0] if m[0].startswith('"') else m[1], clean)
    return json.loads(clean)


def object_file(path, jsonc=False):
    value = (read_jsonc if jsonc else json.loads)(path.read_text()) if path.exists() else {}
    if not isinstance(value, dict):
        raise ValueError(f'{path}: expected a JSON object')
    return value


def merge_shell(value):
    def identity(item):
        return item.get('id') if isinstance(item, dict) else item
    for key, add, remove in (
        ('plugins', {'id': 'phobos.idle'}, 'omarchy.idle'),
        ('disabledPlugins', 'omarchy.idle', 'phobos.idle'),
        ('cloneSourceRestores', 'phobos.idle', None),
    ):
        items = value.setdefault(key, [])
        if not isinstance(items, list):
            raise ValueError(f'shell.json: {key} must be an array')
        items[:] = [item for item in items if remove is None or identity(item) != remove]
        if not any(identity(item) == identity(add) for item in items):
            items.append(add)
    idle = value.setdefault('idle', {})
    if not isinstance(idle, dict):
        raise ValueError('shell.json: idle must be an object')
    idle.setdefault('screensaver', 150)
    idle.setdefault('lock', 300)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='write files (default: preview only)')
    parser.add_argument('--home', type=Path, default=Path.home(), help='target home, useful for isolated tests')
    parser.add_argument('--runtime-only', action='store_true', help='omit Omarchy plugin and shell/menu integration')
    args = parser.parse_args()
    home = args.home.expanduser().resolve()
    source = Path(__file__).resolve().parents[1]
    python = Path('/usr/bin/python3')
    if not python.exists():
        parser.error('/usr/bin/python3 is required')
    check = subprocess.run([str(python), '-c', 'import numpy; import tomllib'], capture_output=True, text=True)
    if check.returncode:
        parser.error('/usr/bin/python3 requires numpy and Python 3.11+ (tomllib)')
    planned = {}

    def copy_file(src, dst, executable=False):
        if src.resolve() == dst.resolve():
            return
        planned[dst] = (src.read_bytes(), 0o755 if executable else src.stat().st_mode & 0o777)

    def copy_tree(src, dst):
        if not src.is_dir():
            raise ValueError(f'missing source directory: {src}')
        for file in sorted(src.rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts:
                copy_file(file, dst / file.relative_to(src))

    runtime = home / '.local/share/wd2-screensaver'
    for file in sorted(source.glob('*.py')):
        copy_file(file, runtime / file.name)
    for folder in ('assets', 'tools'):
        copy_tree(source / folder, runtime / folder)
    copy_file(source / 'integration/launcher/wd2-launch-screensaver', home / '.local/bin/wd2-launch-screensaver', True)
    config = home / '.config/wd2-screensaver/config.toml'
    if not config.exists():
        copy_file(source / 'integration/config/config.toml', config)
    if not args.runtime_only:
        copy_tree(source / 'integration/omarchy/plugins/phobos.idle', home / '.config/omarchy/plugins/phobos.idle')
        shell = home / '.config/omarchy/shell.json'
        planned[shell] = ((json.dumps(merge_shell(object_file(shell)), indent=2, ensure_ascii=False) + '\n').encode(), 0o644)
        menu = home / '.config/omarchy/extensions/omarchy-menu.jsonc'
        value = object_file(menu, jsonc=True)
        entry = value.setdefault('system.screensaver', {})
        if not isinstance(entry, dict):
            raise ValueError('system.screensaver must be an object')
        entry['action'] = '$HOME/.local/bin/wd2-launch-screensaver force'
        planned[menu] = ((json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode(), 0o644)
    for path in planned:
        if not path.resolve().is_relative_to(home) or path.is_symlink():
            raise ValueError(f'refusing a target symlink or path outside home: {path}')
    changed = {p: (data, mode) for p, (data, mode) in planned.items()
               if not p.exists() or p.read_bytes() != data or p.stat().st_mode & 0o777 != mode}
    print(('Apply' if args.apply else 'Dry run') + f': {len(changed)} changed files under {home}')
    for path in changed:
        print(f'  {path.relative_to(home)}')
    if args.apply and changed:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        backup = home / '.local/state/wd2-screensaver/backups' / stamp
        backup.mkdir(parents=True)
        manifest = []
        # Back up every existing target before the first target write.
        for path in changed:
            relative = path.relative_to(home)
            exists = path.exists()
            manifest.append({'path': str(relative), 'existed': exists,
                             'mode': path.stat().st_mode & 0o777 if exists else None})
            if exists:
                saved = backup / 'files' / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(path.read_bytes())
        (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        for path, (data, mode) in changed.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(mode)
        print(f'Backup: {backup}')
    if not args.runtime_only:
        print('To reload explicitly after installation: omarchy restart shell')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(f'Installation stopped: {error}', file=sys.stderr)
        sys.exit(1)
