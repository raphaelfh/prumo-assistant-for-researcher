# Regras de release

- A versão é a interface pública do plugin: bump só quando o consumidor precisa saber (ver RELEASING.md).
- PATCH: correções e refinamentos sem mudança de trigger/output. MINOR: algo invocável novo; breaking pré-1.0 vai em MINOR com "⚠ Breaking". NÃO-releasável: `.github/`, `README.md`, `CHANGELOG.md`, `.gitignore`, `docs/` — reorganização de docs/infra nunca bumpa versão.
- Fonte única de versão: `src/prumo_assist/_version.py`. Propagação: `python .github/scripts/sync_manifest_version.py` → `plugin.json` + `marketplace.json`. NUNCA editar versão nos manifests à mão (Princípio VII da constitution).
- Todo release: atualizar CHANGELOG (mover "Não publicado", completar refs do rodapé), bump + sync, validar (`validate_manifests.py` e `sync_manifest_version.py --check`), commit `release: X.Y.Z - <resumo>` via branch `release/vX.Y.Z` + PR, e após o merge: tag anotada `vX.Y.Z` + `gh release create`. Atualizar `CITATION.cff` (campo `version`).
- CHANGELOG cita princípios pela numeração romana da constitution e referencia ADRs por `ADR-NNNN`.
