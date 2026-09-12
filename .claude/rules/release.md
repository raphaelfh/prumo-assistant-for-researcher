# Regras de release

- A versão é a interface pública do plugin: bump só quando o consumidor precisa saber.
- Pré-1.0 (ADR-0015): PATCH = tudo releasável (inclusive invocável novo); MINOR = breaking ("⚠ Breaking") ou marco do ROADMAP; MAJOR reservado ao 1.0.0.
- NÃO bumpa versão: `.github/`, `docs/`, `README.md`, `CHANGELOG.md`, `RELEASING.md`, `.gitignore`, refator interno sem efeito perceptível.
- Fonte única de versão: `src/par/_version.py`. NUNCA editar versão em `plugin.json`/`marketplace.json` à mão — quem escreve lá é `sync_manifest_version.py` (Princípio VII).
- Cortar release: siga `RELEASING.md` § "Processo de release", os 8 passos na ordem. Não improvise um subconjunto.
- CHANGELOG cita princípios pela numeração romana da constitution e ADRs por `ADR-NNNN`.
