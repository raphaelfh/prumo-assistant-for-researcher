# Regras de release

- A versão é a interface pública do plugin: bump só quando o consumidor precisa saber (ver RELEASING.md).
- Pré-1.0 (ADR-0015): PATCH = tudo releasável (inclusive invocável novo); MINOR = breaking ("⚠ Breaking") ou marco do ROADMAP; MAJOR reservado ao 1.0.0. NÃO-releasável: `.github/`, `README.md`, `CHANGELOG.md`, `.gitignore`, `docs/` — reorganização de docs/infra nunca bumpa versão.
- Fonte única de versão: `src/prumo_assist/_version.py`. Propagação: `python .github/scripts/sync_manifest_version.py` → `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`. NUNCA editar versão nos manifests à mão (Princípio VII da constitution).
- Todo release: atualizar CHANGELOG (mover "Não publicado", completar refs do rodapé), bump + sync, validar (`validate_manifests.py` e `sync_manifest_version.py --check`), commit `release: X.Y.Z - <resumo>` via branch `release/vX.Y.Z` + PR, e após o merge: tag anotada `vX.Y.Z` + `gh release create`. Atualizar `CITATION.cff` (campo `version`).
- CHANGELOG cita princípios pela numeração romana da constitution e referencia ADRs por `ADR-NNNN`.
