---
title: Índice de ADRs
tags: [adr, index]
---

# Decisões registradas (ADRs)

Formato [MADR 4.0](https://adr.github.io/madr/) minimal: Contexto / Decisão / Consequências. ADR aceito é imutável — revisão = ADR novo. Decisão estrutural nova em PR = ADR novo aqui.

<!-- prumo:adr-index:begin -->
- [[adr/adr-0001-adr-log-em-docs-adr]] — ADR log do repo em `docs/adr/`; produto continua gerando `docs/decisions/` · aceito
- [[adr/adr-0002-skills-e-templates-fora-de-src]] — `skills/` e `templates/` fora de `src/`, force-included no wheel · aceito
- [[adr/adr-0003-skill-md-unica-fonte-de-metadata]] — SKILL.md é a única fonte de metadata por skill · aceito
- [[adr/adr-0004-pacote-livre-de-llm]] — O pacote Python é 100% livre de LLM · aceito
- [[adr/adr-0005-layering-core-domains]] — Layering: core ← domains ← fachadas finas · aceito
- [[adr/adr-0006-schemas-forward-only]] — Schemas versionados forward-only · aceito
- [[adr/adr-0007-zotero-stdlib-urllib]] — Zotero/BBT via stdlib urllib, endpoint 127.0.0.1:23119 · aceito
- [[adr/adr-0008-layout-alfa-de-notas]] — Layout α para notas de referência · aceito
- [[adr/adr-0009-blocos-delimitados]] — Blocos delimitados HTML-comment como contrato humano/máquina · aceito
- [[adr/adr-0010-plugin-root-na-raiz]] — Plugin root = raiz do repo; marketplace self-hosting; schemas vivos do validador · aceito
- [[adr/adr-0011-semver-por-visibilidade]] — SemVer por visibilidade ao consumidor; deferrals com trigger · aceito
- [[adr/adr-0012-remocao-agents-ml]] — Remoção dos agents ML pré-pivot · aceito
- [[adr/adr-0013-pdf-via-read-nativo]] — PDFs lidos com a tool Read nativa; sem MCP pdf-reader · aceito
- [[adr/adr-0014-findings-canonico]] — Caminho canônico de findings: `docs/wiki/findings/` com fallback · substituído por [ADR-0023](adr-0023-finding-como-type.md)
- [[adr/adr-0015-pre-1-0-patch-para-releasavel]] — Pré-1.0: PATCH para todo release; MINOR reservado a breaking/marco · aceito
- [[adr/adr-0016-criticmarkup-conservacao-ooxml]] — CriticMarkup como representação de revisão + conservação de citações contada no OOXML · aceito
- [[adr/adr-0017-prumo-mcp-reconciliador]] — prumo-MCP local e reconciliador que propõe marcas · aceito
- [[adr/adr-0018-verificacao-referencias-apis-publicas]] — Verificação de referências via APIs públicas, gate determinístico + enriquecimento opcional · aceito
- [[adr/adr-0019-preflight-uniforme-skills]] — Preflight uniforme gerado nas skills a partir de `requires:` · aceito
- [[adr/adr-0020-connect-autoexport-bbt]] — `prumo paper connect` via `autoexport.add` do Better BibTeX, guardas anti-fantasma · aceito
- [[adr/adr-0021-idioma-de-escrita-cascata-e-default]] — Idioma de escrita por cascata, default `en-US`, e contrato de prosa gerado · aceito
- [[adr/adr-0022-layout-por-escopo]] — Layout por escopo: `docs/` como raiz única de leitura · aceito
- [[adr/adr-0023-finding-como-type]] — Finding como `type: finding` em `notes/`, não diretório próprio · aceito
- [[adr/adr-0024-escopo-desde-o-init]] — Escopo presente desde o `init`; sem máquina de promoção · aceito
- [[adr/adr-0025-tipo-de-pagina-no-frontmatter]] — Tipo de página é campo do frontmatter, não diretório · aceito
- [[adr/adr-0026-mcp-prumo-dominio-paper]] — Servidor MCP cobre o domínio `paper` e passa a se chamar `prumo` · aceito
- [[adr/adr-0027-pj-instalavel]] — O `pj_*` é pacote instalável; código compartilhado tem nome · aceito
<!-- prumo:adr-index:end -->
