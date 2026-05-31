"""Sincroniza a versão dos manifests Claude Code com ``src/prumo_assist/_version.py``.

Uso:

    python .github/scripts/sync_manifest_version.py            # escreve
    python .github/scripts/sync_manifest_version.py --check    # exit 1 se desync

A intenção é que ``_version.py`` (pacote Python) e os manifests do plugin
(``.claude-plugin/plugin.json``, ``.claude-plugin/marketplace.json``) andem
juntos depois de um release. Em períodos de transição (ex.: spin-off de
skills) eles podem divergir intencionalmente — nesse caso, basta não rodar
o script.

Este script **não** edita ``_version.py``: a versão é sempre puxada dele.
Para bumpar a versão, edite ``_version.py`` e rode este script.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERSION_FILE = REPO / "src" / "prumo_assist" / "_version.py"
PLUGIN_JSON = REPO / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO / ".claude-plugin" / "marketplace.json"

_VERSION_RE = re.compile(r'__version__\s*=\s*"([^"]+)"')


def read_package_version() -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = _VERSION_RE.search(text)
    if not match:
        sys.exit(f"{VERSION_FILE}: __version__ não encontrado.")
    return match.group(1)


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def sync(version: str) -> list[str]:
    """Escreve ``version`` em plugin.json e marketplace.json. Retorna mudanças."""
    changes: list[str] = []

    plugin = read_json(PLUGIN_JSON)
    if plugin.get("version") != version:
        changes.append(f"  • plugin.json: {plugin.get('version')} → {version}")
        plugin["version"] = version
        write_json(PLUGIN_JSON, plugin)

    marketplace = read_json(MARKETPLACE_JSON)
    plugin_name = plugin.get("name")
    for entry in marketplace.get("plugins", []):
        if entry.get("name") == plugin_name and entry.get("version") != version:
            changes.append(
                f"  • marketplace.json#{entry['name']}: {entry.get('version')} → {version}"
            )
            entry["version"] = version
    if changes:
        write_json(MARKETPLACE_JSON, marketplace)

    return changes


def check(version: str) -> list[str]:
    """Sem escrever: relata divergências. Lista vazia = tudo alinhado."""
    issues: list[str] = []
    plugin = read_json(PLUGIN_JSON)
    if plugin.get("version") != version:
        issues.append(f"plugin.json#version={plugin.get('version')!r} ≠ _version.py={version!r}")
    marketplace = read_json(MARKETPLACE_JSON)
    plugin_name = plugin.get("name")
    for entry in marketplace.get("plugins", []):
        if entry.get("name") == plugin_name and entry.get("version") != version:
            issues.append(
                f"marketplace.json#{entry['name']}.version="
                f"{entry.get('version')!r} ≠ _version.py={version!r}"
            )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Não escreve; sai com 1 se desync.",
    )
    args = parser.parse_args()

    version = read_package_version()

    if args.check:
        issues = check(version)
        if issues:
            print(f"Desync entre _version.py ({version}) e manifests:", file=sys.stderr)
            for issue in issues:
                print(f"  • {issue}", file=sys.stderr)
            return 1
        print(f"✓ manifests alinhados em v{version}")
        return 0

    changes = sync(version)
    if not changes:
        print(f"✓ manifests já em v{version}, nada a fazer.")
        return 0
    print(f"Sincronizados em v{version}:")
    for change in changes:
        print(change)
    return 0


if __name__ == "__main__":
    sys.exit(main())
