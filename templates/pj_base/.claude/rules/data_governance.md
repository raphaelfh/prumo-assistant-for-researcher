---
paths:
  - "**/content/**"
  - "**/*.ipynb"
  - "**/pj_*/**/*.py"
---

<!-- Esta rule é cópia inicial do template global em .claude/rules/data_governance.md.
     Pode ser customizada livremente para este projeto; vale sobre a rule
     da raiz dentro do escopo deste pj_*. Mantida sem alterações, o
     comportamento é idêntico ao global. -->

# Governança de dados

- `content/01_raw/`: tratar como **somente leitura** após ingestão; nunca sobrescrever arquivos-fonte.
- Saídas transformadas em `content/02_processed/` (subpastas versionadas por data).
- Notebooks: primeira célula com **fonte dos dados**, inclusão/exclusão, definição de **label** e **janela temporal** (reduz risco de leakage).
- Caminhos relativos ao diretório do `pj_*` atual, ancorados em `content/`.
