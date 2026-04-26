"""Valida plugin.json e marketplace.json contra schemas do repo.

Uso:
    python .github/scripts/validate_manifests.py

Falha (exit 1) se qualquer manifest for inválido. Pensado para rodar:
- localmente antes de commit;
- no GitHub Actions (workflow validate-manifests.yml);
- como pre-commit hook futuro.

Também valida coerência cruzada:
- plugin.version == marketplace.plugins[<self>].version
- plugin.name aparece em marketplace.plugins
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[2]

PAIRS = [
    (REPO / ".claude-plugin/plugin.json", REPO / ".github/schemas/plugin.schema.json"),
    (REPO / ".claude-plugin/marketplace.json", REPO / ".github/schemas/marketplace.schema.json"),
]


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def validate_one(manifest_path: Path, schema_path: Path) -> list[str]:
    manifest = load_json(manifest_path)
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(manifest), key=lambda e: e.path)
    return [
        f"  • {'/'.join(map(str, err.absolute_path)) or '<root>'}: {err.message}"
        for err in errors
    ]


def cross_check(plugin: dict, marketplace: dict) -> list[str]:
    issues: list[str] = []
    plugin_name = plugin.get("name")
    plugin_version = plugin.get("version")
    entries = {p.get("name"): p for p in marketplace.get("plugins", [])}

    if plugin_name not in entries:
        issues.append(
            f"  • plugin.json#name='{plugin_name}' não aparece em marketplace.plugins"
        )
        return issues

    entry = entries[plugin_name]
    entry_version = entry.get("version")
    if entry_version and entry_version != plugin_version:
        issues.append(
            f"  • versão divergente: plugin.json={plugin_version} ≠ marketplace={entry_version}"
        )
    return issues


def main() -> int:
    failures: list[str] = []

    for manifest_path, schema_path in PAIRS:
        rel = manifest_path.relative_to(REPO)
        if not manifest_path.exists():
            failures.append(f"{rel}: arquivo não encontrado")
            continue
        errors = validate_one(manifest_path, schema_path)
        if errors:
            failures.append(f"{rel}: schema inválido")
            failures.extend(errors)
        else:
            print(f"✓ {rel}")

    plugin = load_json(REPO / ".claude-plugin/plugin.json")
    marketplace = load_json(REPO / ".claude-plugin/marketplace.json")
    cross_issues = cross_check(plugin, marketplace)
    if cross_issues:
        failures.append("coerência cruzada plugin.json ↔ marketplace.json:")
        failures.extend(cross_issues)
    else:
        print("✓ coerência cruzada plugin.json ↔ marketplace.json")

    if failures:
        print("\n--- FALHAS ---", file=sys.stderr)
        for line in failures:
            print(line, file=sys.stderr)
        return 1
    print("\nTodos os manifests válidos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
