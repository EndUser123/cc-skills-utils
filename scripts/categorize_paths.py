"""Categorize hardcoded paths found in plugin source files."""
import re
from pathlib import Path

plugins_dir = Path('P:\\\\\\packages/.claude-marketplace/plugins')
categories = {'claude-state': set(), 'external-project': set(), 'other': set()}

pattern = re.compile(r'[P-p]:[/\\][^\s`"\'<>]+')

for plugin in sorted(plugins_dir.iterdir()):
    if plugin.name.startswith('.') or not plugin.is_dir():
        continue
    for fpath in plugin.rglob('*'):
        if not fpath.is_file():
            continue
        ext = fpath.suffix.lower()
        if ext not in {'.py', '.md'}:
            continue
        try:
            content = fpath.read_text(errors='ignore')
            for m in pattern.finditer(content):
                path = m.group()
                p = path.replace('/', '\\')
                if re.match(r'P:\\\\\\\.claude', p, re.I):
                    categories['claude-state'].add(path)
                elif re.match(r'P:\\\\\\\__csf', p, re.I):
                    categories['external-project'].add(path)
                else:
                    categories['other'].add(path)
        except Exception:
            pass

for cat, paths in categories.items():
    print(f'{cat}: {len(paths)}')
    for p in sorted(paths)[:5]:
        print(f'  {p}')