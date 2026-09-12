# ADR-0034 — Renomeia o projeto para prumo-assistant-for-researcher (PAR)

- Status: aceito
- Data: 2026-09-12
- Origem: pedido do mantenedor, tomando o [ARS](https://github.com/Imbad0202/academic-research-skills) como referência de naming (nome longo descritivo no repo/marketplace, sigla na prosa).

## Contexto

"prumo-assist" não diz para quem é a ferramenta, e o prefixo das skills (`/prumo-assist:paper extract`) é longo para digitar em toda invocação. O ARS resolve a primeira parte com um nome descritivo e usa a sigla na prosa. Ninguém usa o plugin em produção, então o custo de migração de projetos `pj_*` existentes é zero por decisão.

## Decisão

- **Repo, marketplace e distribuição Python**: `prumo-assistant-for-researcher`.
- **Nome do plugin** (namespace das skills e agents): `par` — as invocações viram `/par:paper extract`, `/par:start`, `par:reviewer`.
- **Pacote Python**: `prumo_assist` → `par` (`src/par/`).
- **Prosa**: "prumo-assist" → "PAR".
- **Permanecem `prumo`**: o CLI (`prumo`, `prumo-zettlr-export`), o servidor MCP (`prumo`), `PrumoError`, `.prumo/`, frontmatter `prumo.*`, variáveis `PRUMO_*` e `_meta.prumo_version`. "prumo" é a primeira palavra do nome novo, não colide com o `par` do Homebrew e evita reescrever contratos persistidos.

Sem migração: `prumo update` não reescreve invocações `prumo-assist:` antigas em projetos existentes.

## Consequências

Instalação muda para `/plugin marketplace add raphaelfh/prumo-assistant-for-researcher` e `/plugin install par@prumo-assistant-for-researcher`; quem tem o marketplace antigo precisa removê-lo e adicionar o novo, e o CLI global precisa ser reinstalado com o nome novo da distribuição. ADRs, planos arquivados, specs e entradas antigas do CHANGELOG mantêm o nome antigo como registro histórico.
