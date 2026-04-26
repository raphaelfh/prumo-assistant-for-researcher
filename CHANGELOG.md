# Changelog

Todas as mudanças relevantes deste plugin.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [Não publicado]

## [0.1.1] - 2026-04-26

### Adicionado
- `.claude-plugin/marketplace.json` — o repo agora é simultaneamente plugin e marketplace de 1 entry, permitindo `/plugin marketplace add raphaelfh/prumo-assist` direto.
- CI (`.github/workflows/validate-manifests.yml`) que valida `plugin.json` e `marketplace.json` contra JSON Schema em cada PR/push.
- Schemas explícitos em `.github/schemas/` (referência viva do que o Claude Code aceita).
- Este `CHANGELOG.md`.

### Corrigido
- `plugin.json#repository` passou de objeto `{type, url}` para string — formato que o validador do Claude Code aceita (rejeitava o anterior em `/plugin install`).
- README: link de instalação corrigido (`raphaelfh/prumo-assist`, não `claude-prumo-assist`) e comando atualizado para o formato qualificado `prumo-assist@prumo-assist`.

## [0.1.0] - 2026-04-22

### Adicionado
- Estrutura inicial do plugin extraída do monorepo `monorepo-anterior`.
- 8 skills: `tabular-eda`, `data-cleaning`, `clinical-metrics`, `paper-manager`, `paper-extract`, `wiki-ingest`, `wiki-query`, `wiki-lint`.
- 2 agents: `ml-theory-expert`, `stack-docs-researcher`.
- MCP `qmd` (busca BM25 + vector + rerank local no wiki).

[Não publicado]: https://github.com/raphaelfh/prumo-assist/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/raphaelfh/prumo-assist/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/raphaelfh/prumo-assist/releases/tag/v0.1.0
